from __future__ import annotations
from typing import Union, Optional, TYPE_CHECKING

from PySide2 import QtWidgets
from PySide2 import QtGui
from PySide2 import QtCore

import re
import string
import colorsys
import os
from pathlib import Path
from webbrowser import open as openURL

import nuke
import contextlib

from datetime import datetime as dt
import shutil

from .repair import RepairHotbox
from .utils import (
    log,
    Constants,
    getAttributeFromFile,
    getFirstAvailableFilePath,
    preferencesNode,
    getTileColor,
    hex2rgb,
    interface2rgb,
    rgb2interface,
    rgb2hex,
    releaseDate,
    version,
)


# NOTE: this is to avoid cyclic imports
#       while still providing type checking
if TYPE_CHECKING:
    from .manager import HotboxManager


# - Classes List
class QListWidgetCustom(QtWidgets.QListWidget):
    def __init__(self, hotboxManager: HotboxManager):
        super(QListWidgetCustom, self).__init__()

        self.enabled = False
        self.hotboxManager = hotboxManager

        self.buildClassesList = False
        self.itemChanged.connect(self.catchCheckboxChange)

    def setEnabled(self, mode=True):
        # only proceed if the mode will be changed
        if self.enabled == mode:
            return

        self.enabled = mode

        # change color
        color = [self.hotboxManager.lockedColor, self.hotboxManager.activeColor][
            int(mode)
        ]
        self.setStyleSheet(f"background-color : {color}")

    def itemSelected(self):
        return bool(self.currentItem())

    def allItemNames(self):
        """
        Return a list of all the items (text)
        """
        return [self.item(index).text() for index in range(self.count())]

    def catchCheckboxChange(self):
        """
        Function that get executed whenever an item is changed.
        """

        # Only un when in Rules mode and when not building the list (so just when I user ticks the checkbox.)
        if self.hotboxManager.mode != "Rules" or self.buildClassesList:
            return

        for index in range(self.count()):
            item = self.item(index)
            fileName = item.text()

            checkState = int(item.checkState())

            newRulePath, origRulePath = [
                self.hotboxManager.path / (fileName + "_" * index) for index in range(2)
            ][:: (checkState - 1)]

            if not newRulePath.exists():
                origRulePath.rename(newRulePath)
                break

    def focusInEvent(self, event):
        """
        Actions executed when widget gains focus.
        """

        # inherit default behaviour
        QtWidgets.QListWidget.focusOutEvent(self, event)

        if (
            self.hotboxManager.mode == "Rules"
            and not self.hotboxManager.rulesFlagCheckbox.isVisible()
        ):
            self.clearSelection()

        return True


