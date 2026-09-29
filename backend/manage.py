#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


class Tee:
    """Mirror text writes to the terminal and a log file."""

    def __init__(self, stream, log_file):
        self.stream = stream
        self.log_file = log_file

    def write(self, data):
        self.stream.write(data)
        self.log_file.write(data)
        self.log_file.flush()
        return len(data)

    def flush(self):
        self.stream.flush()
        self.log_file.flush()

    def isatty(self):
        return self.stream.isatty()

    @property
    def encoding(self):
        return getattr(self.stream, "encoding", "utf-8")


def _test_log_paths():
    if len(sys.argv) < 2 or sys.argv[1] != "test":
        return None

    root = Path(__file__).resolve().parent.parent
    log_dir = root / "test-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return log_dir / f"backend-{timestamp}.txt", log_dir / "backend-latest.txt"


def main():
    """Run administrative tasks."""
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        os.getenv("DJANGO_SETTINGS_MODULE", "config.settings.development"),
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    paths = _test_log_paths()
    if not paths:
        execute_from_command_line(sys.argv)
        return

    log_path, latest_path = paths
    original_stdout, original_stderr = sys.stdout, sys.stderr
    try:
        with log_path.open("w", encoding="utf-8") as log_file:
            sys.stdout = Tee(original_stdout, log_file)
            sys.stderr = Tee(original_stderr, log_file)
            print(f"[test-log] backend output: {log_path}")
            execute_from_command_line(sys.argv)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if log_path.exists():
            shutil.copyfile(log_path, latest_path)
            print(f"[test-log] latest backend log: {latest_path}")


if __name__ == '__main__':
    main()
