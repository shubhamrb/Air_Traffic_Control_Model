from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_discardedStripsDialog(object):
    def setupUi(self, discardedStripsDialog):
        discardedStripsDialog.setObjectName("discardedStripsDialog")
        discardedStripsDialog.resize(387, 292)
        self.verticalLayout = QtWidgets.QVBoxLayout(discardedStripsDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.strip_view = QtWidgets.QListView(discardedStripsDialog)
        self.strip_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.strip_view.setObjectName("strip_view")
        self.verticalLayout.addWidget(self.strip_view)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.clear_button = QtWidgets.QToolButton(discardedStripsDialog)
        self.clear_button.setObjectName("clear_button")
        self.horizontalLayout_2.addWidget(self.clear_button)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.close_button = QtWidgets.QPushButton(discardedStripsDialog)
        self.close_button.setObjectName("close_button")
        self.horizontalLayout_2.addWidget(self.close_button)
        self.recall_button = QtWidgets.QPushButton(discardedStripsDialog)
        self.recall_button.setObjectName("recall_button")
        self.horizontalLayout_2.addWidget(self.recall_button)
        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.retranslateUi(discardedStripsDialog)
        QtCore.QMetaObject.connectSlotsByName(discardedStripsDialog)
        discardedStripsDialog.setTabOrder(self.strip_view, self.clear_button)
        discardedStripsDialog.setTabOrder(self.clear_button, self.recall_button)
        discardedStripsDialog.setTabOrder(self.recall_button, self.close_button)

    def retranslateUi(self, discardedStripsDialog):
        _translate = QtCore.QCoreApplication.translate
        self.clear_button.setText(_translate("discardedStripsDialog", "Clear list"))
        self.close_button.setText(_translate("discardedStripsDialog", "Close"))
        self.recall_button.setText(_translate("discardedStripsDialog", "Recall selected"))