# - Color Swatch
class ColorSwatch(QtWidgets.QLabel):
    # signals
    save = QtCore.Signal()

    def __init__(self, defaultColor: str, size: int = 12):
        super(ColorSwatch, self).__init__()

        self.color = defaultColor

        self.enabled = False
        self.active = False

        self.child = None
        self.parentSwatch = None

        self.setFixedHeight(size)
        self.setFixedWidth(size)

        self.painter = QtGui.QPainter()

        # set line color to black
        self.lineColor = "#000000"

        # painter
        self.paintPen = QtGui.QPen()
        self.paintPen.setColor(QtGui.QColor(0, 0, 0))
        self.paintPen.setWidthF(1.5)

        self.defaultColor = defaultColor
        self.defaultColorInverted = self.invertColor(self.defaultColor)
        self.lockedColor = "#262626"

        self.setColor(adjustChild=False, indirect=True)

        # Tooltip
        self.assignToolTip()

    def assignToolTip(self, child=False):
        """
        Set the
        """
        if child:
            childSpecificToolTip = [
                "text ",
                " When set to default this color will adjust upon altering the button's color in order to remain readable."
                " This behaviour can be turned off by disabling 'Auto adjust text color' in the preferences",
                " Invert default color.",
            ]
        else:
            childSpecificToolTip = ["", "", ""]
        self.toolTipText = f"<p>Change the button's {childSpecificToolTip[0]}color.</p><p>/ indicates the color is set to default.{childSpecificToolTip[1]}</p><ul><li><b>LMB</b> Open color picker to set a custom color.</li><li><b>RMB</b> Revert to default color.{childSpecificToolTip[2]}</li><li><b>CTRL + LMB</b>  Paste color from clipboard.</li><li><b>CTRL + RMB</b> Copy color to clipboard.</li><li><b>SHIFT + LMB</b> Set to color of selected node.</li><li><b>SHIFT + RMB</b> Copy color to clipboard, formatted as a 32bit integer.</li></ul>"

        self.setToolTip(self.toolTipText)

    # - Events
    def saveEvent(self):
        """
        Emit save signal that can be picked up by parent class
        """
        self.save.emit()

    def enterEvent(self, event):
        """
        Set Active to true when the mouse starts hovering over it
        """
        if not self.enabled:
            return False

        self.active = True
        return True

    def leaveEvent(self, event):
        """
        Set Active to false when the mouse stops hovering over it
        """
        if self.enabled:
            self.active = False
        return False

    def mouseReleaseEvent(self, event):
        """
        Set the color of the button
        """
        if not self.enabled or not self.active:
            return False
            # Control key pressed
        if QtWidgets.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
            # left click
            if event.button() == QtCore.Qt.LeftButton:
                self.colorFromSelection()

            # right click
            else:
                self.copyColorInterface()

        elif QtWidgets.QApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
            # left click
            if event.button() == QtCore.Qt.LeftButton:
                # paste color form clipboard
                self.pasteColorHex()

            # right click
            else:
                # copy color to clipboard
                self.copyColorHex()

        elif event.button() == QtCore.Qt.LeftButton:
            # set custom color
            self.getColor()

        else:
            color = (
                self.defaultColorInverted
                if self.parentSwatch and self.color == self.defaultColor
                else None
            )
            self.setColor(color)

        return True

    def dragEnterEvent(self, event):
        # check if color
        if event.mimeData().hasFormat("application/x-color") and self.enabled:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, _event):
        # find color
        node = nuke.toNode(nuke.tcl("stack 0")) or nuke.selectedNode()

        if not node:
            return
        interfaceColor = node.knob("tile_color").value()

        if interfaceColor == 0:
            interfaceColor = nuke.defaultNodeColor(node.Class())

        rgbColor = interface2rgb(interfaceColor)
        color = rgb2hex(rgbColor)

        self.setColor(color)

    # - Color
    def setEnabled(self, mode):
        """
        lock/unlock the colorswatch.
        """

        self.enabled = mode
        self.setAcceptDrops(mode)
        self.setColor(adjustChild=False, indirect=True)

    def getColor(self):
        """
        Open color dialog to let the user pick a color
        """

        # convert current color to Nuke notation
        rgbColor = hex2rgb(self.color)
        interfaceColor = rgb2interface(rgbColor)

        color = nuke.getColor(interfaceColor)

        # if changed, proceed
        # ideally, you would register whenever the user cancels the color picker
        # usually cancel would return False. However...
        # when setting an initial color, pressing cancel wont return False no more...
        if color != interfaceColor:
            rgbColor = interface2rgb(color)
            hexColor = rgb2hex(rgbColor)

            self.setColor(hexColor)

    def setColor(self, color: Optional[str] = None, adjustChild=True, indirect=False):
        """
        Set color of the swatch.
        'Indirect' parameter reflects whether the method was called directly by the user, or as a side effect.
        """

        colorChanged = False

        # if swatch not enabled, set to locked color
        if not self.enabled:
            color = self.lockedColor

        else:
            # if no color specified, set to default color
            if not color:
                color = self.defaultColor

            # if new color is the same as the current color
            if color != self.color:
                colorChanged = True

        # set color
        self.color = color
        self.setStyleSheet(
            "QLabel {border: 1px solid %s; background-color : %s}"
            % (self.lineColor, self.color)
        )

        # set child color. If the color of the child was changed, make sure the colorChanged variable is forced to True
        if adjustChild:
            colorChanged = bool(colorChanged + self.setChildColor())

        # save changes to file if conditions are met.
        if self.enabled and colorChanged and not indirect:
            self.saveEvent()

    def setChildColor(self):
        """
        Change the color of another colorswatch whenever this swatch changes color
        """

        # check if its relevant to compare colors
        if not self.child or not preferencesNode.knob("hotboxAutoTextColor").value():
            return False

        if not self.isNonDefault(True) and self.child.isNonDefault():
            return False

        # if self is default, and child is default
        if not self.isNonDefault(True) and not self.child.isNonDefault():
            self.child.setColor(indirect=True)
            return True

        # parent color
        rgbParentColor = hex2rgb(self.color)
        hsvParentColor = colorsys.rgb_to_hsv(
            rgbParentColor[0], rgbParentColor[1], rgbParentColor[2]
        )

        # child color
        childColor = self.child.color
        rgbChildColor = hex2rgb(childColor)
        hsvChildColor = list(
            colorsys.rgb_to_hsv(rgbChildColor[0], rgbChildColor[1], rgbChildColor[2])
        )

        # check if diffenence is significant enough to be readable
        threshold = 255 / 2

        if abs(hsvParentColor[2] - hsvChildColor[2]) < threshold:
            color = [self.child.defaultColorInverted, self.child.defaultColor][
                int(bool(self.child.isNonDefault(True)))
            ]

            # set child color
            self.child.setColor(color, indirect=True)

            return True

        return False

    def isNonDefault(self, ignoreInverted=False):
        """
        Return the current color. If that's similar to the default color, return None.
        """

        if (
            not ignoreInverted
            and self.parentSwatch
            and self.color == self.defaultColorInverted
        ):
            return None

        # if default
        return None if self.color == self.defaultColor else self.color

    def setChild(self, child):
        """ """
        if isinstance(child, ColorSwatch):
            self.child = child
            self.child.parentSwatch = self
            self.child.assignToolTip(True)

    # - Copy/Paste
    def copyColorHex(self):
        """
        Copy current color to clipboard
        """

        QtWidgets.QApplication.clipboard().setText(self.color)

    def copyColorInterface(self):
        """
        Copy current color to clipboard, formatted as a 32 bit value as used by nuke for interface colors.
        """

        # convert hex to interface
        rgbColor = hex2rgb(self.color)
        color = str(rgb2interface(rgbColor))

        QtWidgets.QApplication.clipboard().setText(color)

    def pasteColorHex(self):
        """
        Paste color from clipboard
        """

        color = QtWidgets.QApplication.clipboard().text()

        # check if clipboard content is a color formatted as a 32 bit value as used by nuke for interface colors.
        # if so, convert to hex
        if color.isdigit():
            rgbColor = interface2rgb(int(color))
            color = rgb2hex(rgbColor)

        if not color:
            return
        # check if clipboard content is a valid hex color
        if re.search("^#(?:[0-9a-fA-F]{2}){3}$", color):
            self.setColor(color)

    def colorFromSelection(self):
        """
        Set color to color of selected node
        """

        selection = nuke.selectedNodes
        if not selection:
            return

        interfaceColor = getTileColor()
        rgbColor = interface2rgb(interfaceColor)
        color = rgb2hex(rgbColor)

        self.setColor(color)

    # - Line
    def invertColor(self, color):
        """
        Retrun color with inverted brightness.
        """

        rgbColor = hex2rgb(color)
        hsvColor = list(colorsys.rgb_to_hsv(rgbColor[0], rgbColor[1], rgbColor[2]))

        hsvColor[2] = 255 - hsvColor[2]

        # convert back to hex
        # the rgb2hex function in the W_hotbox module expects normalized rgb values

        rgbColor = [
            float(value) / 255
            for value in colorsys.hsv_to_rgb(hsvColor[0], hsvColor[1], hsvColor[2])
        ]

        return rgb2hex(rgbColor)

    def paintEvent(self, event):
        """
        Draw diagonal line on top of colorswatch in case the swatch is set to it's default color.
        """
        if self.enabled and not self.isNonDefault():
            size = self.width()
            self.painter.begin(self)
            self.painter.setPen(self.paintPen)
            self.painter.drawLine(size - 1, 1, 1, size - 1)
            self.painter.end()


