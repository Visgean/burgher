from pathlib import Path

from .context_db import ContextDB
from .node import DEFAULT_CONFIG, Node
from .utils import recursive_max_stat, user_prompt


class App(Node):
    """
    The app works in two steps: first it collects root nodes and let them register - grow leafs
    and then it generates all leafs of the graph.
    """

    context_db: ContextDB

    def __init__(
        self,
        name,
        context_db_path,
        output_path="build",
        feed=None,
        local_build=None,
        check_paths=None,
        **config,
    ):
        super().__init__()
        self.feed = feed

        self.app_name = name
        self.context_db = ContextDB(Path(context_db_path))

        self.static_hash = recursive_max_stat(check_paths)

        default_config = DEFAULT_CONFIG.copy()
        default_config.update(config)

        self.config = default_config
        self.output_folder = Path(output_path).resolve()

        self.local_build = local_build
        self.app = self

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
                    node.app = self
                    node.grow()
                    self.children[f"{name}:{node.get_name()}"] = node
            else:  # node pack is just one node
                node_pack.parent = self
                node_pack.app = self
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

        self.context_db.dump()


class GalleryApp(App):
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

        to_delete = [
            f for f in existing_imgs - files_generated if not "/static/" in str(f)
        ]
        to_delete_count = len(to_delete)

        needs_confirmation = to_delete_count > 10
        confirmed = False

        if needs_confirmation:
            for file_to_delete in to_delete:
                print(f"Would delete", file_to_delete)
            confirmed = user_prompt(
                f"Would delete {to_delete_count} files. Please confirm: "
            )

        if not needs_confirmation or (needs_confirmation and confirmed):
            for file_to_delete in to_delete:
                if dry:
                    print(f"Would delete", file_to_delete)
                else:
                    print(f"Deleting", file_to_delete)
                    file_to_delete.unlink()
