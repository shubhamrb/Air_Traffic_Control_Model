
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_recordAtisDialog(object):
    def setupUi(self, recordAtisDialog):
        recordAtisDialog.setObjectName("recordAtisDialog")
        recordAtisDialog.resize(451, 402)
        self.verticalLayout = QtWidgets.QVBoxLayout(recordAtisDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.groupBox = QtWidgets.QGroupBox(recordAtisDialog)
        self.groupBox.setObjectName("groupBox")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout(self.groupBox)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.notepad_textEdit = QtWidgets.QPlainTextEdit(self.groupBox)
        self.notepad_textEdit.setTabChangesFocus(True)
        self.notepad_textEdit.setObjectName("notepad_textEdit")
        self.horizontalLayout_4.addWidget(self.notepad_textEdit)
        self.verticalLayout.addWidget(self.groupBox)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.label_3 = QtWidgets.QLabel(recordAtisDialog)
        self.label_3.setObjectName("label_3")
        self.horizontalLayout_3.addWidget(self.label_3)
        self.infoLetter_edit = QtWidgets.QLineEdit(recordAtisDialog)
        self.infoLetter_edit.setMaxLength(1)
        self.infoLetter_edit.setAlignment(QtCore.Qt.AlignCenter)
        self.infoLetter_edit.setObjectName("infoLetter_edit")
        self.horizontalLayout_3.addWidget(self.infoLetter_edit)
        self.record_button = QtWidgets.QPushButton(recordAtisDialog)
        self.record_button.setCheckable(False)
        self.record_button.setObjectName("record_button")
        self.horizontalLayout_3.addWidget(self.record_button)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label_2 = QtWidgets.QLabel(recordAtisDialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout.addWidget(self.label_2)
        self.status_infoLabel = QtWidgets.QLabel(recordAtisDialog)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.status_infoLabel.setFont(font)
        self.status_infoLabel.setObjectName("status_infoLabel")
        self.horizontalLayout.addWidget(self.status_infoLabel)
        self.verticalLayout.addLayout(self.horizontalLayout)
        spacerItem1 = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.verticalLayout.addItem(spacerItem1)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem2)
        self.close_button = QtWidgets.QPushButton(recordAtisDialog)
        self.close_button.setObjectName("close_button")
        self.horizontalLayout_2.addWidget(self.close_button)
        spacerItem3 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem3)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.label_3.setBuddy(self.infoLetter_edit)

        self.retranslateUi(recordAtisDialog)
        QtCore.QMetaObject.connectSlotsByName(recordAtisDialog)

    def retranslateUi(self, recordAtisDialog):
        _translate = QtCore.QCoreApplication.translate
        recordAtisDialog.setWindowTitle(_translate("recordAtisDialog", "Record ATIS"))
        self.groupBox.setTitle(_translate("recordAtisDialog", "Notepad"))
        self.label_3.setText(_translate("recordAtisDialog", "Information letter:"))
        self.infoLetter_edit.setText(_translate("recordAtisDialog", "A"))
        self.record_button.setToolTip(_translate("recordAtisDialog", "Record!"))
        self.record_button.setText(_translate("recordAtisDialog", "REC"))
        self.label_2.setText(_translate("recordAtisDialog", "Status:"))
        self.status_infoLabel.setText(_translate("recordAtisDialog", "Idle"))
        self.close_button.setText(_translate("recordAtisDialog", "Close"))

