
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_routeSpecsLostDialog(object):
    def setupUi(self, routeSpecsLostDialog):
        routeSpecsLostDialog.setObjectName("routeSpecsLostDialog")
        routeSpecsLostDialog.resize(337, 149)
        self.verticalLayout = QtWidgets.QVBoxLayout(routeSpecsLostDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.message_label = QtWidgets.QLabel(routeSpecsLostDialog)
        self.message_label.setWordWrap(True)
        self.message_label.setObjectName("message_label")
        self.verticalLayout.addWidget(self.message_label)
        self.lostSpecs_box = QtWidgets.QLineEdit(routeSpecsLostDialog)
        self.lostSpecs_box.setReadOnly(True)
        self.lostSpecs_box.setObjectName("lostSpecs_box")
        self.verticalLayout.addWidget(self.lostSpecs_box)
        self.openStripDetailSheet_tickBox = QtWidgets.QCheckBox(routeSpecsLostDialog)
        self.openStripDetailSheet_tickBox.setObjectName("openStripDetailSheet_tickBox")
        self.verticalLayout.addWidget(self.openStripDetailSheet_tickBox)
        self.buttonBox = QtWidgets.QDialogButtonBox(routeSpecsLostDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(routeSpecsLostDialog)
        self.buttonBox.accepted.connect(routeSpecsLostDialog.accept)
        self.buttonBox.rejected.connect(routeSpecsLostDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(routeSpecsLostDialog)

    def retranslateUi(self, routeSpecsLostDialog):
        _translate = QtCore.QCoreApplication.translate
        routeSpecsLostDialog.setWindowTitle(_translate("routeSpecsLostDialog", "Route leg specs lost"))
        self.message_label.setText(_translate("routeSpecsLostDialog", "The following route leg specifications were lost after this modification.\n"
"You have a last chance to copy them below if you need them."))
        self.openStripDetailSheet_tickBox.setText(_translate("routeSpecsLostDialog", "Open corresponding strip detail sheet before closing dialog"))

