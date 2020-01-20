from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_createTrafficDialog(object):
    def setupUi(self, createTrafficDialog):
        createTrafficDialog.setObjectName("createTrafficDialog")
        createTrafficDialog.resize(307, 307)
        self.verticalLayout = QtWidgets.QVBoxLayout(createTrafficDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.groupBox_2 = QtWidgets.QGroupBox(createTrafficDialog)
        self.groupBox_2.setObjectName("groupBox_2")
        self.formLayout = QtWidgets.QFormLayout(self.groupBox_2)
        self.formLayout.setObjectName("formLayout")
        self.label = QtWidgets.QLabel(self.groupBox_2)
        self.label.setObjectName("label")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label)
        self.createAircraftType_edit = AircraftTypeCombo(self.groupBox_2)
        self.createAircraftType_edit.setObjectName("createAircraftType_edit")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.createAircraftType_edit)
        self.label_10 = QtWidgets.QLabel(self.groupBox_2)
        self.label_10.setObjectName("label_10")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_10)
        self.createCallsign_edit = QtWidgets.QLineEdit(self.groupBox_2)
        self.createCallsign_edit.setObjectName("createCallsign_edit")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.createCallsign_edit)
        self.createStripLink_tickBox = QtWidgets.QCheckBox(self.groupBox_2)
        self.createStripLink_tickBox.setObjectName("createStripLink_tickBox")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.SpanningRole, self.createStripLink_tickBox)
        self.verticalLayout.addWidget(self.groupBox_2)
        self.groupBox = QtWidgets.QGroupBox(createTrafficDialog)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout = QtWidgets.QGridLayout(self.groupBox)
        self.gridLayout.setObjectName("gridLayout")
        self.ground_status_radioButton = QtWidgets.QRadioButton(self.groupBox)
        self.ground_status_radioButton.setObjectName("ground_status_radioButton")
        self.gridLayout.addWidget(self.ground_status_radioButton, 0, 0, 1, 1)
        self.airborne_status_radioButton = QtWidgets.QRadioButton(self.groupBox)
        self.airborne_status_radioButton.setChecked(True)
        self.airborne_status_radioButton.setObjectName("airborne_status_radioButton")
        self.gridLayout.addWidget(self.airborne_status_radioButton, 2, 0, 1, 1)
        self.parked_tickBox = QtWidgets.QCheckBox(self.groupBox)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.parked_tickBox.sizePolicy().hasHeightForWidth())
        self.parked_tickBox.setSizePolicy(sizePolicy)
        self.parked_tickBox.setObjectName("parked_tickBox")
        self.gridLayout.addWidget(self.parked_tickBox, 0, 1, 1, 1)
        self.closestParkingPosition_info = QtWidgets.QLabel(self.groupBox)
        self.closestParkingPosition_info.setObjectName("closestParkingPosition_info")
        self.gridLayout.addWidget(self.closestParkingPosition_info, 0, 2, 1, 1)
        self.airborneFL_edit = QtWidgets.QSpinBox(self.groupBox)
        self.airborneFL_edit.setMaximum(500)
        self.airborneFL_edit.setSingleStep(5)
        self.airborneFL_edit.setProperty("value", 100)
        self.airborneFL_edit.setObjectName("airborneFL_edit")
        self.gridLayout.addWidget(self.airborneFL_edit, 2, 1, 1, 1)
        self.startFrozen_tickBox = QtWidgets.QCheckBox(self.groupBox)
        self.startFrozen_tickBox.setObjectName("startFrozen_tickBox")
        self.gridLayout.addWidget(self.startFrozen_tickBox, 2, 2, 1, 1)
        self.ready_status_radioButton = QtWidgets.QRadioButton(self.groupBox)
        self.ready_status_radioButton.setObjectName("ready_status_radioButton")
        self.gridLayout.addWidget(self.ready_status_radioButton, 1, 0, 1, 1)
        self.depRWY_select = QtWidgets.QComboBox(self.groupBox)
        self.depRWY_select.setObjectName("depRWY_select")
        self.gridLayout.addWidget(self.depRWY_select, 1, 1, 1, 1)
        self.verticalLayout.addWidget(self.groupBox)
        self.buttonBox = QtWidgets.QDialogButtonBox(createTrafficDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)
        self.label.setBuddy(self.createAircraftType_edit)
        self.label_10.setBuddy(self.createCallsign_edit)

        self.retranslateUi(createTrafficDialog)
        self.buttonBox.accepted.connect(createTrafficDialog.accept)
        self.buttonBox.rejected.connect(createTrafficDialog.reject)
        self.airborne_status_radioButton.toggled['bool'].connect(self.airborneFL_edit.setEnabled)
        self.airborne_status_radioButton.clicked.connect(self.airborneFL_edit.setFocus)
        self.airborne_status_radioButton.toggled['bool'].connect(self.startFrozen_tickBox.setEnabled)
        self.ready_status_radioButton.toggled['bool'].connect(self.depRWY_select.setEnabled)
        self.ready_status_radioButton.clicked.connect(self.depRWY_select.setFocus)
        self.ground_status_radioButton.clicked.connect(self.parked_tickBox.setFocus)
        QtCore.QMetaObject.connectSlotsByName(createTrafficDialog)
        createTrafficDialog.setTabOrder(self.createAircraftType_edit, self.createCallsign_edit)
        createTrafficDialog.setTabOrder(self.createCallsign_edit, self.createStripLink_tickBox)
        createTrafficDialog.setTabOrder(self.createStripLink_tickBox, self.ground_status_radioButton)
        createTrafficDialog.setTabOrder(self.ground_status_radioButton, self.parked_tickBox)
        createTrafficDialog.setTabOrder(self.parked_tickBox, self.ready_status_radioButton)
        createTrafficDialog.setTabOrder(self.ready_status_radioButton, self.depRWY_select)
        createTrafficDialog.setTabOrder(self.depRWY_select, self.airborne_status_radioButton)
        createTrafficDialog.setTabOrder(self.airborne_status_radioButton, self.airborneFL_edit)
        createTrafficDialog.setTabOrder(self.airborneFL_edit, self.startFrozen_tickBox)
        createTrafficDialog.setTabOrder(self.startFrozen_tickBox, self.buttonBox)

    def retranslateUi(self, createTrafficDialog):
        _translate = QtCore.QCoreApplication.translate
        createTrafficDialog.setWindowTitle(_translate("createTrafficDialog", "Create traffic"))
        self.groupBox_2.setTitle(_translate("createTrafficDialog", "Aircraft"))
        self.label.setText(_translate("createTrafficDialog", "Type:"))
        self.label_10.setText(_translate("createTrafficDialog", "Callsign:"))
        self.createStripLink_tickBox.setText(_translate("createTrafficDialog", "Create linked strip with details"))
        self.groupBox.setTitle(_translate("createTrafficDialog", "Status"))
        self.ground_status_radioButton.setText(_translate("createTrafficDialog", "On ground"))
        self.airborne_status_radioButton.setText(_translate("createTrafficDialog", "Airborne"))
        self.parked_tickBox.setText(_translate("createTrafficDialog", "parked at:"))
        self.closestParkingPosition_info.setText(_translate("createTrafficDialog", "##"))
        self.airborneFL_edit.setPrefix(_translate("createTrafficDialog", "FL"))
        self.startFrozen_tickBox.setText(_translate("createTrafficDialog", "start frozen"))
        self.ready_status_radioButton.setText(_translate("createTrafficDialog", "Ready for DEP"))

from gui.widgets.basicWidgets import AircraftTypeCombo
