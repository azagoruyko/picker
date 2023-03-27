import os
import sys
import json
import re
#import svg.path as svg
import base64

from Qt.QtGui import *
from Qt.QtCore import *
from Qt.QtWidgets import *

import pymel.core as pm
import pymel.api as api
import maya.cmds as cmds

from shiboken2 import wrapInstance
mayaMainWindow = wrapInstance(long(api.MQtUtil.mainWindow()), QMainWindow)
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

NiceColors = ['#FF0000', '#FF7F00', '#FFFF00', '#00FF00', '#00FFFF', '#0000FF', '#8B00FF', '#FF00FF', '#FF1493', '#FF69B4', '#FFC0CB', '#FFD700', '#32CD32', '#00FF7F', '#1E90FF', '#8A2BE2']

if sys.version_info.major > 2:
    RootDirectory = os.path.dirname(__file__)
else:
    RootDirectory = os.path.dirname(__file__.decode(sys.getfilesystemencoding()))

PickerWindows = []
Clipboard = []

def getNodeColor(node):
    MayaIndexColors = {
        0: '#787878',1: '#000000', 2: '#404040',
        3: '#808080', 4: '#9b0028', 5: '#000460',
        6: '#0000ff', 7: '#494949',8: '#260043',
        9: '#c800c8', 10: '#8a4833',11: '#3f231f',
        12: '#992600', 13: '#ff0000',14: '#00ff00',
        15: '#004199', 16: '#ffffff', 17: '#ffff00',
        18: '#64dcff', 19: '#43ffa3', 20: '#ffb0b0',
        21: '#e4ac79', 22: '#ffff63', 23: '#009954',
        24: '#a16a30', 25: '#9ea130',26: '#68a130',
        27: '#30a15d', 28: '#30a1a1', 29: '#3067a1',
        30: '#6f30a1', 31: '#a1306a'}

    node = pm.PyNode(node)
    if isinstance(node, pm.nt.Transform):
        sh = node.getShape()
        if sh and sh.overrideEnabled.get():
            return MayaIndexColors[sh.overrideColor.get()]

def color2hex(r,g,b):
    return "#%0.2x%0.2x%0.2x"%(r,g,b)

def size2scale(s):
    return 25 * (s/100.0 - 1.0)

class PickerItem(object):
    def __init__(self, svgpath="M 0 0 h 100 v 100 h -100 v -100 Z"):
        self.position = [0,0]
        self.background = "#eaa763"
        self.foreground = "#000000"
        self.image = "" # pixmap bytes
        self.imageAspectRatio = 0 # 0-IgnoreAspectRatio, 1-KeepAspectRatio, 2-KeepAspectRatioByExpanding
        self.control = ""
        self.label = ""
        self.font = ""
        self.script = ""
        self.flat = True # draw specular gradient when True
        self.flipped = [False, False]
        self.rotated = False
        self.scale = [-15, -15] # steps of grid size
        self.group = "" # used in double clicks
        self.svgpath = svgpath

    def copy(self, other):
        self.position = other.position[:]
        self.background = other.background
        self.foreground = other.foreground
        self.image = other.image
        self.imageAspectRatio = other.imageAspectRatio
        self.control = other.control
        self.label = other.label
        self.font = other.font
        self.script = other.script
        self.flat = other.flat
        self.flipped = other.flipped[:]
        self.rotated = other.rotated
        self.scale = other.scale[:]
        self.group = other.group
        self.svgpath = other.svgpath

    def duplicate(self):
        a = PickerItem()
        a.copy(self)
        return a

    def toJson(self):
        return {"position":self.position,
                "background":self.background,
                "foreground":self.foreground,
                "image":self.image,
                "imageAspectRatio":self.imageAspectRatio,
                "control":self.control,
                "label": self.label,
                "font": self.font,
                "script": self.script,
                "flat":self.flat,
                "flipped":self.flipped,
                "rotated":self.rotated,
                "scale":self.scale,
                "group":self.group,
                "svgpath":self.svgpath}

    def fromJson(self, data):
        self.position = data["position"]
        self.background = data["background"]
        self.foreground = data["foreground"]
        self.image = data["image"]
        self.imageAspectRatio = data["imageAspectRatio"]
        self.control = data["control"]
        self.label = data["label"]
        self.font = data.get("font", "")
        self.script = data["script"]
        self.flat = data["flat"]
        self.flipped = data["flipped"]
        self.rotated = data["rotated"]
        self.scale = data["scale"]
        self.group = data["group"]
        self.svgpath = data["svgpath"]

class Picker(object):
    def __init__(self, name=""):
        self.name = name
        self.items = []
        self.size = [0,0]
        self.scale = 1

    def copy(self, other):
        self.name = other.name
        self.items = [item.duplicate() for item in other.items]
        self.size = other.size[:]
        self.scale = other.scale

    def isEmpty(self):
        return len(self.items)==0

    def duplicate(self):
        a = Picker()
        a.copy(self)
        return a

    def toJson(self):
        return {"name": self.name, "items": [item.toJson() for item in self.items], "size":self.size, "scale": self.scale}

    def fromJson(self, data):
        self.name = data["name"]
        self.size = data["size"]
        self.scale = data.get("scale", 1)

        self.items = []
        for d in data["items"]:
            item = PickerItem()
            item.fromJson(d)
            self.items.append(item)

def findSymmetricName(name, left=True, right=True):
    L_starts = {"L_": "R_", "l_": "r_"}
    L_ends = {"_L": "_R", "_l": "_r"}

    R_starts = {"R_": "L_", "r_": "l_"}
    R_ends = {"_R": "_L", "_r": "_l"}

    for enable, starts, ends in [(left, L_starts, L_ends), (right, R_starts, R_ends)]:
        if enable:
            for s in starts:
                if name.startswith(s):
                    return starts[s] + name[len(s):]

            for s in ends:
                if name.endswith(s):
                    return name[:-len(s)] + ends[s]

    return name

def pixmap2str(pixmap):
    ba = QByteArray()
    buff = QBuffer(ba)
    buff.open(QIODevice.WriteOnly)
    pixmap.save(buff, "JPG", 100)
    return base64.b64encode(ba.data()).decode("utf8")

def str2pixmap(pixmapStr):
    ba = QByteArray.fromRawData(base64.b64decode(pixmapStr.encode("utf8")))
    pixmap = QPixmap()
    pixmap.loadFromData(ba, "JPG")
    return pixmap

def mayaVisibilityCallback(attr, data):
    item = data["item"]
    if not pm.getAttr(attr):
        item.isMayaControlHidden = True
        item.update()
    else: # check children
        for ch in data["hierarchy"]:
            if not ch.v.get():
                item.isMayaControlHidden = True
                item.update()
                return
        item.isMayaControlHidden = False
        item.update()

def mayaSelectionChangedCallback(mayaParameters, data):
    def splitNamespace(n):
        parts = n.split(":")
        return ":".join(parts[:-1])+":" or "", parts[-1]

    if not data:
        return

    scene = data.values()[0][0].scene()

    scene.blockSignals(True)
    scene.clearSelection()

    ls = cmds.ls(sl=True)
    for node in ls:
        items = data.get(node,[]) # found available item for the control
        for item in items:
            item.setSelected(True)

    scene.blockSignals(False)

def splitString(s):
    return re.split("[ ,;]+", s)

def roundTo(n, k=5):
    _round = lambda num: k * round(float(num) / k, 0)

    T = type(n)

    if T in [int, float]:
        return _round(n)

    elif T in [QPoint, QPointF]:
        return T(_round(n.x()), _round(n.y()))

    elif T in [QRect, QRectF]:
        return T(_round(n.x()), _round(n.y()), _round(n.width()), _round(n.height()))

def clamp(val, mn, mx):
    if val < mn:
        return mn
    elif val > mx:
        return mx
    return val

def enlargeRect(rect, offset):
    if isinstance(rect, QRectF):
        offsetPoint = QPointF(offset, offset)
    else:
        offsetPoint = QPoint(offset, offset)

    rect.setTopLeft(rect.topLeft() - offsetPoint)
    rect.setBottomRight(rect.bottomRight() + offsetPoint)
    return rect

def parsePath(path):
    commands = []

    currentCommand = ""
    commandNumbers = []
    currentNumber = ""
    sign = 1

    for c in path+" ":
        if c in ["M", "m", "L", "l", "H", "h", "V", "v", "C", "c", "Q", "q", "A", "a","Z", "z"]:
            if currentNumber:
                commandNumbers.append(float(currentNumber)*sign)
                sign = 1
                currentNumber = ""

            if currentCommand:
                commands.append((currentCommand, commandNumbers))

            commandNumbers = []
            currentCommand = c
            currentNumber = ""
            sign = 1

        elif c in ["0","1","2","3","4","5","6","7","8","9","."]:
            currentNumber += c

        else:
            if currentNumber:
                commandNumbers.append(float(currentNumber)*sign)
                currentNumber = ""

            sign = -1 if c == "-" else 1

    commands.append((currentCommand, commandNumbers))
    return commands

