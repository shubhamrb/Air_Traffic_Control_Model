from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_cpdlcPanel(object):
    def setupUi(self, cpdlcPanel):
        cpdlcPanel.setObjectName("cpdlcPanel")
        cpdlcPanel.resize(304, 316)
        self.verticalLayout = QtWidgets.QVBoxLayout(cpdlcPanel)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.liveConnections_radioButton = QtWidgets.QRadioButton(cpdlcPanel)
        self.liveConnections_radioButton.setObjectName("liveConnections_radioButton")
        self.horizontalLayout.addWidget(self.liveConnections_radioButton)
        self.historyWith_radioButton = QtWidgets.QRadioButton(cpdlcPanel)
        self.historyWith_radioButton.setObjectName("historyWith_radioButton")
        self.horizontalLayout.addWidget(self.historyWith_radioButton)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.connections_tableView = QtWidgets.QTableView(cpdlcPanel)
        self.connections_tableView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.connections_tableView.setShowGrid(False)
        self.connections_tableView.setObjectName("connections_tableView")
        self.connections_tableView.horizontalHeader().setVisible(False)
        self.connections_tableView.horizontalHeader().setStretchLastSection(True)
        self.connections_tableView.verticalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.connections_tableView)

        self.retranslateUi(cpdlcPanel)
        QtCore.QMetaObject.connectSlotsByName(cpdlcPanel)

    def retranslateUi(self, cpdlcPanel):
        _translate = QtCore.QCoreApplication.translate
        self.liveConnections_radioButton.setText(_translate("cpdlcPanel", "Live data links"))
        self.historyWith_radioButton.setText(_translate("cpdlcPanel", "History with last selection"))

