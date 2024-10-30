import email.utils
from datetime import datetime

from burgher import TemplateNode
from burgher import Album


class Feed(TemplateNode):
    template_name = "rss.xml"

    def __init__(self, root_gallery, **config):
        self.root_gallery = root_gallery
        super().__init__(**config)

    def skip_generation_paths(self):
        return [self.root_gallery]

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        c["now"] = email.utils.format_datetime(datetime.now())

        c["latest_sub_albums"] = sorted(
            [
                a
                for a in self.parent.children_recursive()
                if isinstance(a, Album) and a.pictures
            ],
            key=Album.get_latest_date,
            reverse=True,
        )

        return c