# - Hotbox items tree view (right list in the manager)
class QTreeViewCustom(QtWidgets.QTreeView):
    def __init__(self, parentClass: HotboxManager):
        super(QTreeViewCustom, self).__init__()

        self.enabled = False
        self.clipboard = []
        self.parentClass = parentClass

        self.header().hide()

        self.dataModel = QtGui.QStandardItemModel()
        self.root = self.dataModel.invisibleRootItem()

        self.setModel(self.dataModel)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        # to check whether the tree was populated from scratch of updated
        self.scope: Optional[Path] = None
        self.previousScope: Optional[Path] = None

        self.selectionModel().selectionChanged.connect(self.setSelectedItems)

    def expandsOnDoubleClick(self) -> bool:
        return True

    def setEnabled(self, mode: bool = True):
        self.enabled = mode

        # change color
        color = [self.parentClass.lockedColor, self.parentClass.activeColor][int(mode)]
        self.setStyleSheet(f"background-color : {color}")

    def populateTree(self):
        """
        Fill the QTreeView with items associated with the selected nodeclass
        """

        # store current scope as previous scope
        self.previousScope = self.scope

        self.setEnabled(True)

        # find current scope
        if not self.parentClass.contextual:
            self.scope = self.parentClass.path

        else:
            classItems = self.parentClass.classesList.selectedItems()
            if len(classItems) == 0:
                self.setEnabled(False)
                return

            classItem = classItems[0]
            classItemText = classItem.text()

            if self.parentClass.mode == "Rules" and not int(classItem.checkState()):
                classItemText += "_"

            self.scope = self.parentClass.path / classItemText

        self.do_update = self.previousScope == self.scope
        if self.do_update:
            # find currently collapsed menus
            self.collapsedMenus = []

            for button in self.buttonsList.values():
                log.debug(button)
                log.debug(type(button))

                index = self.dataModel.indexFromItem(button)

                if not self.isExpanded(index):
                    self.collapsedMenus.append(button.path)

        # reset buttons list (all items will be replaced with new items when rebuilding anyway)
        self.buttonsList: dict[str, QStandardItemChild] = {}
        self.clearTree()

        # Fill the buttonstree if there is an item selected in the classescolumn, or the mode is set to all.
        if (
            not self.parentClass.contextual
            or self.parentClass.classesList.selectedItems() != 0
        ):
            self.addChild(self.root, self.scope)

        # Expand/Collapse
        self.expandAll()

        # closeall the menus when updating
        if self.do_update:
            for path in self.collapsedMenus:
                if path in self.buttonsList:
                    button = self.buttonsList[path]
                    index = self.dataModel.indexFromItem(button)
                    self.collapse(index)

        self.parentClass.toggleRulesMode()

    def clearTree(self):
        """
        empty the tree
        self.dataModel.clear() unfortunately this  Nuke
        """
        for _ in range(self.dataModel.rowCount()):
            self.dataModel.takeRow(0)

    def addChild(self, parent: QtGui.QStandardItem, path: Path):
        """
        Loop through folder structure and add items on the fly
        """
        if not path.is_dir():
            raise ValueError(
                "You passed a file instead of a directory: {path.as_posix()}"
            )

        for i in sorted(path.iterdir()):
            if i.name[0] not in ["_", "."]:
                name = getAttributeFromFile(i)
                if not name:
                    return

                child = QStandardItemChild(name, i)
                parent.appendRow(child)

                self.buttonsList[i.as_posix()] = child
                if i.is_dir():
                    self.addChild(child, i)

    def setSelectedItems(self):
        """
        Run when items gets selected
        """
        self.selectedItems = [
            index.model().itemFromIndex(index) for index in self.selectedIndexes()
        ]
        self.selectedItemsPaths = {i.path for i in self.selectedItems}
        self.parentClass.loadScriptEditor()
        self.parentClass.toggleRulesMode(False)

    # TODO: this wasn't updated since in my big refactor, I need to convert it properly to pathlib
    def moveItem(self, direction):
        """
        Change the order of buttons by clicking the up/down buttons
        """

        # get currently selected index and item
        self.currentItem = self.selectedItems[0]
        self.currentIndex = self.currentItem.index()

        # get target index and item
        self.getNextIndex(direction, self.currentIndex)

        # if direction was set to three, the item is supposed to leave the subdir from the top.
        if direction == 2:
            direction = 0

        # if current item is the first or last (depending on direction) in list
        # abort the operation, as theres no point in trying to move
        if self.nextItem is None:
            return

        sourceFolder = self.currentItem.path.parent
        sourceFile = self.currentItem.path.name

        destinationFolder = self.nextItem.path.parent
        destinationFile = self.nextItem.path.name

        log.debug(f"""
        Source Folder: {sourceFolder}
        Source File: {sourceFile}

        Destination Folder: {destinationFolder}
        Destination File: {destinationFile}
        """)
        if sourceFolder == destinationFolder:
            # stay in same (sub)menu
            filesSourceFolder = []
            filesDestinationFolder = [destinationFile]

        else:
            filesSourceFolder = self.indexFolder(sourceFolder)
            filesDestinationFolder = self.indexFolder(destinationFolder)

            if sourceFolder == sorted([sourceFolder, destinationFolder])[0]:
                # enter submenu
                filesSourceFolder = filesSourceFolder[
                    filesSourceFolder.index(sourceFile) :
                ]

                if not direction:
                    # if entering a subfolder from the bottom
                    filesDestinationFolder = []
                    # +1 to name of the file, so the source file will appear at the bottom of the submenu
                    # without overwriting the dest item
                    destinationFile = (
                        str(int(destinationFile[:3]) + 1).zfill(3) + destinationFile[3:]
                    )
            elif direction:
                # if exiting a subfolder at the bottom
                filesSourceFolder = []
            else:
                # exit submenu at top
                filesDestinationFolder = filesDestinationFolder[
                    filesDestinationFolder.index(destinationFile) :
                ]

        if sourceFile in filesSourceFolder:
            filesSourceFolder.remove(sourceFile)

        # make sure destination is same type (file/submenu) as the file being moved
        # if len = 6 (###.py) it's a file, otherwise it must be a submenu (###)
        sourceType = len(sourceFile) == 6
        destinationType = len(destinationFile) == 6

        if destinationType != sourceType:
            if sourceType:
                destinationFile = f"{destinationFile}.py"
            else:
                destinationFile = destinationFile[:3]

        tmpExtention = "_tmp"

        # temporarily rename affected files in affected folders

        tmpFiles = [[], []]

        files = [filesDestinationFolder, filesSourceFolder]

        folders = [destinationFolder, sourceFolder]

        log.debug(f"""
        Source Type: {sourceType}
        Destination Type: {destinationType}
        Destination File: {destinationFile}
        files: {files}
        folders: {folders}
        """)

        for index in range(2):
            for file in files[index]:
                tmpFile = file + tmpExtention
                tmpFiles[index].append(tmpFile)

                folder = folders[index]
                origPath = folder / file
                tmpPath = folder / tmpFile

                # rename files and update lookupTable to keep track of files
                self.renameButton(origPath, tmpPath)

                # if removing a file from a menu by it's top, the submenu will have to be renamed (as the file will take
                # the menu's place). When renaming this menu, we have to update the paths of the source folder as well,
                # otherwise we will not be able to find the files anymore.

                if origPath == folders[1 - index]:
                    folders[1 - index] = tmpPath

        # rename mainfile

        origPath = f"{folders[1]}/{sourceFile}"
        newPath = f"{folders[0]}/{destinationFile}"

        self.renameButton(origPath, newPath)
        # save to restore selection later on
        targetItem = newPath

        # give all the tmp files proper names

        for index in range(2):
            folder = folders[index]

            currentFiles = [i[:3] for i in self.indexFolder(folder)]

            file = "001"

            for tmpFile in tmpFiles[index]:
                # submenu or button
                extension = ""
                if "." in tmpFile:
                    extension = ".py"

                while file in currentFiles:
                    file = str(int(file) + 1).zfill(3)

                currentFiles.append(file)

                origPath = f"{folder}/{tmpFile}"
                newPath = f"{folder}/{file}{extension}"

                # when moving a file from a submenu, make sure the source folder gets renamed after renaming the tmp'd
                # submene, otherwise the tmp'd files living inside that submenu cannot be found.
                if index == 0 and not extension and origPath == folders[1]:
                    folders[1] = newPath

                if origPath == folders[0]:
                    targetItem = f"{newPath}/{destinationFile}"

                self.renameButton(origPath, newPath)

        self.populateTree()

        self.restoreSelection(targetItem)

    def renameButton(self, origPath: Union[Path, str], newPath: Union[Path, str]):
        """
        Rename files and update paths to keep track of buttons
        """
        orig_path = Path(origPath)
        new_path = Path(newPath)

        # rename actual file
        orig_path.rename(new_path)

        # update path for button objects

        for path in [
            p for p in self.buttonsList.keys() if p.startswith(orig_path.as_posix())
        ]:
            button = self.buttonsList[path]

            updatedPath = path.replace(orig_path.as_posix(), new_path.as_posix())
            button.path = Path(updatedPath)

            # add updated path to dict
            self.buttonsList[updatedPath] = button

            # delete outdated path from dict
            del self.buttonsList[path]

    def restoreSelection(self, path: Optional[Path] = None):
        if not path:
            return
        path = Path(path)
        if not path.exists():
            return

        # restore selection
        if path.as_posix() in self.buttonsList:
            self.setCurrentIndex(self.buttonsList[path.as_posix()].index())
        else:
            log.error(
                f"We could not find '{path.as_posix()}' in {self.buttonsList.keys()}"
            )

    def indexFolder(self, folder: Union[Path, str]) -> list[str]:
        """
        Return a list of files currently present in a given folder.
        Only properly named files will be returned.
        """
        if isinstance(folder, str):
            # TODO: remove this now
            return [
                file
                for file in os.listdir(folder)
                if file[0] not in ["_", "."] and len(file) in {3, 6}
            ]
        else:
            return [
                file.name
                for file in folder.iterdir()
                if file.name[0] not in ["_", "."] and len(file.name) in {3, 6}
            ]

    def getNextIndex(self, direction, index):
        """
        Get the index of the item next to the current item
        """

        if direction == 2:
            self.nextItem = self.currentItem.parent()

        else:
            if direction:
                # if current item is the submenu and the move-down button is triggered
                forceExpanded = False
                if not os.path.isfile(self.currentItem.path):
                    item = self.dataModel.itemFromIndex(index)

                    if self.isExpanded(index) and item.hasChildren():
                        self.setExpanded(index, False)
                        forceExpanded = True

                self.nextIndex = self.indexBelow(index)

                if forceExpanded:
                    self.setExpanded(index, True)

            else:
                self.nextIndex = self.indexAbove(index)

            self.nextItem = self.dataModel.itemFromIndex(self.nextIndex)

            # if moving down and current item is last item in a subfolder with no item underneath it.
            if self.nextItem is None and direction:
                parentItem = self.currentItem.parent()
                if parentItem is not None:
                    newBaseName = str(int(os.path.basename(parentItem.path)) + 1).zfill(
                        3
                    )
                    parentItem.path = (
                        f"{os.path.dirname(parentItem.path)}/{newBaseName}"
                    )
                    self.nextItem = parentItem

            # exit
            if self.nextItem is None:
                return

            # if submenu
            # skip item if expanded
            if os.path.dirname(self.nextItem.path) == os.path.dirname(
                self.currentItem.path
            ) and not os.path.isfile(self.nextItem.path):
                if not self.nextItem.hasChildren():
                    self.nextItem.path += (
                        f"/001{os.path.basename(self.currentItem.path)[3:]}"
                    )
                elif direction and (
                    self.isExpanded(self.nextIndex) and self.nextItem.hasChildren()
                ):
                    self.getNextIndex(direction, self.nextIndex)

    # - hotbox items tree actions
    def addItem(self, folder=False):
        """
        Create new item for selected nodeclass
        """

        folderPath = self.scope

        # if item selected, place the new underneath
        selectedIndexes = self.selectedIndexes()
        if len(selectedIndexes) != 0:
            selectedItem = self.dataModel.itemFromIndex(selectedIndexes[0])
            folderPath = Path(selectedItem.path).parent

        # make sure all the files inside the folder are named correctly
        RepairHotbox(folder=folderPath, recursive=False, message=False)

        # loop over content of folder to find an appropriate name for the new item
        itemPath = getFirstAvailableFilePath(folderPath)

        if not folder:
            from .manager import FileHeader

            itemName = "New Item"
            itemPath = itemPath.with_suffix(".py")

            newFileContent = FileHeader(itemName).getHeader()
            itemPath.write_text(newFileContent)
        else:
            itemName = "New Menu"

            itemPath.mkdir()
            (itemPath / "_name.json").write_text(itemName, encoding="utf-8")

        self.populateTree()

        self.restoreSelection(itemPath)

    def removeItem(self):
        """
        Move selected item to the _old folder.
        """

        selectedIndex = self.selectedIndexes()[0]
        currentItem = self.dataModel.itemFromIndex(selectedIndex)

        nextItem = self.dataModel.itemFromIndex(self.indexBelow(selectedIndex))
        if nextItem is None:
            nextItem = self.dataModel.itemFromIndex(self.indexAbove(selectedIndex))

        nextItemPath = Path(nextItem.path) if nextItem is not None else None
        # - remove selected file
        oldFolder = self.scope / "_old"

        if not oldFolder.exists():
            oldFolder.mkdir()

        currentTime = dt.now().strftime("%Y%m%d%H%M%S")
        newFileName = currentTime

        counter = 1
        while newFileName in sorted(oldFolder.iterdir()):
            newFileName = f"{currentTime}_{str(counter).zfill(3)}"
            counter += 1

        shutil.move(currentItem.path, oldFolder / newFileName)

        # - make sure all the files inside the folder are named correctly
        changedFolder = Path(currentItem.path).parent

        RepairHotbox(folder=changedFolder, recursive=False, message=False)

        self.populateTree()

        self.restoreSelection(nextItemPath)

    def copyItem(self):
        """
        Place the selected items in the class' clipboard
        """
        with contextlib.suppress(Exception):
            self.clipboard = list([Path(x) for x in self.selectedItemsPaths])

    def pasteItem(self):
        """
        Copy the items stored in the class' clipboard to the current folder
        """

        if len(self.clipboard) <= 0:
            return

        # - make sure all the files inside the folder are named correctly
        RepairHotbox(folder=self.scope, recursive=False, message=False)

        for path in self.clipboard:
            fileList = sorted(
                [i.stem for i in path.parent.iterdir() if i.name[0] not in [".", "_"]]
            )

            newFileName = "001"

            counter = 1
            while newFileName in fileList:
                counter += 1
                newFileName = str(counter).zfill(3)

            newPath = self.scope / newFileName

            # - if file
            if path.name.endswith(".py"):
                newPath = newPath.with_suffix(".py")
                shutil.copy2(path, newPath)

            # - if menu
            else:
                shutil.copytree(path, newPath)

        self.populateTree()

        self.restoreSelection(newPath)

    def duplicateItem(self):
        """
        Duplicate the currently selected items.
        """
        tmpClipboard = self.clipboard
        self.copyItem()
        self.pasteItem()
        self.clipboard = tmpClipboard


