#----------------------------------------------------------------------------------------------------------
# Wouter Gilsing
# woutergilsing@hotmail.com
version = '1.1'
releaseDate = '28 August 2016'
#----------------------------------------------------------------------------------------------------------

from PySide import QtGui, QtCore

import datetime
import nuke
import os
import shutil
import base64
import re
import webbrowser
import tarfile

preferencesNode = nuke.toNode('preferences')

class hotboxManager(QtGui.QWidget):
    def __init__(self, path = ''):
        super(hotboxManager, self).__init__()

        #--------------------------------------------------------------------------------------------------
        #main widget
        #--------------------------------------------------------------------------------------------------

        self.setWindowTitle('W_hotbox Manager - %s'%path)

        self.setMinimumWidth(1000)
        self.setMinimumHeight(400)

        #--------------------------------------------------------------------------------------------------

        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        
        self.rootLocation = path.replace('\\','/')

        #--------------------------------------------------------------------------------------------------
        #classes list
        #--------------------------------------------------------------------------------------------------

        self.classesListLayout = QtGui.QVBoxLayout()

        self.scopeComboBox = QtGui.QComboBox()
        self.scopeComboBox.addItems(['Single','Multiple','All'])
        self.scopeComboBox.currentIndexChanged.connect( self.builtClassesList )

        self.classesList = QtGui.QListWidget()
        self.classesList.setFixedWidth(150)

        self.classesListLayout.addWidget(self.scopeComboBox)
        self.classesListLayout.addWidget(self.classesList)

        #buttons

        self.classesListButtonsLayout = QtGui.QVBoxLayout()

        self.classesListAddButton = QLabelButton('add')
        self.classesListRemoveButton = QLabelButton('remove')
        self.classesListRenameButton = QLabelButton('rename')

        self.connect(self.classesListAddButton, QtCore.SIGNAL('buttonClicked()'), self.addClass)
        self.connect(self.classesListRemoveButton, QtCore.SIGNAL('buttonClicked()'), self.removeClass)
        self.connect(self.classesListRenameButton, QtCore.SIGNAL('buttonClicked()'), self.renameClass)

        self.classesListButtonsLayout.addStretch()
        self.classesListButtonsLayout.addWidget(self.classesListAddButton)
        self.classesListButtonsLayout.addWidget(self.classesListRemoveButton)
        self.classesListButtonsLayout.addWidget(self.classesListRenameButton)
        self.classesListButtonsLayout.addStretch()

        #--------------------------------------------------------------------------------------------------
        #hotbox items tree
        #--------------------------------------------------------------------------------------------------
        
        self.hotboxItemsTree = QTreeViewCustom(self)
        self.hotboxItemsTree.setFixedWidth(150)
        self.rootPath = nuke.toNode('preferences').knob('hotboxLocation').value()

        self.classesList.itemSelectionChanged.connect(self.hotboxItemsTree.populateTree)

        #--------------------------------------------------------------------------------------------------
        #hotbox items tree actions
        #--------------------------------------------------------------------------------------------------

        self.hotboxItemsTreeButtonsLayout = QtGui.QVBoxLayout()

        self.hotboxItemsTreeAddButton = QLabelButton('add')
        self.hotboxItemsTreeAddFolderButton = QLabelButton('addFolder')
        self.hotboxItemsTreeRemoveButton = QLabelButton('remove')
        self.hotboxItemsTreeDuplicateButton = QLabelButton('duplicate')
        self.hotboxItemsTreeCopyButton = QLabelButton('copy')
        self.hotboxItemsTreePasteButton = QLabelButton('paste')

        self.connect(self.hotboxItemsTreeAddButton, QtCore.SIGNAL('buttonClicked()'), self.hotboxItemsTree.addItem)
        self.connect(self.hotboxItemsTreeAddFolderButton, QtCore.SIGNAL('buttonClicked()'), lambda: self.hotboxItemsTree.addItem(True))
        self.connect(self.hotboxItemsTreeRemoveButton, QtCore.SIGNAL('buttonClicked()'), self.hotboxItemsTree.removeItem)
        self.connect(self.hotboxItemsTreeDuplicateButton, QtCore.SIGNAL('buttonClicked()'), self.hotboxItemsTree.duplicateItem)
        self.connect(self.hotboxItemsTreeCopyButton, QtCore.SIGNAL('buttonClicked()'), self.hotboxItemsTree.copyItem)
        self.connect(self.hotboxItemsTreePasteButton, QtCore.SIGNAL('buttonClicked()'), self.hotboxItemsTree.pasteItem)


        self.hotboxItemsTreeButtonsLayout.addStretch()
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeAddButton)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeAddFolderButton)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeRemoveButton)
        self.hotboxItemsTreeButtonsLayout.addSpacing(25)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeCopyButton)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreePasteButton)
        self.hotboxItemsTreeButtonsLayout.addWidget(self.hotboxItemsTreeDuplicateButton)
        self.hotboxItemsTreeButtonsLayout.addStretch()

        #--------------------------------------------------------------------------------------------------
        #import/export
        #--------------------------------------------------------------------------------------------------

        self.archiveButtonsLayout = QtGui.QHBoxLayout()   

        self.clipboardArchive = QtGui.QRadioButton('Clipboard')
        self.importArchiveButton = QtGui.QPushButton('Import Archive')
        self.exportArchiveButton = QtGui.QPushButton('Export Archive')

        self.importArchiveButton.setMaximumWidth(100)
        self.exportArchiveButton.setMaximumWidth(100)

        self.importArchiveButton.clicked.connect(self.importHotboxArchive)
        self.exportArchiveButton.clicked.connect(self.exportHotboxArchive)

        self.archiveButtonsLayout.addStretch()
        self.archiveButtonsLayout.addWidget(self.clipboardArchive)
        self.archiveButtonsLayout.addWidget(self.importArchiveButton)
        self.archiveButtonsLayout.addWidget(self.exportArchiveButton)

        #--------------------------------------------------------------------------------------------------
        #scriptEditor
        #--------------------------------------------------------------------------------------------------
        
        self.loadedScript = None

        self.scriptEditorLayout = QtGui.QVBoxLayout()       

        #name
        self.scriptEditorNameLayout = QtGui.QHBoxLayout()

        self.scriptEditorNameLabel = QtGui.QLabel('Name')
        self.scriptEditorName = QtGui.QLineEdit()
        self.scriptEditorName.setAlignment(QtCore.Qt.AlignLeft)
        self.scriptEditorName.setReadOnly(True)
        self.scriptEditorName.setStyleSheet('background:#262626')

        self.scriptEditorNameLayout.addWidget(self.scriptEditorNameLabel)
        self.scriptEditorNameLayout.addWidget(self.scriptEditorName)

        self.scriptEditorScript = QtGui.QPlainTextEdit()
        self.scriptEditorScript.setMinimumHeight(200)
        self.scriptEditorScript.setMinimumWidth(500)
        self.scriptEditorScript.setReadOnly(True)
        self.scriptEditorScript.setStyleSheet('background:#262626')

        scriptEditorFont = QtGui.QFont()
        scriptEditorFont.setFamily("Courier")
        scriptEditorFont.setStyleHint(QtGui.QFont.Monospace)
        scriptEditorFont.setFixedPitch(True)
        scriptEditorFont.setPointSize(11)

        self.scriptEditorScript.setFont(scriptEditorFont)
        self.scriptEditorScript.setTabStopWidth(4 * QtGui.QFontMetrics(scriptEditorFont).width(' '))

            
        #buttons
        self.scriptEditorButtonsLayout = QtGui.QHBoxLayout()

        self.scriptEditorImportButton = QtGui.QPushButton('Import')
        self.scriptEditorSaveButton = QtGui.QPushButton('Save')
        
        self.scriptEditorImportButton.clicked.connect(self.importScriptEditor)
        self.scriptEditorSaveButton.clicked.connect(self.saveScriptEditor)

        self.scriptEditorSaveButton.setMaximumWidth(100)

        self.scriptEditorButtonsLayout.addStretch()
        self.scriptEditorButtonsLayout.addWidget(self.scriptEditorImportButton)
        self.scriptEditorButtonsLayout.addWidget(self.scriptEditorSaveButton)
        self.scriptEditorButtonsLayout.addStretch()

        self.scriptEditorLayout.addLayout(self.archiveButtonsLayout)
        self.scriptEditorLayout.addLayout(self.scriptEditorNameLayout)
        self.scriptEditorLayout.addWidget(self.scriptEditorScript)
        self.scriptEditorLayout.addLayout(self.scriptEditorButtonsLayout)

        #--------------------------------------------------------------------------------------------------
        #main buttons
        #--------------------------------------------------------------------------------------------------
        self.mainButtonLayout = QtGui.QHBoxLayout()

        self.aboutButton = QtGui.QPushButton('?')
        self.aboutButton.clicked.connect(self.openAboutDialog)
        self.aboutButton.setMaximumWidth(20)

        self.mainCloseButton = QtGui.QPushButton('Close')
        self.mainCloseButton.clicked.connect(self.closeManager)

        self.mainButtonLayout.addWidget(self.aboutButton)
        self.mainButtonLayout.addStretch()
        self.mainButtonLayout.addWidget(self.mainCloseButton)

        #--------------------------------------------------------------------------------------------------
        #main layout
        #--------------------------------------------------------------------------------------------------
        
        self.mainLayout = QtGui.QHBoxLayout()
        self.mainLayout.addLayout(self.classesListButtonsLayout)
        self.mainLayout.addLayout(self.classesListLayout)
        self.mainLayout.addLayout(self.hotboxItemsTreeButtonsLayout)
        self.mainLayout.addWidget(self.hotboxItemsTree)
        self.mainLayout.addLayout(self.scriptEditorLayout)

        #--------------------------------------------------------------------------------------------------
        #layouts
        #--------------------------------------------------------------------------------------------------
        
        self.masterLayout = QtGui.QVBoxLayout()

        self.masterLayout.addLayout(self.mainLayout)
        self.masterLayout.addLayout(self.mainButtonLayout)

        self.setLayout(self.masterLayout)

        #--------------------------------------------------------------------------------------------------
        #move to center of the screen
        #--------------------------------------------------------------------------------------------------
        
        self.adjustSize()

        screenRes = QtGui.QDesktopWidget().screenGeometry()
        self.move(QtCore.QPoint(screenRes.width()/2,screenRes.height()/2)-QtCore.QPoint((self.width()/2),(self.height()/2)))

        #--------------------------------------------------------------------------------------------------
        #set hotbox to current selection
        #--------------------------------------------------------------------------------------------------

        self.scopeComboBox.setCurrentIndex(1)
        self.scopeComboBox.setCurrentIndex(0)
        

        selection = nuke.selectedNodes()
        if selection > 0:
            classes = set(sorted([i.Class() for i in selection]))
            self.scopeComboBox.setCurrentIndex(max(min(len(classes)-1,1),0))
            for index in range(self.classesList.count()):
                if self.classesList.item(index).text() == '-'.join(classes):
                    self.classesList.setCurrentRow(index)
                    self.hotboxItemsTree.populateTree()
                    break

        #--------------------------------------------------------------------------------------------------
        #shortcuts
        #--------------------------------------------------------------------------------------------------

        #save
        self.saveAction = QtGui.QAction(self)
        self.saveAction.setShortcut(QtGui.QKeySequence(QtCore.Qt.CTRL + QtCore.Qt.Key_S))
        self.saveAction.triggered.connect(self.saveScriptEditor)
        self.addAction(self.saveAction)

    #--------------------------------------------------------------------------------------------------
    #classes list
    #--------------------------------------------------------------------------------------------------
    
    def builtClassesList(self, restoreSelection = False):

        try:
            if restoreSelection:
                currentRow = self.classesList.currentRow()
                currentItems = [self.classesList.item(index).text() for index in range(self.classesList.count())]

            self.classesList.clear()

            self.path = self.rootLocation + self.scopeComboBox.currentText()

            bgColor = '#3a3a3a'

            if self.scopeComboBox.currentText()== 'All':
                bgColor = '#262626'

            self.classesList.setStyleSheet('background:%s'%bgColor)

            items = [folder for folder in sorted(os.listdir(self.path)) if os.path.isdir(self.path + '/' + folder) and folder[0] not in ['.','_']]

            if self.scopeComboBox.currentIndex() == 2:
                self.hotboxItemsTree.populateTree()

            else:
                self.classesList.addItems(items)
                self.hotboxItemsTree.populateTree()

            if restoreSelection:
                newItems = [self.classesList.item(index).text() for index in range(self.classesList.count())]
                if len(newItems) >= len(currentItems):

                    for index, i in enumerate(newItems):
                        if i not in currentItems:
                            self.classesList.setCurrentRow(index)
                            break
        except:
            pass


    def addClass(self):
        '''
        Add a new nodeclass
        '''
        if self.scopeComboBox.currentText() != 'All':

            newClass = 'NewClass'

            counter = 1
            while os.path.isdir(self.path + '/' + newClass):
                newClass = 'NewClass' + str(counter)
                counter += 1

            os.mkdir(self.path + '/' + newClass)

            self.builtClassesList()

            for item in [self.classesList.item(index) for index in range(self.classesList.count())]:
                
                if item.text() == newClass:
                    item.setSelected(True)
                    self.currentItem = item.text()

            self.renameClass('new')


    def removeClass(self):
        '''
        Remove the selected nodeclass
        '''
        if self.scopeComboBox.currentText() != 'All':

            self.currentItem = self.classesList.currentItem().text()
            oldFolder = self.path + '/_old'
            if not os.path.isdir(oldFolder):
                os.mkdir(oldFolder)

            shutil.move(self.path + '/' + self.currentItem, self.path + '/_old/' + self.currentItem + '_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))

            self.builtClassesList(True)

    def renameClass(self, mode = 'rename'):
        '''
        Rename the selected nodeclass
        '''
        if self.scopeComboBox.currentText() != 'All':

            if mode == 'rename':
                self.currentItem = self.classesList.currentItem().text()

            global renameDialogInstance
            if renameDialogInstance == None:
                renameDialogInstance = renameDialog(mode)
                renameDialogInstance.show()

    #--------------------------------------------------------------------------------------------------
    #scriptEditor
    #--------------------------------------------------------------------------------------------------

    def loadScriptEditor(self):
        '''
        Fill the fields of the the script editor with the information read from the currently selected
        file.
        '''


        activeColor = '#3a3a3a'
        lockedColor = '#262626'


        if len(self.hotboxItemsTree.selectedItems) != 0:
            self.selectedItem = self.hotboxItemsTree.selectedItems[0]

        if len(self.hotboxItemsTree.selectedItems) == 1:

            self.loadedScript = self.selectedItem.path

            self.scriptEditorName.setStyleSheet('background:%s'%activeColor)
            self.scriptEditorScript.setStyleSheet('background:%s'%activeColor)

            try:

                if not os.path.isdir(self.selectedItem.path):

                    #set name
                    self.scriptEditorName.setText(self.selectedItem.richTextName)

                    #set script

                    openFile = open(self.loadedScript).readlines()
                    for index, line in enumerate(openFile):
                        if not line.startswith('#'):
                            self.scriptEditorScript.setPlainText(''.join(openFile[index+1:]))
                            break
                    self.scriptEditorScript.setReadOnly(False)

                else:

                    #set name
                    self.scriptEditorName.setText(open(self.loadedScript+'/_name.json').read())
                    self.scriptEditorScript.setReadOnly(True)
                    self.scriptEditorScript.setStyleSheet('background:%s'%lockedColor)
                    self.scriptEditorScript.clear()

                self.scriptEditorName.setReadOnly(False)

            except:
                pass

        else:

            self.loadedScript = None

            self.scriptEditorName.clear()
            self.scriptEditorScript.clear()
            self.scriptEditorName.setReadOnly(True)
            self.scriptEditorScript.setReadOnly(True)
            self.scriptEditorName.setStyleSheet('background:%s'%lockedColor)
            self.scriptEditorScript.setStyleSheet('background:%s'%lockedColor)



    def importScriptEditor(self):
        '''
        Set the current content of the script editor by importing an existing file. 
        '''

        if self.loadedScript != None:

            importFile = nuke.getFilename('select file to  import','*.py *.json')
            self.scriptEditorScript.setPlainText(open(importFile).read())

    def saveScriptEditor(self):
        '''
        Save the current content of the script editor 
        '''

        if self.loadedScript != None:

            name = self.scriptEditorName.text()

            if not os.path.isdir(self.selectedItem.path):

                newFileContent = fileHeader(name).getHeader() +  self.scriptEditorScript.toPlainText()
                currentFile = open(self.selectedItem.path, 'w')
                currentFile.write(newFileContent)
                currentFile.close()

            else:
                currentFile = open(self.selectedItem.path+'/_name.json', 'w')
                currentFile.write(name)
                currentFile.close() 

            self.selectedItem.setText(name)


    #--------------------------------------------------------------------------------------------------
    #Import/Export functions
    #--------------------------------------------------------------------------------------------------


    def exportHotboxArchive(self):

        #create zip
        nukeFolder = os.getenv('HOME').replace('\\','/') + '/.nuke/'
        currentDate = datetime.datetime.now().strftime('%Y%m%d%H%M')
        tempFolder = nukeFolder + 'W_hotboxArchiveImportTemp_%s/'%currentDate
        os.mkdir(tempFolder)

        archiveLocation = tempFolder + 'hotboxArchive_%s.tar.gz'%currentDate

        with tarfile.open(archiveLocation, "w:gz") as tar:
            tar.add(self.rootLocation, arcname=os.path.basename(self.rootLocation))

        #encode
        archive = open(archiveLocation)
        archiveContent = archive.read()
        archive.close()

        if self.clipboardArchive.isChecked():
            encodedArchive = base64.b64encode(archiveContent)
            #save to clipboard
            QtGui.QApplication.clipboard().setText(encodedArchive)

        else:
            #save to file
            exportFileLocation = nuke.getFilename('Export Archive', '*.hotbox')
            if exportFileLocation == None:
                return

            if not exportFileLocation.endswith('.hotbox'):
                exportFileLocation += '.hotbox'

            shutil.copy(archiveLocation, exportFileLocation)

        #delete archive
        shutil.rmtree(tempFolder)


    def indexArchive(self, location, dict = False):
        if dict:
            fileList = {}
        else:
            fileList = []

        for root,b,files in os.walk(location):
            root = root.replace('\\','/')
            level = root.replace(location, '')
        
            if '/_' not in level and '/.' not in level:
        
                newLevel = level
        
                if '_name.json' in files:
                    readName = open(root+'/_name.json').read()
                    if '/' in readName:
                        readName = newLevel.replace('/','**BACKSLASH**')

                    newLevel = '/'.join(level.split('/')[:-1])+'/' + readName

                for file in files:
                    if not file.startswith('.'):
                        newFile = file
                        if len(file) == 6:
                            openFile = open(root + '/' + file).readlines()
            
                            nameTag = '# NAME: '
            
                            for line in (openFile):
            
                                if line.startswith(nameTag):
            
                                    newFile = line.split(nameTag)[-1].replace('\n','')

                                    if '/' in newFile:
                                        newFile = newFile.replace('/','**BACKSLASH**')

                        if dict:
                            fileList[newLevel + '/' + newFile] = level + '/' + file
                        else:
                            fileList.append( [level + '/' + file , newLevel + '/' + newFile ])
        return fileList

    def importHotboxArchive(self):
        '''
        A method to import a set of button to append the current archive with.
        If you're actually reading this, I apologise in advance for what's coming.
        I had trouble getting the code to work on Windows and it turned out it had to do with
        (back)slashes. I ended up trowing in a lot of ".replace('\\','/')". I works, but it
        turned kinda messy...
        '''
        nukeFolder = os.getenv('HOME').replace('\\','/') + '/.nuke/'
        currentDate = datetime.datetime.now().strftime('%Y%m%d%H%M')
        tempFolder = nukeFolder + 'W_hotboxArchiveImportTemp_%s/'%currentDate
        os.mkdir(tempFolder)
        archiveLocation = tempFolder + 'hotboxArchive_%s.tar.gz'%currentDate

        if self.clipboardArchive.isChecked():
            encodedArchive = QtGui.QApplication.clipboard().text()

            archive = open(archiveLocation,'w')
            archive.write(base64.b64decode(encodedArchive))
            archive.close()

        else:

            importFileLocation = nuke.getFilename('select to import', '*.hotbox')
            if importFileLocation == None:
                return

            shutil.copy(importFileLocation, archiveLocation)

        #extract archive
        archive = tarfile.open(archiveLocation)
        importedArchiveLocation = tempFolder + 'archiveExtracted' + currentDate
        os.mkdir(importedArchiveLocation)
        archive.extractall(importedArchiveLocation)
        archive.close()

        importedArchiveLocation += '/'


        importedArchiveLocation = importedArchiveLocation.replace('\\','/')


        #Make sure the current archive is healthy
        for i in ['Single','Multiple','All']:
            repairHotbox(self.rootLocation + i, message = False)

        #Copy stuff from extracted archive to current hotbox location

        importedArchive = self.indexArchive(importedArchiveLocation)
        currentArchive = self.indexArchive(self.rootLocation, dict = True)

        newItems = []
        for i in importedArchive:
            if i[1] in currentArchive.keys():
                #if a file with the same name was found in the same folder, replace it with the new one
                shutil.copy(importedArchiveLocation + i[0],self.rootLocation + currentArchive[i[1]])
            else:
                #if no such file was found, store it in a list to be added later
                if not i[0].endswith('/_name.json'):
                    newItems.append(i)
        newItems = [[i[0].replace('\\','/'),i[1].replace('\\','/')] for i in newItems]
        #gather information about which folders are already present on disk, and which should be created
        allFoldersNeeded = {os.path.dirname(i[1]).replace('\\','/'): os.path.dirname(i[0]).replace('\\','/') for i in newItems}
        allFoldersNeededInverted = {allFoldersNeeded[i] : i for i in allFoldersNeeded.keys()}

        for i in allFoldersNeeded.keys():
            if os.path.dirname(i) in allFoldersNeeded.values():
                dirname1 = os.path.dirname(i).replace('\\','/')
                dirname2 = allFoldersNeededInverted[os.path.dirname(i).replace('\\','/')]
                if dirname1 != dirname2:
                    newItems = [[i[0],i[1].replace(dirname1,dirname2)] for i in newItems]

        #properly sort the list 
        newItemsDict = {i[0]:i[1] for i in newItems}
        newItemsSorted = sorted([i[0] for i in newItems])
        newItems = [[i, newItemsDict[i]] for i in newItemsSorted]

        #move the rest of the files and create new folders when needed
        for i in newItems:
            i = [i[0].replace('\\','/'),i[1].replace('\\','/')]
            if i[0].startswith('All'):
                prefixFolders = 1
            else:
                prefixFolders = 2

            splitFilePath = i[1].split('/')

            classFolders = '/'.join(splitFilePath[:(prefixFolders)])
            baseFolder = self.rootLocation + classFolders
            baseFolder = baseFolder.replace('\\','/')

            if not os.path.isdir(baseFolder):
                os.mkdir(baseFolder)
            
            missingFolders = splitFilePath[prefixFolders:-1]
            for folderName in splitFilePath[prefixFolders:-1]:

                
                #check folders inside existing folder
                for folder in [dir for dir in os.listdir(baseFolder) if len(dir) == 3 and dir[0] not in ['.','_']]:
                    nameFile = baseFolder + '/' + folder + '/_name.json'
                    if open(nameFile).read() == folderName:
                        
                        baseFolder = baseFolder +'/' + folder
                        missingFolders = missingFolders[1:]
                        break

                #is the first folder wasn't found, don't bother lookign for its subfolder
                if missingFolders == splitFilePath[prefixFolders:-1]:
                    break


            #create the missing folders and put _name files in them
            for folder in missingFolders:
                currentFiles = [file[:3] for file in os.listdir(baseFolder) if file[0] not in ['.','_']]
                baseFolder += '/' + str((len(currentFiles) + 1)).zfill(3)
                os.mkdir(baseFolder)
                shutil.copy(importedArchiveLocation + os.path.dirname(i[0]).replace('\\','/') + '/_name.json',baseFolder + '/_name.json')

            currentFiles = [file[:3] for file in os.listdir(baseFolder) if file[0] not in ['.','_']]
            fileName =  str((len(currentFiles) + 1)).zfill(3)+ '.py' 
            shutil.copy(importedArchiveLocation + '/' + i[0], baseFolder + '/' + fileName)


        #delete archive
        shutil.rmtree(tempFolder)

        #reinitiate
        self.builtClassesList(True)

    #--------------------------------------------------------------------------------------------------
    #
    #--------------------------------------------------------------------------------------------------

    def closeManager(self):
        self.close()
        global hotboxManagerInstance
        hotboxManagerInstance = None

    #--------------------------------------------------------------------------------------------------
    #open about widget
    #--------------------------------------------------------------------------------------------------
    def openAboutDialog(self):
        global aboutDialogInstance
        if aboutDialogInstance != None:
            aboutDialogInstance.close()
        aboutDialogInstance = aboutDialog()
        aboutDialogInstance.show()

#------------------------------------------------------------------------------------------------------
#Modified Qt classes
#------------------------------------------------------------------------------------------------------

class QTreeViewCustom(QtGui.QTreeView):
    def __init__(self, parentClass):

        super(QTreeViewCustom,self).__init__()

        self.clipboard = []

        self.parentClass = parentClass

        self.header().hide()
        self.expandsOnDoubleClick = True

        self.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)


        self.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)

        self.dataModel = QtGui.QStandardItemModel()
        self.root = self.dataModel.invisibleRootItem()

        self.root.setDropEnabled(True)

        self.setModel(self.dataModel)
        self.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.SingleSelection)



        #Unfortunatley Nuke 10 crashes on startup when using the following line:
        #self.selectionModel().selectionChanged.connect(self.setSelectedItems)
        #Therefore I had to do this weird construction where the setModel Method is subclassed.

    def setModel(self, model):
        super(QTreeViewCustom, self).setModel(model)
        self.connect(self.selectionModel(),QtCore.SIGNAL("selectionChanged(QItemSelection, QItemSelection)"), self.setSelectedItems)

    #--------------------------------------------------------------------------------------------------

    def populateTree(self, restoreSelection = None):
        '''
        Fill the QTreeView with items associated with the selected nodeclass
        ''' 


        #empty the tree before (re)filling it
        #self.dataModel.clear() #unfortunately this crashes Nuke
        for i in range(self.dataModel.rowCount()):
            self.dataModel.takeRow(0)

        #----------------------------------------------------------------------------------------------
           
        if self.parentClass.scopeComboBox.currentText() == 'All':
            self.scope = self.parentClass.path + '/'

        else:

            classItems = self.parentClass.classesList.selectedItems()
            if len(classItems) == 0:
                return

            classItem = classItems[0].text() + '/'

            self.scope = self.parentClass.path + '/' + classItem

        #----------------------------------------------------------------------------------------------
        #Fill the buttonstree if there is an item selected in the classescolumn, or the mode is set to all.
        if self.parentClass.scopeComboBox.currentText() == 'All' or self.parentClass.classesList.selectedItems() != 0:
            self.addChild(self.root,self.scope)

        self.expandAll()

    def addChild(self, parent, path):
        '''
        Loop through folder structure and add items on the fly
        '''

        for i in sorted(os.listdir(path)):
            if i[0] not in ['_','.']:


                while path[-1] != '/':
                    path = path + '/'
                curPath = path + i

                if os.path.isdir(curPath):
                    try:
                        name = open(curPath +'/_name.json').read()
                    except:
                        name =''

                else:
                    if len(i) != 6:
                        continue
                    nameTag = '# NAME: '

                    for line in open(curPath).readlines():

                        if line.startswith(nameTag):
                            name = line.split(nameTag)[-1].replace('\n','')
                            break

                child = QStandardItemChild(name,curPath)
                parent.appendRow(child)

                if os.path.isdir(curPath):
                    self.addChild(child, curPath)

    def setSelectedItems(self):

        self.selectedItems = [index.model().itemFromIndex(index) for index in self.selectedIndexes()]
        self.selectedItemsPaths = set([i.path for i in self.selectedItems])

        self.parentClass.loadScriptEditor()
    
    #--------------------------------------------------------------------------------------------------
    #Drag and Drop
    #--------------------------------------------------------------------------------------------------

    def iterateFolder(self, path):

        while path[-1] == '/':
            path = path[:-1]

        for i in [path + '/' + i for i in os.listdir(path) if i[0] not in ['.','_']]:
            self.folderContent.insert(0, i )
            if os.path.isdir(i):
                self.iterateFolder(i)

    def dragEnterEvent(self,event):
        index =  self.indexAt(event.pos())
        item = self.dataModel.itemFromIndex(index)
        self.draggedFrom = item.path
        event.acceptProposedAction()

    def dropEvent(self,event):
        index =  self.indexAt(event.pos())
        item = self.dataModel.itemFromIndex(index)


        self.draggedTo = item.path

        folder = False
        if os.path.isdir(self.draggedTo):
            folder = True
            self.draggedTo += '/'

        #calculate whether the item was dropped underneath, above or onto the target
        dropPosY = event.pos().y()
        dropPosLocal = dropPosY%12

        extention = '.py'
        if os.path.isdir(self.draggedFrom):
            extention = ''

        if dropPosLocal < 6:
            #above
            offset = 0

        else:
            #underneath
            offset = 1
        print os.path.basename(self.draggedTo), os.path.basename(self.draggedFrom)
        if os.path.dirname(self.draggedTo) == os.path.dirname(self.draggedFrom):

            if int(os.path.basename(self.draggedTo)[:3]) > int(os.path.basename(self.draggedFrom)[:3]):
                offset -= 1

        if folder:
            if not 2 <= dropPosLocal <= 9:
                folder = False


        #iterate over all the files stored on disk and rename them
        self.folderContent = []        
        self.iterateFolder(self.scope)

        #rename everything to tmp
        for i in self.folderContent:
            os.rename(i,i+'.tmp')

        #rename/move the files that were reordered by the user
        if not folder:
            baseName = int(os.path.basename(self.draggedTo)[:3]) + offset
            baseName = max(1,baseName)
            baseName = str(baseName).zfill(3) + extention
        else:
            baseName = '001' + extention

        subfolders = os.path.dirname(self.draggedTo).replace(os.path.dirname(self.scope),'').split('/')
        subfoldersString = ''.join(['/%s.tmp'%i for i in subfolders if i != ''])
        destinationFolder = os.path.dirname(self.scope) + subfoldersString + '/'
        destinationLocation = destinationFolder + baseName

        try:
            os.rename(self.draggedFrom + '.tmp', destinationLocation)
        except:
            pass

        #iterate over content as its currently stored on disk
        self.folderContent = []
        for baseFolder, folders, files in os.walk(self.scope):
            allContent =  []
            for i in folders + files:
                if '.tmp' in i and i[0] not in ['.','_']:
                    allContent.append(i)
            self.folderContent.insert(0,[baseFolder,sorted(allContent)])

        #remove the tmp tag from all the other files and give them a proper name again
        for content in self.folderContent:
            baseFolder = content[0]
            counter = 1
            for i in content[1]:
                
                if '.py' in i:
                    fileExtention = '.py'
                else:
                    fileExtention = ''

                newName = str(counter).zfill(3) 
                currentFolderContent = os.listdir(baseFolder)
                while newName in currentFolderContent or newName + '.py' in currentFolderContent:
                    counter += 1
                    newName = str(counter).zfill(3) 
            
                counter += 1
                os.rename(baseFolder + '/' + i,baseFolder + '/' + newName + fileExtention)

        #make sure the content of both the source and destination directory are named correctly
        for i in list(set([destinationFolder, os.path.dirname(self.draggedFrom)])):
            repairHotbox(folder = i, recursive = False, message = False)

        #repopulate the tree
        self.populateTree(event.pos())

    #--------------------------------------------------------------------------------------------------
    #hotbox items tree actions
    #--------------------------------------------------------------------------------------------------

    def addItem(self, folder = False):
        '''
        Create new item for selected nodeclass
        '''

        #make sure all the files inside the folder are named correctly
        repairHotbox(folder = self.scope, recursive = False, message = False)

        #loop over content of folder to find an appropriate name for the new item
        counter = 1
        newFileName = '001'
        while newFileName in [i[:3] for i in sorted(os.listdir(self.scope)) if i[0] not in ['.','_']]:
            counter += 1
            newFileName = str(counter).zfill(3)

        itemPath = self.scope + newFileName

        if not folder:
            itemName = 'New Item'

            newFileContent = fileHeader(itemName).getHeader()
            currentFile = open(itemPath + '.py', 'w')
            currentFile.write(newFileContent)
            currentFile.close()

        else:
            itemName = 'New Menu'

            os.mkdir(itemPath)
            currentFile = open(itemPath + '/_name.json', 'w')
            currentFile.write(itemName)
            currentFile.close()



        self.populateTree()

        #select the new item
        self.collapseAll()
        self.setCurrentIndex(self.indexAt(QtCore.QPoint(1,(self.dataModel.rowCount()-1)*12)))
        self.expandAll()

        print

    def removeItem(self):
        '''
        Move selected items to the _old folder.
        '''
        try:

            currentItem = self.selectedIndexes()[0].row()

            for path in  self.selectedItemsPaths:

                oldFolder = self.scope + '_old/'

                if not os.path.isdir(oldFolder):
                    os.mkdir(oldFolder)

                currentTime = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                newFileName = currentTime

                counter = 1
                while newFileName in sorted(os.listdir(oldFolder)):
                    newFileName = currentTime + '_%s'%str(counter).zfill(3)
                    counter += 1

                shutil.move(path, oldFolder + newFileName)

            #make sure all the files inside the folder are named correctly
            changedFolder = os.path.dirname(path)
            repairHotbox(folder = changedFolder, recursive = False, message = False)

            self.populateTree()

            #select the new item
            if currentItem > 0:
                self.collapseAll()
                self.setCurrentIndex(self.indexAt(QtCore.QPoint(1,(currentItem-1)*12)))
                self.expandAll()

        except:
            pass

    def copyItem(self):
        '''
        Place the selected items in the class' clipboard
        '''
        try:
            self.clipboard = []

            for path in self.selectedItemsPaths:
                self.clipboard.append(path)
        except:
            pass

    def pasteItem(self):
        '''
        Copy the items stored in the class' clipboard to the current folder
        '''

        if len(self.clipboard) > 0:

            #make sure all the files inside the folder are named correctly
            repairHotbox(folder = self.scope, recursive = False, message = False)

            for path in self.clipboard:

                fileList = sorted([i[:3] for i in os.listdir(os.path.dirname(path)) if i[0] not in ['.','_']])

                newFileName = '001'

                counter = 1
                while newFileName in fileList:
                    counter += 1
                    newFileName = str(counter).zfill(3)

                if path.endswith('.py'):
                    shutil.copy2(path, self.scope + newFileName + '.py')

                else:
                    shutil.copytree(path, self.scope + newFileName )



            self.populateTree()

    def duplicateItem(self):
        '''
        Duplicate the currently selected items.
        '''
        tmpClipboard = self.clipboard
        self.copyItem()
        self.pasteItem()
        self.clipboard = tmpClipboard

