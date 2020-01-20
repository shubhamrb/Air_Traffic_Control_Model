from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_xpdrCodeSelectorWidget(object):
    def setupUi(self, xpdrCodeSelectorWidget):
        xpdrCodeSelectorWidget.setObjectName("xpdrCodeSelectorWidget")
        xpdrCodeSelectorWidget.resize(163, 24)
        self.horizontalLayout = QtWidgets.QHBoxLayout(xpdrCodeSelectorWidget)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.xpdrCode_edit = XpdrCodeSpinBox(xpdrCodeSelectorWidget)
        self.xpdrCode_edit.setObjectName("xpdrCode_edit")
        self.horizontalLayout.addWidget(self.xpdrCode_edit)
        self.xpdrRange_select = QtWidgets.QComboBox(xpdrCodeSelectorWidget)
        self.xpdrRange_select.setObjectName("xpdrRange_select")
        self.xpdrRange_select.addItem("")
        self.horizontalLayout.addWidget(self.xpdrRange_select)

        self.retranslateUi(xpdrCodeSelectorWidget)
        QtCore.QMetaObject.connectSlotsByName(xpdrCodeSelectorWidget)

    def retranslateUi(self, xpdrCodeSelectorWidget):
        _translate = QtCore.QCoreApplication.translate
        self.xpdrRange_select.setItemText(0, _translate("xpdrCodeSelectorWidget", "From range..."))

from gui.widgets.basicWidgets import XpdrCodeSpinBox
