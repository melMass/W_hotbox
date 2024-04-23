from typing import Optional, Union
import nuke
import pathlib

from PySide2 import QtGui, QtCore, QtWidgets

import os
import shutil

import re
import string
import colorsys
import tempfile
import tarfile
import base64
import contextlib
from pathlib import Path
from datetime import datetime as dt
from webbrowser import open as openURL


from .script_editor import (
    ScriptEditorWidget,
    ScriptEditorNameWidget,
    ScriptEditorTemplateMenu,
    ScriptEditorHighlighter,
)

from .utils import (
    log,
    Constants,
    read_name,
    update_level_with_name,
    process_file_name,
    getAttributeFromFile,
    getFirstAvailableFilePath,
    getHotBoxLocation,
    getScriptFromFile,
    getTileColor,
    hex2rgb,
    interface2rgb,
    preferencesNode,
    releaseDate,
    rgb2hex,
    rgb2interface,
    version,
)


class HotboxManager(QtWidgets.QWidget):
    def __init__(self, path: Union[Path, str] = ""):
        super(HotboxManager, self).__init__()

        # - main widget

        # parent to main nuke interface
        self.setParent(QtWidgets.QApplication.instance().activeWindow())
        self.setWindowFlags(QtCore.Qt.Tool)

        self.setWindowTitle(f"W_hotbox Manager - {path}")

        self.setMinimumWidth(1000)
        self.setMinimumHeight(400)

        # - colors

        self.activeColor = "#3a3a3a"
        self.lockedColor = "#262626"

        if isinstance(path, Path):
            self.rootLocation = path
        else:
            self.rootLocation = Path(path)

        self.path = self.rootLocation
        # - create folders

        # If the manager is launched for the default repository, make sure the current archive exists.

        preferencesLocation = getHotBoxLocation()

        if self.rootLocation == preferencesLocation:
            for subFolder in [
                "",
                "Single",
                "Multiple",
                "All",
                "Single/No Selection",
                "Rules",
                "Templates",
            ]:
                subFolderPath = self.rootLocation / subFolder
                if not subFolderPath.is_dir():
                    with contextlib.suppress(Exception):
                        subFolderPath.mkdir()

        self.templateLocation = self.rootLocation / "Templates"

        # - left column - classes list
        self.classesListLayout = QtWidgets.QVBoxLayout()

        # scope dropdown
        self.scopeComboBox = QtWidgets.QComboBox()
        self.scopeComboBoxItems = ["Single", "Multiple", "All", "Rules"]
        self.scopeComboBox.addItems(self.scopeComboBoxItems)
        self.scopeComboBox.insertSeparator(3)

        self.scopeComboBox.currentIndexChanged.connect(self.buildClassesList)

        # list column
        self.classesList = QListWidgetCustom(self)
        self.classesList.setFixedWidth(150)

        self.classesListLayout.addWidget(self.scopeComboBox)
        self.classesListLayout.addWidget(self.classesList)

        # buttons
        self.classesListButtonsLayout = QtWidgets.QVBoxLayout()

        self.classesListAddButton = QLabelButton("add", self.classesList)
        self.classesListRemoveButton = QLabelButton("remove", self.classesList)
        self.classesListRenameButton = QLabelButton("rename", self.classesList)

        # connect
        self.classesListAddButton.clicked.connect(self.addClass)
        self.classesListRemoveButton.clicked.connect(self.removeClass)
        self.classesListRenameButton.clicked.connect(self.renameClass)

        # assemble layout
        self.classesListButtonsLayout.addStretch()
        self.classesListButtonsLayout.addWidget(self.classesListAddButton)
        self.classesListButtonsLayout.addWidget(self.classesListRemoveButton)
        self.classesListButtonsLayout.addWidget(self.classesListRenameButton)
        self.classesListButtonsLayout.addStretch()

        # - right column - hotbox items tree
        self.hotboxItemsTree = QTreeViewCustom(self)
        self.hotboxItemsTree.setFixedWidth(150)
        self.rootPath = getHotBoxLocation()

        self.classesList.itemSelectionChanged.connect(self.hotboxItemsTree.populateTree)

        # actions
        self.hotboxItemsTreeButtonsLayout = QtWidgets.QVBoxLayout()

        self.hotboxItemsTreeAddButton = QLabelButton("add", self.hotboxItemsTree)
        self.hotboxItemsTreeAddFolderButton = QLabelButton(
            "addFolder", self.hotboxItemsTree
        )
        self.hotboxItemsTreeRemoveButton = QLabelButton("remove", self.hotboxItemsTree)
        self.hotboxItemsTreeDuplicateButton = QLabelButton(
            "duplicate", self.hotboxItemsTree
        )
        self.hotboxItemsTreeCopyButton = QLabelButton("copy", self.hotboxItemsTree)
        self.hotboxItemsTreePasteButton = QLabelButton("paste", self.hotboxItemsTree)

        self.hotboxItemsTreeMoveUp = QLabelButton("moveUp", self.hotboxItemsTree)
        self.hotboxItemsTreeMoveDown = QLabelButton("moveDown", self.hotboxItemsTree)
        self.hotboxItemsTreeMoveUpLevel = QLabelButton(
            "moveUpLevel", self.hotboxItemsTree
        )

        # connect
        self.hotboxItemsTreeAddButton.clicked.connect(self.hotboxItemsTree.addItem)
        self.hotboxItemsTreeAddFolderButton.clicked.connect(
            lambda: self.hotboxItemsTree.addItem(True)
        )
        self.hotboxItemsTreeRemoveButton.clicked.connect(
            self.hotboxItemsTree.removeItem
        )
        self.hotboxItemsTreeDuplicateButton.clicked.connect(
            self.hotboxItemsTree.duplicateItem
        )
        self.hotboxItemsTreeCopyButton.clicked.connect(self.hotboxItemsTree.copyItem)
        self.hotboxItemsTreePasteButton.clicked.connect(self.hotboxItemsTree.pasteItem)

        self.hotboxItemsTreeMoveUp.clicked.connect(
            lambda: self.hotboxItemsTree.moveItem(0)
        )
        self.hotboxItemsTreeMoveDown.clicked.connect(
            lambda: self.hotboxItemsTree.moveItem(1)
        )
        self.hotboxItemsTreeMoveUpLevel.clicked.connect(
            lambda: self.hotboxItemsTree.moveItem(2)
        )

        # assemble layout
        self.hotboxItemsTreeButtonsLayout.addStretch()
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeAddButton)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeAddFolderButton)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeRemoveButton)

        self.hotboxItemsTreeButtonsLayout.addSpacing(25)

        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeMoveUp)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeMoveDown)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeMoveUpLevel)

        self.hotboxItemsTreeButtonsLayout.addSpacing(25)

        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeCopyButton)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreePasteButton)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeDuplicateButton)

        self.hotboxItemsTreeButtonsLayout.addStretch()

        # - import/export
        # create buttons
        self.clipboardArchive = QtWidgets.QCheckBox("Clipboard")
        self.importArchiveButton = QtWidgets.QPushButton("Import Archive")
        self.exportArchiveButton = QtWidgets.QPushButton("Export Archive")

        self.importArchiveButton.setMaximumWidth(100)
        self.exportArchiveButton.setMaximumWidth(100)

        # tooltips
        tooltip = "Make use of the clipboard to import/export an archive, rather than saving a file to disk."
        self.clipboardArchive.setToolTip(tooltip)
        tooltip = "Import a button archive. This will append the current set of buttons and overwrite any buttons with the same name."
        self.importArchiveButton.setToolTip(tooltip)
        tooltip = "Export the current set of buttons as an archive."
        self.exportArchiveButton.setToolTip(tooltip)

        # wire up
        self.importArchiveButton.clicked.connect(self.importHotboxArchive)
        self.exportArchiveButton.clicked.connect(self.exportHotboxArchive)

        # assemble
        self.archiveButtonsLayout = QtWidgets.QHBoxLayout()
        self.archiveButtonsLayout.addStretch()
        self.archiveButtonsLayout.addWidget(self.clipboardArchive)
        self.archiveButtonsLayout.addWidget(self.importArchiveButton)
        self.archiveButtonsLayout.addWidget(self.exportArchiveButton)

        # - scriptEditor
        self.ignoreSave = False
        self.loadedScript = None
        self.scriptEditorLayout = QtWidgets.QVBoxLayout()

        # buttons
        self.scriptEditorButtonsLayout = QtWidgets.QHBoxLayout()

        self.scriptEditorTemplateButton = QtWidgets.QToolButton()
        self.scriptEditorTemplateButton.setText("Templates  ")
        self.scriptEditorTemplateButton.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        self.exitTemplateModeButton = QtWidgets.QPushButton("Exit template mode")
        self.exitTemplateModeButton.setStyleSheet("color: #f7931e")
        self.exitTemplateModeButton.setVisible(False)

        self.scriptEditorImportButton = QtWidgets.QPushButton("Import")
        self.scriptEditorImportButton.clicked.connect(self.importScriptEditor)

        self.scriptEditorTemplateMenu = ScriptEditorTemplateMenu(self)
        self.scriptEditorTemplateButton.setMenu(self.scriptEditorTemplateMenu)
        self.exitTemplateModeButton.clicked.connect(self.toggleTemplateMode)

        self.scriptEditorTemplateButtons = [
            self.exitTemplateModeButton,
            self.scriptEditorTemplateButton,
        ]

        self.scriptEditorButtonsLayout.addStretch()
        for button in self.scriptEditorTemplateButtons + [
            self.scriptEditorImportButton
        ]:
            self.scriptEditorButtonsLayout.addWidget(button)
        self.scriptEditorButtonsLayout.addStretch()

        # name
        self.scriptEditorNameLayout = QtWidgets.QHBoxLayout()

        self.scriptEditorNameLabel = QtWidgets.QLabel("Name")
        self.scriptEditorName = ScriptEditorNameWidget()
        self.scriptEditorName.setAlignment(QtCore.Qt.AlignLeft)

        self.scriptEditorName.editingFinished.connect(self.saveScriptEditor)

        # color swatches
        self.colorSwatchButtonLabel = QtWidgets.QLabel("Button")
        self.colorSwatchButton = ColorSwatch("#525252")

        self.colorSwatchTextLabel = QtWidgets.QLabel("Text")
        self.colorSwatchText = ColorSwatch("#eeeeee")

        self.colorSwatchButton.setChild(self.colorSwatchText)

        # wire up color swatches
        self.colorSwatchButton.save.connect(self.saveScriptEditor)
        self.colorSwatchText.save.connect(self.saveScriptEditor)

        self.scriptEditorNameWidgets = [
            self.scriptEditorNameLabel,
            self.scriptEditorName,
            self.colorSwatchButtonLabel,
            self.colorSwatchButton,
            self.colorSwatchTextLabel,
            self.colorSwatchText,
        ]

        # rules
        self.rulesFlagCheckbox = QtWidgets.QCheckBox("Ignore classes")
        self.rulesFlagCheckbox.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.rulesFlagCheckbox.stateChanged.connect(lambda: self.saveScriptEditor())

        # label to make sure the checkbox is aligned to the right
        self.rulesFlagLabel = QtWidgets.QLabel("")
        self.rulesFlagWidgets = [self.rulesFlagCheckbox, self.rulesFlagLabel]

        for widget in self.rulesFlagWidgets:
            widget.setVisible(False)

        # assemble layout
        for widget in self.rulesFlagWidgets + self.scriptEditorNameWidgets:
            self.scriptEditorNameLayout.addWidget(widget)

        # script
        self.scriptEditorScript = ScriptEditorWidget()
        self.scriptEditorScript.setMinimumHeight(200)
        self.scriptEditorScript.setMinimumWidth(500)

        self.scriptEditorScript.save.connect(self.saveScriptEditor)

        _ = ScriptEditorHighlighter(self.scriptEditorScript.document())

        scriptEditorFont = QtGui.QFont()
        scriptEditorFont.setFamily("Courier")
        scriptEditorFont.setStyleHint(QtGui.QFont.Monospace)
        scriptEditorFont.setFixedPitch(True)
        scriptEditorFont.setPointSize(
            preferencesNode.knob("hotboxScriptEditorFontSize").value()
        )

        self.scriptEditorScript.setFont(scriptEditorFont)
        self.scriptEditorScript.setTabStopWidth(
            4 * QtGui.QFontMetrics(scriptEditorFont).width(" ")
        )

        # assemble
        self.scriptEditorLayout.addLayout(self.archiveButtonsLayout)
        self.scriptEditorLayout.addLayout(self.scriptEditorNameLayout)
        self.scriptEditorLayout.addWidget(self.scriptEditorScript)
        self.scriptEditorLayout.addLayout(self.scriptEditorButtonsLayout)

        # - main buttons
        self.mainButtonLayout = QtWidgets.QHBoxLayout()

        self.aboutButton = QtWidgets.QPushButton("?")
        self.aboutButton.clicked.connect(self.openAboutDialog)
        self.aboutButton.setMaximumWidth(20)

        self.mainCloseButton = QtWidgets.QPushButton("Close")
        self.mainCloseButton.clicked.connect(self.closeManager)

        self.mainButtonLayout.addWidget(self.aboutButton)
        self.mainButtonLayout.addStretch()
        self.mainButtonLayout.addWidget(self.mainCloseButton)

        # - main layout
        self.mainLayout = QtWidgets.QHBoxLayout()
        self.mainLayout.addLayout(self.classesListButtonsLayout)
        self.mainLayout.addLayout(self.classesListLayout)
        self.mainLayout.addLayout(self.hotboxItemsTreeButtonsLayout)
        self.mainLayout.addWidget(self.hotboxItemsTree)
        self.mainLayout.addLayout(self.scriptEditorLayout)

        # - layouts
        self.masterLayout = QtWidgets.QVBoxLayout()

        self.masterLayout.addLayout(self.mainLayout)
        self.masterLayout.addLayout(self.mainButtonLayout)

        self.setLayout(self.masterLayout)

        # - move to center of the screen
        self.adjustSize()

        screenRes = QtWidgets.QDesktopWidget().screenGeometry()
        self.move(
            QtCore.QPoint(screenRes.width() // 2, screenRes.height() // 2)
            - QtCore.QPoint((self.width() // 2), (self.height() // 2))
        )

        # - set values
        self.enableScriptEditor(False, False)

        self.scopeComboBox.setCurrentIndex(1)
        self.scopeComboBox.setCurrentIndex(0)
        self.scopeComboBoxLastIndex = 0

        # - set hotbox to current selection
        launchMode = preferencesNode.knob("hotboxOpenManagerOptions").value()
        launchMode = launchMode.replace("Contextual", "Single/Multiple")
        launchMode = launchMode.split("/")

        found = False

        # contextual
        if len(launchMode) > 1:
            selection = nuke.selectedNodes()

            classes = sorted({node.Class() for node in selection})

            # single/multiple
            self.scopeComboBox.setCurrentIndex(len(classes) > 1)

            for index in range(self.classesList.count()):
                itemClasses = self.classesList.item(index).text().split("-")
                if all(nodeClass in itemClasses for nodeClass in classes):
                    self.classesList.setCurrentRow(index)
                    found = True
                    break

            if len(launchMode) == 2:
                found = True

            else:
                found *= bool(selection)

        # all or rules (2 or 4)
        if not found:
            item = launchMode[-1]
            index = (int(item == "Rules") * 2) + 2
            self.scopeComboBox.setCurrentIndex(index)

    # - classes list
    def buildClassesList(self, selectItem=None):
        """
        Populate classes list with items.
        """

        log.debug("Building class list")
        # if restore based on index, save current index before clearing the widget.
        if isinstance(selectItem, bool) and selectItem:
            itemIndex = self.classesList.currentRow()

        self.mode = self.scopeComboBox.currentText()

        self.contextual = self.mode not in ["All", "Templates"]

        # turn this variable on, to prevent the itemChanged signal from emitting
        self.classesList.buildClassesList = True

        # clear selection
        self.classesList.clearSelection()

        # clear items tree
        self.hotboxItemsTree.clearTree()

        # clear list
        self.classesList.clear()

        # disable scripteditor
        self.enableScriptEditor(False, False)

        self.path = self.rootLocation / self.mode

        # color
        color = self.activeColor

        # disable if templates or all mode
        if self.contextual:
            self.classesList.setEnabled()
        else:
            self.classesList.setEnabled(False)

        if self.contextual:
            log.debug("Contextual")
            # sort items found on disk
            allItems = sorted(
                [
                    x.name
                    for x in self.path.iterdir()
                    if x.is_dir() and x.name[0] not in [".", "_"]
                ],
                key=lambda s: s.lower(),
            )
            log.debug(allItems)
            # add items
            self.classesList.addItems(allItems)

        # add checkbox to item if in rule mode
        if self.mode == "Rules":
            checkedStates = [QtCore.Qt.Unchecked, QtCore.Qt.Checked]
            for index in range(self.classesList.count()):
                item = self.classesList.item(index)
                itemText = item.text()

                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)

                # check if supposed to be enabled according to name
                checkedState = itemText[-1] != "_"
                item.setCheckState(checkedStates[checkedState])
                if not checkedState:
                    item.setText(itemText[:-1])

        self.toggleRulesMode(False)

        # populate buttons tree
        self.hotboxItemsTree.populateTree()

        # restore selection
        if selectItem:
            # select based on string
            if isinstance(selectItem, str):
                foundItems = self.classesList.findItems(
                    selectItem, QtCore.Qt.MatchExactly
                )
                if foundItems:
                    self.classesList.setCurrentItem(foundItems[0])

            # select based on index
            if isinstance(selectItem, bool):
                allItems = self.classesList.count() - 1
                itemIndex = min(allItems, itemIndex)

                self.classesList.setCurrentRow(itemIndex)

        # turn this variable back off
        self.classesList.buildClassesList = False

    def addClass(self):
        """
        Add a new nodeclass
        """
        defaultName = "NewRule" if self.mode == "Rules" else "NewClass"
        name = defaultName

        # in case name allready exists
        counter = 1
        while (self.path / name).is_dir():
            name = defaultName + str(counter)
            counter += 1

        # create folder on disk
        folderPath = self.path / name
        folderPath.mkdir()

        # create rule file
        if self.mode == "Rules":
            (folderPath / "_rule.py").write_text(FileHeader("0", rule=True).getHeader())

        self.buildClassesList(name)
        self.renameClass(True)

    def removeClass(self, className=None):
        """
        Remove the selected nodeclass
        """

        if className:
            selectedClass = className

        else:
            selectedClass = self.getSelectedClass()
            if not selectedClass:
                return

        # move to old folder
        oldFolder = self.path / "_old"
        if not oldFolder.is_dir():
            oldFolder.mkdir()

        shutil.move(
            self.path / selectedClass,
            self.path / "_old" / f"{selectedClass}_{dt.now().strftime('%Y%m%d%H%M%S')}",
        )

        self.buildClassesList(True)

    def renameClass(self, new=False):
        """
        Rename the selected nodeclass
        """

        selectedClass = self.getSelectedClass()
        if not selectedClass:
            return

        # kill any existing instances
        constants = Constants()

        if constants.renameDialogInstance != None:
            constants.renameDialogInstance.closeRenameDialog()

        # spawn new
        constants.renameDialogInstance = RenameDialog(selectedClass, new)
        constants.renameDialogInstance.show()

    def getSelectedClass(self):
        """
        Return the name of the selected class
        """

        if not self.classesList.itemSelected():
            return None

        selectedItem = self.classesList.currentItem()
        selectedClass = selectedItem.text()

        # if rule, check if item enabled
        if self.mode == "Rules":
            selectedClass += "_" * (1 - bool(selectedItem.checkState()))

        return selectedClass

    # - scriptEditor
    def loadScriptEditor(self, rule=False):
        """
        Fill the fields of the the script editor with the information read from the currently selected
        file.
        """

        self.scriptEditorScript.savedText = ""

        itemsSelected = True if rule else bool(self.hotboxItemsTree.selectedItems)
        if itemsSelected:
            if not rule:
                self.selectedItem = self.hotboxItemsTree.selectedItems[0]
                self.loadedScript = self.selectedItem.path

            # if rule mode
            else:
                item = self.classesList.currentItem()
                itemState = 1 - bool(item.checkState())
                self.loadedScript = (
                    self.path / (item.text() + "_" * itemState) / "_rule.py"
                )

            self.loadedScript = Path(self.loadedScript)
            # if item (not submenu)
            if self.loadedScript.name.endswith(".py"):
                self.enableScriptEditor()

                if not rule:
                    # set attributes
                    name = getAttributeFromFile(self.loadedScript)
                    self.scriptEditorName.setText(name)

                    # make sure the colorswatches will remain disabled in template mode
                    if not self.exitTemplateModeButton.isVisible():
                        textColor = getAttributeFromFile(self.loadedScript, "textColor")
                        self.colorSwatchText.setColor(
                            textColor, adjustChild=False, indirect=True
                        )

                        color = getAttributeFromFile(self.loadedScript, "color")
                        self.colorSwatchButton.setColor(
                            color, adjustChild=False, indirect=True
                        )

                # rule
                else:
                    ignoreClasses = bool(
                        getAttributeFromFile(self.loadedScript, "ignore classes") or 0
                    )

                    self.ignoreSave = True
                    self.rulesFlagCheckbox.setChecked(ignoreClasses)
                    self.ignoreSave = False

                # set script
                text = getScriptFromFile(self.loadedScript)
                self.scriptEditorScript.setPlainText(text)
                self.scriptEditorScript.updateSavedText()

            else:
                # set name
                name = read_name(self.loadedScript / "_name.json")
                self.scriptEditorName.setText(name)
                self.enableScriptEditor(False, True)

        else:
            self.loadedScript = None
            self.enableScriptEditor(False, False)

    def enableScriptEditor(self, editor=True, name=True):
        """
        Enable/Disable widgets based on selection.
        """

        colors = [self.activeColor, self.lockedColor]

        # script
        self.scriptEditorScript.setReadOnly(1 - editor)
        self.scriptEditorImportButton.setEnabled(editor)
        self.scriptEditorScript.setStyleSheet(f"background:{colors[1 - editor]}")
        if not editor:
            self.scriptEditorScript.clear()

        # make sure the buttons are colorswatches are always disabled in template mode
        editor = editor * (1 - self.exitTemplateModeButton.isVisible())

        for colorSwatch in [
            self.colorSwatchButton,
            self.colorSwatchText,
            self.colorSwatchButtonLabel,
            self.colorSwatchTextLabel,
        ]:
            colorSwatch.setEnabled(editor)

        # name
        self.scriptEditorName.setReadOnly(1 - name)
        self.scriptEditorNameLabel.setEnabled(name)
        self.scriptEditorName.setStyleSheet(f"background:{colors[1 - name]}")

        if not name:
            self.scriptEditorName.clear()

        # template button
        self.scriptEditorTemplateMenu.enableMenuItems()

    def importScriptEditor(self):
        """
        Set the current content of the script editor by importing an existing file.
        """

        if self.scriptEditorImportButton.isEnabled():
            importFile = nuke.getFilename("select file to  import", "*.py *.json")
            if importFile:
                # replace tabs with spaces
                with open(importFile, encoding="utf-8") as f:
                    text = f.read().replace("\t", " " * 4)

                self.scriptEditorScript.setPlainText(text)
                self.scriptEditorScript.setFocus()

    def saveScriptEditor(self, template=False):
        """
        Save the current content of the script editor
        """

        # dont save whenever this function is triggered while ignoreSave is on.
        if self.ignoreSave:
            return

        rule = self.rulesFlagCheckbox.isVisible()

        if not self.scriptEditorName.isReadOnly():
            name = self.scriptEditorName.text()

            if template:
                path = getFirstAvailableFilePath(self.templateLocation)
                path = path.with_suffix(".py")

            else:
                path = self.loadedScript

            # file
            if path.name.endswith(".py"):
                text = self.scriptEditorScript.toPlainText()

                if not rule:
                    # header
                    color = self.colorSwatchButton.isNonDefault(True)
                    textColor = self.colorSwatchText.isNonDefault(True)

                    newFileContent = (
                        FileHeader(name, color, textColor).getHeader() + text
                    )

                else:
                    newFileContent = (
                        FileHeader(
                            int(self.rulesFlagCheckbox.isChecked()), rule=True
                        ).getHeader()
                        + text
                    )

                path.write_text(newFileContent)
                # change save status
                self.scriptEditorScript.updateSavedText()

            else:
                if self.loadedScript is not None:
                    (self.loadedScript / "_name.json").write_text(name)

            if not rule:
                self.selectedItem.setText(name)

            if template and path.as_posix().startswith(
                self.templateLocation.as_posix()
            ):
                self.scriptEditorTemplateMenu.initMenu()

    # - Rules mode
    def toggleRulesMode(self, mode: bool = True):
        """
        Toggle rule mode on and off.
        """

        # if triggered by item selection
        if mode and self.mode != "Rules":
            return

        # apply change
        for index, widgetList in enumerate(
            [self.rulesFlagWidgets, self.scriptEditorNameWidgets][:: mode * 2 - 1]
        ):
            for widget in widgetList:
                widget.setVisible(bool(1 - index))

        if mode:
            self.loadScriptEditor(rule=True)

    # - Template mode
    def toggleTemplateMode(self):
        """
        Toggle template mode on and off.
        """

        enter = not self.exitTemplateModeButton.isVisible()
        # switch between template dropdown and 'Exit template mode' buttons.
        self.scriptEditorTemplateButton.setVisible(bool(1 - enter))
        self.exitTemplateModeButton.setVisible(enter)

        # store current selection
        if enter:
            # scope
            self.lastSelectedScopeIndex = self.scopeComboBox.currentIndex()

            selectedClassItem = self.classesList.currentItem()
            if selectedClassItem:
                self.lastSelectedClassIndex = self.classesList.indexFromItem(
                    selectedClassItem
                )
            else:
                self.lastSelectedClassIndex = None

            selectedItemIndexes = self.hotboxItemsTree.selectedIndexes()
            if selectedItemIndexes:
                self.lastSelectedItemIndex = selectedItemIndexes[0]
            else:
                self.lastSelectedItemIndex = None

        for index in range(self.scopeComboBox.count())[::-1]:
            self.scopeComboBox.removeItem(index)

        # refill scopeComboBox
        if enter:
            # change items of scopeCombobox to 'Templates'
            self.scopeComboBox.addItems(["Templates"])
            self.scopeComboBox.setCurrentIndex(0)
            self.scopeComboBox.setEditable(False)

        else:
            self._extracted_from_toggleTemplateMode_()

    # TODO Rename this here and in `toggleTemplateMode`
    def _extracted_from_toggleTemplateMode_(self):
        # update template menu
        self.scriptEditorTemplateMenu.initMenu()

        # change items of scopeCombobox to 'Single/Multiple/All'
        self.scopeComboBox.addItems(self.scopeComboBoxItems)

        # disable menu

        # restore last selection
        # scope
        self.scopeComboBox.setCurrentIndex(self.lastSelectedScopeIndex)

        # class
        if self.lastSelectedClassIndex:
            lastSelectedClassItem = self.classesList.itemFromIndex(
                self.lastSelectedClassIndex
            )
            self.classesList.setCurrentItem(lastSelectedClassItem)

        # item
        if self.lastSelectedItemIndex:
            self.hotboxItemsTree.setCurrentIndex(self.lastSelectedItemIndex)

        # make sure the template menu is properly enabled/disabled
        # this should would automatically, but fails when nothing is selected.
        self.scriptEditorTemplateMenu.enableMenuItems()

    # - import/export functions
    # export
    def exportHotboxArchive(self):
        """
        A method to export a set of buttons to an external archive.
        """

        archiveLocation = tempfile.mkstemp()[1]

        # write to zip
        with tarfile.open(archiveLocation, "w:gz") as tar:
            tar.add(self.rootLocation, arcname=self.rootLocation.name)

        # - file
        if not self.clipboardArchive.isChecked():
            # save to file
            exportFileLocation = nuke.getFilename("Export Archive", "*.hotbox")

            if exportFileLocation is None:
                return

            if not exportFileLocation.endswith(".hotbox"):
                exportFileLocation += ".hotbox"

            shutil.copy(archiveLocation, exportFileLocation)

            nuke.message(f"Successfully exported archive to \n{exportFileLocation}")

        else:
            # nuke 13
            if nuke.NUKE_VERSION_MAJOR > 12:
                # read from file
                with open(archiveLocation, "rb") as tar:
                    archiveContent = tar.read()

                # convert bytes to text
                encodedArchive = str(base64.b64encode(archiveContent))
                encodedArchive = encodedArchive[2:-1]

            else:
                # read from file
                archiveContent = pathlib.Path(archiveLocation).read_text()
                encodedArchive = base64.b64encode(archiveContent)

            # save to clipboard
            QtWidgets.QApplication.clipboard().setText(encodedArchive)

    def index_archive(
        self, location: Union[str, Path], as_dict: bool = False
    ) -> Union[dict[str, Path], list[Path]]:
        file_list: Union[dict[str, list[Path]], list[Path]] = {} if as_dict else []

        for root in Path(location).resolve().iterdir():
            if root.is_dir():
                level = root.relative_to(location)
                if not any(
                    part.startswith("_") or part.startswith(".") for part in level.parts
                ):
                    new_level = level
                    name = read_name(root / "_name.json")

                    if name:
                        new_level = update_level_with_name(new_level, name)

                    for file in root.iterdir():
                        if not file.name.startswith("."):
                            new_file = process_file_name(file)
                            if as_dict:
                                file_list[(new_level / new_file).as_posix()] = (
                                    level / file
                                )
                            else:
                                file_list.append([level / file, new_level / new_file])

        return file_list

    # def indexArchiveOld(self, location: Path, dict=False):
    #     fileList = {} if dict else []
    #     for item in location.rglob("*"):
    #         if item.name[0] != "_" and item.name[0] != ".":
    #             newLevel = level
    #
    #             if item.name == "_name.json":
    #                 readName = item.read_text(encoding="utf-8")
    #
    #                 if "/" in readName:
    #                     readName = newLevel.replace("/", "**BACKSLASH**")
    #
    #                 newLevel = "/".join(level.split("/")[:-1]) + "/" + readName
    #
    #             if len(item.name) == 6:
    #                 openfile = read_lines(item)
    #                 nametag = "# name: "
    #
    #                 for line in openfile:
    #                     if line.startswith(nametag):
    #                         newfile = line.split(nametag)[-1].replace("\n", "")
    #
    #                         if "/" in newfile:
    #                             newfile = newfile.replace("/", "**backslash**")
    #
    #             if dict:
    #                 filelist[f"{newlevel}/{newfile}"] = f"{level}/{file}"
    #             else:
    #                 filelist.append([f"{level}/{file}", f"{newlevel}/{newfile}"])
    #     return fileList

    # import
    def importHotboxArchive(self):
        """
        A method to import a set of buttons to append the current archive with.
        If you're actually reading this, I apologise in advance for what's coming.
        I had trouble getting the code to work on Windows and it turned out it had to do with
        (back)slashes. I ended up trowing in a lot of ".replace('\\','/')". I works, but it
        turned kinda messy...
        """

        nukeFolder = Path.home() / ".nuke/"
        currentDate = dt.now().strftime("%Y%m%d%H%M")

        archiveLocation = Path(tempfile.mkstemp()[1])

        # - file
        if self.clipboardArchive.isChecked():
            encodedArchive = QtWidgets.QApplication.clipboard().text()
            decodedArchive = base64.b64decode(encodedArchive)

            _res = archiveLocation.write_bytes(decodedArchive)

        else:
            importFileLocation = nuke.getFilename("select to import", "*.hotbox")
            if importFileLocation is not None:
                shutil.copy(importFileLocation, archiveLocation.as_posix())
            else:
                return

        # - extract archive
        importedArchiveLocation = Path(tempfile.mkdtemp())

        # nuke 13
        if nuke.NUKE_VERSION_MAJOR > 12:
            self.extract_tar(archiveLocation, importedArchiveLocation)
        else:
            with tarfile.open(archiveLocation.as_posix()) as archive:

                def is_within_directory(directory, target):
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)

                    prefix = os.path.commonprefix([abs_directory, abs_target])

                    return prefix == abs_directory

                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")

                    tar.extractall(path, members, numeric_owner=numeric_owner)

                safe_extract(archive, importedArchiveLocation.as_posix())

        # Make sure the current archive is healthy
        for i in ["Single", "Multiple", "All"]:
            RepairHotbox(self.rootLocation / i, message=False)

        # Copy stuff from extracted archive to current hotbox location
        importedArchive = self.indexArchive(importedArchiveLocation)
        currentArchive = self.indexArchive(self.rootLocation, dict=True)

        newItems = []
        for i in importedArchive:
            if i.as_posix() in currentArchive.keys():
                # if a file with the same name was found in the same folder, replace it with the new one
                shutil.copy(
                    importedArchiveLocation / i,
                    self.rootLocation / currentArchive[i[1]],
                )
            elif not i.name == "_name.json":
                newItems.append(i)
        newItems = [
            [i[0].replace("\\", "/"), i[1].replace("\\", "/")] for i in newItems
        ]

        # gather information about which folders are already present on disk, and which should be created
        allFoldersNeeded = {
            os.path.dirname(i[1]).replace("\\", "/"): os.path.dirname(i[0]).replace(
                "\\", "/"
            )
            for i in newItems
        }
        allFoldersNeededInverted = {allFoldersNeeded[i]: i for i in allFoldersNeeded}

        for i in allFoldersNeeded:
            if os.path.dirname(i) in allFoldersNeeded.values():
                dirname1 = os.path.dirname(i).replace("\\", "/")
                dirname2 = allFoldersNeededInverted[
                    os.path.dirname(i).replace("\\", "/")
                ]
                if dirname1 != dirname2:
                    newItems = [
                        [i[0], i[1].replace(dirname1, dirname2)] for i in newItems
                    ]

        # properly sort the list
        newItemsDict = {i[0]: i[1] for i in newItems}
        newItemsSorted = sorted([i[0] for i in newItems])
        newItems = [[i, newItemsDict[i]] for i in newItemsSorted]

        # move the rest of the files and create new folders when needed
        for i in newItems:
            i = [i[0].replace("\\", "/"), i[1].replace("\\", "/")]
            prefixFolders = 1 if i[0].startswith("All") else 2
            splitFilePath = i[1].split("/")

            classFolders = "/".join(splitFilePath[:(prefixFolders)])
            baseFolder = self.rootLocation / classFolders
            baseFolder = baseFolder.replace("\\", "/")

            if not os.path.isdir(baseFolder):
                os.mkdir(baseFolder)

            missingFolders = splitFilePath[prefixFolders:-1]
            for folderName in splitFilePath[prefixFolders:-1]:
                # check folders inside existing folder
                for folder in [
                    dir
                    for dir in os.listdir(baseFolder)
                    if len(dir) == 3 and dir[0] not in [".", "_"]
                ]:
                    nameFile = f"{baseFolder}/{folder}/_name.json"

                    if not os.path.exists(nameFile):
                        continue
                    with open(nameFile, encoding="utf-8") as f:
                        name = f.read()
                    if name == folderName:
                        baseFolder = f"{baseFolder}/{folder}"
                        missingFolders = missingFolders[1:]
                        break

                # is the first folder wasn't found, don't bother lookign for its subfolder
                if missingFolders == splitFilePath[prefixFolders:-1]:
                    break

            # create the missing folders and put _name files in them
            for _ in missingFolders:
                currentFiles = [
                    file[:3]
                    for file in os.listdir(baseFolder)
                    if file[0] not in [".", "_"]
                ]
                baseFolder += f"/{str(len(currentFiles) + 1).zfill(3)}"
                os.mkdir(baseFolder)
                shutil.copy(
                    importedArchiveLocation
                    + os.path.dirname(i[0]).replace("\\", "/")
                    + "/_name.json",
                    f"{baseFolder}/_name.json",
                )

            currentFiles = [
                file[:3] for file in os.listdir(baseFolder) if file[0] not in [".", "_"]
            ]
            fileName = f"{str(len(currentFiles) + 1).zfill(3)}.py"
            shutil.copy(f"{importedArchiveLocation}/{i[0]}", f"{baseFolder}/{fileName}")

        # reinitiate
        self.buildClassesList()

    def extract_tar(self, archiveLocation, importedArchiveLocation):
        # nuke 13 crashes when extracting a tar file...
        # therefore we need to run it through a subprocess

        command = [
            "import tarfile",
            f'with tarfile.open("{archiveLocation}") as archive:',
            f'    archive.extractall("{importedArchiveLocation}")',
        ]
        command = "\n".join(command)

        # write to temp file
        module = tempfile.mkstemp()[1]
        with open(module, "w") as moduleFile:
            moduleFile.write(command)

        # execute temp file
        import subprocess

        process = subprocess.Popen(f"python {module}", shell=True)
        process.wait()

    def closeManager(self):
        self.close()
        constants = Constants()
        constants.hotboxManagerInstance = None

    # - open about widget
    def openAboutDialog(self):
        constants = Constants()

        if constants.aboutDialogInstance != None:
            constants.aboutDialogInstance.close()
        constants.aboutDialogInstance = AboutDialog()
        constants.aboutDialogInstance.show()


# - Classes List
class QListWidgetCustom(QtWidgets.QListWidget):
    def __init__(self, hotboxManager):
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
                f"{self.hotboxManager.path}/{fileName}" + "_" * index
                for index in range(2)
            ][:: (checkState - 1)]

            if not os.path.exists(newRulePath):
                os.rename(origRulePath, newRulePath)
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

    def __init__(self, defaultColor):
        super(ColorSwatch, self).__init__()

        self.color = None

        self.enabled = False
        self.active = False

        self.child = None
        self.parent = None

        self.size = 12
        self.setFixedHeight(self.size)
        self.setFixedWidth(self.size)

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
                if self.parent and self.color == self.defaultColor
                else None
            )
            self.setColor(color)

        return True

    def dragEnterEvent(self, e):
        # check if color
        if e.mimeData().hasFormat("application/x-color") and self.enabled:
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
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

    def setColor(self, color=None, adjustChild=True, indirect=False):
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
            and self.parent
            and self.color == self.defaultColorInverted
        ):
            return None

        # if default
        return None if self.color == self.defaultColor else self.color

    def setChild(self, child):
        """ """
        if isinstance(child, ColorSwatch):
            self.child = child
            self.child.parent = self
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
            self.painter.begin(self)
            self.painter.setPen(self.paintPen)
            self.painter.drawLine(self.size - 1, 1, 1, self.size - 1)
            self.painter.end()


