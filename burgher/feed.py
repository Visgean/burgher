import email.utils
from datetime import datetime

from .album import Album
from .template_nodes import TemplateNode

FEED_ITEMS = 20
FEED_PHOTOS = 6


def rfc2822(dt: datetime) -> str:
    """
    RSS dates. EXIF dates and datetime.now() are naive local times, so attach
    the system zone instead of a made-up offset.
    """
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return email.utils.format_datetime(dt)


class Feed(TemplateNode):
    """
    RSS 2.0 feed of the freshest albums, rendered by templates/rss.xml.

    Items are the same candidates as the "Latest" tiles on the index
    (Album.show_in_fresh, ranked by Album.get_own_latest_date), so a parent
    album is not listed next to its new sub album and embedded parts never
    appear on their own. Each item carries up to `photos_per_item` photos as
    inline <img> tags in the description, which every reader renders exactly
    once, plus the cover as <media:thumbnail> for list previews. No <enclosure>
    or <media:content>: readers that honour those show the cover twice (rss.app)
    or append every photo after the body (NewsBlur).
    """

    template_name = "rss.xml"

    def __init__(self, root_gallery, items=FEED_ITEMS, photos_per_item=FEED_PHOTOS, **config):
        self.root_gallery = root_gallery
        self.items = items
        self.photos_per_item = photos_per_item
        super().__init__(**config)

    def skip_generation_paths(self):
        return [self.root_gallery]

    def get_albums(self):
        albums = [
            a
            for a in self.parent.children_recursive()
            if isinstance(a, Album) and a.show_in_fresh()
        ]
        albums.sort(key=Album.get_own_latest_date, reverse=True)
        return albums[: self.items]

    def get_items(self):
        return [
            {
                "album": album,
                "title": album.get_path_name(),
                "link": album.get_absolute_link(),
                "date": rfc2822(album.get_own_latest_date()),
                "description": album.description or "",
                "photos": album.feed_photos(self.photos_per_item),
            }
            for album in self.get_albums()
        ]

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        c["now"] = rfc2822(datetime.now())
        c["feed_link"] = self.get_absolute_link()
        c["items"] = self.get_items()
        return c
