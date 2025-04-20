import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import markdown2

from .activity_pub import write_activity_pub
from .album import Album
from .template_nodes import MarkdownNode


class Gallery(MarkdownNode):
    """
    This is top level node, I use it as index page for the whole webpage.
    """

    template_node_name = "gallery"

    def __init__(
            self,
            photo_dir,
            template_name="gallery.html",
            output_file="gallery.html",
            **kwargs,
    ):
        super().__init__(template_name=template_name, **kwargs)
        self.output_file = output_file
        self.photo_dir = Path(photo_dir).resolve()

    def get_output_name(self):
        return self.output_file

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        albums_sorted = sorted(
            self.children.values(), key=Album.get_latest_date, reverse=True
        )

        # albums + sub albums
        latest_sub_albums = sorted(
            [
                a
                for a in self.children_recursive()
                if isinstance(a, Album) and a.show_in_fresh()
            ],
            key=Album.get_latest_date,
            reverse=True,
        )[:9]

        albums_per_year = defaultdict(list)
        albums_top_level = []
        for album in albums_sorted:
            if album.is_secret or album in latest_sub_albums or album.is_embedded:
                continue

            albums_top_level.append(album)

            date = album.get_latest_date().strftime("%B, %Y")
            albums_per_year[date].append(album)

        c["latest_sub_albums"] = latest_sub_albums
        c["today"] = datetime.today()
        c["albums_sorted"] = albums_sorted
        c["albums_per_year"] = albums_per_year
        c["albums_top_level"] = albums_top_level
        return c

    def grow(self):
        for gal in [f for f in os.scandir(self.photo_dir) if f.is_dir()]:
            album = Album(name=gal.name, path=gal.path, parent=self, app=self.app)
            info_file = Path(gal) / "info.md"
            if info_file.exists():
                album.description = markdown2.markdown_path(info_file)

            self.children[gal.name] = album
        super().grow()

    def skip_generation_paths(self):
        return [self.source_file, self.photo_dir]

    def generate(self):
        super().generate()
        self.generate_activity_pub()
        # self.generate_json()

    def generate_activity_pub(self):


        all_albums = sorted(
            [
                a
                for a in self.children_recursive()
                if isinstance(a, Album) and not a.is_secret and len(a.pictures) > 0
            ],
            key=Album.get_latest_date,
            reverse=True,
        )


        write_activity_pub(
            output_folder=self.get_output_folder(),
            full_url="https://tintinburgh.com",
            albums=all_albums,
            username='tintinburgh',
            domain='tintinburgh.com'
        )




    def generate_json(self):
        all_pics = []
        models = set()
        lens = set()

        for album in self.children.values():
            if album.is_secret:
                continue

            for pic in album.get_all_pictures():
                pic_data = pic.get_json()
                all_pics.append(pic_data)
                models.add(pic_data.get("model", ""))
                lens.add(pic_data.get("lens", ""))

        models.remove(None)
        lens.remove(None)

        data = {
            "pics": all_pics,
            "models": sorted(list(models)),
            "lens": sorted(list(lens)),
        }

        with open(self.get_output_folder() / "pictures.json", "w") as f:
            f.write(json.dumps(data, indent=4))