def getPainterPath(path, scaleX=1, scaleY=1, flipX=False, flipY=False, rotate=False):
    painterPath = QPainterPath()

    data = parsePath(path)

    if flipX or flipY:
        tmp = getPainterPath(path, 1, 1, False, False, rotate)
        rect = tmp.boundingRect()
        maxX = rect.width()
        maxY = rect.height()

    for cmd, numbers in data:
        cp = painterPath.currentPosition()

        if rotate:
            cmdInversion = {"h":"v", "H":"V", "v":"h", "V": "H"}
            cmd = cmdInversion.get(cmd, cmd)

            if cmd not in ["h", "H", "v", "V"]:
                newNumbers = [0]*len(numbers)
                for i in range(0, len(numbers), 2):
                    newNumbers[i] = numbers[i+1]
                    newNumbers[i+1] = numbers[i]
                numbers = newNumbers

        if flipX or flipY:
            for i in range(len(numbers)):
                if flipX and cmd == "H":
                    numbers[i] = maxX-numbers[i]
                if flipX and cmd == "h":
                    numbers[i] *= -1
                elif flipY and cmd == "V":
                    numbers[i] = maxY-numbers[i]
                elif flipY and cmd == "v":
                    numbers[i] *= -1
                elif cmd in ["M", "m", "L", "l", "C", "c", "Q","q"]:
                    if flipX and i%2==0: # x
                        numbers[i] = maxX-numbers[i]
                    if flipY and i%2!=0: # y
                        numbers[i] = maxY-numbers[i]

        if cmd == "M":
            painterPath.moveTo(numbers[0]*scaleX, numbers[1]*scaleY)
        elif cmd == "m":
            painterPath.moveTo(cp.x()+numbers[0]*scaleX, cp.y()+numbers[1]*scaleY)

        elif cmd == "L":
            painterPath.lineTo(numbers[0]*scaleX, numbers[1]*scaleY)
        elif cmd == "l":
            painterPath.lineTo(cp.x()+numbers[0]*scaleX, cp.y()+numbers[1]*scaleY)

        elif cmd == "H":
            painterPath.lineTo(numbers[0]*scaleX, cp.y())
        elif cmd == "h":
            painterPath.lineTo(cp.x()+numbers[0]*scaleX, cp.y())

        elif cmd == "V":
            painterPath.lineTo(cp.x(), numbers[0]*scaleY)
        elif cmd == "v":
            painterPath.lineTo(cp.x(), cp.y()+numbers[0]*scaleY)

        elif cmd == "C":
            painterPath.cubicTo(numbers[0]*scaleX, numbers[1]*scaleY, numbers[2]*scaleX, numbers[3]*scaleY, numbers[4]*scaleX, numbers[5]*scaleY)
        elif cmd == "c":
            painterPath.cubicTo(cp.x()+numbers[0]*scaleX, cp.y()+numbers[1]*scaleY, cp.x()+numbers[2]*scaleX, cp.y()+numbers[3]*scaleY, cp.x()+numbers[4]*scaleX, cp.y()+numbers[5]*scaleY)

        elif cmd == "Q":
            painterPath.quadTo(numbers[0]*scaleX, numbers[1]*scaleY, numbers[2]*scaleX, numbers[3]*scaleY)
        elif cmd == "q":
            painterPath.quadTo(cp.x()+numbers[0]*scaleX, cp.y()+numbers[1]*scaleY, cp.x()+numbers[2]*scaleX, cp.y()+numbers[3]*scaleY)

        elif cmd in ["Z", "z"]:
            painterPath.closeSubpath()
        '''
        elif cmd == "A":
            start = complex(cp.x(), cp.y())
            rad = complex(numbers[0]*scaleX, numbers[1]*scaleY)
            end = complex(numbers[5]*scaleX, numbers[6]*scaleY)

            arc = svg.Arc(start, rad, numbers[2],numbers[3], numbers[4], end)
            N = 25
            for i in range(N):
                p = arc.point(i/float(N-1))
                painterPath.lineTo(QPointF(p.real, p.imag))

        elif cmd == "a":
            start = complex(cp.x(), cp.y())
            rad = complex(numbers[0]*scaleX, numbers[1]*scaleY)
            end = complex(cp.x()+numbers[5]*scaleX, cp.y()+numbers[6]*scaleY)

            arc = svg.Arc(start, rad, numbers[2], numbers[3], numbers[4], end)
            N = 25
            for i in range(N):
                p = arc.point(i/float(N-1))
                painterPath.lineTo(QPointF(p.real, p.imag))
        '''

    rect = painterPath.boundingRect()
    painterPath.translate(-rect.x(), -rect.y())
    painterPath.setFillRule(Qt.WindingFill)
    return painterPath

def clearLayout(layout):
     if layout is not None:
         while layout.count():
             item = layout.takeAt(0)
             widget = item.widget()
             if widget is not None:
                 widget.setParent(None)
             else:
                 clearLayout(item.layout())

class ScaleAnchorItem(QGraphicsItem):
    Size = 12
    def __init__(self, **kwargs):
        super(ScaleAnchorItem, self).__init__(**kwargs)
        self.setCursor(Qt.CrossCursor)

        self.painterPath = getPainterPath("M 0 0 L 0 -{v} L -{v} 0 Z".format(v=ScaleAnchorItem.Size))

        self.isDragging = False
        self.dragDelta = None
        self.dragPos = None
        self.dragScales = None

    def shape(self):
        return self.painterPath

    def boundingRect(self):
        return self.shape().boundingRect()

    def paint(self, painter, option, widget=None):
        painter.setPen(Qt.NoPen)

        painter.setBrush(QBrush(QColor(255,255,255, 150)))
        if self.parentItem().isSelected():
            painter.drawPath(self.shape())

    def mouseMoveEvent(self, event):
        deltaX = int((event.scenePos().x()-self.dragPos.x()) / 5)
        deltaY = int((event.scenePos().y()-self.dragPos.y()) / 5)

        selection = self.scene().sortedSelection()
        for i, item in enumerate(selection):
            item.setUnitScale(QVector2D(self.dragScales[i].x()+deltaX, self.dragScales[i].y()+deltaY))

    def mousePressEvent(self, event):
        if event.buttons() in [Qt.LeftButton,Qt.MiddleButton]:
            self.isDragging = True
            self.dragPos = event.scenePos()

            self.dragScales = []
            for item in self.scene().sortedSelection():
                self.dragScales.append(item.unitScale())

    def mouseReleaseEvent(self, event):
        self.isDragging = False

