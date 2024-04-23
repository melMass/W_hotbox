from pathlib import Path
from typing import Optional

import nuke

from .utils import getHotBoxLocation


# - Repair
class RepairHotbox:
    def __init__(
        self,
        folder: Optional[Path] = None,
        recursive: bool = True,
        message: bool = True,
    ):
        super().__init__()
        # set root folder
        self.root = getHotBoxLocation() if folder is None else folder
        # make sure the root ends with '/'

        # compose list of folders
        self.dir_list = [self.root / "All"] if folder is None else []

        if recursive:
            self.index_folders(self.root, folder)
        else:
            self.dir_list = [self.root]

        # append every filename with a 'tmp' so no files will be overwritten.
        for i in self.dir_list:
            self.tempifyFolder(i)

        # reset dirlist
        self.dir_list = [self.root / "All"] if folder is None else []
        if recursive:
            self.index_folders(self.root, folder)
        else:
            self.dir_list = [self.root]

        # give every file its proper name

        repairProgress = 100.0 / max(1.0, len(self.dir_list))

        for index, i in enumerate(self.dir_list):
            if message:
                repairProgressBar = nuke.ProgressTask("Repairing ..")

                repairProgressBar.setProgress(int(index * repairProgress))
                repairProgressBar.setMessage(i)

            self.repairFolder(i)

        if message:
            nuke.message("Succesfully repaired")

    def index_folders(self, path: Path, folder: Optional[Path] = None):
        # level = len([i for i in path.replace(self.root, "").split("/") if len(i) > 0])
        level = len([i for i in path.relative_to(self.root).parts if i])

        for child in path.iterdir():
            if child.name[0] not in [".", "_"]:  # Exclude hidden directories
                if child.is_dir():
                    if level != 0 or folder is not None:
                        self.dir_list.insert(0, child)
                    self.index_folders(child, folder)

        # for i in [path + i + "/" for i in os.listdir(path) if i[0] not in [".", "_"]]:
        #     if os.path.isdir(i):
        #         if level != 0 or folder != None:
        #             self.dir_list.insert(0, i)
        #         self.index_folders(i, folder)

    def tempifyFolder(self, folderPath: Path):
        folderContent = [i for i in folderPath.iterdir() if i.name[0] not in [".", "_"]]
        for item in sorted(folderContent):
            _ = item.rename(item.with_suffix(".tmp"))

    def repairFolder(self, folder_path: Path):
        folder_content = [
            i for i in folder_path.iterdir() if i.name[0] not in [".", "_"]
        ]

        for index, old_file in enumerate(sorted(folder_content)):
            extension = ""

            if old_file.is_file():
                extension = ".py"

            new_file = folder_path / f"{str(index + 1).zfill(3)}{extension}"

            _ = old_file.rename(new_file)
