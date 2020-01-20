from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_notepadPane(object):
    def setupUi(self, notepadPane):
        notepadPane.setObjectName("notepadPane")
        notepadPane.resize(383, 531)
        self.verticalLayout = QtWidgets.QVBoxLayout(notepadPane)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_2 = QtWidgets.QLabel(notepadPane)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_2.setFont(font)
        self.label_2.setObjectName("label_2")
        self.verticalLayout.addWidget(self.label_2)
        self.generalNotes_textEdit = QtWidgets.QPlainTextEdit(notepadPane)
        self.generalNotes_textEdit.setObjectName("generalNotes_textEdit")
        self.verticalLayout.addWidget(self.generalNotes_textEdit)
        spacerItem = QtWidgets.QSpacerItem(20, 5, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.verticalLayout.addItem(spacerItem)
        self.label = QtWidgets.QLabel(notepadPane)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.localNotes_textEdit = QtWidgets.QPlainTextEdit(notepadPane)
        self.localNotes_textEdit.setObjectName("localNotes_textEdit")
        self.verticalLayout.addWidget(self.localNotes_textEdit)
        self.label_2.setBuddy(self.generalNotes_textEdit)
        self.label.setBuddy(self.localNotes_textEdit)

        self.retranslateUi(notepadPane)
        QtCore.QMetaObject.connectSlotsByName(notepadPane)

    def retranslateUi(self, notepadPane):
        _translate = QtCore.QCoreApplication.translate
        notepadPane.setWindowTitle(_translate("notepadPane", "Form"))
        self.label_2.setText(_translate("notepadPane", "General notes"))
        self.generalNotes_textEdit.setToolTip(_translate("notepadPane", "Notes saved across all sessions"))
        self.label.setText(_translate("notepadPane", "Local notes"))
        self.localNotes_textEdit.setToolTip(_translate("notepadPane", "Notes saved for this location only"))

