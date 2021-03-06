
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_towerViewControllerPane(object):
    def setupUi(self, towerViewControllerPane):
        towerViewControllerPane.setObjectName("towerViewControllerPane")
        towerViewControllerPane.resize(260, 259)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(towerViewControllerPane)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.lookAt_groupBox = QtWidgets.QGroupBox(towerViewControllerPane)
        self.lookAt_groupBox.setObjectName("lookAt_groupBox")
        self.gridLayout = QtWidgets.QGridLayout(self.lookAt_groupBox)
        self.gridLayout.setObjectName("gridLayout")
        self.label = QtWidgets.QLabel(self.lookAt_groupBox)
        self.label.setObjectName("label")
        self.gridLayout.addWidget(self.label, 0, 0, 1, 2)
        self.lookAtAircraft_OK_button = QtWidgets.QToolButton(self.lookAt_groupBox)
        self.lookAtAircraft_OK_button.setObjectName("lookAtAircraft_OK_button")
        self.gridLayout.addWidget(self.lookAtAircraft_OK_button, 0, 3, 1, 1)
        self.label_2 = QtWidgets.QLabel(self.lookAt_groupBox)
        self.label_2.setObjectName("label_2")
        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)
        self.runway_select = QtWidgets.QComboBox(self.lookAt_groupBox)
        self.runway_select.setObjectName("runway_select")
        self.gridLayout.addWidget(self.runway_select, 1, 1, 1, 1)
        self.runwayPoint_select = QtWidgets.QComboBox(self.lookAt_groupBox)
        self.runwayPoint_select.setObjectName("runwayPoint_select")
        self.runwayPoint_select.addItem("")
        self.runwayPoint_select.addItem("")
        self.gridLayout.addWidget(self.runwayPoint_select, 1, 2, 1, 1)
        self.lookAtRunway_OK_button = QtWidgets.QToolButton(self.lookAt_groupBox)
        self.lookAtRunway_OK_button.setObjectName("lookAtRunway_OK_button")
        self.gridLayout.addWidget(self.lookAtRunway_OK_button, 1, 3, 1, 1)
        self.trackAircraft_tickBox = QtWidgets.QCheckBox(self.lookAt_groupBox)
        self.trackAircraft_tickBox.setObjectName("trackAircraft_tickBox")
        self.gridLayout.addWidget(self.trackAircraft_tickBox, 0, 2, 1, 1)
        self.verticalLayout_2.addWidget(self.lookAt_groupBox)
        self.groupBox = QtWidgets.QGroupBox(towerViewControllerPane)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.groupBox)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.lookEast_button = QtWidgets.QToolButton(self.groupBox)
        self.lookEast_button.setObjectName("lookEast_button")
        self.gridLayout_2.addWidget(self.lookEast_button, 0, 2, 2, 1)
        self.lookWest_button = QtWidgets.QToolButton(self.groupBox)
        self.lookWest_button.setObjectName("lookWest_button")
        self.gridLayout_2.addWidget(self.lookWest_button, 0, 0, 2, 1)
        self.lookNorth_button = QtWidgets.QToolButton(self.groupBox)
        self.lookNorth_button.setObjectName("lookNorth_button")
        self.gridLayout_2.addWidget(self.lookNorth_button, 0, 1, 1, 1)
        self.lookSouth_button = QtWidgets.QToolButton(self.groupBox)
        self.lookSouth_button.setObjectName("lookSouth_button")
        self.gridLayout_2.addWidget(self.lookSouth_button, 1, 1, 1, 1)
        self.verticalLayout_2.addWidget(self.groupBox)
        self.groupBox_2 = QtWidgets.QGroupBox(towerViewControllerPane)
        self.groupBox_2.setObjectName("groupBox_2")
        self.formLayout = QtWidgets.QFormLayout(self.groupBox_2)
        self.formLayout.setObjectName("formLayout")
        self.label_3 = QtWidgets.QLabel(self.groupBox_2)
        self.label_3.setObjectName("label_3")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_3)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.binocularsFactor_edit = QtWidgets.QSpinBox(self.groupBox_2)
        self.binocularsFactor_edit.setMinimum(2)
        self.binocularsFactor_edit.setMaximum(15)
        self.binocularsFactor_edit.setProperty("value", 8)
        self.binocularsFactor_edit.setObjectName("binocularsFactor_edit")
        self.horizontalLayout.addWidget(self.binocularsFactor_edit)
        self.useBinoculars_button = QtWidgets.QToolButton(self.groupBox_2)
        self.useBinoculars_button.setObjectName("useBinoculars_button")
        self.horizontalLayout.addWidget(self.useBinoculars_button)
        self.dropBinoculars_button = QtWidgets.QToolButton(self.groupBox_2)
        self.dropBinoculars_button.setObjectName("dropBinoculars_button")
        self.horizontalLayout.addWidget(self.dropBinoculars_button)
        self.formLayout.setLayout(0, QtWidgets.QFormLayout.FieldRole, self.horizontalLayout)
        self.verticalLayout_2.addWidget(self.groupBox_2)
        self.label.setBuddy(self.trackAircraft_tickBox)
        self.label_2.setBuddy(self.runway_select)
        self.label_3.setBuddy(self.binocularsFactor_edit)

        self.retranslateUi(towerViewControllerPane)
        QtCore.QMetaObject.connectSlotsByName(towerViewControllerPane)
        towerViewControllerPane.setTabOrder(self.trackAircraft_tickBox, self.lookAtAircraft_OK_button)
        towerViewControllerPane.setTabOrder(self.lookAtAircraft_OK_button, self.runway_select)
        towerViewControllerPane.setTabOrder(self.runway_select, self.runwayPoint_select)
        towerViewControllerPane.setTabOrder(self.runwayPoint_select, self.lookAtRunway_OK_button)
        towerViewControllerPane.setTabOrder(self.lookAtRunway_OK_button, self.lookNorth_button)
        towerViewControllerPane.setTabOrder(self.lookNorth_button, self.lookWest_button)
        towerViewControllerPane.setTabOrder(self.lookWest_button, self.lookSouth_button)
        towerViewControllerPane.setTabOrder(self.lookSouth_button, self.lookEast_button)
        towerViewControllerPane.setTabOrder(self.lookEast_button, self.binocularsFactor_edit)
        towerViewControllerPane.setTabOrder(self.binocularsFactor_edit, self.useBinoculars_button)
        towerViewControllerPane.setTabOrder(self.useBinoculars_button, self.dropBinoculars_button)

    def retranslateUi(self, towerViewControllerPane):
        _translate = QtCore.QCoreApplication.translate
        self.lookAt_groupBox.setTitle(_translate("towerViewControllerPane", "Look at"))
        self.label.setText(_translate("towerViewControllerPane", "Selected aircraft"))
        self.lookAtAircraft_OK_button.setText(_translate("towerViewControllerPane", "OK"))
        self.label_2.setText(_translate("towerViewControllerPane", "Runway"))
        self.runwayPoint_select.setItemText(0, _translate("towerViewControllerPane", "threshold"))
        self.runwayPoint_select.setItemText(1, _translate("towerViewControllerPane", "end"))
        self.lookAtRunway_OK_button.setText(_translate("towerViewControllerPane", "OK"))
        self.trackAircraft_tickBox.setText(_translate("towerViewControllerPane", "follow"))
        self.groupBox.setTitle(_translate("towerViewControllerPane", "Look out"))
        self.lookEast_button.setText(_translate("towerViewControllerPane", "East"))
        self.lookWest_button.setText(_translate("towerViewControllerPane", "West"))
        self.lookNorth_button.setText(_translate("towerViewControllerPane", "North"))
        self.lookSouth_button.setText(_translate("towerViewControllerPane", "South"))
        self.groupBox_2.setTitle(_translate("towerViewControllerPane", "Options"))
        self.label_3.setText(_translate("towerViewControllerPane", "Binoculars:"))
        self.binocularsFactor_edit.setSuffix(_translate("towerViewControllerPane", "x"))
        self.useBinoculars_button.setText(_translate("towerViewControllerPane", "Use"))
        self.dropBinoculars_button.setText(_translate("towerViewControllerPane", "Drop"))

