import shutil
from pathlib import Path

from .node import Node


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


class StaticNode(Node):
    """
    This just copies files from one place to another without attempting to access them in any way
    """

    def __init__(self, file, **config):
        super().__init__(**config)
        self.file = Path(file).resolve()

    def get_name(self):
        return self.file.name

    def generate(self):
        """
        TODO: deal with shutil so that we don't have to delete the directory
        """
        shutil.copy(self.file, self.get_output_folder())
        super().generate()
