import os
from collections import defaultdict

import markdown2
from datetime import datetime

import exifread
import pytz

from .burgher import Node, TemplateNode
from pathlib import Path
from wand.image import Image as WandImage
from PIL import Image as PILImage

PICTURE_EXTENSIONS = ['.jpg', '.jpeg', '.png']

EXIF_INTERESTING_TAGS = {
    'Image DateTime': 'date',
    'Image DateTimeOriginal': 'date (original)',
    'Image Model': 'model',
    'EXIF ExposureTime': 'shutterspeed',
    'EXIF FocalLength': 'focallength',
    'EXIF FNumber': 'aperture',
    'EXIF ISOSpeedRatings': 'iso',
    'EXIF LensModel': 'lens',
}
DEFAULT_DATE = datetime(1970, 1, 1)
THUMB_SIZES = ('x400', '1920x')


def parse_exif_date(dt) -> datetime:
    return datetime.strptime(str(dt.values), '%Y:%m:%d %H:%M:%S')


def get_name(filename):
    filename, file_extension = os.path.splitext(filename)
    return filename


def is_pic(filename):
    filename, file_extension = os.path.splitext(filename)
    return file_extension.lower() in PICTURE_EXTENSIONS


class Thumb(Node):
    indexable = False

    def __init__(self, size, **kwargs):
        super().__init__(**kwargs)
        self.size = size

    def get_output_folder(self):
        return self.parent.get_output_folder() / self.size

    def get_output_name(self):
        return self.parent.get_output_name()

    def generate_with_wand(self, wand_img: WandImage):
        # create stripped down version of our image:
        wand_img.strip()
        wand_img.auto_orient()
        wand_img.compression_quality = 90

        thumb = wand_img.clone()
        thumb.transform(resize=self.size)
        thumb.save(filename=str(self.get_output_path()))


class Picture(Node):
    path: Path
    indexable = False

    tags = None
    size_x = None
    size_y = None

    def __init__(self, path, thumb_sizes=THUMB_SIZES, **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.thumb_sizes = thumb_sizes

        # noinspection PyTypeChecker
        with open(self.path, 'rb') as f:
            self.tags = exifread.process_file(f, details=False)
            orientation = self.tags.get('Image Orientation')

        im = PILImage.open(self.path)
        # handle rotated images:
        if orientation and (6 in orientation.values or 8 in orientation.values):
            self.size_y, self.size_x = im.size
        else:
            self.size_x, self.size_y = im.size

    def grow(self):
        self.children = {size: Thumb(size=size, parent=self) for size in self.thumb_sizes}

    # noinspection PyTypeChecker
    def __str__(self):
        tags_found = []
        for tag, name in EXIF_INTERESTING_TAGS.items():
            if tag in self.tags:
                value = self.tags[tag]
                tags_found.append(f'{name}: {value}')
        if tags_found:
            return ', '.join(tags_found)
        return ''

    def get_output_name(self):
        return self.path.name

    def get_name(self):
        return get_name(self.path.name)

    @property
    def smallest_thumb(self):
        return self.children[self.thumb_sizes[0]]

    @property
    def largest_thumb(self):
        return self.children[self.thumb_sizes[-1]]

    @property
    def ratio(self) -> float:
        return self.size_x / self.size_y

    # noinspection PyTypeChecker
    def generate(self):
        super().generate()
        # Imagemagick is slow as fuck so I try to avoid it.
        if all([c.exists() for c in self.children.values()]):  # or not self.full_image_path.exists():
            return

        with WandImage(filename=self.path) as img:
            [thumb.generate_with_wand(img) for thumb in self.children.values() if not thumb.exists()]

    # noinspection PyTypeChecker
    # noinspection PyBroadException
    def get_date(self):
        if 'Image DateTimeOriginal' in self.tags:
            return parse_exif_date(self.tags['Image DateTimeOriginal'])

        if 'Image DateTime' in self.tags:
            return parse_exif_date(self.tags['Image DateTime'])
        return DEFAULT_DATE


class Album(TemplateNode):
    name: str
    path: Path
    description = None
    show_progress = True
    template_node_name = 'album'

    def __init__(self, name, path, description=None, thumb_sizes=THUMB_SIZES, **kwargs):
        super().__init__(template_name="album.html", **kwargs)
        self.name = name
        self.path = path
        self.description = description
        self.thumb_sizes = thumb_sizes

    def get_output_folder(self):
        return super().get_output_folder() / self.get_output_name()

    def get_output_path(self):
        return self.get_output_folder() / 'index.html'

    def get_output_name(self):
        return self.get_name()

    def get_name(self):
        return self.name

    @property
    def best_photo(self) -> Picture:
        if 'main' in self.children:
            return self.children['main']

        good_ratio = 16 / 9
        return sorted(self.children.values(), key=lambda p: good_ratio - p.ratio)[0]

    def get_latest_date(self):
        try:
            return max(filter(None, map(Picture.get_date, self.children.values())))
        except ValueError:
            return DEFAULT_DATE

    def get_pictures_sorted(self):
        return sorted(self.children.values(), key=Picture.get_date, reverse=False)

    def grow(self):
        # find all picture extensions
        self.children.update({
            get_name(p.name): Picture(path=Path(p.path), parent=self)
            for p in os.scandir(self.path)
            if is_pic(p.path)
        })
        super().grow()

    def process_feed(self, feed):
        fe = feed.add_entry()
        fe.id(self.get_absolute_link())
        fe.title(self.name)
        fe.link(href=self.get_absolute_link())

        dt = datetime.combine(self.get_latest_date(), datetime.min.time())
        dt_aware = pytz.utc.localize(dt)

        fe.updated(dt_aware)


class Gallery(TemplateNode):
    template_node_name = 'gallery'

    def __init__(self, photo_dir, template_name='gallery.html', output_file='gallery.html', **kwargs):
        super().__init__(template_name=template_name, **kwargs)
        self.output_file = output_file
        self.photo_dir = Path(photo_dir).resolve()

    def get_output_name(self):
        return self.output_file

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        albums_sorted = sorted(self.children.values(), key=Album.get_latest_date, reverse=True)

        albums_per_year = defaultdict(list)
        for album in albums_sorted:
            albums_per_year[album.get_latest_date().year].append(album)

        c['albums_sorted'] = albums_sorted
        c['albums_per_year'] = albums_per_year
        return c

    def grow(self):
        folders = [f for f in os.scandir(self.photo_dir) if f.is_dir()]
        for gal in folders:
            album = Album(name=gal.name, path=gal.path, parent=self)
            info_file = Path(gal) / 'info.md'
            if info_file.exists():
                album.description = markdown2.markdown_path(info_file)

            self.children[gal.name] = album
        super().grow()
