
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_rackVisibilityDialog(object):
    def setupUi(self, rackVisibilityDialog):
        rackVisibilityDialog.setObjectName("rackVisibilityDialog")
        rackVisibilityDialog.resize(315, 317)
        self.verticalLayout = QtWidgets.QVBoxLayout(rackVisibilityDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.groupBox = QtWidgets.QGroupBox(rackVisibilityDialog)
        self.groupBox.setObjectName("groupBox")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.tableView = QtWidgets.QTableView(self.groupBox)
        self.tableView.setShowGrid(False)
        self.tableView.setObjectName("tableView")
        self.tableView.horizontalHeader().setVisible(False)
        self.tableView.verticalHeader().setVisible(False)
        self.verticalLayout_2.addWidget(self.tableView)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtWidgets.QLabel(self.groupBox)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.selectAll_button = QtWidgets.QToolButton(self.groupBox)
        self.selectAll_button.setObjectName("selectAll_button")
        self.horizontalLayout.addWidget(self.selectAll_button)
        self.selectNone_button = QtWidgets.QToolButton(self.groupBox)
        self.selectNone_button.setObjectName("selectNone_button")
        self.horizontalLayout.addWidget(self.selectNone_button)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.verticalLayout_2.addLayout(self.horizontalLayout)
        self.verticalLayout.addWidget(self.groupBox)
        self.buttonBox = QtWidgets.QDialogButtonBox(rackVisibilityDialog)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(rackVisibilityDialog)
        QtCore.QMetaObject.connectSlotsByName(rackVisibilityDialog)
        rackVisibilityDialog.setTabOrder(self.tableView, self.selectAll_button)
        rackVisibilityDialog.setTabOrder(self.selectAll_button, self.selectNone_button)
        rackVisibilityDialog.setTabOrder(self.selectNone_button, self.buttonBox)

    def retranslateUi(self, rackVisibilityDialog):
        _translate = QtCore.QCoreApplication.translate
        rackVisibilityDialog.setWindowTitle(_translate("rackVisibilityDialog", "Move racks"))
        self.groupBox.setTitle(_translate("rackVisibilityDialog", "Move racks to this view"))
        self.label.setText(_translate("rackVisibilityDialog", "Select:"))
        self.selectAll_button.setText(_translate("rackVisibilityDialog", "all"))
        self.selectNone_button.setText(_translate("rackVisibilityDialog", "none"))

