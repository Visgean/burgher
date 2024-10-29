from pathlib import Path
from typing import Optional
from datetime import datetime
import exifread
from PIL import Image as PILImage, ImageOps
import os
import hashlib

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

    interesting_tags = {}
    tags_parsed = {}

    date = None

    def __init__(self, path, thumb_sizes=THUMB_SIZES, **kwargs):
        super().__init__(**kwargs)

        self.interesting_tags = {}

        self.path = path
        self.thumb_sizes = thumb_sizes

        self.rebuild()

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

    def get_date(self):
        return self.date

    def get_model(self):
        return self.context.get('model')

    def get_lens(self):
        return self.context.get('lens')

    def get_iso(self):
        iso_raw = self.context.get('iso')
        return f'ISO: {iso_raw}'

    def get_aperture(self):
        f = self.context.get('aperture')
        if f:
            return f'f{f}'  # hahaha

    def get_focal_length(self):
        f = self.context.get('length')
        if f:
            return f'{f}mm'

    def get_shutter(self):
        ss = self.context.get('shutter')
        if ss:
            return f'{ss}s'

    def get_output_name(self):
        if self.get_name() == 'main':
            return self.get_hash() + '.jpg'
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
        return self.context['size_x'] / self.context['size_y']

    # noinspection PyTypeChecker
    def generate(self):
        super().generate()
        # Imagemagick is slow as fuck so I try to avoid it.
        thumbs_exists = all(
            [c.exists() for c in self.children.values()]
        )

        if not self.refreshed and thumbs_exists:
            return

        for thumb in self.children.values():
            thumb.generate_pillow(self.path)

    def build_context(self):
        # noinspection PyTypeChecker
        with open(self.path, "rb") as f:
            tags = exifread.process_file(f, details=False)
            orientation = tags.get("Image Orientation")

        interesting_tags, tags_parsed = self.parse_interesting_tags(tags)
        im = PILImage.open(self.path)
        # handle rotated images:
        if orientation and (6 in orientation.values or 8 in orientation.values):
            size_y, size_x = im.size
        else:
            size_x, size_y = im.size

        im.close()

        if "Image DateTimeOriginal" in tags:
            date = parse_exif_date(tags["Image DateTimeOriginal"])
        elif "Image DateTime" in tags:
            date = parse_exif_date(tags["Image DateTime"])
        elif "EXIF DateTimeOriginal" in tags:
            date = parse_exif_date(tags["EXIF DateTimeOriginal"])
        else:
            date = DEFAULT_DATE

        self.date = date

        model = tags_parsed.get('model')
        lens = tags_parsed.get('lens')
        iso = tags_parsed.get('iso')
        aperture = tags_parsed.get('aperture')
        length = tags_parsed.get('length')
        shutter = tags_parsed.get('shutter')

        return {
            'date': date.isoformat(),
            'iso': iso,
            'aperture': aperture,
            'length': length,
            'shutter': shutter,
            'model': model,
            'lens': lens,
            'size_y': size_y,
            'size_x': size_x,
        }

    def get_srcset(self):
        return ",".join(
            [f"{t.get_link()} {t.get_width()}w" for t in self.children.values()]
        )

    def parse_interesting_tags(self, tags):
        interesting_tags = {}
        parsed = {}
        for tag, name in EXIF_INTERESTING_TAGS.items():
            if tag in tags:
                value = tags[tag]
                interesting_tags[name] = value.printable
                parsed[name] = get_exif_tag_value(value)
        return interesting_tags, parsed

    def get_json(self):
        return self.context

    def get_hash(self) -> Optional[str]:
        stat = os.stat(self.path)
        keys = f"{stat.st_mtime}, {stat.st_ctime}, {stat.st_size}"
        h = hashlib.new('sha256')
        h.update(keys.encode())
        return h.hexdigest()

        # with open(self.path, "rb") as f:
        #     return hashlib.file_digest(f, "sha256").hexdigest()

    def rebuild(self):
        data = self.app.context_db.get_key(
            str(self.path),
            self.get_hash()
        )
        if data:
            self.refreshed = False
            self.context = data
            self.date = datetime.fromisoformat(data['date'])
        else:
            self.refreshed = True
            self.context = self.build_context()
            self.app.context_db.set_key(
                str(self.path),
                self.get_hash(),
                self.context
            )
