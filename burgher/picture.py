from pathlib import Path

import exifread
from PIL import Image as PILImage, ImageOps

from burgher import Node
from .defaults import DEFAULT_DATE, THUMB_SIZES, EXIF_INTERESTING_TAGS
from .utils import parse_exif_date, get_name, get_exif_tag_value


class Thumb(Node):
    indexable = False
    size_x = None
    size_y = None

    def __init__(self, size, **kwargs):
        super().__init__(**kwargs)
        self.size = size
        self.size_x, self.size_y = size

    def set_real_size(self):
        im = PILImage.open(self.get_output_path())
        self.size_y, self.size_x = im.size

    def get_width(self):
        if not self.size_x:
            self.set_real_size()
        return self.size_x

    def get_output_folder(self):
        return self.parent.get_output_folder() / (str(self.size_x) + "x")

    def get_output_name(self):
        return self.parent.get_output_name()

    def generate_pillow(self, path):
        with PILImage.open(path) as pillow_img_obj:
            pillow_img_obj = ImageOps.exif_transpose(pillow_img_obj)
            pillow_img_obj.thumbnail(self.size, PILImage.ANTIALIAS)
            pillow_img_obj.save(str(self.get_output_path()))


class Picture(Node):
    path: Path
    indexable = False

    tags = None
    interesting_tags = {}
    tags_parsed = {}
    size_x = None
    size_y = None

    date = None

    def __init__(self, path, thumb_sizes=THUMB_SIZES, **kwargs):
        super().__init__(**kwargs)

        self.interesting_tags = {}
        self.tags_parsed = {}

        self.path = path
        self.thumb_sizes = thumb_sizes

        # noinspection PyTypeChecker
        with open(self.path, "rb") as f:
            self.tags = exifread.process_file(f, details=False)
            self.parse_interesting_tags()
            orientation = self.tags.get("Image Orientation")

        im = PILImage.open(self.path)
        # handle rotated images:
        if orientation and (6 in orientation.values or 8 in orientation.values):
            self.size_y, self.size_x = im.size
        else:
            self.size_x, self.size_y = im.size

        im.close()

    def grow(self):
        for size in self.thumb_sizes:
            size_x, size_y = size.split("x")
            x = int(size_x) if size_x != "" else None
            y = int(size_y) if size_y != "" else None

            self.children[size] = Thumb(size=(x, y), parent=self)

        super().grow()

    # noinspection PyTypeChecker
    def get_info(self):
        parts = filter(None,
           [
               self.get_shutter(),
               self.get_iso(),
               self.get_aperture(),
               self.get_focal_length(),
               self.get_model(),
               self.get_lens(),
           ]
       )

        if parts:
            return ", ".join(parts)
        return ""

    def get_model(self):
        return self.tags_parsed.get('model')

    def get_lens(self):
        return self.tags_parsed.get('lens')

    def get_iso(self):
        iso_raw = self.tags_parsed.get('iso')
        return f'ISO: {iso_raw}'

    def get_aperture(self):
        f = self.tags_parsed.get('aperture')
        if f:
            return f'f{f}'  # hahaha

    def get_focal_length(self):
        f = self.tags_parsed.get('length')
        if f:
            return f'{f}mm'

    def get_shutter(self):
        ss = self.tags_parsed.get('shutter')
        if ss:
            return f'{ss}s'

    def get_output_name(self):
        return self.path.name

    def get_name(self):
        return get_name(self.path.name)

    @property
    def smallest_thumb(self):
        for size in self.thumb_sizes:
            if size in self.children:
                return self.children[size]

    @property
    def largest_thumb(self):
        for size in reversed(self.thumb_sizes):
            if size in self.children:
                return self.children[size]
        return self.children.pop()

    @property
    def ratio(self) -> float:
        return self.size_x / self.size_y

    # noinspection PyTypeChecker
    def generate(self):
        super().generate()
        # Imagemagick is slow as fuck so I try to avoid it.
        if all(
                [c.exists() for c in self.children.values()]
        ):  # or not self.full_image_path.exists():
            return

        [
            thumb.generate_pillow(self.path)
            for thumb in self.children.values()
            if not thumb.exists()
        ]

        # with WandImage(filename=self.path) as img:
        #     [thumb.generate_with_wand(img) for thumb in self.children.values() if not thumb.exists()]

    def get_date(self):
        if self.date:
            return self.date

        if "Image DateTimeOriginal" in self.tags:
            self.date = parse_exif_date(self.tags["Image DateTimeOriginal"])
        elif "Image DateTime" in self.tags:
            self.date = parse_exif_date(self.tags["Image DateTime"])
        elif "EXIF DateTimeOriginal" in self.tags:
            self.date = parse_exif_date(self.tags["EXIF DateTimeOriginal"])
        else:
            self.date = DEFAULT_DATE

        return self.date

    def get_srcset(self):
        return ",".join(
            [f"{t.get_link()} {t.get_width()}w" for t in self.children.values()]
        )

    def parse_interesting_tags(self):
        for tag, name in EXIF_INTERESTING_TAGS.items():
            if tag in self.tags:
                value = self.tags[tag]
                self.interesting_tags[name] = value.printable
                self.tags_parsed[name] = get_exif_tag_value(value)

    def get_json(self):
        return {
            "name": self.get_name(),
            "tags": self.interesting_tags,
            "tags_parsed": self.tags_parsed,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "date": self.date.isoformat(),
            "srcset": self.get_srcset(),
            "ratio": self.ratio,
            "smallest_thumb": self.smallest_thumb.get_link(),
            "largest_thumb": self.largest_thumb.get_link(),
        }
