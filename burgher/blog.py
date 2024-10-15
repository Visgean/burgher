from . import utils
from .template_nodes import FrontMatterNode


class BlogRoot(FrontMatterNode):
    show_progress = False

    def __init__(self, post_folder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.post_folder = post_folder
        self.template_name = "blog.html"

    def get_output_name(self):
        return "index.html"

    def grow(self):
        posts = FrontMatterNode.from_folder(self.post_folder, template_name="post.html")

        posts_sorted = sorted(posts, reverse=True, key=lambda p: p.metadata["date"])

        for post in posts_sorted:
            post.parent = self
            self.children[post.get_name()] = post

        super().grow()

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        c["blog_posts"] = self.children.values()
        return c
