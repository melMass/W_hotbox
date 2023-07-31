#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import nuke
import os
import platform
import contextlib
import subprocess

# region constants

# - true constants
version = "1.9"
releaseDate = "March 28 2021"
preferencesNode = nuke.toNode("preferences")
operatingSystem = platform.system()
homeFolder = os.getenv("HOME").replace("\\", "/") + "/.nuke"


# - mutable constant singleton
class Constants:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Constants, cls).__new__(cls)
            cls._instance.init_singleton()
        return cls._instance

    def init_singleton(self):
        self.hotboxInstance = None
        self.hotboxManagerInstance = None
        self.aboutDialogInstance = None
        self.renameDialogInstance = None
        self.lastPosition = ""
        self.shortcut = None

    def some_singleton_method(self):
        # Implement the methods of the singleton class here
        pass


# endregion

# region preferences


def addToPreferences(knobObject, tooltip=None):
    """
    Add a knob to the preference panel.
    Save current preferences to the prefencesfile in the .nuke folder.
    """

    if knobObject.name() not in preferencesNode.knobs().keys():
        if tooltip != None:
            knobObject.setTooltip(tooltip)

        preferencesNode.addKnob(knobObject)
        savePreferencesToFile()
        return preferencesNode.knob(knobObject.name())


def savePreferencesToFile():
    """
    Save current preferences to the prefencesfile in the .nuke folder.
    Pythonic alternative to the 'ok' button of the preferences panel.
    """

    nukeFolder = os.path.expanduser("~") + "/.nuke/"
    preferencesFile = (
        f"{nukeFolder}preferences{nuke.NUKE_VERSION_MAJOR}.{nuke.NUKE_VERSION_MINOR}.nk"
    )

    preferencesNode = nuke.toNode("preferences")

    customPrefences = preferencesNode.writeKnobs(
        nuke.WRITE_USER_KNOB_DEFS
        | nuke.WRITE_NON_DEFAULT_ONLY
        | nuke.TO_SCRIPT
        | nuke.TO_VALUE
    )
    customPrefences = customPrefences.replace("\n", "\n  ")

    preferencesCode = (
        "Preferences {\n inputs 0\n name Preferences%s\n}" % customPrefences
    )
    # write to file
    with open(preferencesFile, "wb") as f:
        f.write(preferencesCode.encode("utf-8"))


def deletePreferences():
    """
    Delete all the W_hotbox related items in the properties panel.
    """

    firstLaunch = True
    for i in preferencesNode.knobs().keys():
        if "hotbox" in i:
            preferencesNode.removeKnob(preferencesNode.knob(i))
            firstLaunch = False

    # remove TabKnob
    with contextlib.suppress(Exception):
        preferencesNode.removeKnob(preferencesNode.knob("hotboxLabel"))

    if not firstLaunch:
        savePreferencesToFile()


def updatePreferences():
    """
    Check whether the hotbox was updated since the last launch. If so refresh the preferences.
    """

    allKnobs = preferencesNode.knobs().keys()

    # Older versions of the hotbox had a knob called 'iconLocation'.
    # This was a mistake and the knob was supposed to be called
    #'hotboxIconLocation', similar to the rest of the knobs.

    forceUpdate = False

    # if "iconLocation" in allKnobs and "hotboxIconLocation" not in allKnobs:
    #     forceUpdate = fix_old_icon_location()
    allKnobs = preferencesNode.knobs().keys()
    proceedUpdate = True

    if "hotboxVersion" in allKnobs:
        if not forceUpdate:
            try:
                if float(version) == float(
                    preferencesNode.knob("hotboxVersion").value()
                ):
                    proceedUpdate = False
            except Exception:
                proceedUpdate = True

        if proceedUpdate:
            resetPreferences(allKnobs)
    elif forceUpdate:
        if proceedUpdate:
            resetPreferences(allKnobs)
    # nuke 12.2v4 and 13 bug. The last tab wont be shown. Workaround is to add an extra tab
    customTabs = [
        k.name()
        for k in preferencesNode.knobs().values()
        if isinstance(k, nuke.Tab_Knob)
    ]
    if customTabs and customTabs[-1] == "hotboxLabel":
        # make new tab and hide it
        dummyTab = nuke.Tab_Knob("hotboxDummyTab", "Dummy")
        dummyTab.setFlag(0x00040000)

        addToPreferences(dummyTab)


