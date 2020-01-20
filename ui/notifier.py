

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_notifierFrame(object):
    def setupUi(self, notifierFrame):
        notifierFrame.setObjectName("notifierFrame")
        notifierFrame.resize(354, 270)
        self.verticalLayout = QtWidgets.QVBoxLayout(notifierFrame)
        self.verticalLayout.setObjectName("verticalLayout")
        self.notification_table = QtWidgets.QTableView(notifierFrame)
        self.notification_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.notification_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.notification_table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.notification_table.setShowGrid(False)
        self.notification_table.setWordWrap(False)
        self.notification_table.setObjectName("notification_table")
        self.notification_table.horizontalHeader().setVisible(False)
        self.notification_table.horizontalHeader().setStretchLastSection(True)
        self.notification_table.verticalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.notification_table)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.sounds_menuButton = QtWidgets.QToolButton(notifierFrame)
        self.sounds_menuButton.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.sounds_menuButton.setObjectName("sounds_menuButton")
        self.horizontalLayout.addWidget(self.sounds_menuButton)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.cleanUp_button = QtWidgets.QToolButton(notifierFrame)
        self.cleanUp_button.setObjectName("cleanUp_button")
        self.horizontalLayout.addWidget(self.cleanUp_button)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(notifierFrame)
        QtCore.QMetaObject.connectSlotsByName(notifierFrame)

    def retranslateUi(self, notifierFrame):
        _translate = QtCore.QCoreApplication.translate
        self.sounds_menuButton.setText(_translate("notifierFrame", "Sounds"))
        self.cleanUp_button.setText(_translate("notifierFrame", "Clear"))