class QStandardItemChild(QtGui.QStandardItem):
    def __init__(self, name, path):

        super(QStandardItemChild, self).__init__()

        self.richTextName = name

        #convert rich text to plain text
        if '<' in name:

            richToPlain = re.compile('<[^>]*>').sub('',name)

            if len(richToPlain) > 0:
                name = richToPlain
            else:
                #if image tag was used
                if 'img ' in name:
                    richToPlain = name.replace(' ','').replace('<imgsrc=','').replace("'",'"')
                    richToPlain = richToPlain.split('">')[0]
                    richToPlain = os.path.basename(richToPlain)
                    if len(richToPlain) > 0:
                        name = richToPlain

        #if the name has a whitespace at the beginning due to the conversion to plain text, get rid of them.
        while name.startswith(' '):
            name = name[1:]

        self.setText(name)

        #path points to the place the file is currently stored
        #parent points to the place in the gui

        self.path = path

        self.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsDragEnabled)

        if os.path.isdir(self.path):
            self.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled)

        parentObject = self.parent()
        if parentObject != None:
            self.currentGuiPath = parentObject.path

class QLabelButton(QtGui.QLabel):
    def __init__(self,name):
        super(QLabelButton, self).__init__()
        
        self.setToolTip(name)

        iconFolder = preferencesNode.knob('iconLocation').value()
        while iconFolder[-1] == '/':
            iconFolder = iconFolder[:-1]

        self.imageFile = '%s/hotbox_%s'%(iconFolder,name)
        
        self.setPixmap(QtGui.QPixmap('%s_neutral.png'%self.imageFile))


    def enterEvent(self, event):
        self.setPixmap(QtGui.QPixmap('%s_hover.png'%self.imageFile))

    def leaveEvent(self,event):
        self.setPixmap(QtGui.QPixmap('%s_neutral.png'%self.imageFile))

    def mousePressEvent(self,event):
        self.setPixmap(QtGui.QPixmap('%s_clicked.png'%self.imageFile))

    def mouseReleaseEvent(self,event):
        self.emit(QtCore.SIGNAL('buttonClicked()'))
        self.setPixmap(QtGui.QPixmap('%s_hover.png'%self.imageFile))