def resetPreferences(allKnobs):
    currentSettings = {
        knob: preferencesNode.knob(knob).value()
        for knob in allKnobs
        if knob.startswith("hotbox") and knob != "hotboxVersion"
    }

    # delete all the preferences
    deletePreferences()

    # re-add all the knobs
    addPreferences()

    # restore
    for knob, value in currentSettings.items():
        with contextlib.suppress(Exception):
            preferencesNode.knob(knob).setValue(value)

    # save to file
    savePreferencesToFile()


# def fix_old_icon_location():
#     currentSetting = preferencesNode.knob("iconLocation").value()

#     # delete 'iconLocation'
#     preferencesNode.removeKnob(preferencesNode.knob("iconLocation"))

#     # re-add 'hotboxIconLocation'
#     iconLocationKnob = nuke.File_Knob("hotboxIconLocation", "Icons location")
#     iconLocationKnob.setValue(currentSetting)
#     addToPreferences(iconLocationKnob)

#     return True


def addPrefKnob(knob, tooltip, new_line=False):
    if new_line:
        knob.clearFlag(nuke.STARTLINE)
    addToPreferences(knob, tooltip)

    return tooltip


def addPreferences():
    """
    Add knobs to the preferences needed for this module to work properly.
    """
    constants = Constants()

    addToPreferences(nuke.Tab_Knob("hotboxLabel", "W_hotbox"))
    addToPreferences(nuke.Text_Knob("hotboxGeneralLabel", "<b>General</b>"))

    # - version knob to check whether the hotbox was updated
    knob = nuke.String_Knob("hotboxVersion", "version")
    knob.setValue(version)
    addToPreferences(knob)
    preferencesNode.knob("hotboxVersion").setVisible(False)

    # - location knob
    knob = nuke.File_Knob("hotboxLocation", "Hotbox location")

    addPrefKnob(
        knob,
        "The folder on disk the Hotbox uses to store the Hotbox buttons. Make sure this path links to the folder containing the 'All','Single' and 'Multiple' folders.",
    )

    # - icons knob
    knob = nuke.File_Knob("hotboxIconLocation", "Icons location")
    knob.setValue(f"{homeFolder}/icons/W_hotbox")

    addPrefKnob(
        knob,
        "The folder on disk the where the Hotbox related icons are stored. Make sure this path links to the folder containing the PNG files.",
    )

    # - open manager button
    knob = nuke.PyScript_Knob(
        "hotboxOpenManager",
        "open hotbox manager",
        "W_hotboxManager.showHotboxManager()",
    )
    addPrefKnob(knob, "Open the Hotbox Manager.", True)

    # - open in file system button knob
    knob = nuke.PyScript_Knob(
        "hotboxOpenFolder", "open hotbox folder", "W_hotbox_utils.revealInBrowser(True)"
    )
    addPrefKnob(
        knob, "Open the folder containing the files that store the Hotbox buttons."
    )

    # - delete preferences button knob
    knob = nuke.PyScript_Knob(
        "hotboxDeletePreferences",
        "delete preferences",
        "W_hotbox_utils.deletePreferences()",
    )

    addPrefKnob(
        knob,
        "Delete all the Hotbox related knobs from the Preferences Panel. After clicking this button the Preferences Panel should be closed by clicking the 'cancel' button.",
    )

    # Launch Label knob
    addToPreferences(nuke.Text_Knob("hotboxLaunchLabel", "<b>Launch</b>"))

    # shortcut knob
    knob = nuke.String_Knob("hotboxShortcut", "Shortcut")
    knob.setValue("`")

    addPrefKnob(
        knob,
        "The key that triggers the Hotbox. Should be set to a single key without any modifier keys. "
        "Spacebar can be defined as 'space'. Nuke needs be restarted in order for the changes to take effect.",
    )

    constants.shortcut = preferencesNode.knob("hotboxShortcut").value()

    # reset shortcut knob
    knob = nuke.PyScript_Knob("hotboxResetShortcut", "set", "W_hotbox.resetMenuItems()")
    addPrefKnob(knob, "Apply new shortcut.", True)
    # trigger mode knob
    knob = nuke.Enumeration_Knob(
        "hotboxTriggerDropdown", "Launch mode", ["Press and Hold", "Single Tap"]
    )

    addPrefKnob(
        knob,
        "The way the hotbox is launched. When set to 'Press and Hold' the Hotbox will appear whenever the shortcut is pressed and disappear as soon as the user releases the key. "
        "When set to 'Single Tap' the shortcut will toggle the Hotbox on and off.",
    )

    knob = addPrefBoolKnob(
        "hotboxCloseOnClick",
        "Close on button click",
        False,
        "Close the Hotbox whenever a button is clicked (excluding submenus obviously). This option will only take effect when the launch mode is set to 'Single Tap'.",
    )
    knob = addPrefBoolKnob(
        "hotboxExecuteOnClose",
        "Execute button without click",
        False,
        "Execute the button underneath the cursor whenever the Hotbox is closed.",
    )
    # Rule/Class order
    knob = nuke.Enumeration_Knob(
        "hotboxRuleClassOrder", "Order", ["Class - Rule", "Rule - Class"]
    )
    addPrefKnob(knob, "The order in which the buttons will be loaded.")

    # Manager startup default
    knob = nuke.Enumeration_Knob(
        "hotboxOpenManagerOptions",
        "Manager startup default",
        ["Contextual", "All", "Rules", "Contextual/All", "Contextual/Rules"],
    )
    tooltip = addPrefKnob(
        knob,
        "The section of the Manager that will be opened on startup.\n"
        "\n<b>Contextual</b> Open the 'Single' or 'Multiple' section, depending on selection."
        "\n<b>All</b> Open the 'All' section."
        "\n<b>Rules</b> Open the 'Rules' section."
        "\n<b>Contextual/All</b> Contextual if the selection matches a button in the 'Single' or 'Multiple' section, otherwise the 'All' section will be opened."
        "\n<b>Contextual/Rules</b> Contextual if the selection matches a button in the 'Single' or 'Multiple' section, otherwise the 'Rules' section will be opened.",
        True,
    )
    # Appearence knob
    addToPreferences(nuke.Text_Knob("hotboxAppearanceLabel", "<b>Appearance</b>"))

    # color dropdown knob
    knob = nuke.Boolean_Knob("hotboxMirroredLayout", "Mirrored")

    addPrefKnob(
        knob,
        "By default the contextual buttons will appear at the top of the hotbox and the non contextual buttons at the bottom.",
    )

    # color dropdown knob
    knob = nuke.Enumeration_Knob(
        "hotboxColorDropdown", "Color scheme", ["Maya", "Nuke", "Custom"]
    )

    addPrefKnob(
        knob,
        "The color of the buttons when selected.\n"
        "\n<b>Maya</b> Autodesk Maya's muted blue."
        "\n<b>Nuke</b> Nuke's bright orange."
        "\n<b>Custom</b> which lets the user pick a color.",
    )

    # custom color knob
    knob = nuke.ColorChip_Knob("hotboxColorCustom", "")
    addPrefKnob(
        knob,
        "The color of the buttons when selected, when the color dropdown is set to 'Custom'.",
        True,
    )
    knob = addPrefBoolKnob(
        "hotboxColorCenter",
        "Colorize hotbox center",
        True,
        "Color the center button of the hotbox depending on the current selection. When unticked the center button will be colored a lighter tone of grey.",
    )
    knob = addPrefBoolKnob(
        "hotboxAutoTextColor",
        "Auto adjust text color",
        True,
        "Automatically adjust the color of a button's text to its background color in order to keep enough of a difference to remain readable.",
    )
    knob = addPrefIntKnob(
        "hotboxFontSize",
        "Font size",
        8,
        "The font size of the text that appears in the hotbox buttons, unless defined differently on a per-button level.",
    )
    # fontsize manager's script editor knob
    knob = nuke.Int_Knob("hotboxScriptEditorFontSize", "Font size script editor")
    knob.setValue(11)
    addPrefKnob(
        knob,
        "The font size of the text that appears in the hotbox manager's script editor.",
        True,
    )
    addToPreferences(nuke.Text_Knob("hotboxItemsLabel", "<b>Items per Row</b>"))

    knob = addPrefIntKnob(
        "hotboxRowAmountSelection",
        "Selection specific",
        3,
        "The maximum amount of buttons a row in the upper half of the Hotbox can contain. "
        "When the row's maximum capacity is reached a new row will be started. This new row's maximum capacity will be incremented by the step size.",
    )
    knob = addPrefIntKnob(
        "hotboxRowAmountAll",
        "All",
        3,
        "The maximum amount of buttons a row in the lower half of the Hotbox can contain. "
        "When the row's maximum capacity is reached a new row will be started.This new row's maximum capacity will be incremented by the step size.",
    )
    knob = addPrefIntKnob(
        "hotboxRowStepSize",
        "Step size",
        1,
        "The amount a buttons every new row's maximum capacity will be increased by. "
        "Having a number unequal to zero will result in a triangular shape when having multiple rows of buttons.",
    )
    # spawnmode knob
    knob = nuke.Boolean_Knob("hotboxButtonSpawnMode", "Add new buttons to the sides")
    knob.setValue(True)
    knob.setFlag(nuke.STARTLINE)

    addPrefKnob(
        knob,
        "Add new buttons left and right of the row alternately, instead of to the right, in order to preserve muscle memory.",
    )

    # hide the iconLocation knob if environment varible called 'W_HOTBOX_HIDE_ICON_LOC' is set to 'true' or '1'
    preferencesNode.knob("hotboxIconLocation").setVisible(True)
    if "W_HOTBOX_HIDE_ICON_LOC" in os.environ and os.environ[
        "W_HOTBOX_HIDE_ICON_LOC"
    ].lower() in ["true", "1"]:
        preferencesNode.knob("hotboxIconLocation").setVisible(False)

    savePreferencesToFile()


