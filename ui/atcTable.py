

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_atcPane(object):
    def setupUi(self, atcPane):
        atcPane.setObjectName("atcPane")
        atcPane.resize(264, 242)
        self.verticalLayout = QtWidgets.QVBoxLayout(atcPane)
        self.verticalLayout.setObjectName("verticalLayout")
        self.ATC_view = AtcTableView(atcPane)
        self.ATC_view.setAcceptDrops(True)
        self.ATC_view.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)
        self.ATC_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.ATC_view.setShowGrid(False)
        self.ATC_view.setObjectName("ATC_view")
        self.ATC_view.horizontalHeader().setVisible(False)
        self.ATC_view.verticalHeader().setVisible(False)
        self.ATC_view.verticalHeader().setDefaultSectionSize(35)
        self.verticalLayout.addWidget(self.ATC_view)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.publiciseFrequency_tickBox = QtWidgets.QCheckBox(atcPane)
        self.publiciseFrequency_tickBox.setObjectName("publiciseFrequency_tickBox")
        self.horizontalLayout.addWidget(self.publiciseFrequency_tickBox)
        self.publicFrequency_edit = FrequencyPickCombo(atcPane)
        self.publicFrequency_edit.setEnabled(False)
        self.publicFrequency_edit.setObjectName("publicFrequency_edit")
        self.horizontalLayout.addWidget(self.publicFrequency_edit)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.whoHas_button = QtWidgets.QToolButton(atcPane)
        self.whoHas_button.setObjectName("whoHas_button")
        self.horizontalLayout.addWidget(self.whoHas_button)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(atcPane)
        self.publiciseFrequency_tickBox.toggled['bool'].connect(self.publicFrequency_edit.setEnabled)
        self.publiciseFrequency_tickBox.toggled['bool'].connect(self.publicFrequency_edit.setFocus)
        QtCore.QMetaObject.connectSlotsByName(atcPane)
        atcPane.setTabOrder(self.ATC_view, self.publiciseFrequency_tickBox)
        atcPane.setTabOrder(self.publiciseFrequency_tickBox, self.publicFrequency_edit)

    def retranslateUi(self, atcPane):
        _translate = QtCore.QCoreApplication.translate
        self.publiciseFrequency_tickBox.setToolTip(_translate("atcPane", "Make frequency visible to neighbouring ATCs"))
        self.publiciseFrequency_tickBox.setText(_translate("atcPane", "Publicise\n"
"frequency:"))
        self.whoHas_button.setText(_translate("atcPane", "Who\n"
"has?"))

from gui.widgets.basicWidgets import FrequencyPickCombo
from gui.widgets.atcTableView import AtcTableView