class QStandardItemChild(QtGui.QStandardItem):
    def __init__(self, name: str, path: Path):
        super(QStandardItemChild, self).__init__()

        # self.richTextName = name

        # - convert rich text to plain text

        if "<" in name:
            richToPlain = re.compile("<[^>]*>").sub("", name)

            if len(richToPlain) > 0:
                name = richToPlain
            elif "img " in name:
                richToPlain = (
                    name.replace(" ", "").replace("<imgsrc=", "").replace("'", '"')
                )
                richToPlain = richToPlain.split('">')[0]
                richToPlain = os.path.basename(richToPlain)
                if len(richToPlain) > 0:
                    name = richToPlain

        # - if the name has a whitespace at the beginning due to the conversion to plain text, get rid of them.
        while name.startswith(" "):
            name = name[1:]

        self.setText(name)

        # - path points to the place the file is currently stored
        # - parent points to the place in the gui

        self.path = path

        self.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)

        # - change color is submenu
        if self.path.is_dir():
            self.setBackground(QtGui.QColor(45, 45, 45))

        parentObject = self.parent()
        if parentObject != None:
            self.currentGuiPath = parentObject.path


class QLabelButton(QtWidgets.QLabel):
    """
    Custom class to make a Qlabel function as a button.
    """

    # - signals
    clicked = QtCore.Signal()

    def __init__(self, name, linkedWidget=None):
        super(QLabelButton, self).__init__()

        self.linkedWidget = linkedWidget

        iconFolder = preferencesNode.knob("hotboxIconLocation").value()

        while iconFolder[-1] == "/":
            iconFolder = iconFolder[:-1]

        iconFolder = os.path.expandvars(iconFolder)

        self.imageFile = f"{iconFolder}/hotbox_{name}"

        # - check if icon is present. If not, display '?'
        if not os.path.isfile(f"{self.imageFile}_neutral.png"):
            self.imageFile = None

            self.setText('<font size = "6">?</font>')
            self.setAlignment(QtCore.Qt.AlignCenter)
            self.setStyleSheet("color: #717171")

        else:
            self.updateIcon()

        # - format name
        if name != name.lower():
            newName = ""

            for character in name:
                if character in string.ascii_uppercase:
                    character = f" {character.lower()}"
                newName = newName + character

            name = newName

        # - tooltip
        self.setToolTip(name)

    # - Events
    def enterEvent(self, event):
        self.updateIcon("hover")

    def leaveEvent(self, event):
        self.updateIcon()

    def mousePressEvent(self, event):
        self.updateIcon("clicked")

    def mouseReleaseEvent(self, event):
        # - emit signal

        self.updateIcon("hover")

        # - if button has a linkedwidget set, check if that widget is enabled.
        # - if not, dont emit clicked signal

        if self.linkedWidget and not self.linkedWidget.enabled:
            return

        self.clicked.emit()

    # --------------------------------------------------------------------------------------------------

    def updateIcon(self, mode="neutral"):
        if self.imageFile:
            path = f"{self.imageFile}_{mode}.png"
            self.setPixmap(QtGui.QPixmap(path))


