import email.utils
from datetime import datetime

from .template_nodes import TemplateNode
from .album import Album


class SiteMap(TemplateNode):
    template_name = "sitemap.xml"

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()

        c["albums"] = [a
            for a in self.parent.children_recursive()
            if isinstance(a, Album) and a.pictures and not a.is_secret
        ]

        return c
