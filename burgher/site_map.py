from datetime import datetime

from .album import Album
from .gallery import Gallery
from .template_nodes import FrontMatterNode, TemplateNode


class SiteMap(TemplateNode):
    """
    sitemap.xml: the index, every markdown page and every album that is not
    secret (nor inside a secret album). Rendered by templates/sitemap.xml as a
    plain <urlset>; lastmod is a date, Google ignores priority/changefreq.
    """

    template_name = "sitemap.xml"

    def get_entries(self):
        entries = []
        for node in self.parent.children_recursive():
            if isinstance(node, Album):
                if node.is_hidden():
                    continue
                entries.append((node.get_absolute_link(), node.get_latest_date()))
            elif isinstance(node, Gallery):
                dates = [a.get_latest_date() for a in node.children.values() if isinstance(a, Album)]
                entries.append((node.get_absolute_link(), max(dates) if dates else datetime.now()))
            elif isinstance(node, FrontMatterNode):
                mtime = datetime.fromtimestamp(node.source_file.stat().st_mtime)
                entries.append((node.get_absolute_link(), mtime))
        return [{"loc": loc, "lastmod": date.strftime("%Y-%m-%d")} for loc, date in entries]

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        c["entries"] = self.get_entries()
        return c
