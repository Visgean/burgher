import hashlib
import os
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from .defaults import PICTURE_EXTENSIONS


def user_prompt(question: str) -> bool:
    """Prompt the yes/no-*question* to the user."""
    answers = {"yes": True, "no": False}
    for _ in range(10):
        user_input = input(question + " [yes/no]: ")
        if user_input in answers:
            return answers[user_input]
        else:
            print("Please use y/n or yes/no.\n")
    return False


def parse_exif_date(dt) -> datetime:
    return datetime.strptime(str(dt.values), "%Y:%m:%d %H:%M:%S")


def get_name(filename):
    filename, file_extension = os.path.splitext(filename)
    return filename


def is_pic(filename):
    filename, file_extension = os.path.splitext(filename)
    return file_extension.lower() in PICTURE_EXTENSIONS


def get_exif_tag_value(value):
    parsed_value = value.printable
    if "/" in parsed_value:
        try:
            f = Fraction(value.printable)
            if f.numerator == 1:
                return parsed_value
            nice_value = "{:.1f}".format(float(f))
            if nice_value == "0.0":
                return parsed_value
            return nice_value
        except:
            return parsed_value

    return parsed_value


def recursive_max_stat(paths: list[Path], initial_hash=""):
    if not paths:
        return ""

    files = []
    prev_hash = initial_hash

    for p in paths:
        if p.is_dir():
            files.extend(list(p.rglob("**/*")))
        else:
            files.append(p)

    for path in sorted(files):
        stat = os.stat(path)
        keys = f"{stat.st_mtime}, {stat.st_ctime}, {stat.st_size}, {prev_hash}"
        h = hashlib.new("sha256")
        h.update(keys.encode())
        prev_hash = h.hexdigest()

    return prev_hash
