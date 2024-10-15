import os
from datetime import datetime
from fractions import Fraction

from .defaults import PICTURE_EXTENSIONS


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