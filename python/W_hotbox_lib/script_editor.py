from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2 import QtCore

from pathlib import Path

from .utils import getHotBoxLocation, getAttributeFromFile, getScriptFromFile


class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, scriptEditor):
        super(LineNumberArea, self).__init__(scriptEditor)

        self.scriptEditor = scriptEditor
        self.setStyleSheet("text-align: center;")

    def paintEvent(self, event):
        self.scriptEditor.lineNumberAreaPaintEvent(event)
        return


# -  File Name
class ScriptEditorNameWidget(QtWidgets.QLineEdit):
    """
    Subclassed QLineEdit.
    Added some functionality to check whether the text was changed and to save.
    """

    # signals
    save = QtCore.Signal()

    def __init__(self):
        super(ScriptEditorNameWidget, self).__init__()

        self.savedText = ""
        self.editingFinished.connect(self.saveEvent)

    # - Subclassed methods/events
    def saveEvent(self):
        """
        Emit save signal that can be picked up by parent class.
        Make sure text is actually changed and valid before emitting a signal.
        """

        # check if changed
        if self.text() != self.savedText:
            textFormatted = self.text().strip()
            if textFormatted:
                self.setText(textFormatted)
                self.save.emit()

            else:
                self.setText(self.savedText)

    def setText(self, text):
        """
        Set text
        """

        self.savedText = text
        # keep default behaviour
        QtWidgets.QLineEdit.setText(self, text)


