from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_startStudentSessionDialog(object):
    def setupUi(self, startStudentSessionDialog):
        startStudentSessionDialog.setObjectName("startStudentSessionDialog")
        startStudentSessionDialog.resize(236, 109)
        self.verticalLayout = QtWidgets.QVBoxLayout(startStudentSessionDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.formLayout = QtWidgets.QFormLayout()
        self.formLayout.setObjectName("formLayout")
        self.label = QtWidgets.QLabel(startStudentSessionDialog)
        self.label.setObjectName("label")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label)
        self.teachingServiceHost_edit = QtWidgets.QLineEdit(startStudentSessionDialog)
        self.teachingServiceHost_edit.setObjectName("teachingServiceHost_edit")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.teachingServiceHost_edit)
        self.label_3 = QtWidgets.QLabel(startStudentSessionDialog)
        self.label_3.setObjectName("label_3")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_3)
        self.teachingServicePort_edit = QtWidgets.QSpinBox(startStudentSessionDialog)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.teachingServicePort_edit.sizePolicy().hasHeightForWidth())
        self.teachingServicePort_edit.setSizePolicy(sizePolicy)
        self.teachingServicePort_edit.setMaximum(99999)
        self.teachingServicePort_edit.setObjectName("teachingServicePort_edit")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.teachingServicePort_edit)
        self.verticalLayout.addLayout(self.formLayout)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.cancel_button = QtWidgets.QPushButton(startStudentSessionDialog)
        self.cancel_button.setObjectName("cancel_button")
        self.horizontalLayout.addWidget(self.cancel_button)
        self.OK_button = QtWidgets.QPushButton(startStudentSessionDialog)
        self.OK_button.setDefault(True)
        self.OK_button.setObjectName("OK_button")
        self.horizontalLayout.addWidget(self.OK_button)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.label.setBuddy(self.teachingServiceHost_edit)
        self.label_3.setBuddy(self.teachingServicePort_edit)

        self.retranslateUi(startStudentSessionDialog)
        self.cancel_button.clicked.connect(startStudentSessionDialog.reject)
        self.OK_button.clicked.connect(startStudentSessionDialog.accept)
        QtCore.QMetaObject.connectSlotsByName(startStudentSessionDialog)
        startStudentSessionDialog.setTabOrder(self.teachingServiceHost_edit, self.teachingServicePort_edit)
        startStudentSessionDialog.setTabOrder(self.teachingServicePort_edit, self.OK_button)
        startStudentSessionDialog.setTabOrder(self.OK_button, self.cancel_button)

    def retranslateUi(self, startStudentSessionDialog):
        _translate = QtCore.QCoreApplication.translate
        startStudentSessionDialog.setWindowTitle(_translate("startStudentSessionDialog", "Start a student session"))
        self.label.setText(_translate("startStudentSessionDialog", "Teacher host:"))
        self.label_3.setText(_translate("startStudentSessionDialog", "Service port:"))
        self.cancel_button.setText(_translate("startStudentSessionDialog", "Cancel"))
        self.OK_button.setText(_translate("startStudentSessionDialog", "OK"))
