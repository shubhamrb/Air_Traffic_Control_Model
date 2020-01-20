
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_selectionInfoPane(object):
    def setupUi(self, selectionInfoPane):
        selectionInfoPane.setObjectName("selectionInfoPane")
        selectionInfoPane.resize(236, 365)
        self.verticalLayout = QtWidgets.QVBoxLayout(selectionInfoPane)
        self.verticalLayout.setObjectName("verticalLayout")
        self.scrollArea = QtWidgets.QScrollArea(selectionInfoPane)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.info_area = QtWidgets.QWidget()
        self.info_area.setEnabled(False)
        self.info_area.setGeometry(QtCore.QRect(0, 0, 200, 381))
        self.info_area.setObjectName("info_area")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.info_area)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.aircraft_box = QtWidgets.QGroupBox(self.info_area)
        self.aircraft_box.setObjectName("aircraft_box")
        self.formLayout_4 = QtWidgets.QFormLayout(self.aircraft_box)
        self.formLayout_4.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.formLayout_4.setObjectName("formLayout_4")
        self.label_20 = QtWidgets.QLabel(self.aircraft_box)
        self.label_20.setObjectName("label_20")
        self.formLayout_4.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_20)
        self.aircraftHeading_info = QtWidgets.QLabel(self.aircraft_box)
        self.aircraftHeading_info.setText("")
        self.aircraftHeading_info.setObjectName("aircraftHeading_info")
        self.formLayout_4.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.aircraftHeading_info)
        self.label_17 = QtWidgets.QLabel(self.aircraft_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_17.sizePolicy().hasHeightForWidth())
        self.label_17.setSizePolicy(sizePolicy)
        self.label_17.setObjectName("label_17")
        self.formLayout_4.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_17)
        self.aircraftAltitude_info = QtWidgets.QLabel(self.aircraft_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.aircraftAltitude_info.sizePolicy().hasHeightForWidth())
        self.aircraftAltitude_info.setSizePolicy(sizePolicy)
        self.aircraftAltitude_info.setText("")
        self.aircraftAltitude_info.setObjectName("aircraftAltitude_info")
        self.formLayout_4.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.aircraftAltitude_info)
        self.label_18 = QtWidgets.QLabel(self.aircraft_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_18.sizePolicy().hasHeightForWidth())
        self.label_18.setSizePolicy(sizePolicy)
        self.label_18.setObjectName("label_18")
        self.formLayout_4.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_18)
        self.aircraftGroundSpeed_info = QtWidgets.QLabel(self.aircraft_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.aircraftGroundSpeed_info.sizePolicy().hasHeightForWidth())
        self.aircraftGroundSpeed_info.setSizePolicy(sizePolicy)
        self.aircraftGroundSpeed_info.setText("")
        self.aircraftGroundSpeed_info.setObjectName("aircraftGroundSpeed_info")
        self.formLayout_4.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.aircraftGroundSpeed_info)
        self.label_2 = QtWidgets.QLabel(self.aircraft_box)
        self.label_2.setObjectName("label_2")
        self.formLayout_4.setWidget(4, QtWidgets.QFormLayout.LabelRole, self.label_2)
        self.aircraftVerticalSpeed_info = QtWidgets.QLabel(self.aircraft_box)
        self.aircraftVerticalSpeed_info.setText("")
        self.aircraftVerticalSpeed_info.setObjectName("aircraftVerticalSpeed_info")
        self.formLayout_4.setWidget(4, QtWidgets.QFormLayout.FieldRole, self.aircraftVerticalSpeed_info)
        self.label_9 = QtWidgets.QLabel(self.aircraft_box)
        self.label_9.setObjectName("label_9")
        self.formLayout_4.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_9)
        self.indicatedAirSpeed_info = QtWidgets.QLabel(self.aircraft_box)
        self.indicatedAirSpeed_info.setText("")
        self.indicatedAirSpeed_info.setObjectName("indicatedAirSpeed_info")
        self.formLayout_4.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.indicatedAirSpeed_info)
        self.verticalLayout_2.addWidget(self.aircraft_box)
        self.route_box = QtWidgets.QGroupBox(self.info_area)
        self.route_box.setObjectName("route_box")
        self.formLayout_2 = QtWidgets.QFormLayout(self.route_box)
        self.formLayout_2.setObjectName("formLayout_2")
        self.label_3 = QtWidgets.QLabel(self.route_box)
        self.label_3.setObjectName("label_3")
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_3)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.legCount_info = QtWidgets.QLabel(self.route_box)
        self.legCount_info.setText("")
        self.legCount_info.setObjectName("legCount_info")
        self.horizontalLayout_2.addWidget(self.legCount_info)
        self.viewRoute_button = QtWidgets.QToolButton(self.route_box)
        self.viewRoute_button.setObjectName("viewRoute_button")
        self.horizontalLayout_2.addWidget(self.viewRoute_button)
        self.formLayout_2.setLayout(0, QtWidgets.QFormLayout.FieldRole, self.horizontalLayout_2)
        self.label = QtWidgets.QLabel(self.route_box)
        self.label.setObjectName("label")
        self.formLayout_2.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label)
        self.legSpec_info = QtWidgets.QLabel(self.route_box)
        self.legSpec_info.setText("")
        self.legSpec_info.setWordWrap(True)
        self.legSpec_info.setObjectName("legSpec_info")
        self.formLayout_2.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.legSpec_info)
        self.label_4 = QtWidgets.QLabel(self.route_box)
        self.label_4.setObjectName("label_4")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_4)
        self.waypointAt_info = QtWidgets.QLabel(self.route_box)
        self.waypointAt_info.setText("")
        self.waypointAt_info.setObjectName("waypointAt_info")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.waypointAt_info)
        self.label_5 = QtWidgets.QLabel(self.route_box)
        self.label_5.setObjectName("label_5")
        self.formLayout_2.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_5)
        self.waypointTTF_info = QtWidgets.QLabel(self.route_box)
        self.waypointTTF_info.setText("")
        self.waypointTTF_info.setObjectName("waypointTTF_info")
        self.formLayout_2.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.waypointTTF_info)
        self.verticalLayout_2.addWidget(self.route_box)
        self.airport_box = QtWidgets.QGroupBox(self.info_area)
        self.airport_box.setObjectName("airport_box")
        self.formLayout = QtWidgets.QFormLayout(self.airport_box)
        self.formLayout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.formLayout.setObjectName("formLayout")
        self.label_6 = QtWidgets.QLabel(self.airport_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_6.sizePolicy().hasHeightForWidth())
        self.label_6.setSizePolicy(sizePolicy)
        self.label_6.setObjectName("label_6")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_6)
        self.label_7 = QtWidgets.QLabel(self.airport_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_7.sizePolicy().hasHeightForWidth())
        self.label_7.setSizePolicy(sizePolicy)
        self.label_7.setObjectName("label_7")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_7)
        self.airportDistance_info = QtWidgets.QLabel(self.airport_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.airportDistance_info.sizePolicy().hasHeightForWidth())
        self.airportDistance_info.setSizePolicy(sizePolicy)
        self.airportDistance_info.setText("")
        self.airportDistance_info.setObjectName("airportDistance_info")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.airportDistance_info)
        self.airportTTF_info = QtWidgets.QLabel(self.airport_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.airportTTF_info.sizePolicy().hasHeightForWidth())
        self.airportTTF_info.setSizePolicy(sizePolicy)
        self.airportTTF_info.setText("")
        self.airportTTF_info.setObjectName("airportTTF_info")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.airportTTF_info)
        self.label_8 = QtWidgets.QLabel(self.airport_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_8.sizePolicy().hasHeightForWidth())
        self.label_8.setSizePolicy(sizePolicy)
        self.label_8.setObjectName("label_8")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_8)
        self.airportBearing_info = QtWidgets.QLabel(self.airport_box)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.airportBearing_info.sizePolicy().hasHeightForWidth())
        self.airportBearing_info.setSizePolicy(sizePolicy)
        self.airportBearing_info.setText("")
        self.airportBearing_info.setObjectName("airportBearing_info")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.airportBearing_info)
        self.verticalLayout_2.addWidget(self.airport_box)
        self.scrollArea.setWidget(self.info_area)
        self.verticalLayout.addWidget(self.scrollArea)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.cheatContact_toggle = QtWidgets.QCheckBox(selectionInfoPane)
        self.cheatContact_toggle.setEnabled(False)
        self.cheatContact_toggle.setObjectName("cheatContact_toggle")
        self.horizontalLayout.addWidget(self.cheatContact_toggle)
        self.ignoreContact_toggle = QtWidgets.QCheckBox(selectionInfoPane)
        self.ignoreContact_toggle.setEnabled(False)
        self.ignoreContact_toggle.setObjectName("ignoreContact_toggle")
        self.horizontalLayout.addWidget(self.ignoreContact_toggle)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(selectionInfoPane)
        QtCore.QMetaObject.connectSlotsByName(selectionInfoPane)
        selectionInfoPane.setTabOrder(self.scrollArea, self.viewRoute_button)
        selectionInfoPane.setTabOrder(self.viewRoute_button, self.cheatContact_toggle)
        selectionInfoPane.setTabOrder(self.cheatContact_toggle, self.ignoreContact_toggle)

    def retranslateUi(self, selectionInfoPane):
        _translate = QtCore.QCoreApplication.translate
        self.aircraft_box.setTitle(_translate("selectionInfoPane", "Flight parameters"))
        self.label_20.setText(_translate("selectionInfoPane", "Heading:"))
        self.label_17.setText(_translate("selectionInfoPane", "Altitude/FL:"))
        self.label_18.setText(_translate("selectionInfoPane", "Ground speed:"))
        self.label_2.setText(_translate("selectionInfoPane", "Vertical speed:"))
        self.label_9.setText(_translate("selectionInfoPane", "IAS:"))
        self.route_box.setTitle(_translate("selectionInfoPane", "Current route leg"))
        self.label_3.setText(_translate("selectionInfoPane", "Leg count:"))
        self.viewRoute_button.setToolTip(_translate("selectionInfoPane", "Route details"))
        self.viewRoute_button.setText(_translate("selectionInfoPane", "V"))
        self.label.setText(_translate("selectionInfoPane", "Leg spec:"))
        self.label_4.setText(_translate("selectionInfoPane", "Waypoint at:"))
        self.label_5.setText(_translate("selectionInfoPane", "Time to fly:"))
        self.airport_box.setTitle(_translate("selectionInfoPane", "To base airport"))
        self.label_6.setText(_translate("selectionInfoPane", "Bearing:"))
        self.label_7.setText(_translate("selectionInfoPane", "Distance:"))
        self.label_8.setText(_translate("selectionInfoPane", "Time to fly:"))
        self.cheatContact_toggle.setText(_translate("selectionInfoPane", "Cheat"))
        self.ignoreContact_toggle.setText(_translate("selectionInfoPane", "Ignore"))
