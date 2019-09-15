# burgher
Experimental static site generator


# Example app: 

```

from datetime import datetime
import email.utils
import config

from burgher import App, FrontMatterNode, StaticFolderNode, TemplateNode
from burgher.gallery import Gallery
from photo_stats import get_photo_stats

feed = []

app = App(
    template_dir="templates",
    output_path='build',
    domain='http://tintinburgh.com',
    feed=feed
)


class Stats(TemplateNode):
    template_name = 'stats.html'

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        c.update(get_photo_stats())
        return c


class Feed(TemplateNode):
    template_name = 'rss.xml'

    def __init__(self, feed, **config):
        super().__init__(**config)
        self.feed = feed

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        c['feed'] = self.feed
        c['now'] = email.utils.format_datetime(datetime.now())
        return c


feed_obj = Feed(feed=feed)

app.register(
    pages=FrontMatterNode.from_folder('pages', template_name='page.html'),
    static=StaticFolderNode('static'),
    gallery=Gallery(config.PHOTO_DIR, output_file='index.html'),
    stats=Stats(),
    rss=feed_obj
    # hidden=MarkdownNode.from_folder(config.PRIVATE_DIR),
)

app.generate()

feed_obj.generate()

```
