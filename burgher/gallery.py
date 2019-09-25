import os
from collections import defaultdict
from multiprocessing.pool import Pool

import markdown2
from datetime import datetime, timedelta

import exifread
import pytz
import email.utils

from .node import Node
from .template_nodes import TemplateNode
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
THUMB_SIZES = ('x10', 'x400', '1200x', '1920x', '3000x', '4000x')


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
    size_x = None
    size_y = None

    def __init__(self, size, **kwargs):
        super().__init__(**kwargs)
        self.size = size

    def set_real_size(self):
        im = PILImage.open(self.get_output_path())
        self.size_y, self.size_x = im.size

    def get_width(self):
        if not self.size_x:
            self.set_real_size()
        return self.size_x

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

    date = None

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
        for size in self.thumb_sizes:
            size_x, size_y = size.split('x')
            x = int(size_x) if size_x != '' else None
            y = int(size_y) if size_y != '' else None

            if (x and x > self.size_x) or (y and y > self.size_y):
                continue

            self.children[size] = Thumb(size=size, parent=self)

        super().grow()

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
        for size in self.thumb_sizes:
            if size in self.children:
                return self.children[size]

    @property
    def largest_thumb(self):
        for size in reversed(self.thumb_sizes):
            if size in self.children:
                return self.children[size]

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

    def get_date(self):
        if self.date:
            return self.date

        if 'Image DateTimeOriginal' in self.tags:
            self.date = parse_exif_date(self.tags['Image DateTimeOriginal'])
        elif 'Image DateTime' in self.tags:
            self.date = parse_exif_date(self.tags['Image DateTime'])
        else:
            self.date = DEFAULT_DATE

        return self.date

    def get_srcset(self):
        return ",".join([
            f'{t.get_link()} {t.get_width()}w' for t in self.children.values()
        ])


class Album(TemplateNode):
    name: str
    path: Path
    description = None
    template_node_name = 'album'
    show_progress = True
    indexable = True

    def __init__(self, name, path, description=None, thumb_sizes=THUMB_SIZES, **kwargs):
        super().__init__(template_name="album.html", **kwargs)
        self.name = name
        self.path = path
        self.description = description
        self.thumb_sizes = thumb_sizes
        self.thumb_galleries = []
        self.pictures = {}
        self.sub_albums = {}

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
        if not self.pictures:
            return list(self.sub_albums.values())[0].best_photo

        if 'main' in self.pictures:
            return self.pictures['main']

        good_ratio = 16 / 9
        return sorted(self.pictures.values(), key=lambda p: good_ratio - p.ratio)[0]

    def get_latest_date(self):
        picture_dates = list(filter(None, map(Picture.get_date, self.pictures.values())))
        sub_album_dates = list(filter(None, map(Album.get_latest_date, self.sub_albums.values())))

        if picture_dates and sub_album_dates:
            return max(max(picture_dates), max(sub_album_dates))

        if picture_dates:
            return max(picture_dates)
        if sub_album_dates:
            return max(sub_album_dates)
        return DEFAULT_DATE

    def get_pictures_sorted(self):
        if not self.pictures:
            return []

        ascending = list(sorted(self.pictures.values(), key=Picture.get_date, reverse=False))
        difference: timedelta = ascending[-1].get_date() - ascending[0].get_date()

        if difference.days > 10:
            return reversed(ascending)
        return ascending

    def get_sub_albums_sorted(self):
        if not self.sub_albums:
            return []

        return list(sorted(self.sub_albums.values(), key=Album.get_latest_date, reverse=True))

    def grow(self):
        # find all picture extensions
        self.pictures.update({
            get_name(p.name): Picture(path=Path(p.path), parent=self)
            for p in os.scandir(self.path)
            if is_pic(p.path)
        })

        for gal in [f for f in os.scandir(self.path) if f.is_dir()]:
            album = Album(name=gal.name, path=gal.path, parent=self)
            info_file = Path(gal) / 'info.md'
            if info_file.exists():
                album.description = markdown2.markdown_path(info_file)
            self.sub_albums[gal.name] = album

        self.children.update(self.pictures)
        self.children.update(self.sub_albums)
        super().grow()

    def process_feed(self, feed: list):
        latest_date = self.get_latest_date()

        if datetime.now() - latest_date > timedelta(days=30):
            return


        feed.append({
            'title': self.name,
            'link': self.get_absolute_link(),
            'date': email.utils.format_datetime(latest_date),
            'description': f'New album - {self.name}',
            'image': self.best_photo.largest_thumb.get_absolute_link(),
        })

        super().process_feed(feed)


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
            date = album.get_latest_date().strftime("%B, %Y")
            albums_per_year[date].append(album)

        c['today'] = datetime.today()
        c['albums_sorted'] = albums_sorted
        c['albums_per_year'] = albums_per_year
        return c

    def grow(self):
        for gal in [f for f in os.scandir(self.photo_dir) if f.is_dir()]:
            album = Album(name=gal.name, path=gal.path, parent=self)
            info_file = Path(gal) / 'info.md'
            if info_file.exists():
                album.description = markdown2.markdown_path(info_file)

            self.children[gal.name] = album
        super().grow()