class SceneItem(QGraphicsItem):
    ShadowOffset = 5

    def __init__(self, pickerItem, **kwargs):
        super(SceneItem, self).__init__(**kwargs)

        self.isMayaControlHidden = False
        self.isMayaControlInvalid = False

        self.pickerItem = pickerItem
        self.imagePixmap = None

        self.painterPath = getPainterPath(pickerItem.svgpath)

        self.scaleAnchorItem = ScaleAnchorItem()
        self.scaleAnchorItem.setVisible(False)
        self.scaleAnchorItem.setParentItem(self)

        self.isHover = False

        self._isDragging = False
        self._startPos = None
        self._lastPos = None

        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSelectedChange | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsMovable)
        self.setAcceptHoverEvents(True)

        self.updateScaleAnchor()

        shadowEffect = QGraphicsDropShadowEffect()
        shadowEffect.setOffset(2)
        self.setGraphicsEffect(shadowEffect)

        self.setUnitScale(QVector2D(self.pickerItem.scale[0],self.pickerItem.scale[1]))

    def copy(self, other):
        self.pickerItem.copy(other.pickerItem)
        self.updateShape()

    def unitScale(self):
        return QVector2D(self.pickerItem.scale[0], self.pickerItem.scale[1])

    def updateShape(self):
        scaleX = self.pickerItem.scale[0] / 25 + 1
        scaleY = self.pickerItem.scale[1] / 25 + 1

        self.prepareGeometryChange()
        self.painterPath = getPainterPath(self.pickerItem.svgpath, scaleX, scaleY, self.pickerItem.flipped[0], self.pickerItem.flipped[1], self.pickerItem.rotated)

        self.imagePixmap = QPixmap()

        pixmap = None
        if self.pickerItem.image.startswith("/9j/"): # image bytes
            pixmap = str2pixmap(self.pickerItem.image)
        else:
            imagePath = os.path.expandvars(self.pickerItem.image)
            if os.path.exists(imagePath):
                pixmap = QPixmap()
                pixmap.load(imagePath)

        if pixmap:
            aspectRatio = {0:Qt.IgnoreAspectRatio, 1:Qt.KeepAspectRatio, 2: Qt.KeepAspectRatioByExpanding}
            boundingRect = self.painterPath.boundingRect()
            self.imagePixmap = pixmap.scaled(boundingRect.width(), boundingRect.height(), aspectRatio[self.pickerItem.imageAspectRatio], Qt.SmoothTransformation)
            self.setZValue(-1)

        self.updateScaleAnchor()

    def setUnitScale(self, scale):
        if self.scene():
            self.scene().undoAppendForSelected("scale")

        if scale:
            self.pickerItem.scale[0] = clamp(scale.x(),-25+2, scale.x())
            self.pickerItem.scale[1] = clamp(scale.y(),-25+2, scale.y())

        self.updateShape()

    def itemChange(self, change, value):
        scene = self.scene()

        if not scene:
            return super(SceneItem, self).itemChange(change, value)

        if change == QGraphicsItem.ItemSelectedChange:
            self.scaleAnchorItem.setVisible(value and scene.editMode())

            if (not scene.editMode() or scene.isImagesLocked) and self.pickerItem.image:
                pm.select(cl=True)
                value = False

        elif change == QGraphicsItem.ItemPositionChange:
            scene.undoAppendForSelected("move")
            value = roundTo(value)
            self.pickerItem.position = [value.x(), value.y()]

            scene.mayaParameters.pickerIsModified = True

        return super(SceneItem, self).itemChange(change, value)

    def updateScaleAnchor(self):
        boundingRect = self.boundingRect()
        offset = ScaleAnchorItem.Size/2
        self.scaleAnchorItem.setPos(boundingRect.width()-offset, boundingRect.height()-offset)

    def boundingRect(self):
        return self.shape().boundingRect()

    def shape(self):
        return self.painterPath

    def paint(self, painter, option, widget=None):
        painter.setRenderHints(QPainter.Antialiasing)

        boundingRect = self.boundingRect()

        if self.pickerItem.image:
            painter.drawPixmap(0,0,self.imagePixmap)

        else:
            if self.pickerItem.background:
                background = self.pickerItem.background if not self.isSelected() else "#eeeeee"
                pen = QPen(QColor(background).darker(200))
                pen.setCosmetic(True) # don't change line width while scaling

                if self.pickerItem.flat:
                    brushStyle = Qt.SolidPattern
                    background = QColor(background).lighter(133) if self.isHover else background
                    gradient = None
                else:
                    brushStyle = Qt.LinearGradientPattern
                    gradient = QLinearGradient(boundingRect.topLeft(),boundingRect.center())
                    gradient.setColorAt(0.4, QColor(255,255,255))
                    gradient.setColorAt(0.8, QColor(background).lighter(133) if self.isHover else background)

                if not self.scene().editMode():
                    if self.isMayaControlHidden:
                        background = "#666666"
                        pen.setColor("#333333")
                        gradient = None
                    if self.isMayaControlInvalid:
                        brushStyle = Qt.BDiagPattern
                        background = "#cc4444"
                        pen = Qt.NoPen
                        gradient = None

                painter.setPen(pen)
                if gradient:
                    painter.setBrush(gradient)
                else:
                    brush = QBrush(QColor(background))
                    brush.setStyle(brushStyle)
                    painter.setBrush(brush)
            else:
                painter.setPen(Qt.NoPen)
                painter.setBrush(Qt.NoBrush)

            painter.drawPath(self.shape())

            # label
            if self.pickerItem.label:
                painter.setPen(QColor(self.pickerItem.foreground))

                if self.pickerItem.font:
                    font = QFont()
                    font.fromString(self.pickerItem.font)
                    painter.setFont(font)
                else:
                    font = painter.font()
                    font.setBold(True)
                    painter.setFont(font)

                fontMetrics = QFontMetrics(painter.font())
                textSize = fontMetrics.boundingRect(self.pickerItem.label)
                painter.drawText(boundingRect.center() - QPoint(textSize.width()/2, -textSize.height()/4), self.pickerItem.label)

        if self.isSelected():
            painter.setBrush(Qt.NoBrush)
            pen = QPen(QColor(0,255,0, 150))
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawRect(boundingRect)

    def hoverMoveEvent(self, event):
        self.isHover = True
        if not self.pickerItem.image:
            self.setCursor(Qt.PointingHandCursor)
        self.update()

    def hoverLeaveEvent(self, event):
        self.isHover = False
        self.unsetCursor()
        self.update()

    def mouseDoubleClickEvent(self, event): # select group of controls
        super(SceneItem, self).mouseDoubleClickEvent(event)

        scene = self.scene()
        if not scene.editMode() and self.pickerItem.group:
            found = scene.findItemsByProperty("group", self.pickerItem.group)

            oldSelection = scene.sortedSelection()
            scene.blockSignals(True)

            for item in found:
                item.setSelected(True)

            scene.blockSignals(False)
            scene.selectionChangedCallback()

    def mousePressEvent(self, event):
        alt = event.modifiers() & Qt.AltModifier
        shift = event.modifiers()  & Qt.ShiftModifier # add to selection
        ctrl = event.modifiers() & Qt.ControlModifier # remove from selection

        if alt:
            return

        scene = self.scene()

        if event.button() == Qt.LeftButton and not scene.editMode() and self.pickerItem.script: # execute script
            pm.undoInfo(ock=True)
            try:
                exec(self.pickerItem.script.replace("@", scene.mayaParameters.namespace))
            finally:
                pm.undoInfo(cck=True)

        elif event.button() in [Qt.LeftButton, Qt.MiddleButton]: # handle selection
            # when we press on a selected item with middle mouse, don't clear selection
            if not (event.button() == Qt.MiddleButton and self.isSelected()):
                # Deselect all other items in the same scene
                if not shift and not ctrl:
                    scene.blockSignals(True)
                    for item in scene.selectedItems():
                        if item != self:
                            item.setSelected(False)
                    scene.blockSignals(False)

                if ctrl:
                    self.setSelected(False)
                elif ctrl and shift:
                    self.setSelected(True)
                elif shift:
                    self.setSelected(not self.isSelected())
                else:
                    self.setSelected(True)

        if event.button() == Qt.MiddleButton and not ctrl and not shift:
            for item in scene.selectedItems():
                item._isDragging = True
                item._lastPos = event.scenePos()
                item._startPos = item.pos()

    def mouseMoveEvent(self, event):
        if self._isDragging:
            scene = self.scene()
            for item in scene.items():
                if isinstance(item, SceneItem) and item._isDragging:
                    delta = item._lastPos - event.scenePos()
                    newPos = item._startPos - delta
                    item.setPos(newPos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            scene = self.scene()
            for item in scene.items():
                if isinstance(item, SceneItem) and item.isSelected():
                    item._isDragging = False

            if scene.mayaParameters.pickerIsModified:
                scene.mayaParameters.pickerWindow.saveToMayaNode()

class Scene(QGraphicsScene):
    editModeChanged = Signal(bool)

    def __init__(self, propertiesWidget, mayaParameters, **kwargs):
        super(Scene, self).__init__(**kwargs)

        self.propertiesWidget = propertiesWidget
        self.propertiesWidget.somethingChanged.connect(self.updateItemsProperties)
        self.mayaParameters = mayaParameters

        self.isImagesLocked = False

        self._editMode = False
        self._sortedSelection = []

        self.undoEnabled = True
        self._undoDisableOder = 0 # beginEditBlock/endEditBlock inc/dec this
        self._undoStack = [] # [(id, function), (id, function)], where id identifies undo operation, function is a recover function
        self._undoTempStack = []

        self.selectionChanged.connect(self.selectionChangedCallback)

    def updateProperties(self):
        selection = self.sortedSelection()
        self.propertiesWidget.updateProperties(selection[-1].pickerItem if selection else None)

    def updateItemsProperties(self):
        if not self.editMode():
            return

        self.undoAppendForSelected("properties")

        propItem = self.propertiesWidget.pickerItem.duplicate()
        changedProperties = self.propertiesWidget.changedProperties
        for item in self.sortedSelection():
            if "svgpath" in changedProperties:
                item.pickerItem.svgpath = propItem.svgpath

            elif "image" in changedProperties:
                item.pickerItem.image = propItem.image

            elif "background" in changedProperties:
                item.pickerItem.background = propItem.background

            elif "foreground" in changedProperties:
                item.pickerItem.foreground = propItem.foreground

            elif "imageAspectRatio" in changedProperties:
                item.pickerItem.imageAspectRatio = propItem.imageAspectRatio

            elif "control" in changedProperties:
                item.pickerItem.control = propItem.control

            elif "label" in changedProperties:
                item.pickerItem.label = propItem.label

            elif "font" in changedProperties:
                item.pickerItem.font = propItem.font[:]

            elif "group" in changedProperties:
                item.pickerItem.group = propItem.group

            elif "flat" in changedProperties:
                item.pickerItem.flat = propItem.flat

            elif "flipped" in changedProperties:
                item.pickerItem.flipped = propItem.flipped[:]

            elif "rotated" in changedProperties:
                item.pickerItem.rotated = propItem.rotated

            elif "script" in changedProperties:
                item.pickerItem.script = propItem.script

            self.propertiesWidget.changedProperties = []
            item.updateShape()

    def findItemsByProperty(self, propname, propvalue):
        found = []
        for item in self.items():
            if isinstance(item, SceneItem) and item.pickerItem.__getattribute__(propname) == propvalue:
                found.append(item)
        return found

    def updateSortedSelection(self):
        # add prev selection into undo stack
        undoFunc = lambda items=self.sortedSelection(): (self.clearSelection(), [item.setSelected(True) for item in items])
        self.undoAppend("selection", undoFunc, str([id(item) for item in self.sortedSelection()]))

        # sort selected items by distance to origin
        selectedItems = sorted(self.selectedItems(), key=lambda item: QVector2D(self.sceneRect().topLeft()-item.pos()).length())

        if selectedItems:
            self._sortedSelection = [item for item in self._sortedSelection if item.isSelected()]

            for sel in selectedItems:
                if sel not in self._sortedSelection:
                    self._sortedSelection.append(sel)

        else:
            del self._sortedSelection[:]

    def selectionChangedCallback(self):
        self.updateSortedSelection()
        self.updateProperties()

        if not self.editMode():
            nodes = set()
            for item in self.sortedSelection():
                for ctrl in splitString(item.pickerItem.control):
                    node = ctrl if ctrl.startswith(':') else self.mayaParameters.namespace+ctrl
                    if cmds.objExists(node):
                        nodes.add(node)

            cmds.select(nodes)

    def sortedSelection(self):
        return self._sortedSelection[:]

    def beginEditBlock(self):
        self._undoDisableOder += 1

    def endEditBlock(self):
        self._undoDisableOder -= 1

        # append all temporary operations as a single undo function
        if self._undoTempStack and not self.isInEditBlock():
            tempStackFunc = lambda lst=self._undoTempStack: [f() for _,f in lst]
            self.undoAppend("temp", tempStackFunc)
            self._undoTempStack = []

    def isInEditBlock(self):
        return self._undoDisableOder > 0

    def undoNewBlock(self): # used to separate operations from previous onces
        self.undoAppend("newBlock", None)

    def undoAppendForSelected(self, name):
        funcList = []
        for item in self.sortedSelection():
            f = lambda item=item, state=item.pickerItem.duplicate(): (item.pickerItem.copy(state),
                                                                      item.updateShape(),
                                                                      item.setPos(state.position[0], state.position[1]))
            funcList.append(f)
        undoFunc = lambda funcList=funcList: [f() for f in funcList]

        self.undoAppend(name, undoFunc, str([id(item) for item in self.sortedSelection()]))

    def undoAppend(self, name, undoFunc, operationId=None):
        if not self.undoEnabled or not self.editMode():
            return

        lastOp = self.getUndoLastOperation()

        cmd = "%s %s"%(name, operationId)
        if operationId is not None and lastOp and lastOp[0] == cmd:
            pass
        else:
            if self.isInEditBlock():
                self._undoTempStack.append((cmd, undoFunc))
            else:
                self._undoStack.append((cmd, undoFunc))

    def getUndoLastOperation(self):
        if self.isInEditBlock():
            return self._undoTempStack[-1] if self._undoTempStack else None
        else:
            return self._undoStack[-1] if self._undoStack else None

    def flushUndo(self):
        self._undoStack = []

    def keyPressEvent(self, event):
        ctrl = event.modifiers() & Qt.ControlModifier

        if ctrl and event.key() == Qt.Key_Z:
            if not self._undoStack:
                print("Selection undo is empty")
            else:
                self.undoEnabled = False

                while True and self._undoStack:
                    cmd, undoFunc = self._undoStack.pop()

                    if callable(undoFunc):
                        undoFunc()
                        break

                self.undoEnabled = True

                self.updateProperties()

        else:
            super(Scene, self).keyPressEvent(event)

    def editMode(self):
        return self._editMode

    def setEditMode(self, v):
        if v == self._editMode:
            return

        for item in self.selectedItems():
            if isinstance(item, SceneItem):
                item.scaleAnchorItem.setVisible(v)

        self._editMode = v
        self.update() # repaint items
        self.editModeChanged.emit(v)

class View(QGraphicsView):
    pickerLoaded = Signal(object, bool) # picker, asImport (True, False)
    somethingDropped = Signal()

    def __init__(self, scene, **kwargs):
        super(View, self).__init__(scene, **kwargs)

        self._startDrag = None
        self._mouseMovePos = None
        self._isPanning = False
        self.rubberBand = None
        self.selectionBeforeRubberBand = []

        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setAcceptDrops(True)

        self.setSceneRect(QRect(0,0, 300, 400))

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        mimeData = event.mimeData()
        if mimeData.hasText():
            nodes = [pm.PyNode(n).stripNamespace() for n in mimeData.text().split()]

            self.scene().clearSelection()
            self.insertItems(self.mapToScene(event.pos()), nodes)
            event.acceptProposedAction()
            self.somethingDropped.emit()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def newPicker(self, window=False, quiet=False):
        if not window:
            ok = quiet or QMessageBox.question(self, "Picker", "Clear current and make new picker?",
                                               QMessageBox.Yes and QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes
            if ok:
                self.setTransform(QTransform()) # reset scale
                self.scene().setEditMode(True)
                self.scene().clear()
                self.scene().flushUndo()
        else:
            PickerWindow().show()

    def toPicker(self, selected=False):
        picker = Picker()
        for item in self.scene().items()[::-1]: # reverse to make the list from the first birth
            if isinstance(item, SceneItem):
                if selected and not item.isSelected():
                    continue

                picker.items.append(item.pickerItem)

        picker.size = [self.viewport().width(), self.viewport().height()]
        picker.scale = self.getViewportScale()[0] # use sx
        return picker

    def savePicker(self, selected=False):
        path, _ = QFileDialog.getSaveFileName(None, "Save picker", "", "*.picker")

        if path:
            picker = self.toPicker(selected)

            with open(path, "w") as f:
                json.dump(picker.toJson(), f, indent=4)

    def loadPickerFromFile(self):
        path, _ = QFileDialog.getOpenFileName(None, "Load picker", "", "*.picker")

        if path:
            picker = Picker()
            with open(path, "r") as f:
                picker.fromJson(json.load(f))
            return picker

    def selectAllItems(self):
        oldSelection = self.scene().sortedSelection()
        scene = self.scene()

        undoFunc = lambda scene=scene, items=oldSelection: (scene.clearSelection(), [item.setSelected(True) for item in items])
        scene.undoAppend("selection", undoFunc, str([id(item) for item in oldSelection]))

        scene.beginEditBlock()
        for item in scene.items():
            item.setSelected(True)
        scene.endEditBlock()

    def replaceInNames(self):
        replace, ok = QInputDialog.getText(self, "Replace", "Replace inside control/group (old=new)", QLineEdit.Normal, "L_=R_")
        if ok and replace:
            replaceItems = replace.split("=")
            if len(replaceItems)==2:
                old, new = replaceItems
                selection = self.scene().sortedSelection()
                for item in selection:
                    item.pickerItem.control = item.pickerItem.control.replace(old,new)
                    item.pickerItem.group = item.pickerItem.group.replace(old,new)

                self.scene().updateProperties()
            else:
                QMessageBox.critical(self, "Replace", "Invalid replace format. Must be 'old=new', i.e L_=R_")

    def loadPicker(self, picker=None, asImport=False):
        if not picker:
            picker = self.loadPickerFromFile()
        if not picker:
            return

        scene = self.scene()
        scene.beginEditBlock()

        oldSelection = scene.sortedSelection()

        if asImport:
            scene.clearSelection()
        else:
            scene.clear()

        newItems = []
        for pickerItem in picker.items:
            item = SceneItem(pickerItem)
            scene.addItem(item)

            item.setPos(item.pickerItem.position[0], item.pickerItem.position[1])

            if asImport:
                item.setSelected(True)

            newItems.append(item)

        scene.endEditBlock()

        if not asImport: # clear undo when just open new picker
            scene.flushUndo()

            self.setTransform(QTransform()) # reset scale
            self.scale(picker.scale, picker.scale)
            self.pickerLoaded.emit(picker, False)

            self.frameAll()

        else: # track undo

            undoFunc = lambda scene=scene, items=newItems, oldSelection=oldSelection: ([scene.removeItem(item) for item in items],
                                                                                        scene.clearSelection(),
                                                                                        [item.setSelected(True) for item in oldSelection])
            scene.undoAppend("loadPicker", undoFunc)
            self.pickerLoaded.emit(picker, True)

    def flipItems(self, edge):
        if not self.scene().editMode():
            return

        boundingRect = QRectF()

        selected = self.scene().sortedSelection()

        for item in selected: # find bounding box of selected items
            boundingRect = boundingRect.united(item.boundingRect().translated(item.pos()))

        for item in selected[::-1]:
            if edge in ["left", "right"]:
                anchor = boundingRect.left() if edge=="left" else boundingRect.right()

                delta = abs(item.pos().x() - anchor + item.boundingRect().width())
                x = anchor - delta if edge=="left" else anchor + delta
                item.setPos(x, item.pos().y())
                item.pickerItem.flipped[0] = not item.pickerItem.flipped[0]

            elif edge in ["up", "down"]:
                anchor = boundingRect.top() if edge=="up" else boundingRect.bottom()

                delta = abs(item.pos().y() - anchor + item.boundingRect().height())
                y = anchor - delta if edge=="up" else anchor + delta
                item.setPos(item.pos().x(), y)
                item.pickerItem.flipped[1] = not item.pickerItem.flipped[1]

            item.updateShape()

        self.scene().updateProperties()

    def lockImages(self):
        if not self.scene().editMode():
            return

        self.scene().isImagesLocked = not self.scene().isImagesLocked

    def removeItems(self):
        def undoRemoveItems(scene, items):
            for item in items:
                sceneItem = SceneItem(item)
                scene.addItem(sceneItem)
                sceneItem.setPos(item.position[0], item.position[1])

        if not self.scene().editMode():
            return

        keepItems = []
        for item in self.scene().sortedSelection():
            keepItems.append(item.pickerItem.duplicate())
            self.scene().removeItem(item)

        undoFunc = lambda scene=self.scene(), items=keepItems: undoRemoveItems(scene, items)
        self.scene().undoAppend("remove", undoFunc)

    def clipboardCopyItems(self):
        global Clipboard
        Clipboard = []
        for item in self.scene().sortedSelection()[::-1]:
            Clipboard.append(item.pickerItem.duplicate())

    def clipboardCutItems(self):
        self.clipboardCopyItems()
        self.removeItems()

    def clipboardPasteItems(self):
        global Clipboard

        if not self.scene().editMode():
            return

        if Clipboard:
            oldSelection = self.scene().sortedSelection()

            self.scene().clearSelection()

            newItems = []
            for pickerItem in Clipboard:
                item = SceneItem(pickerItem)

                self.scene().beginEditBlock()
                self.scene().addItem(item)
                item.setPos(pickerItem.position[0], pickerItem.position[1])
                item.setSelected(True)
                self.scene().endEditBlock()

                newItems.append(item)

            undoFunc = lambda items=newItems, scene=self.scene, selection=oldSelection: ([scene.removeItem(item) for item in items],
                                                                                         scene.clearSelection(),
                                                                                         [item.setSelected(True) for item in oldSelection])
            self.scene().undoAppend("paste", undoFunc)

            self.scene().updateProperties()
            Clipboard = []

    def insertItems(self, position=None, controls=None):
        position = roundTo(position or self.mapToScene(self.mapFromGlobal(QCursor.pos())))

        if not controls:
            controls = [n.stripNamespace() for n in pm.ls(sl=True)]
            if not controls:
                controls = [""] # single empty item when no selection

        shapeBrower = ShapeBrowserWidget(parent=self)
        shapeBrower.exec_()
        if shapeBrower.selectedSvgpath:
            scene = self.scene()

            items = []
            oldSelection = scene.sortedSelection()
            scene.beginEditBlock()
            for ctrl in controls:
                pickerItem = PickerItem(shapeBrower.selectedSvgpath)

                pickerItem.control = ctrl
                if cmds.objExists(scene.mayaParameters.namespace+ctrl):
                    nodeColor = getNodeColor(scene.mayaParameters.namespace+ctrl)
                    if nodeColor:
                        pickerItem.background = nodeColor

                item = SceneItem(pickerItem)
                scene.addItem(item)
                item.setPos(position)
                item.setSelected(True)

                items.append(item)
            scene.endEditBlock()

            self.makeRowColumnFromSelected("column", 5)

            undoFunc = lambda items=items, scene=scene, selection=oldSelection: ([scene.removeItem(item) for item in items],
                                                                                 scene.clearSelection(),
                                                                                 [item.setSelected(True) for item in oldSelection])
            scene.undoAppend("insert", undoFunc)

            scene.updateProperties()

    def rotateItems(self):
        if not self.scene().editMode():
            return

        selected = self.scene().sortedSelection()
        for item in selected:
            item.pickerItem.rotated = not item.pickerItem.rotated
            item.updateShape()

        self.scene().updateProperties()

    def setItemsSize(self, size):
        if not self.scene().editMode():
            return

        for item in self.scene().sortedSelection():
            item.setUnitScale(QVector2D(size, size))

    def mirrorItems(self):
        if not self.scene().editMode():
            return

        scene = self.scene()
        scene.beginEditBlock()
        self.duplicateItems(QPointF(0,0))
        self.flipItems("left")
        scene.endEditBlock()

        for item in scene.selectedItems():
            item.pickerItem.control = findSymmetricName(item.pickerItem.control)
            item.pickerItem.group = findSymmetricName(item.pickerItem.group)

        scene.updateProperties()

    def duplicateItems(self, offset=QPointF(20,20)):
        if not self.scene().editMode():
            return

        scene = self.scene()
        selected = scene.sortedSelection()

        if selected:
            scene.beginEditBlock()

            newItems = []
            for sel in selected[::-1]:
                newPos = sel.pos() + offset
                item = SceneItem(sel.pickerItem.duplicate())
                scene.addItem(item)
                item.setPos(newPos)
                newItems.append(item)

            scene.clearSelection()
            for item in newItems:
                item.setSelected(True)

            scene.endEditBlock()

            undoFunc = lambda scene=scene, items=newItems, oldSelection=selected: ([scene.removeItem(item) for item in items],
                                                                                   scene.clearSelection(),
                                                                                   [item.setSelected(True) for item in oldSelection])
            scene.undoAppend("duplicate", undoFunc)

    def makeRowColumnFromSelected(self, orientation, size=0):
        selected = self.scene().sortedSelection()
        if len(selected) > 1:
            self.scene().undoNewBlock()

            prev = 0
            for item in selected[1:]:
                prevWidth = roundTo(selected[prev].boundingRect().width())
                prevHeight = roundTo(selected[prev].boundingRect().height())

                if orientation=="column":
                    item.setPos(selected[0].x(), selected[prev].y()+prevHeight+size)
                elif orientation=="row":
                    item.setPos(selected[prev].x()+prevWidth+size, selected[0].y())
                elif orientation=="ldiag":
                    item.setPos(selected[prev].x()-prevWidth-size, selected[prev].y()+prevHeight+size)
                elif orientation=="rdiag":
                    item.setPos(selected[prev].x()+prevWidth+size, selected[prev].y()+prevHeight+size)
                prev +=1

    def setSameSize(self):
        if not self.scene().editMode():
            return

        selected = self.scene().sortedSelection()
        if len(selected) > 1:
            for item in selected[1:]:
                item.setUnitScale(selected[0].unitScale())

    def alignItems(self, edge):
        if not self.scene().editMode():
            return

        selected = self.scene().sortedSelection()
        if selected and len(selected) > 1:
            self.scene().undoNewBlock()

            for item in selected[1:]:
                if edge == "left":
                    item.setPos(selected[0].x(), item.y())
                elif edge == "top":
                    item.setPos(item.x(), selected[0].y())
                elif edge == "right":
                    anchor = selected[0].pos() + selected[0].boundingRect().bottomRight()
                    x = anchor.x() - item.boundingRect().width()
                    item.setPos(x, item.y())
                elif edge == "hcenter":
                    anchor = selected[0].pos().x() + selected[0].boundingRect().width()/2
                    x = anchor - item.boundingRect().width()/2
                    item.setPos(x, item.y())
                elif edge == "vcenter":
                    anchor = selected[0].pos().y() + selected[0].boundingRect().height()/2
                    y = anchor - item.boundingRect().height()/2
                    item.setPos(item.x(), y)

    def frameAll(self):
        if self.scene().items():
            rect = self.scene().itemsBoundingRect()
            self.setSceneRect(enlargeRect(rect, 10))
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def keyPressEvent(self, event):
        ctrl = event.modifiers() & Qt.ControlModifier
        alt = event.modifiers() & Qt.AltModifier

        if event.key() == Qt.Key_Escape:
            self.scene().setEditMode(False)

        else:
            super(View, self).keyPressEvent(event)

    def mousePressEvent(self, event):
        alt = event.modifiers() & Qt.AltModifier

        if not alt and event.button() == Qt.LeftButton:
            self.selectionBeforeRubberBand = self.scene().sortedSelection()

            itemAt = self.itemAt(event.pos())
            # check if it's a simple SceneItem or image with conditions
            if isinstance(itemAt, ScaleAnchorItem):
                return

            if itemAt and\
               (not itemAt.pickerItem.image or
                (itemAt.pickerItem.image and
                 not (self.scene().isImagesLocked or not self.scene().editMode()))):
               super(View, self).mousePressEvent(event) # pass forward to items
               return

            self._startDrag = event.pos()

            if not self.rubberBand:
                self.rubberBand = MyRubberBand(parent=self.viewport())

            self.rubberBand.setGeometry(QRect(self._startDrag, QSize()))
            self.rubberBand.show()

        elif event.button() == Qt.RightButton:
            self._mouseMovePos = event.pos()

        elif event.buttons() in [Qt.LeftButton, Qt.MiddleButton]:
            if self.items(event.pos()): # when items under mouse
                super(View, self).mousePressEvent(event)

            self._isPanning = True
            self._panningPos = event.pos()

        else:
            super(View, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super(View, self).mouseMoveEvent(event)

        alt = event.modifiers() & Qt.AltModifier
        ctrl = event.modifiers() & Qt.ControlModifier

        if (ctrl or alt) and event.buttons() == Qt.RightButton:
            delta = event.pos().x() - self._mouseMovePos.x()
            scale = 1 + delta / 500.0
            self.scale(scale, scale)
            self._mouseMovePos = event.pos()

        elif (ctrl or alt) and event.buttons() in [Qt.LeftButton, Qt.MiddleButton] and self._isPanning:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - (event.x() - self._panningPos.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - (event.y() - self._panningPos.y()))
            self._panningPos = event.pos()

        elif event.buttons() == Qt.LeftButton and self.rubberBand:
            self.rubberBand.setGeometry(QRect(self._startDrag, event.pos()).normalized())

    def mouseReleaseEvent(self, event):
        ctrl = event.modifiers() & Qt.ControlModifier
        shift = event.modifiers() & Qt.ShiftModifier

        self._isPanning = False

        if event.button() == Qt.LeftButton:
            if self.rubberBand:
                rect = self.mapToScene(self.rubberBand.geometry().normalized()).boundingRect()
                if rect.width() > 3 and rect.height() > 3:
                    scene = self.scene()
                    oldSelection = scene.selectedItems()

                    scene.blockSignals(True)

                    area = QPainterPath()
                    area.addRect(rect)
                    scene.setSelectionArea(area)

                    newSelected = scene.selectedItems()
                    scene.clearSelection()

                    if ctrl or shift: # keep previous selection in ctrl/shift modes
                        for sel in oldSelection:
                            sel.setSelected(True)

                    for sel in newSelected:
                        if shift and ctrl:
                            sel.setSelected(True)
                        elif shift:
                            sel.setSelected(not sel.isSelected())
                        elif ctrl:
                            sel.setSelected(False)
                        else:
                            sel.setSelected(True)

                    scene.blockSignals(False)
                    scene.selectionChangedCallback()

                    if self.selectionBeforeRubberBand:
                        undoFunc = lambda scene=scene, items=self.selectionBeforeRubberBand[:]: (scene.clearSelection(), [item.setSelected(True) for item in items])
                        scene.undoAppend("selection", undoFunc, str([id(item) for item in oldSelection]))

                else: # clear selection
                    self.scene().clearSelection()

                self.rubberBand.deleteLater()
                self.rubberBand = None
        else:
            super(View, self).mouseReleaseEvent(event)

    def getViewportScale(self):
        sx = QVector2D(self.transform().m11(), self.transform().m12()).length()
        sy = QVector2D(self.transform().m21(), self.transform().m22()).length()
        return sx, sy

    def getViewportActualRect(self):
        sx, sy = self.getViewportScale()
        rect = self.viewport().geometry()
        rect.setWidth(rect.width()*(1/sx))
        rect.setHeight(rect.height()*(1/sy))
        return rect

    def wheelEvent(self, event):
        ctrl = event.modifiers() & Qt.ControlModifier
        alt = event.modifiers() & Qt.AltModifier
        if ctrl or alt:
            delta = event.delta() / 120
            scale = 1 + delta*0.1
            self.scale(scale, scale)

class MyRubberBand(QWidget):
    def __init__(self, **kwargs):
        super(MyRubberBand, self).__init__(**kwargs)
        self.color = QColor(85,105,155, 100)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setBrush(self.color)
        painter.setPen(Qt.NoPen)
        painter.drawRect(0,0,self.width()-1, self.height()-1)

class PickerItemWidget(QWidget):
    selected = Signal(object)

    def __init__(self, svgpath="", color="", **kwargs):
        super(PickerItemWidget, self).__init__(**kwargs)

        self.svgpath = svgpath
        self.painterPath = getPainterPath(svgpath, 0.3, 0.3)
        self.color = QColor(color or "#cccccc")

        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)

    def updateShape(self, svgpath="", color=""):
        if color:
            self.color = QColor(color)
        if svgpath:
            self.svgpath = svgpath

        self.painterPath = getPainterPath(self.svgpath, 0.3, 0.3)

    def mousePressEvent(self, event):
        self.selected.emit(self)

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHints(QPainter.Antialiasing)

        boundingRect = self.painterPath.boundingRect()
        grad = QLinearGradient(boundingRect.topLeft(), boundingRect.center())
        grad.setColorAt(0.4, QColor(255,255,255))
        grad.setColorAt(0.8, self.color)

        painter.setPen(self.color.darker(200))
        painter.setBrush(grad)

        painter.drawPath(self.painterPath)

class ShapeBrowserWidget(QDialog):
    def __init__(self, **kwargs):
        super(ShapeBrowserWidget, self).__init__(**kwargs)

        self.selectedSvgpath = ""

        self.setWindowTitle("Select shape")

        with open(RootDirectory+"/shapes.json", "r") as f:
            shapes = json.load(f)

        gridLayout = QGridLayout()
        gridLayout.setDefaultPositioning(10, Qt.Horizontal)

        for sh in sorted(shapes):
            w = PickerItemWidget(shapes[sh])
            w.setToolTip(sh)
            w.selected.connect(self.somethingSelected)
            gridLayout.addWidget(w)

        scrollArea = QScrollArea()
        scrollWidget = QWidget()
        scrollArea.setWidget(scrollWidget)
        scrollArea.setWidgetResizable(True)

        scrollWidget.setLayout(gridLayout)
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(scrollArea)

    def somethingSelected(self, w):
        self.selectedSvgpath = w.svgpath
        self.done(0)

class MySplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent, **kwargs):
        super(MySplitterHandle, self).__init__(orientation, parent, **kwargs)

    def paintEvent(self, event):
        painter = QPainter(self)
        brush = QBrush()
        brush.setStyle(Qt.Dense6Pattern)
        brush.setColor(QColor(150, 150, 150))
        painter.fillRect(event.rect(), QBrush(brush))

class MySplitter(QSplitter):
    def __init__(self, orientation, **kwargs):
        super(MySplitter, self).__init__(orientation, **kwargs)
        self.setHandleWidth(3)

    def createHandle(self):
        return MySplitterHandle(self.orientation(), self)

class ColorWidget(QWidget):
    colorChanged = Signal()
    def __init__(self, color="#000000", **kwargs):
        super(ColorWidget, self).__init__(**kwargs)

        self.color = QColor(color)
        self.setFixedSize(30,30)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        super(ColorWidget, self).paintEvent(event)
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.color if self.color else Qt.NoBrush)
        painter.drawRect(0,0,50,50)

    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            colorDialog = QColorDialog(self.color)
            for i, color in enumerate(NiceColors): # add nice colors
                colorDialog.setCustomColor(i, QColor(color))
            colorDialog.exec_()

            if colorDialog.result():
                self.color = colorDialog.selectedColor()
                self.colorChanged.emit()

        elif event.buttons() == Qt.RightButton:
            ok = QMessageBox.question(self, "Picker", "Remove background?", QMessageBox.Yes and QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes
            if ok:
                self.color = None
                self.colorChanged.emit()

class ImageWidget(QLabel):
    imageChanged = Signal()
    def __init__(self, imagePath="", **kwargs):
        super(ImageWidget, self).__init__(**kwargs)

        self.originalPixmap = QPixmap()

        self.setCursor(Qt.PointingHandCursor)
        self.updatePixmap(None)

    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            fileDialog = QFileDialog.getOpenFileName(self, "Select image", "", "*.jpg;*.png")
            filePath, _ = fileDialog
            if filePath:
                pixmap = QPixmap()
                pixmap.load(filePath)
                self.updatePixmap(pixmap)
                self.imageChanged.emit()

        elif event.buttons() == Qt.RightButton:
            ok = QMessageBox.question(self, "Picker", "Remove image?", QMessageBox.Yes and QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes
            if ok:
                self.updatePixmap(None)
                self.imageChanged.emit()

    def updatePixmap(self, pixmap):
        if pixmap:
            self.setPixmap(pixmap.scaled(50,50))
            self.originalPixmap = pixmap
        else:
            self.originalPixmap = QPixmap()
            self.clear()
            self.setText("(No image)")

class PropertiesWidget(QWidget):
    somethingChanged = Signal()

    def __init__(self, pickerItem=None, **kwargs):
        super(PropertiesWidget, self).__init__(**kwargs)

        self.pickerItem = pickerItem.duplicate() if pickerItem else None # always use copy
        self.changedProperties = []

        self._updating = False

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.shapeWidget = PickerItemWidget()
        self.shapeWidget.selected.connect(lambda _=None: self.selectShape())

        self.backgroundColorWidget = ColorWidget()
        self.backgroundColorWidget.colorChanged.connect(self.backgroundChanged)

        self.foregroundColorWidget = ColorWidget()
        self.foregroundColorWidget.colorChanged.connect(self.foregroundChanged)

        self.imageWidget = ImageWidget()
        self.imageWidget.imageChanged.connect(self.imageChanged)

        self.imageAspectRatioWidget = QComboBox()
        self.imageAspectRatioWidget.addItems(["Ignore", "Keep", "Keep by expanding"])
        self.imageAspectRatioWidget.currentIndexChanged.connect(lambda _=None: self.imageAspectRatioChanged())

        controlLayout = QHBoxLayout()
        self.controlWidget = QLineEdit()
        self.controlWidget.editingFinished.connect(self.controlChanged)
        self.controlWidget.returnPressed.connect(self.controlChanged)
        addControlBtn = QPushButton("<<")
        addControlBtn.setFixedWidth(40)
        addControlBtn.clicked.connect(self.addControlClicked)
        controlLayout.addWidget(self.controlWidget)
        controlLayout.addWidget(addControlBtn)
        controlLayout.setStretch(0,1)
        controlLayout.setStretch(1,0)

        labelLayout = QHBoxLayout()
        self.labelWidget = QLineEdit()
        self.labelWidget.editingFinished.connect(self.labelChanged)
        self.labelWidget.returnPressed.connect(self.labelChanged)
        fontBtn = QPushButton("Font")
        fontBtn.clicked.connect(self.fontChanged)
        fontBtn.setFixedWidth(40)
        labelLayout.addWidget(self.labelWidget)
        labelLayout.addWidget(fontBtn)
        labelLayout.setStretch(0,1)
        labelLayout.setStretch(1,0)

        self.groupWidget = QLineEdit()
        self.groupWidget.editingFinished.connect(self.groupChanged)
        self.groupWidget.returnPressed.connect(self.groupChanged)

        self.flatWidget = QCheckBox()
        self.flatWidget.stateChanged.connect(lambda _=None: self.flatChanged())

        self.flippedWidget = QWidget()
        flippedLayout = QHBoxLayout()
        self.flippedWidget.setLayout(flippedLayout)
        self.flippedWidget.flippedX = QCheckBox("X")
        self.flippedWidget.flippedX.stateChanged.connect(lambda _=None: self.flippedChanged())
        self.flippedWidget.flippedY = QCheckBox("Y")
        self.flippedWidget.flippedY.stateChanged.connect(lambda _=None: self.flippedChanged())
        flippedLayout.addWidget(self.flippedWidget.flippedX)
        flippedLayout.addWidget(self.flippedWidget.flippedY)

        self.rotatedWidget = QCheckBox()
        self.rotatedWidget.stateChanged.connect(lambda _=None: self.rotatedChanged())

        self.scriptWidget = QTextEdit()
        self.scriptWidget.setWordWrapMode(QTextOption.NoWrap)
        self.scriptWidget.setTabStopWidth(16)
        self.scriptWidget.textChanged.connect(self.scriptChanged)

        layout.addWidget(QLabel("Shape"))
        layout.addWidget(self.shapeWidget)

        layout.addWidget(QLabel("Background"))
        layout.addWidget(self.backgroundColorWidget)

        layout.addWidget(QLabel("Foreground"))
        layout.addWidget(self.foregroundColorWidget)

        layout.addWidget(QLabel("Image"))
        layout.addWidget(self.imageWidget)

        layout.addWidget(QLabel("Aspect ratio"))
        layout.addWidget(self.imageAspectRatioWidget)

        layout.addWidget(QLabel("Control"))
        layout.addLayout(controlLayout)

        layout.addWidget(QLabel("Label"))
        layout.addLayout(labelLayout)

        layout.addWidget(QLabel("Group"))
        layout.addWidget(self.groupWidget)

        layout.addWidget(QLabel("Flat"))
        layout.addWidget(self.flatWidget)

        layout.addWidget(QLabel("Flipped"))
        layout.addWidget(self.flippedWidget)

        layout.addWidget(QLabel("Rotated"))
        layout.addWidget(self.rotatedWidget)

        layout.addWidget(QLabel("Script"))
        layout.addWidget(self.scriptWidget)

        layout.addStretch()

        self.updateProperties()

    def fontChanged(self):
        if self.pickerItem.font:
            itemFont = QFont()
            itemFont.fromString(self.pickerItem.font)
        else:
            itemFont = self.font()

        fontDialog = QFontDialog(itemFont, self)
        fontDialog.exec_()
        if fontDialog.result():
            self.pickerItem.font = fontDialog.currentFont().toString()
            self.changedProperties.append("font")
            self.somethingChanged.emit()

    def addControlClicked(self):
        ls = cmds.ls(sl=True)
        if ls:
            self.controlWidget.setText(",".join([n.split(":")[-1] for n in ls]))
            self.controlChanged()

    def selectShape(self):
        shapeBrower = ShapeBrowserWidget(parent=self)
        shapeBrower.exec_()
        if shapeBrower.selectedSvgpath:
            self.shapeWidget.updateShape(shapeBrower.selectedSvgpath)
            self.pickerItem.svgpath = shapeBrower.selectedSvgpath
            self.changedProperties.append("svgpath")
            self.somethingChanged.emit()

    def updateProperties(self, pickerItem=None):
        self.setEnabled(True if pickerItem else False)

        if not pickerItem:
            return

        self.pickerItem = pickerItem.duplicate()

        self._updating = True

        self.shapeWidget.updateShape(self.pickerItem.svgpath, self.pickerItem.background)
        self.backgroundColorWidget.color = QColor(self.pickerItem.background)
        self.foregroundColorWidget.color = QColor(self.pickerItem.foreground)
        self.imageWidget.updatePixmap(str2pixmap(self.pickerItem.image))
        self.imageAspectRatioWidget.setCurrentIndex(self.pickerItem.imageAspectRatio)
        self.imageAspectRatioWidget.setEnabled(True if self.pickerItem.image else False)

        self.controlWidget.setText(self.pickerItem.control)
        self.labelWidget.setText(self.pickerItem.label)
        self.groupWidget.setText(self.pickerItem.group)

        self.flatWidget.setChecked(self.pickerItem.flat)

        self.flippedWidget.flippedX.setChecked(self.pickerItem.flipped[0])
        self.flippedWidget.flippedY.setChecked(self.pickerItem.flipped[1])

        self.rotatedWidget.setChecked(self.pickerItem.rotated)
        self.scriptWidget.setText(self.pickerItem.script)

        self._updating = False
        self.changedProperties = []
        self.update()

    def imageChanged(self):
        if self._updating:return
        self.pickerItem.image = pixmap2str(self.imageWidget.originalPixmap)
        self.imageAspectRatioWidget.setEnabled(True if self.pickerItem.image else False)

        self.changedProperties.append("image")
        self.somethingChanged.emit()

    def imageAspectRatioChanged(self):
        if self._updating:return
        self.pickerItem.imageAspectRatio = self.imageAspectRatioWidget.currentIndex()
        self.changedProperties.append("imageAspectRatio")
        self.somethingChanged.emit()

    def backgroundChanged(self):
        if self._updating:return
        self.pickerItem.background = self.backgroundColorWidget.color.name() if self.backgroundColorWidget.color else ""
        self.changedProperties.append("background")
        self.somethingChanged.emit()

    def foregroundChanged(self):
        if self._updating:return
        self.pickerItem.foreground = self.foregroundColorWidget.color.name()
        self.changedProperties.append("foreground")
        self.somethingChanged.emit()

    def controlChanged(self):
        if self._updating:return
        tmp = self.controlWidget.text()
        if tmp != self.pickerItem.control:
            self.pickerItem.control = self.controlWidget.text()
            self.changedProperties.append("control")
            self.somethingChanged.emit()

    def labelChanged(self):
        if self._updating:return
        tmp = self.labelWidget.text()
        if tmp != self.pickerItem.label:
            self.pickerItem.label = self.labelWidget.text()
            self.changedProperties.append("label")
            self.somethingChanged.emit()

    def groupChanged(self):
        if self._updating:return
        tmp = self.groupWidget.text()
        if tmp != self.pickerItem.group:
            self.pickerItem.group = self.groupWidget.text()
            self.changedProperties.append("group")
            self.somethingChanged.emit()

    def flatChanged(self):
        if self._updating:return
        self.pickerItem.flat = self.flatWidget.isChecked()
        self.changedProperties.append("flat")
        self.somethingChanged.emit()

    def flippedChanged(self):
        if self._updating:return
        self.pickerItem.flipped = [self.flippedWidget.flippedX.isChecked(), self.flippedWidget.flippedY.isChecked()]
        self.changedProperties.append("flipped")
        self.somethingChanged.emit()

    def rotatedChanged(self):
        if self._updating:return
        self.pickerItem.rotated = self.rotatedWidget.isChecked()
        self.changedProperties.append("rotated")
        self.somethingChanged.emit()

    def scriptChanged(self):
        if self._updating:return
        self.pickerItem.script = self.scriptWidget.toPlainText()
        self.changedProperties.append("script")
        self.somethingChanged.emit()

class MayaParameters(object):
    def __init__(self, namespace=":"):
        self.namespace = namespace
        self.attributeToSave = "" # within picker node
        self.doSaveInMayaNode = True
        self.pickerIsModified = False # when picker is changed not in Edit Mode (like a position via middle mouse)
        self.pickerWindow = None

        self.visibilityCallbackIds = []
        self.selectionChangedCallbackId = None

class PropertiesWindow(QDialog):
    def __init__(self):
        super(PropertiesWindow, self).__init__(parent=mayaMainWindow)

        self.setWindowTitle("Properties")
        self.setGeometry(600, 200, 250, 400)

        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint & ~Qt.WindowContextHelpButtonHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.propertiesWidget = PropertiesWidget()
        propsScrollArea = QScrollArea()
        propsScrollArea.setWidget(self.propertiesWidget)
        propsScrollArea.setWidgetResizable(True)

        layout.addWidget(propsScrollArea)

class DraggableButton(QPushButton):
    def __init__(self, title="", **kwargs):
        super(DraggableButton, self).__init__(title, **kwargs)

    def mousePressEvent(self, event):
        if event.buttons() in [Qt.MiddleButton, Qt.LeftButton]:
            mime_data = QMimeData()
            mime_data.setText(" ".join(cmds.ls(sl=True)))

            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, event):
        event.accept()

class PickerWindow(QFrame): # MayaQWidgetDockableMixin
    def __init__(self):
        super(PickerWindow, self).__init__(parent=mayaMainWindow)

        self.mayaParameters = MayaParameters()
        self.mayaParameters.pickerWindow = self

        self._stayOnTopEnabled = False

        self.setWindowTitle("Picker")
        self.setGeometry(600, 200, 400, 500)
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)
        mainLayout.setMargin(0)

        self.propertiesWindow = PropertiesWindow()

        self.scene = Scene(self.propertiesWindow.propertiesWidget, self.mayaParameters)
        self.scene.editModeChanged.connect(self.editModeChanged)

        self.view = View(self.scene)
        self.view.pickerLoaded.connect(self.pickerLoaded)
        self.view.somethingDropped.connect(self.somethingDroppedOnView)

        self.menuBar = self.createMenuBar()

        # tool buttons
        toolsLayout = QHBoxLayout()
        openBtn = QPushButton()
        openBtn.setIcon(QIcon(RootDirectory+"/icons/open.png"))
        openBtn.setToolTip("Open a picker")
        openBtn.clicked.connect(self.view.loadPicker)

        saveBtn = QPushButton()
        saveBtn.setIcon(QIcon(RootDirectory+"/icons/save.png"))
        saveBtn.setToolTip("Save current picker")
        saveBtn.clicked.connect(self.view.savePicker)

        self.toggleEditModeBtn = QPushButton()
        self.toggleEditModeBtn.setIcon(QIcon(RootDirectory+"/icons/edit.png"))
        self.toggleEditModeBtn.setToolTip("Toggle edit mode")
        self.toggleEditModeBtn.setShortcut("Space")
        self.toggleEditModeBtn.clicked.connect(self.toggleEditMode)

        makeControlBtn = DraggableButton()
        makeControlBtn.setIcon(QIcon(RootDirectory+"/icons/plus.png"))
        makeControlBtn.setToolTip("Add controls from selection")

        focusBtn = QPushButton()
        focusBtn.setIcon(QIcon(RootDirectory+"/icons/focus.png"))
        focusBtn.setToolTip("Frame all (F)")
        focusBtn.setShortcut("F")
        focusBtn.clicked.connect(self.view.frameAll)

        self.pinBtn = QPushButton()
        self.pinBtn.setIcon(QIcon(RootDirectory+"/icons/pin.png"))
        self.pinBtn.setToolTip("Toggle stay of top")
        self.pinBtn.clicked.connect(self.toggleStayOnTop)

        toolsLayout.addWidget(openBtn)
        toolsLayout.addWidget(saveBtn)
        toolsLayout.addStretch()
        toolsLayout.addWidget(makeControlBtn)
        toolsLayout.addStretch()
        toolsLayout.addWidget(self.pinBtn)
        toolsLayout.addWidget(focusBtn)
        toolsLayout.addWidget(self.toggleEditModeBtn)

        self.namespaceWidget = QComboBox()
        self.namespaceWidget.activated.connect(self.namespaceChanged)
        self.namespaceWidget.mousePressEvent = self.namespaceMousePressEvent

        mainLayout.setMenuBar(self.menuBar)
        mainLayout.addLayout(toolsLayout)
        mainLayout.addWidget(self.view)
        mainLayout.addWidget(self.namespaceWidget)

        self.updateNamespaces()

        global PickerWindows
        PickerWindows.append(self)

    def somethingDroppedOnView(self):
        self.scene.setEditMode(True)

        if not self.scene.editMode():
            self.uninstallCallbacks()
            self.installCallbacks()

    def pickerLoaded(self, picker, asImport):
        if not asImport:
            if self.scene.editMode():
                self.scene.setEditMode(False)

        self.saveToMayaNode()
        self.installCallbacks()

    def updateNamespaces(self):
        self.namespaceWidget.blockSignals(True)

        current = self.namespaceWidget.currentText()
        self.namespaceWidget.clear()
        self.namespaceWidget.addItem(":")

        for ns in pm.namespaceInfo(lon=True):
            if ns not in ["UI", "shared"]:
                self.namespaceWidget.addItem(ns+":")

        idx = self.namespaceWidget.findText(current)
        if idx != -1:
            self.namespaceWidget.setCurrentIndex(idx)

        self.namespaceWidget.blockSignals(False)

    def namespaceMousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.updateNamespaces()
        QComboBox.mousePressEvent(self.namespaceWidget, event)

    def namespaceChanged(self, idx):
        self.mayaParameters.namespace = self.namespaceWidget.itemText(idx)
        self.installCallbacks()

    def reposePropertyWindow(self):
        rect = self.geometry()
        propGeometry = self.propertiesWindow.geometry()
        self.propertiesWindow.setGeometry(rect.x()-propGeometry.width(), rect.y(), propGeometry.width(), rect.height())

    def moveEvent(self, event):
        self.reposePropertyWindow()

    def resizeEvent(self, event):
        self.reposePropertyWindow()

    def toggleEditMode(self):
        self.scene.setEditMode(False if self.scene.editMode() else True)
        self.scene.updateProperties()

    def editModeChanged(self, v):
        self.toggleEditModeBtn.setStyleSheet("background-color: #dddd88" if v else "")

        if v:
            self.propertiesWindow.show()
            self.reposePropertyWindow()
            self.uninstallCallbacks()
        else:
            self.propertiesWindow.close()
            self.installCallbacks()
            self.saveToMayaNode()

    def saveToMayaNode(self):
        if not self.mayaParameters.doSaveInMayaNode:
            return

        pickerNode = "picker"
        if not pm.objExists(pickerNode):
            pickerNode = pm.createNode("network", n=pickerNode)
        else:
            pickerNode = pm.PyNode(pickerNode)

        pickerIdx = PickerWindows.index(self)
        if not self.mayaParameters.attributeToSave:
            self.mayaParameters.attributeToSave = "data"+str(pickerIdx)

        if not pickerNode.hasAttr(self.mayaParameters.attributeToSave):
            pickerNode.addAttr(self.mayaParameters.attributeToSave, dt="string")

        picker = self.view.toPicker()
        pickerNode.attr(self.mayaParameters.attributeToSave).set(json.dumps(picker.toJson()))
        self.mayaParameters.pickerIsModified = False

    def createNewPicker(self, window=False):
        if window:
            self.view.newPicker(window)
        else:
            self.uninstallCallbacks()
            self.view.newPicker(window)

    def createMenuBar(self):
        menuBar = QMenuBar()

        # file
        fileMenu = QMenu("File", self)
        menuBar.addMenu(fileMenu)

        newAction = QAction("New", self)
        newAction.triggered.connect(lambda _=None:self.createNewPicker(window=False))
        fileMenu.addAction(newAction)

        newWindowAction = QAction("New window", self)
        newWindowAction.triggered.connect(lambda _=None:self.createNewPicker(window=True))
        fileMenu.addAction(newWindowAction)

        openAction = QAction("Open", self)
        openAction.setShortcut("Ctrl+O")
        openAction.triggered.connect(lambda _=None:self.view.loadPicker())
        fileMenu.addAction(openAction)

        saveAction = QAction("Save", self)
        saveAction.setShortcut("Ctrl+S")
        saveAction.triggered.connect(lambda _=None:self.view.savePicker())
        fileMenu.addAction(saveAction)

        fileMenu.addSeparator()

        importAction = QAction("Import", self)
        importAction.setShortcut("Ctrl+I")
        importAction.triggered.connect(lambda _=None: self.view.loadPicker(asImport=True))
        fileMenu.addAction(importAction)

        exportAction = QAction("Export selected", self)
        exportAction.setShortcut("Ctrl+E")
        exportAction.triggered.connect(lambda _=None: self.view.savePicker(selected=True))
        fileMenu.addAction(exportAction)

        fileMenu.addSeparator()

        closeThisPickerAction = QAction("Close this picker", self)
        closeThisPickerAction.triggered.connect(self.closeThisPicker)
        fileMenu.addAction(closeThisPickerAction)

        # edit
        editMenu = QMenu("Edit", self)

        removeAction = QAction("Remove", self)
        removeAction.setShortcut("Delete")
        removeAction.triggered.connect(lambda _=None:self.view.removeItems())
        editMenu.addAction(removeAction)

        duplicateAction = QAction("Duplicate", self)
        duplicateAction.setShortcut("Ctrl+D")
        duplicateAction.triggered.connect(lambda _=None:self.view.duplicateItems())
        editMenu.addAction(duplicateAction)

        mirrorAction = QAction("Mirror", self)
        mirrorAction.setShortcut("Ctrl+M")
        mirrorAction.triggered.connect(lambda _=None:self.view.mirrorItems())
        editMenu.addAction(mirrorAction)

        flipPositionMenu = QMenu("Flip", self)
        for typ in ["left", "right", "up", "down"]:
            action = QAction(typ.capitalize(), self)
            action.triggered.connect(lambda _=None, t=typ: self.view.flipItems(t))
            flipPositionMenu.addAction(action)
        editMenu.addMenu(flipPositionMenu)

        editMenu.addSeparator()

        copyAction = QAction("Copy", self)
        copyAction.setShortcut("Ctrl+C")
        copyAction.triggered.connect(lambda _=None:self.view.clipboardCopyItems())
        editMenu.addAction(copyAction)

        cutAction = QAction("Cut", self)
        cutAction.setShortcut("Ctrl+X")
        cutAction.triggered.connect(lambda _=None:self.view.clipboardCutItems())
        editMenu.addAction(cutAction)

        pasteAction = QAction("Paste", self)
        pasteAction.setShortcut("Ctrl+V")
        pasteAction.triggered.connect(lambda _=None:self.view.clipboardPasteItems())
        editMenu.addAction(pasteAction)

        editMenu.addSeparator()

        rotateAction = QAction("Rotate shape", self)
        rotateAction.triggered.connect(lambda _=None: self.view.rotateItems())
        editMenu.addAction(rotateAction)

        replaceAction = QAction("Replace in control/group", self)
        replaceAction.triggered.connect(lambda _=None: self.view.replaceInNames())
        editMenu.addAction(replaceAction)

        lockImagesAction = QAction("Lock images", self)
        lockImagesAction.setShortcut("Ctrl+L")
        lockImagesAction.setCheckable(True)
        lockImagesAction.setChecked(self.scene.isImagesLocked)
        lockImagesAction.triggered.connect(lambda _=None: self.view.lockImages())
        editMenu.addAction(lockImagesAction)

        selectAllAction = QAction("Select all", self)
        selectAllAction.triggered.connect(lambda _=None:self.view.selectAllItems())
        selectAllAction.setShortcut("Ctrl+A")
        editMenu.addAction(selectAllAction)

        menuBar.addMenu(editMenu)

        # Structure
        arrangementMenu = QMenu("Arrangement", self)

        # row and column
        for label, orientation in [("Make row","row"), ("Make column", "column")]:
            orientMenu = QMenu(label, self)
            for label, size in [("No space", 0), ("Tiny", 5), ("Small", 15), ("Medium", 25), ("Large",35)]:
                action = QAction(label, self)
                action.triggered.connect(lambda _=None, orientation=orientation, size=size: self.view.makeRowColumnFromSelected(orientation, size))
                orientMenu.addAction(action)
            arrangementMenu.addMenu(orientMenu)

        ldiagAction = QAction("Make left diagonal", self)
        ldiagAction.triggered.connect(lambda _=None: self.view.makeRowColumnFromSelected("ldiag", 0))
        arrangementMenu.addAction(ldiagAction)

        rdiagAction = QAction("Make right diagonal", self)
        rdiagAction.triggered.connect(lambda _=None: self.view.makeRowColumnFromSelected("rdiag", 0))
        arrangementMenu.addAction(rdiagAction)

        alignMenu = QMenu("Align", self)
        for label, key, edge in [("Left", "[", "left"), ("Right", "]", "right"), ("Top", "_", "top"), ("HCenter","=", "hcenter"), ("VCenter", "-", "vcenter")]:
            action = QAction(label, self)
            action.setShortcut(key)
            action.triggered.connect(lambda _=None, edge=edge: self.view.alignItems(edge))
            alignMenu.addAction(action)
        arrangementMenu.addMenu(alignMenu)

        menuBar.addMenu(arrangementMenu)

        # size
        sizeMenu = QMenu("Size", self)
        for label, size in [("Tiny", -21), ("Small", -19), ("Meduim", -15), ("Large", -5)]:
            action = QAction(label, self)
            action.triggered.connect(lambda _=None, size=size: self.view.setItemsSize(size))
            sizeMenu.addAction(action)

        sizeMenu.addSeparator()
        sameSizeAction = QAction("As first selected", self)
        sameSizeAction.setShortcut("*")
        sameSizeAction.triggered.connect(lambda _=None:self.view.setSameSize())
        sizeMenu.addAction(sameSizeAction)

        menuBar.addMenu(sizeMenu)
        return menuBar

    def hideEvent(self, event): # on close or minimization
        if self.scene.editMode():
            self.scene.setEditMode(False)

    def closeThisPicker(self):
        self.uninstallCallbacks()
        self.scene.clear()
        self.saveToMayaNode()
        self.close()

    def installCallbacks(self):
        self.uninstallCallbacks()

        controlItemDict = {} # {"namespace:M_spine_1_control": [SceneItem], ...}

        ls = set(cmds.ls(sl=True))

        for item in self.scene.items():
            if isinstance(item, SceneItem) and item.pickerItem.control: # for items with controls
                if len(splitString(item.pickerItem.control)) > 1: # skip multiple selection
                    continue

                node = item.pickerItem.control if item.pickerItem.control.startswith(":") else self.mayaParameters.namespace+item.pickerItem.control

                if pm.objExists(node):
                    node = pm.PyNode(node)

                    item.setSelected(node.name() in ls)

                    if node.name() not in controlItemDict:
                        controlItemDict[node.name()] = [item]
                    else:
                        controlItemDict[node.name()].append(item)

                    hierarchy = [node]+node.getAllParents()
                    for n in hierarchy:
                        data = {"hierarchy":hierarchy, "item":item}
                        callback = pm.scriptJob(ac=[n+".v", pm.Callback(mayaVisibilityCallback, n+".v", data)], kws=True) # attribute change on visibility
                        self.mayaParameters.visibilityCallbackIds.append(callback)

                    item.isMayaControlHidden = False
                    for h in hierarchy:
                        if not h.v.get():
                            item.isMayaControlHidden = True
                            break

                    item.isMayaControlInvalid = False
                else:
                    item.isMayaControlInvalid = True

                item.update()

        f = lambda data=controlItemDict: mayaSelectionChangedCallback(self.mayaParameters, data)
        self.mayaParameters.selectionChangedCallbackId = pm.scriptJob(e=["SelectionChanged", f], kws=True)

    def uninstallCallbacks(self):
        if self.mayaParameters.selectionChangedCallbackId and pm.scriptJob(exists=self.mayaParameters.selectionChangedCallbackId):
            pm.scriptJob(kill=self.mayaParameters.selectionChangedCallbackId)

        for callback in self.mayaParameters.visibilityCallbackIds:
            if pm.scriptJob(exists=callback):
                pm.scriptJob(kill=callback)

        self.mayaParameters.selectionChangedCallbackId = None
        self.mayaParameters.visibilityCallbackIds = []

    def toggleStayOnTop(self):
        if self._stayOnTopEnabled:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._stayOnTopEnabled = not self._stayOnTopEnabled
        self.show()

        self.pinBtn.setStyleSheet("background-color: #88dd88" if self._stayOnTopEnabled else "")

def restoreFromMayaNode():
    global PickerWindows
    global pickerWindow

    while PickerWindows: # clear picker windows
        w = PickerWindows.pop()
        w.uninstallCallbacks()
        w.close()

    pickerNode = "picker"
    if pm.objExists(pickerNode):
        pickerNode = pm.PyNode(pickerNode)
        for attr in pickerNode.listAttr(ud=True, st="data*"):
            picker = Picker()
            picker.fromJson(json.loads(attr.get()))

            if not picker.isEmpty():
                w = PickerWindow()
                w.mayaParameters.attributeToSave = attr.longName()
                w.mayaParameters.doSaveInMayaNode = False
                w.view.loadPicker(picker)
                w.mayaParameters.doSaveInMayaNode = True
                w.show()
                w.view.frameAll()

    if PickerWindows: # use first found
        pickerWindow = PickerWindows[0]
    else:
        pickerWindow = PickerWindow()
        pickerWindow.show()

pickerWindow = PickerWindow()
