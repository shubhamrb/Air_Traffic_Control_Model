from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_rwyUseDialog(object):
    def setupUi(self, rwyUseDialog):
        rwyUseDialog.setObjectName("rwyUseDialog")
        rwyUseDialog.resize(315, 412)
        self.verticalLayout = QtWidgets.QVBoxLayout(rwyUseDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.groupBox = QtWidgets.QGroupBox(rwyUseDialog)
        self.groupBox.setObjectName("groupBox")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.tableView = QtWidgets.QTableView(self.groupBox)
        self.tableView.setObjectName("tableView")
        self.tableView.horizontalHeader().setStretchLastSection(True)
        self.tableView.verticalHeader().setVisible(False)
        self.verticalLayout_2.addWidget(self.tableView)
        self.verticalLayout.addWidget(self.groupBox)
        self.avoidOppositeRunways_tickBox = QtWidgets.QCheckBox(rwyUseDialog)
        self.avoidOppositeRunways_tickBox.setChecked(True)
        self.avoidOppositeRunways_tickBox.setObjectName("avoidOppositeRunways_tickBox")
        self.verticalLayout.addWidget(self.avoidOppositeRunways_tickBox)
        self.buttonBox = QtWidgets.QDialogButtonBox(rwyUseDialog)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(rwyUseDialog)
        QtCore.QMetaObject.connectSlotsByName(rwyUseDialog)
        rwyUseDialog.setTabOrder(self.tableView, self.buttonBox)

    def retranslateUi(self, rwyUseDialog):
        _translate = QtCore.QCoreApplication.translate
        rwyUseDialog.setWindowTitle(_translate("rwyUseDialog", "Runway use"))
        self.groupBox.setTitle(_translate("rwyUseDialog", "Select runway use"))
        self.avoidOppositeRunways_tickBox.setText(_translate("rwyUseDialog", "Deselect opposite runways"))

