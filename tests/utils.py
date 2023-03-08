import contextlib

from csv import writer
from datetime import datetime
from pathlib import Path
from shutil import rmtree

RESOLUTION = 300  # DPI


@contextlib.contextmanager
def custom_test_dir():
    """Create a specific dir to store test files"""
    dir_ = Path(f"temp_tests_{datetime.now().timestamp()}")
    dir_.mkdir()

    try:
        yield dir_
    finally:
        rmtree(dir_)
        pass


def make_csv(data: iter, path: Path):
    """Create a csv file on filesystem"""
    with path.open("w") as text_file:
        csv_writer = writer(text_file)
        for row in data:
            csv_writer.writerow(row)
