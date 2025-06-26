import yaml


class SFTPConfig:
    def __init__(self):
        self.host = None
        self.username = None
        self.root_dir = '/'
        self.ssh_private_key_passphrase = None
        self.ssh_private_key_path = None
        self.min_test_file_size_bytes = 6000
        self.max_test_file_size_bytes = 64000000
        self.num_test_files = 1
        self.connect_timeout_seconds = 20
        self.transfer_timeout_seconds = 20
        self.sftp_threads = 1
        self.sftp_sleep_interval = -1
        self.keep_alive_enabled = 0
        self.retry_attempts = 0

    @classmethod
    def from_yaml(cls, path: str) -> "SFTPConfig":
        """Load configuration values from a YAML file."""
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        cfg = cls()
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return cfg

    def setHost(self, host: str):
        self.host = host

    def setUserName(self, username: str):
        self.username = username

    def setRootDir(self, root: str):
        self.root_dir = root

    def setSshPrivateKeyPassPhrase(self, phrase: str):
        self.ssh_private_key_passphrase = phrase

    def setSshPrivateKeyPath(self, path: str):
        self.ssh_private_key_path = path

    def minTestFileSizeBytes(self, size: int):
        self.min_test_file_size_bytes = int(size)

    def maxTestFileSizeBytes(self, size: int):
        self.max_test_file_size_bytes = int(size)

    def numTestFiles(self, num: int):
        self.num_test_files = int(num)

    def ConnectTimeoutSeconds(self, timeout: int):
        self.connect_timeout_seconds = int(timeout)

    def TransferTimeoutSeconds(self, timeout: int):
        self.transfer_timeout_seconds = int(timeout)

    def sftpThreads(self, threads: int):
        self.sftp_threads = int(threads)

    def sftpSleepInterval(self, interval: int):
        self.sftp_sleep_interval = int(interval)

    def keepAliveEnabled(self, enabled: int):
        self.keep_alive_enabled = int(enabled)

    def retryAttempts(self, attempts: int):
        self.retry_attempts = int(attempts)