def addPrefIntKnob(arg0, arg1, arg2, arg3):
    # fontsize knob
    result = nuke.Int_Knob(arg0, arg1)
    result.setValue(arg2)

    addPrefKnob(result, arg3)

    return result


def addPrefBoolKnob(arg0, arg1, arg2, arg3):
    # close on click
    result = nuke.Boolean_Knob(arg0, arg1)
    result.setValue(arg2)
    addPrefKnob(result, arg3, True)
    return result


# endregion


# region colors


def interface2rgb(hexValue, normalize=True):
    """
    Convert a color stored as a 32 bit value as used by nuke for interface colors to normalized rgb values.

    """
    return [(0xFF & hexValue >> i) / 255.0 for i in [24, 16, 8]]


def rgb2hex(rgbaValues):
    """
    Convert a color stored as normalized rgb values to a hex.
    """

    rgbaValues = [int(i * 255) for i in rgbaValues]

    if len(rgbaValues) < 3:
        return

    return "#%02x%02x%02x" % (rgbaValues[0], rgbaValues[1], rgbaValues[2])


def hex2rgb(hexColor):
    """
    Convert a color stored as hex to rgb values.
    """

    hexColor = hexColor.lstrip("#")
    return tuple(int(hexColor[i : i + 2], 16) for i in (0, 2, 4))


