from .template_nodes import TemplateNode, FrontMatterNode


class BlogRoot(TemplateNode):
    show_progress = False

    def __init__(self, post_folder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.post_folder = post_folder

    def get_output_name(self):
        return "index.html"

    def grow(self):
        posts = FrontMatterNode.from_folder(self.post_folder, template_name="page.html")
        posts_sorted = sorted(posts, reverse=True, key=lambda p: p.metadata["date"])

        for post in posts_sorted:
            post.parent = self
            self.children[post.get_name()] = post

        super().grow()

    def get_extra_context(self) -> dict:
        c = super().get_extra_context()
        c["blog_posts"] = self.children.values()
        return c
