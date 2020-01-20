from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_fgcomEchoTestDialog(object):
    def setupUi(self, fgcomEchoTestDialog):
        fgcomEchoTestDialog.setObjectName("fgcomEchoTestDialog")
        fgcomEchoTestDialog.resize(253, 83)
        self.verticalLayout = QtWidgets.QVBoxLayout(fgcomEchoTestDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(fgcomEchoTestDialog)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.OK_button = QtWidgets.QDialogButtonBox(fgcomEchoTestDialog)
        self.OK_button.setOrientation(QtCore.Qt.Horizontal)
        self.OK_button.setStandardButtons(QtWidgets.QDialogButtonBox.Ok)
        self.OK_button.setObjectName("OK_button")
        self.verticalLayout.addWidget(self.OK_button)

        self.retranslateUi(fgcomEchoTestDialog)
        self.OK_button.accepted.connect(fgcomEchoTestDialog.accept)
        QtCore.QMetaObject.connectSlotsByName(fgcomEchoTestDialog)

    def retranslateUi(self, fgcomEchoTestDialog):
        _translate = QtCore.QCoreApplication.translate
        fgcomEchoTestDialog.setWindowTitle(_translate("fgcomEchoTestDialog", "FGCom echo test"))
        self.label.setText(_translate("fgcomEchoTestDialog", "Starting FGCOM..."))