def rgb2interface(rgb):
    """
    Convert a color stored as rgb values to a 32 bit value as used by nuke for interface colors.
    """
    if len(rgb) == 3:
        rgb = rgb + (255,)

    return int("%02x%02x%02x%02x" % rgb, 16)


def getTileColor(node=None):
    """
    If a node has it's color set automatically, the 'tile_color' knob will return 0.
    If so, this function will scan through the preferences to find the correct color value.
    """

    if not node:
        node = nuke.selectedNode()

    interfaceColor = node.knob("tile_color").value()

    if interfaceColor == 0:
        interfaceColor = nuke.defaultNodeColor(node.Class())

    return interfaceColor


def getSelectionColor():
    """
    Return color to be used for the selected items of the hotbox.
    """

    customColor = rgb2hex(
        interface2rgb(preferencesNode.knob("hotboxColorCustom").value())
    )
    colorMode = int(preferencesNode.knob("hotboxColorDropdown").getValue())

    return ["#5285a6", "#f7931e", customColor][colorMode]


# endregion


# region OS
def getHotBoxLocation(path=None):
    """
    Returns the location of the hotbox.
    """
    folder = ""
    folder = path or preferencesNode.knob("hotboxLocation").value()
    if folder[-1] != "/":
        folder += "/"

    return os.path.expandvars(folder.replace("\\", "/"))


def revealInBrowser(startFolder=False):
    """
    Reveal the hotbox folder in a filebrowser
    """
    constants = Constants()
    if startFolder:
        path = getHotBoxLocation()

    else:
        try:
            path = constants.hotboxInstance.topLayout.folderList[0]
        except Exception:
            path = (
                constants.hotboxInstance.topLayout.path + constants.hotboxInstance.mode
            )

    if not os.path.exists(path):
        path = os.path.dirname(path)

    if operatingSystem == "Windows":
        os.startfile(path)
    elif operatingSystem == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def getFileBrowser():
    """
    Determine the name of the file browser on the current system.
    """

    if operatingSystem == "Darwin":
        return "Finder"
    elif operatingSystem == "Windows":
        return "Explorer"
    else:
        return "file browser"


# endregion
