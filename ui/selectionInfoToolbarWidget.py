
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_selectionInfoToolbarWidget(object):
    def setupUi(self, selectionInfoToolbarWidget):
        selectionInfoToolbarWidget.setObjectName("selectionInfoToolbarWidget")
        selectionInfoToolbarWidget.resize(379, 43)
        self.horizontalLayout = QtWidgets.QHBoxLayout(selectionInfoToolbarWidget)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.selection_info = QtWidgets.QLabel(selectionInfoToolbarWidget)
        self.selection_info.setObjectName("selection_info")
        self.horizontalLayout.addWidget(self.selection_info)
        self.cheatContact_toggle = QtWidgets.QToolButton(selectionInfoToolbarWidget)
        self.cheatContact_toggle.setCheckable(True)
        self.cheatContact_toggle.setObjectName("cheatContact_toggle")
        self.horizontalLayout.addWidget(self.cheatContact_toggle)
        self.ignoreContact_toggle = QtWidgets.QToolButton(selectionInfoToolbarWidget)
        self.ignoreContact_toggle.setCheckable(True)
        self.ignoreContact_toggle.setObjectName("ignoreContact_toggle")
        self.horizontalLayout.addWidget(self.ignoreContact_toggle)

        self.retranslateUi(selectionInfoToolbarWidget)
        QtCore.QMetaObject.connectSlotsByName(selectionInfoToolbarWidget)
        selectionInfoToolbarWidget.setTabOrder(self.cheatContact_toggle, self.ignoreContact_toggle)

    def retranslateUi(self, selectionInfoToolbarWidget):
        _translate = QtCore.QCoreApplication.translate
        selectionInfoToolbarWidget.setWindowTitle(_translate("selectionInfoToolbarWidget", "Selection info"))
        self.selection_info.setText(_translate("selectionInfoToolbarWidget", "###"))
        self.cheatContact_toggle.setToolTip(_translate("selectionInfoToolbarWidget", "Cheat"))
        self.cheatContact_toggle.setText(_translate("selectionInfoToolbarWidget", "C"))
        self.ignoreContact_toggle.setToolTip(_translate("selectionInfoToolbarWidget", "Ignore"))
        self.ignoreContact_toggle.setText(_translate("selectionInfoToolbarWidget", "I"))

