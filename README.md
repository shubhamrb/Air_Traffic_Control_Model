# Air_Traffic_Control_Model

==============
  IMPORTANT
==============

Due to greater size apt.dat file is not uploaded here so please download it from https://drive.google.com/open?id=1PyTMTmLbYk71GMJ4_JzM5wLmdb-qzs8j   and move it into resources/x-plane/ folder.



==============
  INSTALLING
==============

The program depends on two major software dependencies, required for it to run:
 - Python3 (3.3 or higher)
 - PyQt5 (5.2 or higher)

In addition, the following libraries can optionally be installed to enable
further features. ATC-pie will run without them, and they can be always be
installed at a later time:
 - PyAudio (0.2.11 or higher) and PocketSphinx (0.1.3 or higher) for voice
   instruction recognition in solo sessions;
 - pyttsx3 for speech synthesis of pilot read-back in solo sessions;
 - the IRC lib for full coordination features and ATC text chat system in
   multi-player sessions.

For tower viewing, a FlightGear client must be available, either installed on
this host (incl. appropriate scenery and aircraft models) or running on the
local network. Use version 2017.2 or later to support all animation features.


*** Linux ***

REQUIRED:
Assuming apt-get or a similar package installation system, the program
dependencies to install are:
 - python3
 - python3-pyqt5
 - python3-pyqt5.qtmultimedia
 - libqt5multimedia5-plugins

OPTIONAL [voice instruction recognition in solo sessions]:
You must first install the following packages:
 - portaudio19-dev
 - swig
 - libpulse-dev
Then, you need the Python libraries. The easiest way is to install python3-pip,
then run:
 - sudo pip3 install pyaudio
 - sudo pip3 install PocketSphinx

OPTIONAL [voice pilot read-back in solo sessions]:
Single library needed: "sudo pip3 install pyttsx3"

OPTIONAL [full ATC coordination and text chat]:
Single library needed: "sudo pip3 install irc"


*** Windows ***

To get both Python3 and PyQt5 dependencies working at once, a trick is to
install a WinPython+Qt5 package, downloadable from:
  https://sourceforge.net/projects/winpython/

Once the ATC-pie files are downloaded/extracted, to create a shortcut and enable
starting ATC-pie with a double-click from the desktop or file browser:
 - right click on "ATC-pie.py" and create a new shortcut;
 - in the "target" field, add "cmd /k " before the path already present;
 - "run from" should contain ATC-pie directory path (where "ATC-pie.py" is);
 - accept the dialog.

If your .py files are correctly associated with Python3 (cf. "Open with"),
double clicking on the created shortcut should start the ATC-pie launcher.


*** Mac ***

Use the official download links below, and have a look at the following forum
thread: http://forum.flightgear.org/viewtopic.php?f=83&t=25416&p=251892#p251884


*** Official download links for dependencies ***

Python3:      https://www.python.org/downloads/
PyQt5:        http://www.riverbankcomputing.com/software/pyqt/download5
PyAudio:      https://pypi.python.org/pypi/PyAudio
PocketSphinx: https://pypi.python.org/pypi/pocketsphinx
pyttsx3:      https://pypi.python.org/pypi/pyttsx3
IRC library:  https://pypi.python.org/pypi/irc
FlightGear:   http://www.flightgear.org/download/



===============
  CUSTOMISING
===============

Many configuration options can be managed from the application itself, via
menus and dialogs. For more control, read the "Notice" files in the various
sub-directories to learn about what you can further customise and how.

Short list of "Notice" files for configuration:
 - settings:         personal settings, colours, etc.
 - resources/acft:   aircraft data base and FlightGear model conversions
 - resources/apt:    airport source data
 - resources/bg-img: background images for radars and loose strip bays
 - resources/elev:   ground elevation maps
 - resources/fgcom:  FGCom executables
 - resources/nav:    navigation and routing data
 - resources/speech: airline and navpoint pronunciation



=================================
  SCRIPTS IN THE ROOT DIRECTORY
=================================

*** ATC-pie.py ***

The one you most want to run. See user guide for help and options (link in the
resource section below).


*** cleanUp.sh ***

ATC-pie generates log and cache files, which are safe to remove if you want to
clear up space. Run this script with no argument to do so. It will neither
break ATC-pie start-up nor alter any personal setting.


*** mkElevMap.py ***

This is a convenient script to generate an elevation map for an area, typically
around an airport for more accurate rendering of AI traffic in solo and
teaching sessions. It uses the "fgelev" tool, which comes with FlightGear.

Usage: mkElevMap.py <nw> <se> <prec_metres> [-- <fgelev_cmd>]
Replace <nw> and <se> with the cordinates of the North-West and South-East
corners of the area you want to cover with your map (it should cover all
airport taxiways and runways). Argument <prec_metres> is the minimum precision
you want to generate the map with, in metres between the plotted points. The
flatter your field is, the larger this value can be. You may provide a full
path to the "fgelev" executable if needed (last argument <fgelev_cmd>).

See resources/elev/Notice for more details on the format and purpose of ground
elevation maps.