#------------------------------------------------------------------------------------------------------
#rename  dialog
#------------------------------------------------------------------------------------------------------

class renameDialog(QtGui.QWidget):
    '''
    Dialog that will pop up when the rename button in the manager is clicked.
    '''

    def __init__(self, mode = 'rename'):

        super(renameDialog, self).__init__()

        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        if mode == 'new':
            renameButtonLabel = 'Create'
            self.setWindowTitle('Assign new hotbox class')

        else:
            renameButtonLabel = 'Rename'
            self.setWindowTitle('Rename hotbox class')

        masterLayout = QtGui.QVBoxLayout()
        buttonsLayout = QtGui.QHBoxLayout()

        self.newNameLineEdit = QtGui.QLineEdit()
        self.newNameLineEdit.setText(hotboxManagerInstance.currentItem) 
        self.newNameLineEdit.selectAll()



        renameButton = QtGui.QPushButton(renameButtonLabel)
        cancelButton = QtGui.QPushButton('Cancel')

        renameButton.clicked.connect(self.renameButtonClicked)
        cancelButton.clicked.connect(self.closeRenameDialog)

        buttonsLayout.addWidget(renameButton)
        buttonsLayout.addWidget(cancelButton)

        masterLayout.addWidget(self.newNameLineEdit)
        masterLayout.addLayout(buttonsLayout)
        self.setLayout(masterLayout)


        self.enterAction = QtGui.QAction(self)
        self.enterAction.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Return))
        self.enterAction.triggered.connect(self.renameButtonClicked)
        self.addAction(self.enterAction)

        self.adjustSize()

        screenRes = QtGui.QDesktopWidget().screenGeometry()
        self.move(QtCore.QPoint(screenRes.width()/2,screenRes.height()/2)-QtCore.QPoint((self.width()/2),(self.height()/2)))


    def renameButtonClicked(self):

        shutil.move(hotboxManagerInstance.path + '/' + hotboxManagerInstance.currentItem, hotboxManagerInstance.path + '/' + self.newNameLineEdit.text())

        hotboxManagerInstance.builtClassesList(True)

        self.closeRenameDialog()

    def closeRenameDialog(self):
        self.close()
        global renameDialogInstance
        renameDialogInstance = None
        return False

