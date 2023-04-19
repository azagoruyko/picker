import json
import os
import sys
import base64

from picker import Picker, PickerItem, size2scale, color2hex
from animschool_parser import *

from PySide2.QtGui import QFontMetrics, QFont, QPixmap
from PySide2.QtCore import QByteArray, QBuffer, QIODevice
from PySide2.QtWidgets import QApplication

if sys.version_info.major > 2:
    RootDirectory = os.path.dirname(__file__)
else:    
    RootDirectory = os.path.dirname(__file__.decode(sys.getfilesystemencoding()))

def pixmap2str(pixmap):
    ba = QByteArray()
    buff = QBuffer(ba)
    buff.open(QIODevice.WriteOnly) 
    pixmap.save(buff, "JPG", 100)
    return base64.b64encode(ba.data()).decode("utf8")

def bytes2pixmap(pixmapBytes):    
    ba = QByteArray.fromHex(pixmapBytes)
    pixmap = QPixmap()
    pixmap.loadFromData(ba, "PNG")
    return pixmap

def convertFromPkrFile(pkrFile):
	title, buttons, png_data = parse_animschool_picker(pkrFile)

	pixmap = bytes2pixmap(png_data)

	picker = Picker()
	picker.size = [pixmap.width(), pixmap.height()]

	bgItem = PickerItem()
	bgItem.image = pixmap2str(pixmap)
	bgItem.imageAspectRatio = 0
	bgItem.scale = [size2scale(pixmap.width()), size2scale(pixmap.height())]
	picker.items.append(bgItem)

	fontMetrics = QApplication.fontMetrics()

	for data in buttons:
		pickerItem = PickerItem()

		pickerItem.label = data["label"]
		pickerItem.background = color2hex(data["bgcolor"][0], data["bgcolor"][1], data["bgcolor"][2])
		pickerItem.foreground = color2hex(data["txtcolor"][0], data["txtcolor"][1], data["txtcolor"][2])

		fontSize = fontMetrics.boundingRect(data["label"])

		width = max(data["w"], fontSize.width(), 10)
		height = max(data["h"], 10)

		pickerItem.scale = [size2scale(width), size2scale(height)]
		pickerItem.position = [data["x"] - width/2, data["y"] - height/2]

		if data["action"] == "command":
			lang = data["lang"]
			if lang == "python":
				pickerItem.script = " ".join(data["targets"])

			elif lang == "mel":
				mel = " ".join(data["targets"]).replace("\n", "")
				pickerItem.script = "import pymel.core as pm;pm.mel.eval('%s')"%mel

		if data["action"] == "select":
			pickerItem.control = " ".join(data["targets"])

		picker.items.append(pickerItem)

	with open(pkrFile+".picker", "w") as f: 
		json.dump(picker.toJson(), f)

#convertFromPkrFile("D:/Reimu_Picker_Body_v3.pkr")