# - Tree View
class QTreeViewCustom(QtWidgets.QTreeView):
    def __init__(self, parentClass: HotboxManager):
        super(QTreeViewCustom, self).__init__()

        self.enabled = False

        self.clipboard = []

        self.parentClass = parentClass

        self.header().hide()
        self.expandsOnDoubleClick = True

        self.dataModel = QtGui.QStandardItemModel()
        self.root = self.dataModel.invisibleRootItem()

        self.setModel(self.dataModel)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)

        # to check whether the tree was populated from scratch of updated
        self.scope = ""
        self.previousScope = ""

        # Unfortunatley Nuke 10 crashes on startup when using the following line:
        # self.selectionModel().selectionChanged.connect(self.setSelectedItems)
        # Therefore I had to do this weird construction where the setModel Method is subclassed.

    # --------------------------------------------------------------------------------------------------

    def setModel(self, model):
        super(QTreeViewCustom, self).setModel(model)
        self.connect(
            self.selectionModel(),
            QtCore.SIGNAL("selectionChanged(QItemSelection, QItemSelection)"),
            self.setSelectedItems,
        )

    # --------------------------------------------------------------------------------------------------

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
            self.scope: Path = self.parentClass.path

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

        self.update = self.previousScope == self.scope
        if self.update:
            # find currently collapsed menus
            self.collapsedMenus = []

            for button in self.buttonsList.values():
                index = self.dataModel.indexFromItem(button)

                if not self.isExpanded(index):
                    self.collapsedMenus.append(button.path)

        # reset buttons list (all items will be replaced with new items when rebuilding anyway)
        self.buttonsList: dict[str, QtWidgets.QWidget] = {}
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
        if self.update:
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

    def addChild(self, parent, path: Path):
        """
        Loop through folder structure and add items on the fly
        """

        for i in sorted(path.iterdir()):
            if i.name[0] not in ["_", "."]:
                name = getAttributeFromFile(i)
                if not name:
                    return

                child = QStandardItemChild(name, str(i))
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

        sourceFolder = Path(self.currentItem.path).parent
        sourceFile = Path(self.currentItem.path).name

        destinationFolder = Path(self.nextItem.path).parent
        destinationFile = Path(self.nextItem.path).name

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
            button.path = updatedPath

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
    def __init__(self, name, path):
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
        if os.path.isdir(self.path):
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


