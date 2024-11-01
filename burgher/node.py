import os
from typing import Optional
from urllib.parse import quote

from progress.bar import Bar
from slugify import slugify

from .hash_utils import recursive_max_stat

DEFAULT_CONFIG = {"template_dir": "templates"}


class Node:
    parent: "Node" = None
    children = None
    show_progress = False
    indexable = True
    rewrite_html_links = True  # /page.html -> /page
    app: "app"

    def __init__(self, parent=None, app=None, **config):
        self.children = {}
        self.parent = parent
        self.config = config
        self.cache_data = False
        self.app = app

    def __str__(self):
        return self.get_name()

    def get_config(self, key, default=None):
        if key in self.config:
            return self.config[key]

        if self.parent:
            return self.parent.get_config(key, default)
        return default

    def get_base_link_url(self):
        if self.get_config("local_build"):
            return ""
        # domain = self.get_config('domain', '')
        base_path = self.get_config("base_path", "")
        if base_path:
            return f"/{base_path}/"
        return "/"

    def get_link(self):
        if self.get_config("local_build"):
            return str(self.get_output_path())

        relative_dir = self.get_output_path().relative_to(self.get_absolute_output())
        if relative_dir.name == "index.html":
            relative_dir = relative_dir.parent

        link = quote(f"{self.get_base_link_url()}{relative_dir}")

        if self.rewrite_html_links and link.endswith(".html"):
            return link[:-5]
        return link

    def get_absolute_link(self):
        return self.get_config("domain", "") + self.get_link()

    def get_output_folder(self):
        return self.parent.get_output_folder()

    def get_output_path(self):
        return self.get_output_folder() / self.get_output_name()

    def get_output_name(self):
        return slugify(self.get_name())

    def get_name(self):
        raise NotImplementedError

    def skip_generation_paths(self):
        return []

    def skip_generation(self):
        """
        Override if this template has been safely assumed to be unchanged
        """
        paths = self.skip_generation_paths()
        if not paths:
            return False

        app = self.get_root_node()
        key = str(self.get_output_path())

        most_mtime = recursive_max_stat(paths, app.static_hash)
        unchanged = app.context_db.get_key(key, str(most_mtime))
        if unchanged:
            self.show_progress = False
            return True

        app.context_db.set_key(key, str(most_mtime), True)

    def generate(self):
        """
        Method that generates the file into the output directory
        """
        os.makedirs(self.get_output_folder().absolute(), exist_ok=True)

        if self.show_progress:
            for child in Bar(self.get_name()).iter(self.children.values()):
                child.generate()
        else:
            for c in self.children.values():
                c.generate()

    def children_recursive(self) -> list:
        r = []
        for c in self.children.values():
            r.append(c)
            r.extend(c.children_recursive())
        return r

    def exists(self):
        return self.get_output_path().exists()

    def get_absolute_output(self):
        return self.get_root_node().get_output_folder()

    def get_root_node(self):
        if self.app:
            return self.app
        if self.parent:
            return self.parent.get_root_node()
        return self

    def grow(self):
        """
        This gets called after parameter self.parent is filled.
        """
        [c.grow() for c in self.children.values()]

    def process_feed(self, feed):
        if not self.indexable:
            return

        [c.process_feed(feed) for c in self.children.values()]

    def get_hash(self) -> Optional[str]:
        return None

    def rebuild(self) -> bool:
        """
        Does this node need to be re-build or can be skipped based on cache
        """
        return True

    def build_context(self):
        return {}