#------------------------------------------------------------------------------------------------------
#Dialog with contact informaton
#------------------------------------------------------------------------------------------------------

class aboutDialog(QtGui.QWidget):
    '''
    Dialog that will show some information about the current version of the Hotbox.
    '''

    def __init__(self):

        super(aboutDialog, self).__init__()

        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        masterLayout = QtGui.QVBoxLayout()

        self.setFixedHeight(250)
        self.setFixedWidth(230)

        aboutHotbox = QtGui.QLabel()
        aboutHotbox.setPixmap(QtGui.QPixmap(preferencesNode.knob('iconLocation').value() + '/icon.png'))

        aboutVersion = QtGui.QLabel(version)
        aboutDate = QtGui.QLabel(releaseDate)
        aboutDownload = QWebLink('Nukepedia','http://www.nukepedia.com/python/ui/w_hotbox/')
        aboutName = QtGui.QLabel('Wouter Gilsing')
        aboutMail = QWebLink('woutergilsing@hotmail.com','mailto:woutergilsing@hotmail.com?body=')
        aboutWeb = QWebLink('woutergilsing.com','http://www.woutergilsing.com')


        fontSize = 0.3
        font = 'Verdana'
        mediumFont = QtGui.QFont(font, fontSize * 40)
        smallFont = QtGui.QFont(font, fontSize * 30)


        aboutVersion.setFont(smallFont)
        aboutDate.setFont(smallFont)
        aboutDownload.setFont(mediumFont)
        aboutName.setFont(smallFont)
        aboutName.setAlignment(QtCore.Qt.AlignRight)
        aboutMail.setFont(smallFont)
        aboutMail.setAlignment(QtCore.Qt.AlignRight)
        aboutWeb.setFont(smallFont)
        aboutWeb.setAlignment(QtCore.Qt.AlignRight)

        masterLayout.addWidget(aboutHotbox)
        masterLayout.addWidget(aboutVersion)
        masterLayout.addWidget(aboutDate) 
        masterLayout.addSpacing(40)
        masterLayout.addWidget(aboutDownload)
        masterLayout.addSpacing(20) 
        masterLayout.addWidget(aboutName)
        masterLayout.addWidget(aboutMail)
        masterLayout.addWidget(aboutWeb)

        self.setLayout(masterLayout)

        self.adjustSize()

        screenRes = QtGui.QDesktopWidget().screenGeometry()
        self.move(QtCore.QPoint(screenRes.width()/2,screenRes.height()/2)-QtCore.QPoint((self.width()/2),(self.height()/2)))


