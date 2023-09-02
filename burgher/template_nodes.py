from os.path import splitext
from pathlib import Path

import frontmatter
import markdown2
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .node import Node
from .static import StaticFolderNode


def path_not_ignored(f: Path):
    return not (f.name.startswith("_") or f.name.startswith("."))


class TemplateNode(Node):
    """
    Represents a simple Jinja2 template render - this is base class for all jinja2 nodes
    """

    template_node_name = "node"
    template_name = "default.html"

    def __init__(self, template_name=None, **config):
        """
        template name is relative to the template dir...
        """
        super().__init__(**config)
        if template_name:
            self.template_name = template_name

    def get_extra_context(self) -> dict:
        return {
            self.template_node_name: self,
            "base_link": self.get_base_link_url(),
        }

    def generate(self):
        super().generate()
        env = Environment(
            loader=FileSystemLoader(self.get_config("template_dir")),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template(self.template_name)
        with open(self.get_output_path(), "w") as f:
            f.write(template.render(**self.get_extra_context()))

    def get_output_name(self):
        return self.template_name

    def get_name(self):
        return self.template_name


class FileTemplateNode(TemplateNode):
    def __init__(self, source_file, template_name="page.html", **config):
        super().__init__(template_name, **config)
        self.source_file = Path(source_file)

    # noinspection PyArgumentList
    @classmethod
    def from_folder(klass, path, **kwargs):
        return [
            klass(f, **kwargs)
            for f in Path(path).iterdir()
            if path_not_ignored(f) and not f.is_dir()
        ]

    def get_name(self):
        name, ext = splitext(self.source_file.name)
        return name

    def get_output_name(self):
        return self.get_name() + ".html"


class MarkdownNode(FileTemplateNode):
    def get_extra_context(self):
        c = super().get_extra_context()
        c["content"] = markdown2.markdown_path(self.source_file)
        return c


class FrontMatterNode(FileTemplateNode):
    markdown_extras = ["fenced-code-blocks", "tables"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.metadata = frontmatter.load(self.source_file)
        except Exception as e:
            print(f"Can't parse markdown file {self.source_file}, fix it!")
            raise e

        self.markdown_content = self.metadata.content
        self.html_content = markdown2.markdown(
            self.markdown_content, extras=self.markdown_extras
        )

    def get_extra_context(self):
        c = super().get_extra_context()
        c["metadata"] = self.metadata
        c["html_content"] = self.html_content
        return c

    def grow(self):
        folder = self.source_file.parent
        asset_dir = folder / (str(self.get_name()) + ".assets")
        if asset_dir.exists():
            self.children["assets"] = StaticFolderNode(asset_dir, parent=self)
        super().grow()