# - Top portion of the files that will be generated
class FileHeader:
    def __init__(
        self,
        name: str,
        color: Optional[str] = None,
        textColor: Optional[str] = None,
        rule: bool = False,
    ):
        super().__init__()
        dividerLine = "-" * 106

        text = [
            f"#{dividerLine}",
            "#",
            "# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX",
            "#",
            f"# NAME: {name}",
            "#",
            f"#{dividerLine}\n\n",
        ]

        if rule:
            text[4] = text[4].replace("# NAME:", "# IGNORE CLASSES:")

        # add extra attributes if available
        if textColor:
            text.insert(5, f"# TEXTCOLOR: {textColor}")
        if color:
            text.insert(5, f"# COLOR: {color}")

        self.text = "\n".join(text)

    def getHeader(self):
        return self.text


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


def clearHotboxManager(sections: Optional[list[str]] = None):
    """
    Clear the buttons of the section specified. By default all buttons will be erased.
    """

    if sections is None:
        sections = ["Single", "Multiple", "All", "Rules"]
    message = "This will erase all of the excisting buttons added to the hotbox. This action can't be undone.\n\nAre you sure?"
    if len(sections) == 1:
        message = (
            "This will erase all of the buttons added to the '%s'-section of the hotbox. This can't be undone.\n\nAre you sure?"
            % sections[0]
        )

    if not nuke.ask(message):
        return

    hotboxLocation = getHotBoxLocation()

    clearProgressBar = nuke.ProgressTask("Clearing ..")

    clearProgressIncrement = 100 / (len(sections) * 2)
    clearProgress = 0.0
    clearProgressBar.setProgress(int(clearProgress))

    # Empty folders
    for i in sections:
        clearProgress += clearProgressIncrement
        clearProgressBar.setProgress(int(clearProgress))
        clearProgressBar.setMessage(f"Clearing {i}")

        with contextlib.suppress(Exception):
            shutil.rmtree(hotboxLocation + i)

    # Rebuild folders
    for i in sections:
        clearProgress += clearProgressIncrement
        clearProgressBar.setProgress(int(clearProgress))
        clearProgressBar.setMessage(f"Rebuilding {i}")

        with contextlib.suppress(Exception):
            os.mkdir(hotboxLocation + i)


# hotboxManagerInstance = None
# renameDialogInstance = None
# aboutDialogInstance = None


def showHotboxManager(path=""):
    """
    Launch an instance of the hotbox manager
    """
    constants = Constants()

    # check if the manager is opened already, if so close that instance.
    if constants.hotboxManagerInstance != None:
        constants.hotboxManagerInstance.close()

    path = getHotBoxLocation(path)

    constants.hotboxManagerInstance = HotboxManager(path)
    constants.hotboxManagerInstance.show()
