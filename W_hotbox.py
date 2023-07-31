# ----------------------------------------------------------------------------------------------------------
# Wouter Gilsing
# woutergilsing@hotmail.com


# - modules
import nuke

from W_hotbox_utils import (
    getHotBoxLocation,
    operatingSystem,
    preferencesNode,
    version,
    releaseDate,
    getFileBrowser,
    interface2rgb,
    getTileColor,
    rgb2hex,
    getSelectionColor,
    revealInBrowser,
    updatePreferences,
    homeFolder,
    Constants,
)
from M_Log import mklog

log = mklog("W_hotbox")

from PySide2 import QtGui, QtCore, QtWidgets

import os
import traceback
import colorsys
import contextlib

import W_hotboxManager
from W_hotbox_utils import addPreferences


class Hotbox(QtWidgets.QWidget):
    """
    The main class for the hotbox
    """

    def __init__(self, subMenuMode=False, path="", name="", position=""):
        super(Hotbox, self).__init__()
        log.debug("Initializing Hotbox class")

        self.active = True
        self.activeButton = None

        self.triggerMode = preferencesNode.knob("hotboxTriggerDropdown").getValue()

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        )

        self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # enable transparency on Linux
        if (
            operatingSystem not in ["Darwin", "Windows"]
            and nuke.NUKE_VERSION_MAJOR < 11
        ):
            self.setAttribute(QtCore.Qt.WA_PaintOnScreen)

        masterLayout = QtWidgets.QVBoxLayout()
        self.setLayout(masterLayout)

        # - context
        self.selection = nuke.selectedNodes()

        # check whether selection in group
        self.groupRoot = "root"

        if self.selection:
            nodeRoot = self.selection[0].fullName()
            if nodeRoot.count("."):
                self.groupRoot = ".".join([self.groupRoot] + nodeRoot.split(".")[:-1])

        # - main hotbox
        if not subMenuMode:
            self.mode = "Single"

            if (
                len(self.selection) > 1
                and len(list({node.Class() for node in nuke.selectedNodes()})) > 1
            ):
                self.mode = "Multiple"

            # Layouts
            centerLayout = QtWidgets.QHBoxLayout()
            centerLayout.addStretch()
            centerLayout.addWidget(
                HotboxButton(f"Reveal in {getFileBrowser()}", "revealInBrowser()")
            )
            centerLayout.addSpacing(25)
            centerLayout.addWidget(HotboxCenter())
            centerLayout.addSpacing(25)
            centerLayout.addWidget(
                HotboxButton("Hotbox Manager", "showHotboxManager()")
            )
            centerLayout.addStretch()

            self.topLayout = NodeButtons()
            self.bottomLayout = NodeButtons("bottom")

            spacing = 12

        else:
            allItems = [
                f"{path}/{i}"
                for i in sorted(os.listdir(path))
                if i[0] not in [".", "_"]
            ]

            centerItems = allItems[:2]

            lists = [[], []]
            for index, item in enumerate(allItems[2:]):
                if int((index % 4) // 2):
                    lists[index % 2].append(item)
                else:
                    lists[index % 2].insert(0, item)

            # Stretch layout
            centerLayout = QtWidgets.QHBoxLayout()

            centerLayout.addStretch()
            for index, item in enumerate(centerItems):
                centerLayout.addWidget(HotboxButton(item))
                if index == 0:
                    centerLayout.addWidget(HotboxCenter(False, path))

            if len(centerItems) == 1:
                centerLayout.addSpacing(105)

            centerLayout.addStretch()

            self.topLayout = NodeButtons("SubMenuTop", lists[0])
            self.bottomLayout = NodeButtons("SubMenuBottom", lists[1])

            spacing = 0

        # - Equalize layouts to make sure the center layout is the center of the hotbox
        difference = self.topLayout.count() - self.bottomLayout.count()

        if difference != 0:
            extraLayout = QtWidgets.QVBoxLayout()

            for _ in range(abs(difference)):
                extraLayout.addSpacing(35)

            if difference > 0:
                self.bottomLayout.addLayout(extraLayout)
            else:
                self.topLayout.insertLayout(0, extraLayout)

        masterLayout.addLayout(self.topLayout)
        masterLayout.addSpacing(spacing)
        masterLayout.addLayout(centerLayout)
        masterLayout.addSpacing(spacing)
        masterLayout.addLayout(self.bottomLayout)

        # position
        self.adjustSize()

        self.spwanPosition = QtGui.QCursor().pos() - QtCore.QPoint(
            (self.width() // 2), (self.height() // 2)
        )

        # set last position if a fresh instance of the hotbox is launched
        constants = Constants()
        if position == "" and not subMenuMode:
            constants.lastPosition = self.spwanPosition

        if subMenuMode:
            self.move(self.spwanPosition)

        else:
            self.move(constants.lastPosition)

        # make sure the widgets closes when it loses focus
        self.installEventFilter(self)

    def closeHotbox(self, hotkey=False):
        # if the execute on close function is turned on, the hotbox will execute the selected button upon close

        if hotkey and (
            preferencesNode.knob("hotboxExecuteOnClose").value()
            and self.activeButton != None
        ):
            self.activeButton.invokeButton()
            self.activeButton = None

        self.active = False
        self.close()

    def keyReleaseEvent(self, event):
        constants = Constants()
        if event.isAutoRepeat():
            return False
        if event.text() == constants.shortcut:
            constants.lastPosition = ""

            # if set to single tap, leave the hotbox open after launching, else close it.
            if not self.triggerMode:
                self.closeHotbox(hotkey=True)

            return True

    def keyPressEvent(self, event):
        constants = Constants()

        if event.text() != constants.shortcut:
            return False
        if event.isAutoRepeat():
            return False

        # if launch mode is set to 'Single Tap' close the hotbox.
        if self.triggerMode:
            self.closeHotbox(hotkey=True)

    def eventFilter(self, object, event):
        if event.type() in [QtCore.QEvent.WindowDeactivate, QtCore.QEvent.FocusOut]:
            self.closeHotbox()
            return True
        return False


# - Button field


class NodeButtons(QtWidgets.QVBoxLayout):
    """
    Create QLayout filled with buttons
    """

    def __init__(self, mode="", allItems=""):
        super(NodeButtons, self).__init__()

        selectedNodes = nuke.selectedNodes()

        # - submenu
        if "submenu" in mode.lower():
            self.rowMaxAmount = 3
            mirrored = "top" not in mode.lower()

        else:
            mirrored = True
            mode = mode == "bottom"

            if preferencesNode.knob("hotboxMirroredLayout").value():
                mode = 1 - mode
                mirrored = 1 - mirrored

            self.path = getHotBoxLocation()

            self.allRepositories = list(
                set([self.path] + [i[1] for i in extraRepositories])
            )

            self.rowMaxAmount = int(preferencesNode.knob("hotboxRowAmountAll").value())

            self.folderList = []

            # - noncontextual

            if mode:
                self.folderList += [
                    f"{repository}All" for repository in self.allRepositories
                ]

            else:
                mirrored = 1 - mirrored

                self.rowMaxAmount = int(
                    preferencesNode.knob("hotboxRowAmountSelection").value()
                )

                # - rules
                # collect all folders storing buttons for applicable rules

                ignoreClasses = False
                tag = "# IGNORE CLASSES: "

                allRulePaths = []

                for repository in self.allRepositories:
                    rulesFolder = f"{repository}Rules"
                    if not os.path.exists(rulesFolder):
                        continue

                    rules = [
                        "/".join([rulesFolder, rule])
                        for rule in os.listdir(rulesFolder)
                        if rule[0] not in ["_", "."] and rule[-1] != "_"
                    ]

                    # validate rules
                    for rule in rules:
                        log.debug(f"Validating rules: {rule}")

                        ruleFile = f"{rule}/_rule.py"

                        if os.path.exists(ruleFile) and self.validateRule(ruleFile):
                            allRulePaths.append(rule)

                            # read ruleFile to check if ignoreClasses was enabled.
                            if not ignoreClasses:
                                with open(ruleFile, encoding="utf-8") as f:
                                    for line in f:
                                        # no point in checking boyond the header
                                        if not line.startswith("#"):
                                            break
                                        # if proper tag is found, check its value
                                        if line.startswith(tag):
                                            ignoreClasses = bool(
                                                int(
                                                    line.split(tag)[-1].replace(
                                                        "\n", ""
                                                    )
                                                )
                                            )
                                            break

                # - classes
                # collect all folders storing buttons for applicable classes

                if not ignoreClasses:
                    allClassPaths = []

                    nodeClasses = list({node.Class() for node in selectedNodes})

                    # if nothing selected
                    if not nodeClasses:
                        nodeClasses = ["No Selection"]

                    else:
                        # check if group, if so take the name of the group, as well as the class
                        groupNodes = []
                        if "Group" in nodeClasses:
                            for node in selectedNodes:
                                if node.Class() == "Group":
                                    groupName = node.name()
                                    while groupName[-1] in [str(i) for i in range(10)]:
                                        groupName = groupName[:-1]
                                    if (
                                        groupName not in groupNodes
                                        and groupName != "Group"
                                    ):
                                        groupNodes.append(groupName)

                        if groupNodes:
                            groupNodes = [
                                nodeClass
                                for nodeClass in nodeClasses
                                if nodeClass != "Group"
                            ] + groupNodes

                        if len(nodeClasses) > 1:
                            nodeClasses = [nodeClasses]
                        if len(groupNodes) > 1:
                            groupNodes = [groupNodes]

                        nodeClasses += groupNodes

                    # Check which defined class combinations on disk are applicable to the current selection.
                    for repository in self.allRepositories:
                        for nodeClass in nodeClasses:
                            if isinstance(nodeClass, list):
                                for managerNodeClasses in [
                                    i
                                    for i in os.listdir(f"{repository}Multiple")
                                    if i[0] not in ["_", "."]
                                ]:
                                    managerNodeClassesList = managerNodeClasses.split(
                                        "-"
                                    )
                                    match = list(
                                        set(nodeClass).intersection(
                                            managerNodeClassesList
                                        )
                                    )

                                    if len(match) >= len(nodeClass):
                                        allClassPaths.append(
                                            f"{repository}Multiple/{managerNodeClasses}"
                                        )
                            else:
                                allClassPaths.append(f"{repository}Single/{nodeClass}")

                    allClassPaths = list(set(allClassPaths))
                    allClassPaths = [
                        path for path in allClassPaths if os.path.exists(path)
                    ]

                # - combine classes and rules
                if ignoreClasses:
                    self.folderList = allRulePaths

                else:
                    self.folderList = allClassPaths + allRulePaths

                    if preferencesNode.knob("hotboxRuleClassOrder").getValue():
                        self.folderList.reverse()

            # - files on disk representing items
            allItems = []

            for folder in self.folderList:
                allItems.extend(
                    "/".join([folder, file])
                    for file in sorted(os.listdir(folder))
                    if file[0] not in [".", "_"] and len(file) in {3, 6}
                )
        row = []

        allRows = []
        for item in allItems:
            if preferencesNode.knob("hotboxButtonSpawnMode").value():
                if len(row) % 2:
                    row.append(item)
                else:
                    row.insert(0, item)
            else:
                row.append(item)

            # when a row reaches its full capacity, add the row to the allRows list
            # and start a new one. Increase rowcapacity to get a triangular shape
            if len(row) == self.rowMaxAmount:
                allRows.append(row)
                row = []
                self.rowMaxAmount += preferencesNode.knob("hotboxRowStepSize").value()

        # if the last row is not completely full, add it to the allRows list anyway
        if len(row) != 0:
            allRows.append(row)

        if not mirrored:
            allRows.reverse()

        # nodeHotboxLayout
        for row in allRows:
            self.rowLayout = QtWidgets.QHBoxLayout()

            self.rowLayout.addStretch()

            for button in row:
                buttonObject = HotboxButton(button)
                self.rowLayout.addWidget(buttonObject)
            self.rowLayout.addStretch()

            self.addLayout(self.rowLayout)

        self.rowAmount = len(allRows)

    def validateRule(self, ruleFile):
        """
        Run the rule, return True or False.
        """

        log.debug(f"Validation the rule from {ruleFile}")

        error = False

        # read from file
        with open(ruleFile, encoding="utf-8") as rule:
            ruleString = rule.read()

        # quick sanity check
        if "ret=" not in ruleString.replace(" ", ""):
            error = "RuleError: rule must contain variable named 'ret'"

        else:
            # prepend the rulestring with a nuke import statement and make it return False by default
            prefix = "import nuke\nret = False\n"
            ruleString = prefix + ruleString

            # run rule
            try:
                scope = {}
                log.debug(ruleString)
                exec(ruleString, scope, scope)

                if "ret" in scope:
                    result = bool(scope["ret"])

            except Exception as e:
                error = traceback.format_exc()
                log.error(error)
                log.error(e)

        # run error
        if error:
            printError(
                error, buttonName=os.path.basename(os.path.dirname(ruleFile)), rule=True
            )
            result = False

        # return the result of the rule
        return result


class HotboxCenter(QtWidgets.QLabel):
    """
    Center button of the hotbox.
    If the 'color nodes' is set to True in the preferences panel, the button will take over the color and
    name of the current selection. If not, the button will be the same color as the other buttons will
    be in their selected state. The text will be read from the _name.json file in the folder.
    """

    def __init__(self, node=True, name=""):
        super(HotboxCenter, self).__init__()

        self.node = node

        nodeColor = "#525252"
        textColor = "#eeeeee"

        selectedNodes = nuke.selectedNodes()

        if node:
            # if no node selected
            if len(selectedNodes) == 0:
                name = "W_hotbox"
                nodeColorRGB = interface2rgb(640034559)

            # if node(s) selected
            else:
                name = nuke.selectedNode().name()
                nodeColorRGB = interface2rgb(getTileColor())

            if preferencesNode.knob("hotboxColorCenter").value():
                nodeColor = rgb2hex(nodeColorRGB)

                nodeColorHSV = colorsys.rgb_to_hsv(
                    nodeColorRGB[0], nodeColorRGB[1], nodeColorRGB[2]
                )

                if nodeColorHSV[2] > 0.7 and nodeColorHSV[1] < 0.4:
                    textColor = "#262626"

            width = 115
            height = 60

            if len({i.Class() for i in selectedNodes}) > 1:
                name = "Selection"

        else:
            with open(f"{name}/_name.json", encoding="utf-8") as nameFile:
                name = nameFile.read()

            nodeColor = getSelectionColor()

            width = 105
            height = 35

        self.setText(name)

        self.setAlignment(QtCore.Qt.AlignCenter)

        self.setFixedWidth(width)
        self.setFixedHeight(height)

        # resize font based on length of name
        fontSize = int(max(5, (13 - (max(0, (len(name) - 11)) / 2))))
        font = QtGui.QFont(preferencesNode.knob("UIFont").value(), fontSize)
        self.setFont(font)

        self.setStyleSheet(
            """
                border: 1px solid black;
                color:%s;
                background:%s"""
            % (textColor, nodeColor)
        )

        self.setSelectionStatus(True)

    def setSelectionStatus(self, selected=False):
        """
        Define the style of the button for different states
        """
        if not self.node:
            self.selected = selected

    def enterEvent(self, event):
        """
        Change color of the button when the mouse starts hovering over it
        """
        if not self.node:
            self.setSelectionStatus(True)
        return True

    def leaveEvent(self, event):
        """
        Change color of the button when the mouse starts hovering over it
        """
        if not self.node:
            self.setSelectionStatus()
        return True

    def mouseReleaseEvent(self, event):
        """ """
        if not self.node:
            showHotbox(True, resetPosition=False)
        return True


# - Buttons
class HotboxButton(QtWidgets.QLabel):
    """
    Button class
    """

    def __init__(self, name, function=None):
        super(HotboxButton, self).__init__()

        self.menuButton = False
        self.filePath = name
        self.bgColor = "#525252"

        self.borderColor = "#000000"

        # set the border color to grey for buttons from an additional repository
        for i in extraRepositories:
            if name.startswith(i[1]):
                self.borderColor = "#959595"
                break

        if function != None:
            self.function = function

        elif os.path.isdir(self.filePath):
            self.menuButton = True
            with open(f"{self.filePath}/_name.json", encoding="utf-8") as f:
                name = f.read()
            self.function = f'showHotboxSubMenu(r"{self.filePath}","{name}")'
            self.bgColor = "#333333"

        else:
            with open(name, encoding="utf-8") as f:
                self.openFile = f.readlines()

            header = []
            for index, line in enumerate(self.openFile):
                if not line.startswith("#"):
                    self.function = "".join(self.openFile[index:])
                    break

                header.append(line)

            tags = [f"# {tag}: " for tag in ["NAME", "TEXTCOLOR", "COLOR"]]

            tagResults = []

            for tag in tags:
                tagResult = next(
                    (
                        line.split(tag)[-1].replace("\n", "")
                        for line in header
                        if line.startswith(tag)
                    ),
                    None,
                )
                tagResults.append(tagResult)

            name, textColor, color = tagResults

            if textColor and name:
                name = f'<font color = "{textColor}">{name}</font>'

            if color:
                self.bgColor = color

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMouseTracking(True)
        self.setFixedWidth(105)
        self.setFixedHeight(35)

        fontSize = preferencesNode.knob("hotboxFontSize").value()
        font = QtGui.QFont(
            preferencesNode.knob("UIFont").value(), fontSize, QtGui.QFont.Bold
        )

        self.setFont(font)
        self.setWordWrap(True)
        self.setTextFormat(QtCore.Qt.RichText)

        self.setText(name)

        self.setAlignment(QtCore.Qt.AlignCenter)

        self.selected = False
        self.setSelectionStatus()

    def invokeButton(self):
        """
        Execute script attached to button
        """
        constants = Constants()
        with nuke.toNode(constants.hotboxInstance.groupRoot):
            try:
                log.debug(self.function)
                scope = globals().copy()
                exec(self.function, scope, scope)

            except Exception:
                printError(traceback.format_exc(), self.filePath, self.text())

        # if 'close on click' is ticked, close the hotbox
        if not self.menuButton and (
            preferencesNode.knob("hotboxCloseOnClick").value()
            and preferencesNode.knob("hotboxTriggerDropdown").getValue()
        ):
            constants.hotboxInstance.closeHotbox()

    def setSelectionStatus(self, selected=False):
        """
        Define the style of the button for different states
        """
        constants = Constants()

        # if button becomes selected
        if selected:
            self.setStyleSheet(
                """
                                border: 1px solid black;
                                background:%s;
                                color:#eeeeee;
                                """
                % getSelectionColor()
            )

        # if button becomes unselected
        else:
            self.setStyleSheet(
                """
                                border: 1px solid %s;
                                background:%s;
                                color:#eeeeee;
                                """
                % (self.borderColor, self.bgColor)
            )

        if (
            preferencesNode.knob("hotboxExecuteOnClose").value()
            and constants.hotboxInstance != None
        ):
            constants.hotboxInstance.activeButton = None

            # if launch mode set to Press and Hold and the button is a menu button,
            # dont open a submenu upon shortcut release

            if (
                not self.menuButton
                and not preferencesNode.knob("hotboxTriggerDropdown").getValue()
            ) and selected:
                constants.hotboxInstance.activeButton = self

        self.selected = selected

    def enterEvent(self, event):
        """
        Change color of the button when the mouse starts hovering over it
        """
        self.setSelectionStatus(True)
        return True

    def leaveEvent(self, event):
        """
        Change color of the button when the mouse stops hovering over it
        """
        self.setSelectionStatus()
        return True

    def mouseReleaseEvent(self, event):
        """
        Execute the buttons' self.function (str)
        """
        if self.selected:
            nuke.Undo().name(self.text())
            nuke.Undo().begin()

            self.invokeButton()

            nuke.Undo().end()

        return True


# - error catching
def printError(error, path="", buttonName="", rule=False):
    """
    Format error message and print it to the scripteditor and shell.
    """

    fullError = error.splitlines()

    buttonName = [buttonName]

    # line number
    lineNumber = ""
    for index, line in enumerate(reversed(fullError)):
        if line.startswith('  File "<'):
            for i in line.split(","):
                if i.startswith(" line "):
                    lineNumber = i

            index = len(fullError) - index
            break

    lineNumber = f" -{lineNumber}" * bool(lineNumber)

    fullError = fullError[index:]
    errorDescription = "\n".join(fullError)

    # button
    if not rule:
        scriptFolder = os.path.dirname(path)
        scriptFolderName = os.path.basename(scriptFolder)

        while len(scriptFolderName) == 3 and scriptFolderName.isdigit():
            name = open(f"{scriptFolder}/_name.json").read()
            buttonName.insert(0, name)
            scriptFolder = os.path.dirname(scriptFolder)
            scriptFolderName = os.path.basename(scriptFolder)

        for _ in range(2):
            buttonName.insert(0, os.path.basename(scriptFolder))
            scriptFolder = os.path.dirname(scriptFolder)

    # buttonName = [buttonName]

    hotboxError = "\nW_HOTBOX %sERROR: %s%s:\n%s" % (
        "RULE " * int(bool(rule)),
        "/".join(buttonName),
        lineNumber,
        errorDescription,
    )

    # print error
    print(hotboxError)
    nuke.tprint(hotboxError)


# - launch hotbox


def showHotbox(force=False, resetPosition=True):
    constants = Constants()

    # is launch mode is set to single tap, close the hotbox if it's open
    if (
        preferencesNode.knob("hotboxTriggerDropdown").getValue()
        and not force
        and (constants.hotboxInstance != None and constants.hotboxInstance.active)
    ):
        constants.hotboxInstance.closeHotbox(hotkey=True)
        return

    if force:
        constants.hotboxInstance.active = False
        constants.hotboxInstance.close()

    if resetPosition:
        constants.lastPosition = ""

    if constants.hotboxInstance is None or not constants.hotboxInstance.active:
        constants.hotboxInstance = Hotbox(position=constants.lastPosition)
        constants.hotboxInstance.show()


def showHotboxSubMenu(path, name):
    constants = Constants()
    constants.hotboxInstance.active = False
    if constants.hotboxInstance is None or not constants.hotboxInstance.active:
        constants.hotboxInstance = Hotbox(True, path, name)
        constants.hotboxInstance.show()


def showHotboxManager():
    """
    Open the hotbox manager from the hotbox
    """
    constants = Constants()

    constants.hotboxInstance.closeHotbox()
    W_hotboxManager.showHotboxManager()


# - menu items
def addMenuItems():
    """
    Add items to the Nuke menu
    """
    constants = Constants()
    editMenu.addCommand("W_hotbox/Open W_hotbox", showHotbox, constants.shortcut)
    editMenu.addCommand("W_hotbox/-", "", "")
    editMenu.addCommand(
        "W_hotbox/Open Hotbox Manager", "W_hotboxManager.showHotboxManager()"
    )
    editMenu.addCommand(f"W_hotbox/Open in {getFileBrowser()}", revealInBrowser)
    editMenu.addCommand("W_hotbox/-", "", "")
    editMenu.addCommand("W_hotbox/Repair", "W_hotboxManager.repairHotbox()")
    editMenu.addCommand(
        "W_hotbox/Clear/Clear Everything", "W_hotboxManager.clearHotboxManager()"
    )
    editMenu.addCommand(
        "W_hotbox/Clear/Clear Section/Single",
        'W_hotboxManager.clearHotboxManager(["Single"])',
    )
    editMenu.addCommand(
        "W_hotbox/Clear/Clear Section/Multiple",
        'W_hotboxManager.clearHotboxManager(["Multiple"])',
    )
    editMenu.addCommand(
        "W_hotbox/Clear/Clear Section/All",
        'W_hotboxManager.clearHotboxManager(["All"])',
    )
    editMenu.addCommand("W_hotbox/Clear/Clear Section/-", "", "")
    editMenu.addCommand(
        "W_hotbox/Clear/Clear Section/Templates",
        'W_hotboxManager.clearHotboxManager(["Templates"])',
    )


def resetMenuItems():
    """
    Remove and read all items to the Nuke menu. Used to change the shotcut
    """

    constants = Constants()
    constants.shortcut = preferencesNode.knob("hotboxShortcut").value()

    if editMenu.findItem("W_hotbox"):
        editMenu.removeItem("W_hotbox")

    addMenuItems()


# add knobs to preferences


updatePreferences()
addPreferences()

# make sure the archive folders are present, if not, create them
hotboxLocationPathKnob = preferencesNode.knob("hotboxLocation")
hotboxLocationPath = getHotBoxLocation()

if not hotboxLocationPath:
    hotboxLocationPath = f"{homeFolder}/W_hotbox"
    hotboxLocationPathKnob.setValue(hotboxLocationPath)

if hotboxLocationPath[-1] != "/":
    hotboxLocationPath += "/"

for subFolder in [
    "",
    "Single",
    "Multiple",
    "All",
    "Rules",
    "Single/No Selection",
    "Templates",
]:
    subFolderPath = hotboxLocationPath + subFolder
    if not os.path.isdir(subFolderPath):
        with contextlib.suppress(Exception):
            os.makedirs(subFolderPath)

# menu items
editMenu = nuke.menu("Nuke").findItem("Edit")
editMenu.addCommand("-", "", "")
addMenuItems()

# EXTRA REPOSTITORIES
"""
Add them like this:

W_HOTBOX_REPO_PATHS=/path1:/path2:/path3
W_HOTBOX_REPO_NAMES=name1:name2:name3

"""

extraRepositories = []

if "W_HOTBOX_REPO_PATHS" in os.environ and "W_HOTBOX_REPO_NAMES" in os.environ:
    extraRepositoriesPaths = os.environ["W_HOTBOX_REPO_PATHS"].split(os.pathsep)
    extraRepositoriesNames = os.environ["W_HOTBOX_REPO_NAMES"].split(os.pathsep)

    for index, i in enumerate(
        range(min(len(extraRepositoriesPaths), len(extraRepositoriesNames)))
    ):
        path = extraRepositoriesPaths[index].replace("\\", "/")

        # make sure last character is a '/'
        if path[-1] != "/":
            path += "/"

        name = extraRepositoriesNames[index]
        if name not in [i[0] for i in extraRepositories] and path not in [
            i[1] for i in extraRepositories
        ]:
            extraRepositories.append([name, path])

    if extraRepositories:
        editMenu.addCommand("W_hotbox/-", "", "")
        for repo in extraRepositories:
            editMenu.addCommand(
                f"W_hotbox/Special/Open Hotbox Manager - {repo[0]}",
                f'W_hotboxManager.showHotboxManager(path="{repo[1]}")',
            )


nuke.tprint(
    f"W_hotbox v{version}, built {releaseDate}.\nCopyright (c) 2016-{releaseDate.split()[-1]} Wouter Gilsing. All Rights Reserved."
)