class QWebLink(QtGui.QLabel):
    def __init__(self, name, link):
        super(QWebLink, self).__init__()

        self.link = link
        if self.link.startswith('mailto:'):
            self.link = self.link + self.composeEmail()
        self.setToolTip(self.link)

        self.origText = name
        self.setText(self.origText)

        self.active = False

    def composeEmail(self):

        import platform

        hotboxVersion = 'W_hotbox v%s (%s)'%(version, releaseDate)
        nukeVersion = 'Nuke ' + nuke.NUKE_VERSION_STRING

        osType = platform.system()

        if osType == 'Windows':
            osName = 'Windows'
            osVersion = platform.win32_ver()[0]

        elif osType == 'Darwin':
            osName = 'OSX'
            osVersion = platform.mac_ver()[0]
        else:
            osName = platform.linux_distribution(full_distribution_name=0)[0]
            osVersion = platform.linux_distribution(full_distribution_name=0)[1]

        operatingSystem = ' '.join([osName,osVersion])

        return '\n'.join(["I'm running:\n",hotboxVersion,nukeVersion,operatingSystem])


    def activate(self):
        self.setText('<font color = #f7931e>%s</font>'%self.origText)

    def deactivate(self):
        self.setText('<font color = #c8c8c8>%s</font>'%self.origText)

    def enterEvent(self, event):
        self.activate()

    def leaveEvent(self,event):
        self.deactivate()


    def mouseReleaseEvent(self,event):

        webbrowser.open(self.link)

