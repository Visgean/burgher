import email.utils
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import markdown2

from .album_meta import apply_order, load_album_meta
from .defaults import DEFAULT_DATE, THUMB_SIZES
from .picture import Picture
from .template_nodes import TemplateNode
from .utils import get_name, is_pic


class AlbumError(Exception):
    pass


class Album(TemplateNode):
    name: str
    path: Path
    description = None
    template_node_name = "album"
    show_progress = True
    indexable = True

    # Embedded albums are directly rendered to the album but they also have
    # their own page. This is useful for making descriptions for parts of the album.
    is_embedded = False

    def __init__(self, name, path, description=None, thumb_sizes=THUMB_SIZES, **kwargs):
        super().__init__(template_name="album.html", **kwargs)
        self.name = name
        self.path = path
        self.description = description
        self.thumb_sizes = thumb_sizes
        self.thumb_galleries = []
        self.pictures = {}
        self.sub_albums = {}
        self.embedded = {}

        self.is_embedded = name.startswith("_")
        if self.is_embedded:
            self.name = name[1:]

        # Optional album.yaml: explicit ordering, cover, per-photo descriptions.
        self.meta = load_album_meta(Path(path))
        self.is_secret = (Path(path) / ".secret").exists() or self.meta.secret

    def get_output_folder(self):
        return super().get_output_folder() / self.get_output_name()

    def get_output_path(self):
        return self.get_output_folder() / "index.html"

    def get_output_name(self):
        return self.get_name()

    def get_name(self):
        return self.name

    def get_long_name(self):
        if self.get_name().isnumeric():
            return f"{self.parent.get_name()} / {self.get_name()}"
        return self.name

    def best_photo(self) -> Picture:
        good_ratio = 16 / 9
        candidates = []

        if not self.pictures and self.sub_albums:
            candidates.extend([a.best_photo() for a in self.sub_albums.values()])
        if not self.pictures and self.embedded:
            candidates.extend([a.best_photo() for a in self.embedded.values()])

        if candidates:
            for c in candidates:
                if c.get_name() == "main":
                    return c

            by_ratio = sorted(candidates, key=lambda p: good_ratio - p.ratio)
            return by_ratio[0]

        if self.meta.cover:
            for p in self.pictures.values():
                if p.path.name == self.meta.cover:
                    return p

        if "main" in self.pictures:
            return self.pictures["main"]

        good_ratio = 16 / 9
        by_ratio = sorted(self.pictures.values(), key=lambda p: good_ratio - p.ratio)

        if not by_ratio:
            raise AlbumError(f"Album {{ self.get_output_folder() }} might be empty!")

        return by_ratio[0]

    def skip_generation_paths(self):
        return [Path(self.path)]

    def get_latest_date(self):
        dates = [DEFAULT_DATE]
        dates.extend(filter(None, map(Picture.get_date, self.pictures.values())))
        dates.extend(filter(None, map(Album.get_latest_date, self.sub_albums.values())))
        dates.extend(filter(None, map(Album.get_latest_date, self.embedded.values())))

        return max(dates)

    def get_own_latest_date(self):
        """
        Freshness of the album's own content: its pictures and embedded parts,
        ignoring sub albums. Used to rank the "Latest" tiles on the index, so a
        parent such as /Light Shows does not surface next to its new sub album
        just because it holds a couple of loose photos.
        """
        dates = [DEFAULT_DATE]
        dates.extend(filter(None, map(Picture.get_date, self.pictures.values())))
        dates.extend(filter(None, map(Album.get_latest_date, self.embedded.values())))

        return max(dates)

    def get_pictures_sorted(self):
        if not self.pictures:
            return []

        ascending = list(
            sorted(self.pictures.values(), key=Picture.get_date, reverse=False)
        )
        difference: timedelta = ascending[-1].get_date() - ascending[0].get_date()

        by_date = list(reversed(ascending)) if difference.days > 10 else ascending
        return apply_order(by_date, self.meta.photo_order, key=lambda p: p.path.name)

    def get_sub_albums_sorted(self):
        if not self.sub_albums:
            return []

        by_date = sorted(self.sub_albums.values(), key=Album.get_latest_date, reverse=True)
        return apply_order(by_date, self.meta.subalbum_order, key=Album.get_dir_name)

    def get_embedded_sorted(self):
        if not self.embedded:
            return []

        by_date = sorted(self.embedded.values(), key=Album.get_latest_date, reverse=False)
        return apply_order(by_date, self.meta.embedded_order, key=Album.get_dir_name)

    def get_dir_name(self):
        """Folder name on disk, including the "_" of embedded albums."""
        return Path(self.path).name

    def grow(self):
        # find all picture extensions
        self.pictures.update(
            {
                get_name(p.name): Picture(path=Path(p.path), parent=self, app=self.app)
                for p in os.scandir(self.path)
                if is_pic(p.path)
            }
        )
        for pic in self.pictures.values():
            pic.description = self.meta.description(pic.path.name)

        for gal in [f for f in os.scandir(self.path) if f.is_dir()]:
            album = Album(name=gal.name, path=gal.path, parent=self, app=self.app)
            info_file = Path(gal) / "info.md"
            if info_file.exists():
                album.description = markdown2.markdown_path(info_file)

            if album.is_embedded:
                self.embedded[gal.name] = album
            else:
                self.sub_albums[gal.name] = album

        self.children.update(self.pictures)
        self.children.update(self.sub_albums)
        self.children.update(self.embedded)
        super().grow()

    def generate(self):
        super().generate()

    def get_all_pictures(self):
        pics = list(self.pictures.values())
        for c in self.sub_albums.values():
            pics.extend(c.get_all_pictures())
        for c in self.embedded.values():
            pics.extend(c.get_all_pictures())
        return pics

    def process_feed(self, feed: list):
        latest_date = self.get_latest_date()

        if datetime.now() - latest_date > timedelta(days=30):
            return

        feed.append(
            {
                "title": self.name,
                "link": self.get_absolute_link(),
                "date": email.utils.format_datetime(latest_date),
                "description": f"New album - {self.name}",
                "image": self.best_photo().largest_thumb.get_absolute_link(),
            }
        )

        super().process_feed(feed)

    def parents_reversed(self):
        """
        Essentially returns the breadcrumbs of the album.
        """
        parents = []
        n = self

        while True:
            parent = n.parent
            if parent:
                if not isinstance(parent, Album):
                    break
                parents.append(parent)
                n = parent
            else:
                break
        return reversed(parents)

    def show_in_fresh(self):
        """
        Candidate for the "Latest" tiles on the index.

        for example: /London/2024
        I want only 2024 to be displayed - not London.
        But for /Studio we have one album that only contains
        embedded - so we should display it.
        Candidates are ranked by get_own_latest_date(), so a parent with loose
        photos of its own only shows up when those photos are the new thing.
        """

        if self.is_secret:
            return False

        embedded_children = any([k.startswith("_") for k in self.children.keys()])

        return (self.pictures or embedded_children) and not self.is_embedded

    # ------------------------------------------------------------------
    # Previous / next navigation.
    #
    # Albums are walked depth-first in the same order they are displayed:
    # an album, then its sub albums (newest first), then the next sibling.
    # "next" therefore descends into the first sub album when there is one,
    # and "previous" is the exact inverse, so the two links always mirror
    # each other. Secret and embedded albums are skipped.
    # ------------------------------------------------------------------

    def get_nav_children(self):
        return [a for a in self.get_sub_albums_sorted() if not a.is_secret]

    def get_nav_siblings(self):
        parent = self.parent
        if isinstance(parent, Album):
            return parent.get_nav_children()
        if hasattr(parent, "get_albums_sorted"):
            return parent.get_albums_sorted()
        return []

    def get_last_descendant(self):
        node = self
        while True:
            children = node.get_nav_children()
            if not children:
                return node
            node = children[-1]

    def get_next_album(self):
        children = self.get_nav_children()
        if children:
            return children[0]

        node = self
        while isinstance(node, Album):
            siblings = node.get_nav_siblings()
            if node in siblings:
                index = siblings.index(node)
                if index + 1 < len(siblings):
                    return siblings[index + 1]
            node = node.parent
        return None

    def get_previous_album(self):
        siblings = self.get_nav_siblings()
        if self in siblings:
            index = siblings.index(self)
            if index > 0:
                return siblings[index - 1].get_last_descendant()

        if isinstance(self.parent, Album):
            return self.parent
        return None

    def get_path_name(self):
        """
        Name including parents, e.g. "Portugal / 2019 / Porto".
        """
        parts = [p.get_name() for p in self.parents_reversed()]
        parts.append(self.get_name())
        return " / ".join(parts)