# - rename  dialog


class RenameDialog(QtWidgets.QDialog):
    """
    Dialog that will pop up when the rename button in the manager is clicked.
    """

    def __init__(self, currentName, new=False):
        super(RenameDialog, self).__init__()

        self.currentName = currentName

        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)

        self.new = new

        constants = Constants()
        self.hotboxManager = constants.hotboxManagerInstance

        # list of all items currently in list
        self.allItems = self.hotboxManager.classesList.allItemNames()
        if self.currentName in self.allItems:
            self.allItems.remove(self.currentName)

        enitity = "Rule" if self.hotboxManager.mode == "Rules" else "Class"
        # window title
        if self.new:
            renameButtonLabel = "Create"
            self.setWindowTitle(f"New {enitity}")

        else:
            renameButtonLabel = "Rename"
            self.setWindowTitle(f"Rename {enitity}")

        # layout
        masterLayout = QtWidgets.QVBoxLayout()
        buttonsLayout = QtWidgets.QHBoxLayout()

        self.newNameLineEdit = QtWidgets.QLineEdit()
        self.newNameLineEdit.setText(self.currentName)
        self.newNameLineEdit.selectAll()

        self.newNameLineEdit.textChanged.connect(self.validateName)

        self.renameButton = QtWidgets.QPushButton(renameButtonLabel)
        cancelButton = QtWidgets.QPushButton("Cancel")

        self.renameButton.clicked.connect(self.renameButtonClicked)
        cancelButton.clicked.connect(self.cancelRenameDialog)

        for button in [self.renameButton, cancelButton]:
            buttonsLayout.addWidget(button)

        masterLayout.addWidget(self.newNameLineEdit)
        masterLayout.addLayout(buttonsLayout)
        self.setLayout(masterLayout)

        # shortcuts
        self.enterAction = QtWidgets.QAction(self)
        self.enterAction.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Return))
        self.enterAction.triggered.connect(self.renameButtonClicked)
        self.addAction(self.enterAction)

        # move to screen center
        self.adjustSize()
        screenRes = QtWidgets.QDesktopWidget().screenGeometry()
        self.move(
            QtCore.QPoint(screenRes.width() // 2, screenRes.height() // 2)
            - QtCore.QPoint((self.width() // 2), (self.height() // 2))
        )

    def validateName(self):
        """
        Check the imput name and disable the 'Rename button' accordingly.
        """
        text = self.newNameLineEdit.text()
        valid = True

        try:
            valid *= text not in self.allItems
            valid *= len(text) > 0
            valid *= text[-1] != "_"
            valid *= text[0] != "_"
        except:
            valid = False

        self.renameButton.setEnabled(valid)

    def renameButtonClicked(self):
        currentPath = f"{self.hotboxManager.path}/{self.currentName}"
        newPath = f"{self.hotboxManager.path}/{self.newNameLineEdit.text()}"

        if currentPath != newPath:
            counter = 1
            while os.path.isdir(newPath):
                splitPath = os.path.basename(newPath).split("_")
                if len(splitPath) > 1:
                    suffix = splitPath[-1]
                    if suffix.isdigit():
                        counter = int(suffix) + 1

                newPath = (
                    f"{self.hotboxManager.path}/{self.newNameLineEdit.text()}_{counter}"
                )
                counter += 1

            shutil.move(currentPath, newPath)

            self.hotboxManager.buildClassesList(os.path.basename(newPath))

        self.closeRenameDialog()

    def cancelRenameDialog(self):
        if self.new:
            self.hotboxManager.removeClass(self.currentName)

        self.closeRenameDialog()

    def closeRenameDialog(self):
        self.close()
        constants = Constants()
        constants.renameDialogInstance = None
        return False


# - Dialog with contact informaton
class AboutDialog(QtWidgets.QFrame):
    """
    Dialog that will show some information about the current version of the Hotbox.
    """

    def __init__(self):
        super(AboutDialog, self).__init__()

        self.setWindowFlags(QtCore.Qt.ToolTip)

        self.setFixedHeight(250)
        self.setFixedWidth(230)

        self.setFrameStyle(QtWidgets.QFrame.Plain | QtWidgets.QFrame.StyledPanel)

        # logo
        aboutHotbox = QtWidgets.QLabel()
        aboutIcon = (
            preferencesNode.knob("hotboxIconLocation").value().replace("\\", "/")
            + "/icon.png"
        )
        aboutIcon = aboutIcon.replace("//icon.png", "/icon.png")
        aboutHotbox.setPixmap(QtGui.QPixmap(aboutIcon))

        # version
        aboutVersion = QtWidgets.QLabel(version)
        aboutDate = QtWidgets.QLabel(releaseDate)

        # clickable links
        aboutDownload = QWebLink(
            "Nukepedia", "http://www.nukepedia.com/python/ui/w_hotbox/"
        )
        aboutName = QtWidgets.QLabel("Wouter Gilsing")
        aboutMail = QWebLink(
            "woutergilsing@hotmail.com", "mailto:woutergilsing@hotmail.com?body="
        )
        aboutWeb = QWebLink("woutergilsing.com", "http://www.woutergilsing.com")

        # set fonts
        fontSize = 0.3
        font = preferencesNode.knob("UIFont").value()
        mediumFont = QtGui.QFont(font, fontSize * 40)
        smallFont = QtGui.QFont(font, fontSize * 30)

        aboutDownload.setFont(mediumFont)

        for label in [aboutVersion, aboutDate, aboutName, aboutMail, aboutWeb]:
            label.setFont(smallFont)

        # assemble interface
        masterLayout = QtWidgets.QVBoxLayout()

        masterLayout.addWidget(aboutHotbox)

        masterLayout.addWidget(aboutVersion)
        masterLayout.addWidget(aboutDate)
        masterLayout.addSpacing(40)
        masterLayout.addLayout(self.wrapInLayout(aboutDownload))
        masterLayout.addSpacing(20)

        masterLayout.addWidget(aboutName)
        masterLayout.addLayout(self.wrapInLayout(aboutMail, True))
        masterLayout.addLayout(self.wrapInLayout(aboutWeb, True))

        self.setLayout(masterLayout)

        # move to screen center
        self.adjustSize()
        screenRes = QtWidgets.QDesktopWidget().screenGeometry()
        self.move(
            QtCore.QPoint(screenRes.width() // 2, screenRes.height() // 2)
            - QtCore.QPoint((self.width() // 2), (self.height() // 2))
        )

    def mouseReleaseEvent(self, event):
        """
        Close window when clicked. Like a splashscreen.
        """
        self.close()

    def wrapInLayout(self, weblink, alignment=None):
        """
        Wrap label/Weblink in a layout, to make sure it will be aligned properly and only the actual text is clickable.
        """

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(weblink)

        if alignment:
            weblink.setAlignment(QtCore.Qt.AlignRight)

        layout.insertStretch(bool(alignment))

        return layout


class QWebLink(QtWidgets.QLabel):
    def __init__(self, name, link):
        super(QWebLink, self).__init__()

        self.link = link
        if self.link.startswith("mailto:"):
            self.link = self.link + self.composeEmail()
        self.setToolTip(self.link)

        self.origText = name
        self.setText(self.origText)

        self.active = False

    def composeEmail(self):
        import platform

        operatingSystem = platform.system()

        hotboxVersion = f"W_hotbox v{version} ({releaseDate})"
        nukeVersion = f"Nuke {nuke.NUKE_VERSION_STRING}"

        if operatingSystem == "Windows":
            osName = "Windows"
            osVersion = platform.win32_ver()[0]

        elif operatingSystem == "Darwin":
            osName = "OSX"
            osVersion = platform.mac_ver()[0]
        else:
            osName = platform.linux_distribution(full_distribution_name=0)[0]
            osVersion = platform.linux_distribution(full_distribution_name=0)[1]

        operatingSystem = " ".join([osName, osVersion])

        return "\n".join(
            ["I'm running:\n", hotboxVersion, nukeVersion, operatingSystem]
        )

    def activate(self):
        self.setText(f"<font color = #f7931e>{self.origText}</font>")

    def deactivate(self):
        self.setText(f"<font color = #c8c8c8>{self.origText}</font>")

    def enterEvent(self, event):
        self.activate()

    def leaveEvent(self, event):
        self.deactivate()

    def mouseReleaseEvent(self, event):
        openURL(self.link)
