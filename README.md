# SFTP Tester

This project provides a simple Python utility to stress test an SFTP server.
It generates random zip files, uploads them to the server and removes them,
collecting timing statistics for each file.

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `config.yml.example` to `config.yml` and edit the values to match
   your SFTP server.
3. Run the tester:
   ```bash
   python sftp_tester.py --config config.yml
   ```
4. A report named `sftp_report_<timestamp>.txt` will be generated with
   statistics for each file transfer.

The script is cross-platform and relies on the `paramiko` library.
