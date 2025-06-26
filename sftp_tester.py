import argparse
import os
import random
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional

import paramiko
from tqdm import tqdm
import logging

from sftp_config import SFTPConfig

@dataclass
class FileStat:
    name: str
    size: int
    connect_time: float
    transfer_time: float
    success: bool
    error: Optional[str] = None

@dataclass
class TestReport:
    file_stats: List[FileStat] = field(default_factory=list)

    def add(self, stat: FileStat):
        self.file_stats.append(stat)

    def to_text(self) -> str:
        lines = ["SFTP Test Report", "================="]
        for stat in self.file_stats:
            lines.append(
                f"File: {stat.name} Size: {stat.size} bytes Success: {stat.success}"\
                f" ConnectTime: {stat.connect_time:.2f}s TransferTime: {stat.transfer_time:.2f}s"\
                + (f" Error: {stat.error}" if stat.error else "")
            )
        return "\n".join(lines)


def create_random_zip(destination: str, size: int) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = os.path.join(tmpdir, "data.bin")
        with open(data_path, "wb") as f:
            f.write(os.urandom(size))
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(data_path, arcname="data.bin")


def _validate_private_key(config: SFTPConfig) -> bool:
    """Attempt to load the private key to verify the passphrase works."""
    if not config.ssh_private_key_path:
        logging.warning("No private key path specified")
        return False

    loaders = [
        paramiko.RSAKey.from_private_key_file,
        paramiko.ECDSAKey.from_private_key_file,
        paramiko.Ed25519Key.from_private_key_file,
        paramiko.DSSKey.from_private_key_file,
    ]

    for loader in loaders:
        try:
            loader(config.ssh_private_key_path, password=config.ssh_private_key_passphrase)
            logging.info("Successfully loaded private key with %s", loader.__qualname__)
            return True
        except FileNotFoundError:
            logging.error("Private key file not found: %s", config.ssh_private_key_path)
            return False
        except paramiko.PasswordRequiredException:
            logging.error("Private key is encrypted; passphrase missing or invalid")
            return False
        except paramiko.SSHException:
            continue

    logging.error("Unable to load the private key; unsupported format or bad passphrase")
    return False


def _create_client(config: SFTPConfig) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=config.host,
        username=config.username,
        key_filename=config.ssh_private_key_path,
        passphrase=config.ssh_private_key_passphrase,
        timeout=None if config.connect_timeout_seconds == -1 else config.connect_timeout_seconds,
    )
    return client


def sftp_operation(
    config: SFTPConfig,
    local_path: str,
    remote_name: str,
    client: Optional[paramiko.SSHClient] = None,
    position: int = 0,
) -> FileStat:
    file_size = os.path.getsize(local_path)
    if client is None:
        start_conn = time.monotonic()
        try:
            client = _create_client(config)
            connect_time = time.monotonic() - start_conn
        except Exception as e:
            return FileStat(remote_name, file_size, time.monotonic() - start_conn, 0, False, str(e))
    else:
        connect_time = 0.0

    sftp = client.open_sftp()
    start_transfer = time.monotonic()
    pbar = tqdm(
        total=file_size,
        desc=f"Uploading {remote_name}",
        unit="B",
        unit_scale=True,
        position=position,
        leave=False,
    )

    def cb(transferred, total):
        pbar.update(transferred - pbar.n)

    try:
        sftp.put(local_path, os.path.join(config.root_dir, remote_name), callback=cb)
        sftp.remove(os.path.join(config.root_dir, remote_name))
        success = True
        error = None
    except Exception as e:
        success = False
        error = str(e)
    pbar.close()
    transfer_time = time.monotonic() - start_transfer
    sftp.close()
    if not config.keep_alive_enabled:
        client.close()
    if config.sftp_sleep_interval > 0:
        time.sleep(config.sftp_sleep_interval)
    return FileStat(remote_name, file_size, connect_time, transfer_time, success, error)


def run_tests(config: SFTPConfig) -> TestReport:
    temp_dir = tempfile.mkdtemp()
    report = TestReport()
    paths = []
    try:
        for i in range(config.num_test_files):
            size = random.randint(config.min_test_file_size_bytes, config.max_test_file_size_bytes)
            local_path = os.path.join(temp_dir, f"test_{i}.zip")
            create_random_zip(local_path, size)
            paths.append((local_path, f"test_{i}.zip"))
        max_workers = config.sftp_threads if config.sftp_threads > 0 else os.cpu_count()
        if config.keep_alive_enabled:
            clients = [_create_client(config) for _ in range(max_workers)]
        else:
            clients = [None] * max_workers

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for idx, (path, name) in enumerate(paths):
                client = clients[idx % max_workers]
                futures.append(
                    executor.submit(sftp_operation, config, path, name, client, idx)
                )

            progress = tqdm(total=len(futures), desc="Files uploaded", unit="file", position=max_workers)
            for future in as_completed(futures):
                stat = future.result()
                report.add(stat)
                progress.update(1)
                if not stat.success:
                    logging.error(f"Failed to transfer {stat.name}: {stat.error}")
            progress.close()

        if config.keep_alive_enabled:
            for c in clients:
                c.close()
    finally:
        for path, _ in paths:
            if os.path.exists(path):
                os.remove(path)
        os.rmdir(temp_dir)
    return report


def save_report(report: TestReport, filename: str) -> None:
    with open(filename, "w") as f:
        f.write(report.to_text())


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run SFTP stress tests")
    parser.add_argument(
        "--config",
        default="config.yml",
        help="Path to YAML configuration file (default: config.yml)",
    )
    args = parser.parse_args()

    config = SFTPConfig.from_yaml(args.config)

    _validate_private_key(config)

    report = run_tests(config)
    filename = f"sftp_report_{int(time.time())}.txt"
    save_report(report, filename)
    print(f"Report saved to {filename}")


if __name__ == "__main__":
    main()