#------------------------------------------------------------------------------------------------------
#Top portion of the files that will be generated
#------------------------------------------------------------------------------------------------------

class fileHeader():
    def __init__(self,name):
        self.text = '\n'.join(['#----------------------------------------------------------------------------------------------------------',
                                '#',
                                '# AUTOMATICALLY GENERATED FILE TO BE USED BY W_HOTBOX',
                                '#',
                                '# NAME: %s'%name,
                                '#',
                                '#----------------------------------------------------------------------------------------------------------\n\n'])
    def getHeader(self):
        return self.text

#------------------------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------------------------
#Repair
#------------------------------------------------------------------------------------------------------

class repairHotbox():

    #--------------------------------------------------------------------------------------------------
    def __init__(self, folder = None, recursive = True, message = True):

        #set root folder
        if folder == None:
            self.root = preferencesNode.knob('hotboxLocation').value()
        else:
            self.root = folder

        #make sure the root ends with '/'
        while self.root[-1] != '/':
            self.root += '/'

        #compose list of folders
        if folder == None:
            self.dirList = ['%sAll/'%self.root]
        else:
            self.dirList = []

        if recursive:
            self.indexFolders(self.root, folder)
        else:
            self.dirList = [self.root]

        #append every filename with a 'tmp' so no files will be overwritten.
        for i in self.dirList:
            self.tempifyFolder(i)

        #reset dirlist
        if folder == None:
            self.dirList = ['%sAll/'%self.root]
        else:
            self.dirList = []

        if recursive:
            self.indexFolders(self.root, folder)
        else:
            self.dirList = [self.root]

        #give every file its proper name

        repairProgress = 100.0 / max(1.0,len(self.dirList))

        for index, i in enumerate(self.dirList):
            if message:
                repairProgressBar = nuke.ProgressTask('Repairing W_hotbox...')

                repairProgressBar.setProgress(int(index * repairProgress))
                repairProgressBar.setMessage(i)

            self.repairFolder(i)

        if message:
            nuke.message('Reparation succesfully')

    #--------------------------------------------------------------------------------------------------

    def indexFolders(self, path, folder):

        while path[-1] != '/':
            path += '/'

        level = len([i for i in path.replace(self.root,'').split('/') if len(i) > 0])

        for i in [path + i + '/' for i in os.listdir(path) if i[0] not in ['.','_']]:

            if os.path.isdir(i):

                if level == 0 and folder == None:
                    pass
                else:
                    self.dirList.insert(0, i)
                self.indexFolders(i, folder)

    #--------------------------------------------------------------------------------------------------

    def tempifyFolder(self, folderPath):

        folderContent = [folderPath + i for i in os.listdir(folderPath) if i[0] not in [".", "_"]]
        for i in sorted(folderContent):
            os.rename(i, i + '.tmp')

    #--------------------------------------------------------------------------------------------------

    def repairFolder(self, folderPath):

        folderContent = [folderPath + i for i in os.listdir(folderPath) if i[0] not in [".", "_"]]

        for index, oldFile in enumerate(sorted(folderContent)):
            extension = ''

            if os.path.isfile(oldFile):
                extension = '.py'

            newFile = folderPath + str(index + 1).zfill(3)+ extension

            os.rename(oldFile, newFile)

