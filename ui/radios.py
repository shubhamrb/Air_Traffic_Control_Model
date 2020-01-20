
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_radioCentrePane(object):
    def setupUi(self, radioCentrePane):
        radioCentrePane.setObjectName("radioCentrePane")
        radioCentrePane.resize(328, 315)
        self.verticalLayout = QtWidgets.QVBoxLayout(radioCentrePane)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.recordATIS_button = QtWidgets.QToolButton(radioCentrePane)
        self.recordATIS_button.setEnabled(True)
        self.recordATIS_button.setObjectName("recordATIS_button")
        self.horizontalLayout_2.addWidget(self.recordATIS_button)
        self.ATISfreq_combo = FrequencyPickCombo(radioCentrePane)
        self.ATISfreq_combo.setEditable(True)
        self.ATISfreq_combo.setObjectName("ATISfreq_combo")
        self.horizontalLayout_2.addWidget(self.ATISfreq_combo)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.radios_table = QtWidgets.QTableWidget(radioCentrePane)
        self.radios_table.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.radios_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.radios_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.radios_table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.radios_table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.radios_table.setColumnCount(1)
        self.radios_table.setObjectName("radios_table")
        self.radios_table.setRowCount(0)
        self.radios_table.horizontalHeader().setVisible(False)
        self.radios_table.verticalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.radios_table)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.addBox_button = QtWidgets.QToolButton(radioCentrePane)
        self.addBox_button.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self.addBox_button.setObjectName("addBox_button")
        self.horizontalLayout.addWidget(self.addBox_button)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem1)
        self.muteAllRadios_tickBox = QtWidgets.QCheckBox(radioCentrePane)
        self.muteAllRadios_tickBox.setObjectName("muteAllRadios_tickBox")
        self.horizontalLayout.addWidget(self.muteAllRadios_tickBox)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.actionCreate_blank_strip = QtWidgets.QAction(radioCentrePane)
        self.actionCreate_blank_strip.setObjectName("actionCreate_blank_strip")

        self.retranslateUi(radioCentrePane)
        QtCore.QMetaObject.connectSlotsByName(radioCentrePane)
        radioCentrePane.setTabOrder(self.addBox_button, self.muteAllRadios_tickBox)
        radioCentrePane.setTabOrder(self.muteAllRadios_tickBox, self.recordATIS_button)
        radioCentrePane.setTabOrder(self.recordATIS_button, self.ATISfreq_combo)
        radioCentrePane.setTabOrder(self.ATISfreq_combo, self.radios_table)

    def retranslateUi(self, radioCentrePane):
        _translate = QtCore.QCoreApplication.translate
        self.recordATIS_button.setText(_translate("radioCentrePane", "Record ATIS:"))
        self.addBox_button.setToolTip(_translate("radioCentrePane", "Click: add box using internal FGCom process\n"
"Hold: use an externally running FGCom client"))
        self.addBox_button.setText(_translate("radioCentrePane", "+ radio box"))
        self.muteAllRadios_tickBox.setText(_translate("radioCentrePane", "Mute radios"))
        self.actionCreate_blank_strip.setText(_translate("radioCentrePane", "Create blank strip"))

from gui.widgets.basicWidgets import FrequencyPickCombo