# - Script Editor
class ScriptEditorWidget(QtWidgets.QPlainTextEdit):
    """
    Script editor widget.
    """

    # signals
    save = QtCore.Signal()

    def __init__(self):
        super(ScriptEditorWidget, self).__init__()

        self.savedText = ""
        self.savedName = ""

        # Setup line numbers
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.updateLineNumberAreaWidth()

        # highlight line
        self.textChanged.connect(self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth()

    # --------------------------------------------------------------------------------------------------
    # events
    # --------------------------------------------------------------------------------------------------

    def focusOutEvent(self, event):
        """
        Actions executed when widget loses focus.
        """

        # inherit default behaviour
        QtWidgets.QPlainTextEdit.focusOutEvent(self, event)

        self.highlightCurrentLine()

        # save to file
        if not self.isReadOnly() and self.isChanged():
            self.save.emit()

        return True

    # indents

    def keyPressEvent(self, event):
        """
        Custom actions for specific keystrokes
        """

        # if Tab convert to Space
        if event.key() == 16777217:
            self.indentation("indent")

        # if Shift+Tab remove indent
        elif event.key() == 16777218:
            self.indentation("unindent")

        # if BackSpace try to snap to previous indent level
        elif event.key() == 16777219:
            if not self.unindentBackspace():
                QtWidgets.QPlainTextEdit.keyPressEvent(self, event)

        # if shift+/ comment out current line(s) (toggle)
        elif (
            event.key() == 47
            and QtWidgets.QApplication.keyboardModifiers() == QtCore.Qt.ControlModifier
        ):
            # QtWidgets.QPlainTextEdit.keyPressEvent(self, event)
            self.toggleComment()

        # if enter or return, match indent level
        elif event.key() in [16777220, 16777221]:
            # QtWidgets.QPlainTextEdit.keyPressEvent(self, event)
            self.indentNewLine()

        else:
            QtWidgets.QPlainTextEdit.keyPressEvent(self, event)

    # --------------------------------------------------------------------------------------------------

    def isChanged(self):
        """
        Check whether current text is the same as the text saved to disk.
        """

        currentText = self.toPlainText()

        return currentText != self.savedText

    def updateSavedText(self):
        """
        Update the variable that holds the text as it is saved to disk.
        """

        self.savedText = self.toPlainText()

    # --------------------------------------------------------------------------------------------------
    # Line Numbers

    # While researching the implementation of line numbers, I had a look at Nuke's Blinkscript interface.
    # This node has an excellent C++ editor, built with Qt.
    # The source code for that editor can be found here (or in Nuke's installation folder):
    # thefoundry.co.uk/products/nuke/developers/100/pythonreference/nukescripts.blinkscripteditor-pysrc.html
    # I stripped and modified the useful bits of the line number related parts of the code
    # and implemented it in the Hotbox Manager. Credits to theFoundry for writing the blinkscripteditor,
    # best example code I could have wished for.
    # --------------------------------------------------------------------------------------------------

    def lineNumberAreaWidth(self):
        digits = 1
        maxNum = max(1, self.blockCount())
        while maxNum >= 10:
            maxNum //= 10
            digits += 1

        return 7 + self.fontMetrics().width("9") * digits

    def updateLineNumberAreaWidth(self):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(
                0, rect.y(), self.lineNumberArea.width(), rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth()

    def resizeEvent(self, event):
        QtWidgets.QPlainTextEdit.resizeEvent(self, event)

        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QtCore.QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event):
        if self.isReadOnly():
            return

        painter = QtGui.QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QtGui.QColor(38, 38, 38))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())
        currentLine = (
            self.document().findBlock(self.textCursor().position()).blockNumber()
        )

        painter.setPen(self.palette().color(QtGui.QPalette.Text))

        while block.isValid() and top <= event.rect().bottom():
            # default grey
            textColor = QtGui.QColor(155, 155, 155)

            if blockNumber == currentLine and self.hasFocus():
                # current line
                textColor = QtGui.QColor(255, 170, 0, 255)

            painter.setPen(textColor)

            number = f"{str(blockNumber + 1)} "
            painter.drawText(
                0,
                top,
                self.lineNumberArea.width(),
                self.fontMetrics().height(),
                QtCore.Qt.AlignRight,
                number,
            )

            # Move to the next block
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    # --------------------------------------------------------------------------------------------------

    def getCursorInfo(self):
        self.cursor = self.textCursor()

        self.firstChar = self.cursor.selectionStart()
        self.lastChar = self.cursor.selectionEnd()

        self.noSelection = False
        if self.firstChar == self.lastChar:
            self.noSelection = True

        self.originalPosition = self.cursor.position()
        self.cursorBlockPos = self.cursor.positionInBlock()

    # --------------------------------------------------------------------------------------------------

    def unindentBackspace(self):
        """
        snap to previous indent level
        """

        self.getCursorInfo()

        if not self.noSelection or self.cursorBlockPos == 0:
            return False

        # check text in front of cursor
        textInFront = (
            self.document().findBlock(self.firstChar).text()[: self.cursorBlockPos]
        )

        # check whether solely spaces
        if textInFront != " " * self.cursorBlockPos:
            return False

        # snap to previous indent level
        spaces = len(textInFront)
        for _ in range(spaces - ((spaces - 1) // 4) * 4 - 1):
            self.cursor.deletePreviousChar()

    def indentNewLine(self):
        """
        Auto indent a new line
        """

        # in case selection covers multiple line, make it one line first
        self.insertPlainText("")

        self.getCursorInfo()

        # check how many spaces after cursor
        text = self.document().findBlock(self.firstChar).text()

        textInFront = text[: self.cursorBlockPos]

        if len(textInFront) == 0:
            self.insertPlainText("\n")
            return

        indentLevel = 0
        for i in textInFront:
            if i == " ":
                indentLevel += 1
            else:
                break

        indentLevel //= 4

        # find out whether textInFront's last character was a ':'
        # if that's the case add another indent.
        # ignore any spaces at the end, however also
        # make sure textInFront is not just an indent
        if textInFront.count(" ") != len(textInFront):
            while textInFront[-1] == " ":
                textInFront = textInFront[:-1]

        if textInFront[-1] == ":":
            indentLevel += 1

        # new line
        self.insertPlainText("\n")
        # match indent
        self.insertPlainText(" " * (4 * indentLevel))

    def indentation(self, mode):
        """
        Indent selected
        """

        self.getCursorInfo()

        # if nothing is selected and mode is set to indent, simply insert as many
        # space as needed to reach the next indentation level.

        if self.noSelection and mode == "indent":
            remainingSpaces = 4 - (self.cursorBlockPos % 4)
            self.insertPlainText(" " * remainingSpaces)
            return

        self.insert_at_cursor(mode)

    def toggleComment(self):
        """
        Disable a line by putting  a # in front of it.
        """

        self.getCursorInfo()

        self.insert_at_cursor("comment")

    def insert_at_cursor(self, arg0):
        selectedBlocks = self.findBlocks(self.firstChar, self.lastChar)
        beforeBlocks = self.findBlocks(last=self.firstChar - 1, exclude=selectedBlocks)
        afterBlocks = self.findBlocks(first=self.lastChar + 1, exclude=selectedBlocks)
        beforeBlocksText = self.blocks2list(beforeBlocks)
        selectedBlocksText = self.blocks2list(selectedBlocks, arg0)
        afterBlocksText = self.blocks2list(afterBlocks)
        combinedText = "\n".join(
            beforeBlocksText + selectedBlocksText + afterBlocksText
        )
        originalBlockCount = len(self.toPlainText().split("\n"))
        combinedText = "\n".join(combinedText.split("\n")[:originalBlockCount])
        self.clear()
        self.setPlainText(combinedText)
        self.restoreSelection()

    def restoreSelection(self):
        """
        Restore the original selection and cursor posiftion modifing the text.
        """

        if self.noSelection:
            self.cursor.setPosition(self.lastChar)

        # check whether the the original selection was from top to bottom or vice versa
        else:
            if self.originalPosition == self.firstChar:
                first = self.lastChar
                last = self.firstChar
                firstBlockSnap = QtGui.QTextCursor.EndOfBlock
                lastBlockSnap = QtGui.QTextCursor.StartOfBlock
            else:
                first = self.firstChar
                last = self.lastChar
                firstBlockSnap = QtGui.QTextCursor.StartOfBlock
                lastBlockSnap = QtGui.QTextCursor.EndOfBlock

            self.cursor.setPosition(first)
            self.cursor.movePosition(firstBlockSnap, QtGui.QTextCursor.MoveAnchor)
            self.cursor.setPosition(last, QtGui.QTextCursor.KeepAnchor)
            self.cursor.movePosition(lastBlockSnap, QtGui.QTextCursor.KeepAnchor)

        self.setTextCursor(self.cursor)

    # --------------------------------------------------------------------------------------------------

    def findBlocks(self, first=0, last=None, exclude=None):
        """
        Divide text in blocks
        """

        if exclude is None:
            exclude = []
        blocks = []
        if last is None:
            last = self.document().characterCount()
        for pos in range(first, last + 1):
            block = self.document().findBlock(pos)
            if block not in blocks and block not in exclude:
                blocks.append(block)
        return blocks

    def blocks2list(self, blocks, mode=None):
        """
        Convert a block to a string.
        If a mode is specified, preform custom modification to the text.
        """

        text = []

        toggle = None

        for block in blocks:
            blockText = block.text()

            # ------------------------------------------------------------------------------------------

            if mode == "unindent":
                if blockText.startswith(" " * 4):
                    blockText = blockText[4:]
                    self.lastChar -= 4

                elif blockText.startswith("\t"):
                    blockText = blockText[1:]
                    self.lastChar -= 1

            # ------------------------------------------------------------------------------------------

            elif mode == "indent":
                blockText = " " * 4 + blockText
                self.lastChar += 4

            # ------------------------------------------------------------------------------------------

            elif mode == "comment":
                unindentedBlockText = blockText.lstrip()
                indents = len(blockText) - len(unindentedBlockText)

                if toggle is None:
                    toggle = not unindentedBlockText.startswith("#")

                # kill comment
                if unindentedBlockText.startswith("# "):
                    unindentedBlockText = unindentedBlockText[2:]

                elif unindentedBlockText.startswith("#"):
                    unindentedBlockText = unindentedBlockText[1:]

                # combine
                blockText = (" " * indents) + ("# " * int(toggle)) + unindentedBlockText

            # ------------------------------------------------------------------------------------------

            text.append(blockText)

        return text

    # --------------------------------------------------------------------------------------------------
    # current line hightlighting
    # --------------------------------------------------------------------------------------------------

    def highlightCurrentLine(self):
        """
        Highlight currently selected line
        """

        selection = QtWidgets.QTextEdit.ExtraSelection()

        lineColor = QtGui.QColor(88, 88, 88, 255)

        if not self.hasFocus() or self.isReadOnly():
            lineColor.setAlpha(0)

        selection.format.setBackground(lineColor)
        selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()

        extraSelections = [selection]
        self.setExtraSelections(extraSelections)


class ScriptEditorHighlighter(QtGui.QSyntaxHighlighter):
    """
    Modified, simplified version of some code found I found when researching:
    wiki.python.org/moin/PyQt/Python%20syntax%20highlighting
    They did an awesome job, so credits to them. I only needed to make some
    modifications to make it fit my needs.
    """

    def __init__(self, document):
        super(ScriptEditorHighlighter, self).__init__(document)

        self.styles = {
            "keyword": self.format([238, 117, 181], "bold"),
            "string": self.format([242, 136, 135]),
            "comment": self.format([143, 221, 144]),
            "numbers": self.format([174, 129, 255]),
            "placeholders": self.format([255, 190, 0]),
        }

        self.keywords = [
            "and",
            "assert",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "exec",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "not",
            "or",
            "pass",
            "print",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
        ]

        self.operatorKeywords = [
            "=",
            "==",
            "!=",
            "<",
            "<=",
            ">",
            ">=",
            "\+",
            "-",
            "\*",
            "/",
            "//",
            "\%",
            "\*\*",
            "\+=",
            "-=",
            "\*=",
            "/=",
            "\%=",
            "\^",
            "\|",
            "\&",
            "\~",
            ">>",
            "<<",
        ]

        self.numbers = ["True", "False", "None"]

        self.tri_single = (QtCore.QRegExp("'''"), 1, self.styles["comment"])
        self.tri_double = (QtCore.QRegExp('"""'), 2, self.styles["comment"])

        self.placeholders = ["KNOBNAME", "NODECLASS", "NODENAME", "VALUE", "EXPRESSION"]

        # rules
        rules = []

        rules += [(r"\b%s\b" % i, 0, self.styles["keyword"]) for i in self.keywords]
        rules += [
            (r"\b%s\b" % i, 0, self.styles["placeholders"]) for i in self.placeholders
        ]
        rules += [(i, 0, self.styles["keyword"]) for i in self.operatorKeywords]
        rules += [(r"\b%s\b" % i, 0, self.styles["numbers"]) for i in self.numbers]

        rules += [
            # integers
            (r"\b[0-9]+\b", 0, self.styles["numbers"]),
            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, self.styles["string"]),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, self.styles["string"]),
            # From '#' until a newline
            (r"#[^\n]*", 0, self.styles["comment"]),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, fmt) for (pat, index, fmt) in rules]

    def format(self, rgb, style=""):
        """
        Return a QtGui.QTextCharFormat with the given attributes.
        """

        color = QtGui.QColor(*rgb)
        textFormat = QtGui.QTextCharFormat()
        textFormat.setForeground(color)

        if "bold" in style:
            textFormat.setFontWeight(QtGui.QFont.Bold)
        if "italic" in style:
            textFormat.setFontItalic(True)

        return textFormat

    def highlightBlock(self, text):
        """
        Apply syntax highlighting to the given block of text.
        """
        # Do other syntax formatting
        for expression, nth, format in self.rules:
            index = expression.indexIn(text, 0)

            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        # Do multi-line strings
        in_multiline = self.matchMultiline(
            text, *self.tri_single
        ) or self.matchMultiline(text, *self.tri_double)

    def matchMultiline(self, text, delimiter, in_state, style):
        """
        Check whether highlighting requires multiple lines.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return True if still inside a multi-line string, False Otherwise
        return self.currentBlockState() == in_state


# - Template Button
class ScriptEditorTemplateMenu(QtWidgets.QMenu):
    def __init__(self, parentObject):
        super(ScriptEditorTemplateMenu, self).__init__()

        self.hotbox = parentObject

        # set default template folder
        folder = getHotBoxLocation()

        self.templateFolder = folder / "Templates"

        self.initMenu()

    def initMenu(self):
        self.clear()
        self.menuItems = []

        # add menu entries pointing to templates stored on disk
        self.addUserTemplates(folder=self.templateFolder)

        self.addSeparator()

        # add function to manage templates
        self.addQAction(self, "Save current script as template", self.saveAsTemplate)
        self.addQAction(self, "Manage templates", self.hotbox.toggleTemplateMode)

    def addUserTemplates(self, folder: Path, parent=None):
        """
        Scan template folder and add an item for every template.
        """

        if not parent:
            parent = self

        for path in [
            (folder / file)
            for file in folder.iterdir()
            if file.stem[0] not in ["_", "."]
        ]:
            name = getAttributeFromFile(path)

            # make sure name won't be longer than 'Save current script as template'
            maxNameLength = 31

            # file
            if path.is_file():
                # trim name if to long
                if len(name) > maxNameLength:
                    name = f"{name[:maxNameLength - 3]}..."

                self.addQAction(parent, name, path)

            else:
                # trim name if to long
                maxNameLength -= 3
                if len(name) > maxNameLength:
                    name = f"{name[:maxNameLength - 3]}..."

                # create new QMenu
                menu = QtWidgets.QMenu()
                menu.setTitle(name)

                # add QMenu to parent
                parent.addMenu(menu)
                self.menuItems.append(menu)

                # Run this function again, with new Qmenu as menu
                self.addUserTemplates(parent=menu, folder=path)

    def addQAction(self, parent, name, function):
        """
        Create new action and add to menu.
        """

        # create new QAction
        action = QtWidgets.QAction(parent)
        action.setText(name)

        # bind function

        # if a script is passed instead of a function, turn it into a function
        if not callable(function):
            script = function
            function = lambda: self.insertTemplate(script)

        action.triggered.connect(function)

        # addToMenu
        parent.addAction(action)
        self.menuItems.append(action)

    def insertTemplate(self, path):
        """
        Insert template script into script editor
        """

        # get script
        template = getScriptFromFile(path)

        # add proper indentation
        template = self.adjustTemplate(template)

        self.hotbox.scriptEditorScript.insertPlainText(template)

    def saveAsTemplate(self):
        """
        Save current script as a template
        """

        self.hotbox.saveScriptEditor(True)

    def adjustTemplate(self, script):
        """
        Modify template script based on current cursor position
        """
        cursor = self.hotbox.scriptEditorScript.textCursor()
        cursorPosition = cursor.positionInBlock()

        textBeforeCursor = cursor.block().text()[:cursorPosition]
        textBeforeCursorNoIndent = textBeforeCursor.lstrip()

        # if cursor at beginning of block, return original script
        if textBeforeCursor == "":
            return script

        # find current indentation, rounded by 4
        indentLevel = " " * (
            4 * ((len(textBeforeCursor) - len(textBeforeCursorNoIndent)) // 4)
        )

        if textBeforeCursorNoIndent != "":
            script = "\n" + script

        script = script.replace("\n", "\n" + indentLevel)

        return script

    def enableMenuItems(self):
        """
        Enable items based on state of script editor.
        """

        # check if script editor widget is accessible
        mode = 1 - self.hotbox.scriptEditorScript.isReadOnly()

        # skip last item (enter template mode)
        for menuItem in self.menuItems[:-1]:
            menuItem.setEnabled(mode)