#--------------------------------------------------------------------------------------------------

def clearHotboxManager(sections = ['Single','Multiple','All']):
    '''
    Clear the buttons of the section specified. By default all buttons will be erased.
    '''

    message = "This will erase all of the excisting buttons added to the hotbox. This action can't be undone.\n\nAre you sure?"
    if len(sections) == 1:
        message = "This will erase all of the buttons added to the '%s'-section of the hotbox. This can't be undone.\n\nAre you sure?"%sections[0]

    if not nuke.ask(message):
        return

    hotboxLocation = preferencesNode.knob('hotboxLocation').value()
    if hotboxLocation[-1] != '/':
        hotboxLocation += '/'

    clearProgressBar = nuke.ProgressTask('Clearing W_hotbox...')

    clearProgressIncrement = 100/(len(sections)*2)
    clearProgress = 0.0
    clearProgressBar.setProgress(int(clearProgress))

    #Empty folders
    for i in sections:
        clearProgress += clearProgressIncrement
        clearProgressBar.setProgress(int(clearProgress))
        clearProgressBar.setMessage('Clearing ' + i)

        try:
            shutil.rmtree(hotboxLocation + i)
        except:
            pass

    #Rebuilt folders
    for i in sections:
        clearProgress += clearProgressIncrement
        clearProgressBar.setProgress(int(clearProgress))
        clearProgressBar.setMessage('Rebuilding ' + i)

        try:
            os.mkdir(hotboxLocation + i)
        except:
            pass


#--------------------------------------------------------------------------------------------------

hotboxManagerInstance = None
renameDialogInstance = None
aboutDialogInstance = None

def showHotboxManager(path = ''):
    '''
    Launch an instance of the hotbox manager
    '''
    global hotboxManagerInstance
    #check if the manager is opened already, if so close that instance.
    if hotboxManagerInstance != None:
        hotboxManagerInstance.close()

    if path == '':
        path = preferencesNode.knob('hotboxLocation').value()
        
    if path[-1] != '/':
        path += '/' 

    hotboxManagerInstance = hotboxManager(path)
    hotboxManagerInstance.show()