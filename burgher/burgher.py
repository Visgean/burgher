import os
import shutil
from os.path import splitext
from pathlib import Path

import frontmatter
import markdown2
from jinja2 import Environment, FileSystemLoader, select_autoescape
from slugify import slugify
from progress.bar import Bar

DEFAULT_CONFIG = {
    "template_dir": 'templates'
}


class Node:
    parent: 'Node' = None
    children = None
    show_progress = False
    indexable = True

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
        return "/"

    def get_link(self):
        relative_dir = self.get_output_path().relative_to(self.get_absolute_output())
        return f"{self.get_base_link_url()}{relative_dir}"

    def get_absolute_link(self):
        return self.get_config('domain', '') + self.get_link()

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

    def __init__(self, output_path="build", feed=None, **config):
        super().__init__()
        self.feed = feed

        default_config = DEFAULT_CONFIG.copy()
        default_config.update(config)

        self.config = default_config
        self.output_folder = Path(output_path).resolve()

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

        if self.feed:
            self.process_feed(self.feed)
            self.feed.atom_file(str(self.output_folder / 'atom.xml'))
            self.feed.rss_file(str(self.output_folder / 'rss.xml'))


class StaticFolderNode(Node):
    """
    This just copies files from one place to another without attempting to access them in any way
    """

    def __init__(self, folder, **config):
        super().__init__(**config)
        self.folder = Path(folder).resolve()

    def get_output_folder(self):
        return super().get_output_folder() / self.get_name()

    def get_name(self):
        return self.folder.name

    def generate(self):
        """
        TODO: deal with shutil so that we don't have to delete the directory
        """
        out = self.get_output_folder()
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(self.folder, self.get_output_folder())
        super().generate()


class TemplateNode(Node):
    """
    Represents a simple Jinja2 template render - this is base class for all jinja2 nodes
    """
    template_node_name = 'node'
    template_name = 'default.html'

    def __init__(self, template_name=None, **config):
        """
        template name is relative to the template dir...
        """
        super().__init__(**config)
        if template_name:
            self.template_name = template_name

    def get_extra_context(self) -> dict:
        return {self.template_node_name: self}

    def generate(self):
        super().generate()
        env = Environment(
            loader=FileSystemLoader(self.get_config('template_dir')),
            autoescape=select_autoescape(['html', 'xml'])
        )
        template = env.get_template(self.template_name)
        with open(self.get_output_path(), 'w') as f:
            f.write(template.render(**self.get_extra_context()))

    def get_output_name(self):
        return self.template_name

    def get_name(self):
        return self.template_name


class FileTemplateNode(TemplateNode):
    def __init__(self, source_file, template_name='page.html', **config):
        super().__init__(template_name, **config)
        self.source_file = Path(source_file)

    # noinspection PyArgumentList
    @classmethod
    def from_folder(klass, path, **kwargs):
        return [klass(f, **kwargs) for f in Path(path).iterdir()]

    def get_name(self):
        name, ext = splitext(self.source_file.name)
        return name

    def get_output_name(self):
        return self.get_name() + '.html'


class MarkdownNode(FileTemplateNode):
    def get_extra_context(self):
        c = super().get_extra_context()
        c['content'] = markdown2.markdown_path(self.source_file)
        return c


class FrontMatterNode(FileTemplateNode):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.post = frontmatter.load(self.source_file)
        self.content = markdown2.markdown(self.post.content)

    def get_extra_context(self):
        c = super().get_extra_context()
        c['post'] = self.post
        c['content'] = self.content
        return c
