from datetime import datetime

PICTURE_EXTENSIONS = [".jpg", ".jpeg", ".png"]
EXIF_INTERESTING_TAGS = {
    # "Image DateTime": "date",
    # "Image DateTimeOriginal": "date (original)",
    "Image Model": "model",
    "EXIF ExposureTime": "shutter",
    "EXIF FocalLength": "length",
    "EXIF FNumber": "aperture",
    # "EXIF ApertureValue": "aperture",
    "EXIF ISOSpeedRatings": "iso",
    "EXIF LensModel": "lens",
}
DEFAULT_DATE = datetime(1970, 1, 1)
THUMB_SIZES = ("1920x1920", "3000x3000", "4000x3000")
