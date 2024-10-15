import os
from pathlib import Path
from urllib.parse import quote

from slugify import slugify
from progress.bar import Bar


DEFAULT_CONFIG = {"template_dir": "templates"}


class Node:
    parent: "Node" = None
    children = None
    show_progress = False
    indexable = True
    rewrite_html_links = True  # /page.html -> /page

    def __init__(self, parent=None, **config):
        self.children = {}
        self.parent = parent
        self.config = config

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


class App(Node):
    """
    The app works in two steps: first it collects root nodes and let them register - grow leafs
    and then it generates all leafs of the graph.
    """

    def __init__(self, output_path="build", feed=None, local_build=None, **config):
        super().__init__()
        self.feed = feed

        default_config = DEFAULT_CONFIG.copy()
        default_config.update(config)

        self.config = default_config
        self.output_folder = Path(output_path).resolve()

        self.local_build = local_build

    def get_output_folder(self):
        return self.output_folder

    def register(self, **nodes):
        """
        The keyword arguments are used to as a namespace
        """
        for name, node_pack in nodes.items():
            if isinstance(node_pack, list):
                for node in node_pack:
                    node.parent = self
                    node.grow()
                    self.children[f"{name}:{node.get_name()}"] = node
            else:  # node pack is just one node
                node_pack.parent = self
                node_pack.grow()
                self.children[name] = node_pack

    def generate(self):
        super().generate()

        if self.feed is not None:
            self.process_feed(self.feed)

        if self.local_build:
            self.output_folder = Path(self.local_build).resolve()
            self.config["domain"] = ""
            self.config["local_build"] = True
            super().generate()

    def photo_cleanup(self, dry=True):
        """
        Clean up files that are present from previous builds
        """

        # List of all images we generated:
        files_generated = {
            child.get_output_path() for child in self.children_recursive()
        }

        # Find all images
        existing_imgs = set()
        exts = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
        for img_ext in exts:
            existing_imgs.update(set(self.output_folder.rglob(img_ext)))

        print(
            "Found",
            len(existing_imgs),
            "images",
            "generated",
            len(files_generated),
            "files",
        )

        to_delete = existing_imgs - files_generated
        to_delete_count = len(to_delete)
        if to_delete_count > 100:
            print(f'would delete {to_delete_count} files, this is probably mistake!')
        else:
            for file_to_delete in existing_imgs - files_generated:
                if "/static/" in str(file_to_delete):
                    continue

                if dry:
                    print(f"Would delete", file_to_delete)
                else:
                    print(f"Deleting", file_to_delete)
                    file_to_delete.unlink()
