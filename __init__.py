import os
import sys
import random
import json
import re
#import svg.path as svg
import base64

from Qt.QtGui import *
from Qt.QtCore import *
from Qt.QtWidgets import *

try:
    import pymel.core as pm
    import pymel.api as api
    import maya.cmds as cmds

    from shiboken2 import wrapInstance
    mayaMainWindow = wrapInstance(long(api.MQtUtil.mainWindow()), QMainWindow)
    from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

    IsInsideMaya = True
except ImportError:
    IsInsideMaya = False

from classes import *    

NiceColors = ["#E6D0DE", "#CDA2BE", "#B5739D", "#E1D5E7", "#C3ABD0", "#A680B8", "#D4E1F5", "#A9C4EB", "#7EA6E0", "#D5E8D4", "#9AC7BF", "#67AB9F", "#D5E8D4", "#B9E0A5", "#97D077", "#FFF2CC", "#FFE599", "#FFD966", "#FFF4C3", "#FFCE9F", "#FFB570", "#F8CECC", "#F19C99", "#EA6B66"]
getNiceColor = lambda:NiceColors[random.randrange(len(NiceColors))]

if sys.version_info.major > 2:
    RootDirectory = os.path.dirname(__file__)
else:    
    RootDirectory = os.path.dirname(__file__.decode(sys.getfilesystemencoding()))

PickerWindows = []
Clipboard = []

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

    scene = data.values()[0].scene()

    mayaParameters.ignoreDoubleSelection = True
    scene.ignoreSelectionChanged = True
    scene.clearSelection()     

    ls = cmds.ls(sl=True)
    #print("maya selection", ls)
    for node in ls:
        item = data.get(node) # found available item for the control
        if item:
            item.setSelected(True)

    scene.ignoreSelectionChanged = False
    scene.updateSortedSelection()

    mayaParameters.ignoreDoubleSelection = False

def splitString(s):
    return re.split("[ ,;]+", s)

def roundTo(n, k=5):
    def _round(n):
        return int(n/k)*k

    T = type(n)

    if T in  [int, float]:
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

        self._ignoreMouseRelease = False

        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSelectedChange | QGraphicsItem.ItemSendsGeometryChanges| QGraphicsItem.ItemIsMovable)
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
        scaleX = self.pickerItem.scale[0]/25 + 1
        scaleY = self.pickerItem.scale[1]/25 + 1

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
        if not self.scene():
            return super(SceneItem, self).itemChange(change, value)

        scene = self.scene()

        if change == QGraphicsItem.ItemSelectedChange:
            self.scaleAnchorItem.setVisible(value and scene.editMode())

            if (not scene.editMode() or scene.isImagesLocked) and self.pickerItem.image:
                cmds.select(cl=True)
                value = False
            elif not scene.editMode() and self.pickerItem.script: # do not select script items
                value = False

            #print("itemChange", value, self)

        elif change == QGraphicsItem.ItemPositionChange:
            scene.undoAppendForSelected("move")

            shift = QApplication.keyboardModifiers() & Qt.ShiftModifier
            if not shift:
                value.setX(roundTo(value.x()))
                value.setY(roundTo(value.y()))

            self.pickerItem.position = [value.x(), value.y()]

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

                if IsInsideMaya and not self.scene().editMode():
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
                
                painter.drawText(boundingRect.center()-QPoint(textSize.width()/2, -textSize.height()/3), self.pickerItem.label)

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
            scene.ignoreSelectionChanged = True

            for item in found:
                item.setSelected(True)
            scene.ignoreSelectionChanged = False
            scene.selectionChangedCallback()

            self._ignoreMouseRelease = True

    def mouseMoveEvent(self, event):
        if self.pickerItem.image and self.scene().isImagesLocked:
            return

        super(SceneItem, self).mouseMoveEvent(event)

    def mousePressEvent(self, event): # exec python script
        if not self.scene().editMode() and self.pickerItem.script:
            if event.buttons() == Qt.LeftButton:            
                self.moveBy(1,1)

                exec(self.pickerItem.script.replace("@", self.scene().mayaParameters.namespace))
        else:
            super(SceneItem, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._ignoreMouseRelease:
            self._ignoreMouseRelease = False
            return

        if not self.scene().editMode() and self.pickerItem.script:
            self.moveBy(-1,-1)
        elif not self.scene().editMode() and len(splitString(self.pickerItem.control))>1: # skip mouseReleaseEvent constuctor for multi control widgets
            return
        else:
            super(SceneItem, self).mouseReleaseEvent(event)

            lastOp = self.scene().getUndoLastOperation()
            if lastOp and lastOp[0].startswith("move"):
                self.scene().undoNewBlock()

class Scene(QGraphicsScene):
    editModeChanged = Signal(bool)

    def __init__(self, propertiesWidget, mayaParameters, **kwargs):
        super(Scene, self).__init__(**kwargs)        

        self.propertiesWidget = propertiesWidget
        self.propertiesWidget.somethingChanged.connect(self.updateItemsProperties)
        self.mayaParameters = mayaParameters

        self.ignoreSelectionChanged = False
        self.isImagesLocked = False

        self._editMode = True
        self._sortedSelection = []

        self.undoEnabled = True
        self._undoStack = [] # [(id, function), (id, function)], where id identifies undo operation, function is a recover function

        self.selectionChanged.connect(self.selectionChangedCallback)

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

        selectedItems = sorted(self.selectedItems(), key=lambda item: QVector2D(self.sceneRect().topLeft()-item.pos()).length()) # distance to origin

        if selectedItems:
            self._sortedSelection = [item for item in self._sortedSelection if item.isSelected()]

            for sel in selectedItems:
                if sel not in self._sortedSelection:
                    self._sortedSelection.append(sel)

        else:
            del self._sortedSelection[:]            

    def selectionChangedCallback(self):        
        if self.ignoreSelectionChanged:
            return

        self.updateSortedSelection()
        
        if self.editMode() and self.sortedSelection():
            self.propertiesWidget.setEnabled(True)                
            self.propertiesWidget.updateProperties(self.sortedSelection()[-1].pickerItem)
        else:
            self.propertiesWidget.setEnabled(False)

        if IsInsideMaya and not self.editMode() and not self.mayaParameters.ignoreDoubleSelection:
            #print("selectionChanged")
            nodes = []
            for item in self.sortedSelection():
                itemNodes = [self.mayaParameters.namespace + ctrl for ctrl in splitString(item.pickerItem.control)]
                itemNodes = [node for node in itemNodes if cmds.objExists(node)]
                nodes += itemNodes

            if nodes:
                cmds.select(nodes)
            else:
                cmds.select(cl=True)

    def sortedSelection(self):
        return self._sortedSelection[:]

    def beginEditBlock(self):
        self.undoEnabled = False
        self.ignoreSelectionChanged = True

    def endEditBlock(self):
        self.updateSortedSelection()
        self.undoEnabled = True
        self.ignoreSelectionChanged = False

    def undoNewBlock(self):
        self.undoAppend("newBlock", None)
    
    def undoAppendForSelected(self, name):
        if not self.undoEnabled or not self.editMode() or not self.sortedSelection():
            return

        funcList = []
        for item in self.sortedSelection():
            f = lambda item=item, state=item.pickerItem.duplicate(): (item.pickerItem.copy(state),                                                                       
                                                                      item.updateShape(),              
                                                                      item.setPos(state.position[0], state.position[1]))
            funcList.append(f)
        undoFunc = lambda funcList=funcList: [f() for f in funcList]

        self.undoAppend(name, undoFunc, str([id(item) for item in self.sortedSelection()]))

    def undoAppend(self, name, undoFunc, operationId=None): # always append into undoStack when operationId is None
        if self.undoEnabled and self.editMode():
            lastOp = self.getUndoLastOperation()

            cmd = "%s %s"%(name, operationId)
            if operationId is not None and lastOp and lastOp[0] == cmd:
                #lastOp = (cmd, undoFunc)
                pass
            else:
                #print("undoAppend new", name)
                self._undoStack.append((cmd, undoFunc))

    def getUndoLastOperation(self):
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
                        #print("undo: "+cmd)
                        break

                self.undoEnabled = True

        else:
            super(Scene, self).keyPressEvent(event)

    def updateItemsFlags(self):
        for item in self.items():
            if isinstance(item, SceneItem):
                if self.editMode():
                    item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSelectedChange | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
                else:
                    item.setFlags(QGraphicsItem.ItemIsSelectable)

    def editMode(self): 
        return self._editMode

    def setEditMode(self, v):
        if v == self._editMode:
            return

        self._editMode = v
        
        self.updateItemsFlags()
        self.editModeChanged.emit(v)

class View(QGraphicsView):
    pickerLoaded = Signal(object, bool) # picker, asImport (True, False)

    def __init__(self, scene, **kwargs):
        super(View, self).__init__(scene, **kwargs)        
        
        self._startDrag = None
        self._isPanning = False
        self.rubberBand = None
        self.selectionBeforeRubberBand = []

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

        self.setMouseTracking(True)
        #self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        #self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        self.setSceneRect(QRect(0,0, 300, 400))

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        if not self.scene().editMode():
            editAction = QAction("Edit", self)
            editAction.triggered.connect(lambda _=None: self.switchEditMode(True))
            menu.addAction(editAction)

            menu.popup(event.globalPos())
        else:
            exitEditAction = QAction("Edit done\tESC", self)
            exitEditAction.triggered.connect(lambda _=None: self.switchEditMode(False))
            menu.addAction(exitEditAction)

        fileMenu = QMenu("File", self)
        newAction = QAction("New", self)
        newAction.triggered.connect(lambda _=None:self.newPicker())
        fileMenu.addAction(newAction)

        newWindowAction = QAction("New window\tCTRL-N", self)
        newWindowAction.triggered.connect(lambda _=None:self.newPicker(window=True))
        fileMenu.addAction(newWindowAction)

        saveAction = QAction("Save\tCTRL-S", self)
        saveAction.triggered.connect(self.savePicker)
        fileMenu.addAction(saveAction)

        openAction = QAction("Open\tCTRL-O", self)
        openAction.triggered.connect(lambda _=None:self.loadPicker())
        fileMenu.addAction(openAction)

        importAction = QAction("Import\tCTRL-I", self)
        importAction.triggered.connect(lambda _=None: self.loadPicker(asImport=True))
        fileMenu.addAction(importAction)

        exportAction = QAction("Export selected", self)
        exportAction.triggered.connect(lambda _=None: self.savePicker(selected=True))
        fileMenu.addAction(exportAction)

        fileMenu.addSeparator()

        showClosedAction = QAction("Show closed windows", self)
        showClosedAction.triggered.connect(lambda _=None: self.showClosedWindows())
        fileMenu.addAction(showClosedAction)

        restoreFromMayaAction = QAction("Restore from Maya", self)
        restoreFromMayaAction.triggered.connect(lambda _=None: restoreFromMayaNode())
        fileMenu.addAction(restoreFromMayaAction)

        menu.addMenu(fileMenu)

        frameAllAction = QAction("Frame all\tf", self)
        frameAllAction.triggered.connect(lambda _=None:self.frameAll())
        menu.addAction(frameAllAction)

        if self.scene().editMode():
            menu.addSeparator()
            insertAction = QAction("Insert\tINS", self)
            insertAction.triggered.connect(lambda _=None:self.insertItem())
            menu.addAction(insertAction)

            removeAction = QAction("Remove\tDEL", self)
            removeAction.triggered.connect(lambda _=None:self.removeItems())
            menu.addAction(removeAction)

            duplicateAction = QAction("Duplicate\tCTRL-D", self)
            duplicateAction.triggered.connect(lambda _=None:self.duplicateItems())
            menu.addAction(duplicateAction)   

            clipboardMenu = QMenu("Clipboard", self)
            copyAction = QAction("Copy\tCTRL-C", self)
            copyAction.triggered.connect(lambda _=None:self.clipboardCopyItems())
            clipboardMenu.addAction(copyAction)

            cutAction = QAction("Cut\tCTRL-X", self)
            cutAction.triggered.connect(lambda _=None:self.clipboardCutItems())
            clipboardMenu.addAction(cutAction)

            pasteAction = QAction("Paste\tCTRL-V", self)
            pasteAction.triggered.connect(lambda _=None:self.clipboardPasteItems())
            pasteAction.setEnabled(True if Clipboard else False)
            clipboardMenu.addAction(pasteAction)

            menu.addMenu(clipboardMenu)

            menu.addSeparator()     

            for label, orientation in [("Make row","row"), ("Make column", "column"), ("Make left diagonal", "ldiag"), ("Make right diagonal", "rdiag")]:
                orientMenu = QMenu(label, self)
                keys = {"row": "\t1", "column": "\t2", "ldiag":"\t3", "rdiag": "\t4"}
                for label, size in [("Tiny", 5), ("Small"+keys.get(orientation,""), 10), ("Medium", 20), ("Large",40)]:
                    action = QAction(label, self)
                    action.triggered.connect(lambda _=None, orientation=orientation, size=size: self.makeRowColumnFromSelected(orientation, size))
                    orientMenu.addAction(action)            
                menu.addMenu(orientMenu)

            alignMenu = QMenu("Align", self)
            for label, edge in [("Left\t[", "left"), ("Right\t]", "right"), ("Top\t_", "top"), ("HCenter\t=", "hcenter"), ("VCenter\t-", "vcenter")]:
                action = QAction(label, self)
                action.triggered.connect(lambda _=None, edge=edge: self.alignItems(edge))
                alignMenu.addAction(action)

            snapToGridAction = QAction("Snap to grid\t.", self)
            snapToGridAction.triggered.connect(lambda _=None: self.snapToGridItems())
            alignMenu.addAction(snapToGridAction)
            menu.addMenu(alignMenu)

            flipPositionMenu = QMenu("Flip", self)
            for typ in ["left", "right", "up", "down"]:
                action = QAction(typ.capitalize(), self)
                action.triggered.connect(lambda _=None, t=typ: self.flipItems(t))
                flipPositionMenu.addAction(action)            
            menu.addMenu(flipPositionMenu)    
            
            sizeMenu = QMenu("Size", self)
            for label, size in [("Tiny", -21), ("Small\tALT-1", -19), ("Meduim\tALT-2", -15), ("Large", -5)]:
                action = QAction(label, self)
                action.triggered.connect(lambda _=None, size=size: self.setItemsSize(size))
                sizeMenu.addAction(action)

            sizeMenu.addSeparator()
            sameSizeAction = QAction("As first selected\t*", self)
            sameSizeAction.triggered.connect(lambda _=None:self.setSameSize())
            sizeMenu.addAction(sameSizeAction)
            menu.addMenu(sizeMenu)

            rotateAction = QAction("Rotate", self)
            rotateAction.triggered.connect(lambda _=None: self.rotateItems())
            menu.addAction(rotateAction)

            toolsMenu = QMenu("Tools", self)
            replaceAction = QAction("Replace in control/group", self)
            replaceAction.triggered.connect(lambda _=None: self.replaceAction())
            toolsMenu.addAction(replaceAction)
            menu.addMenu(toolsMenu)

            menu.addSeparator()

            lockImagesAction = QAction("Lock images\tCTRL-L", self)
            lockImagesAction.setCheckable(True)
            lockImagesAction.setChecked(self.scene().isImagesLocked)
            lockImagesAction.triggered.connect(lambda _=None: self.lockImages())
            menu.addAction(lockImagesAction)

            selectAllAction = QAction("Select all", self)
            selectAllAction.triggered.connect(lambda _=None:self.selectAllItems())
            menu.addAction(selectAllAction)   

        menu.popup(event.globalPos())

    def showClosedWindows(self):
        for w in PickerWindows:
            w.show()

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
        if Clipboard:
            scene = self.scene()
            oldSelection = scene.sortedSelection()
            
            scene.clearSelection()

            newItems = []
            for pickerItem in Clipboard:
                item = SceneItem(pickerItem)

                scene.beginEditBlock()
                scene.addItem(item)
                item.setPos(pickerItem.position[0], pickerItem.position[1])    
                item.setSelected(True)
                scene.endEditBlock()

                newItems.append(item)

            undoFunc = lambda items=newItems, scene=scene, selection=oldSelection: ([scene.removeItem(item) for item in items],
                                                                                    scene.clearSelection(), 
                                                                                    [item.setSelected(True) for item in oldSelection])
            scene.undoAppend("paste", undoFunc)

            scene.propertiesWidget.updateProperties(newItems[-1].pickerItem)
            Clipboard = []  

    def selectAllItems(self):
        oldSelection = self.scene().sortedSelection()
        scene = self.scene()

        undoFunc = lambda scene=scene, items=oldSelection: (scene.clearSelection(), [item.setSelected(True) for item in items])
        scene.undoAppend("selection", undoFunc, str([id(item) for item in oldSelection]))

        scene.beginEditBlock()
        for item in scene.items():
            item.setSelected(True)
        scene.endEditBlock()

    def snapToGridItems(self, items=None):
        for sel in items or self.scene().sortedSelection():
            sel.setPos(roundTo(sel.pos()))

    def replaceAction(self):
        replace, ok = QInputDialog.getText(self, "Replace", "Replace inside control/group (old=new)", QLineEdit.Normal, "L_=R_")
        if ok and replace:
            replaceItems = replace.split("=")
            if len(replaceItems)==2:
                old, new = replaceItems
                selection = self.scene().sortedSelection()
                for item in selection:
                    item.pickerItem.control = item.pickerItem.control.replace(old,new)
                    item.pickerItem.group = item.pickerItem.group.replace(old,new)

                self.scene().propertiesWidget.updateProperties(selection[-1].pickerItem)
            else:
                QMessageBox.critical(self, "Replace", "Invalid replace format. Must be 'old=new', i.e L_=R_")

    def newPicker(self, window=False):
        if not window:
            ok = QMessageBox.question(self, "Picker", "Clear current and make new picker?", QMessageBox.Yes and QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes
            if ok:
                self.setTransform(QTransform()) # reset scale
                scene = self.scene()
                scene.setEditMode(True)
                scene.clear()
                scene.flushUndo()
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

    def loadPicker(self, picker=None, asImport=False): 
        if not picker:
            picker = self.loadPickerFromFile()
        if not picker:
            return

        scene = self.scene()
        scene.undoEnabled = False

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

        scene.undoEnabled = True

        scene.updateItemsFlags()

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

        if selected:
            self.scene().propertiesWidget.updateProperties(selected[-1].pickerItem)

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

    def insertItem(self):
        if not self.scene().editMode():
            return
            
        newPos = roundTo(self.mapToScene(self.mapFromGlobal(QCursor.pos())))

        shapeBrower = ShapeBrowserWidget(parent=self)
        shapeBrower.exec_()
        if shapeBrower.selectedSvgpath:            
            item = SceneItem(PickerItem(shapeBrower.selectedSvgpath))

            scene = self.scene()
            oldSelection = scene.sortedSelection()

            scene.beginEditBlock()
            scene.addItem(item)
            item.setPos(newPos)    
            item.setSelected(True)
            scene.endEditBlock()

            undoFunc = lambda item=item, scene=scene, selection=oldSelection: (scene.removeItem(item), 
                                                                               scene.clearSelection(), 
                                                                               [item.setSelected(True) for item in oldSelection])
            scene.undoAppend("insert", undoFunc)

            scene.propertiesWidget.updateProperties(item.pickerItem)

    def switchEditMode(self, v):
        self.setSceneRect(enlargeRect(self.scene().itemsBoundingRect(), 10))

        self.scene().setEditMode(v)
        self.scene().propertiesWidget.setEnabled(v)

    def rotateItems(self):
        if not self.scene().editMode():
            return

        selected = self.scene().sortedSelection()
        for item in selected:
            item.pickerItem.rotated = not item.pickerItem.rotated
            item.updateShape()

        if selected:
            self.scene().propertiesWidget.updateProperties(selected[-1].pickerItem)

    def setItemsSize(self, size):
        if not self.scene().editMode():
            return
        
        for item in self.scene().sortedSelection():
            item.setUnitScale(QVector2D(size, size))

    def duplicateItems(self):
        if not self.scene().editMode():
            return

        scene = self.scene()
        selected = scene.sortedSelection()

        if selected:
            scene.beginEditBlock()

            newItems = []
            for sel in selected[::-1]:
                newPos = sel.pos() + QPointF(25,25)
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
            self.scene().undoAppend("duplicate", undoFunc)

    def makeRowColumnFromSelected(self, orientation, size):
        if not self.scene().editMode():
            return

        selected = self.scene().sortedSelection()
        if len(selected) > 1:
            self.scene().undoNewBlock()

            prev = 0
            for item in selected[1:]:
                prevWidth = roundTo(selected[prev].boundingRect().width())
                prevHeight = roundTo(selected[prev].boundingRect().height())

                if orientation=="column":
                    item.setPos(selected[0].x(), selected[prev].pos().y()+prevHeight+size)
                elif orientation=="row":
                    item.setPos(selected[prev].pos().x()+prevWidth+size, selected[0].y())
                elif orientation=="ldiag":
                    item.setPos(selected[prev].x()-size*2, selected[prev].pos().y()+prevHeight+5)
                elif orientation=="rdiag":
                    item.setPos(selected[prev].x()+size*2, selected[prev].pos().y()+prevHeight+5)
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

        if ctrl and event.key() == Qt.Key_D:
            self.duplicateItems()

        elif event.key() == Qt.Key_Escape:
            self.switchEditMode(False)

        elif ctrl and event.key() == Qt.Key_S:
            self.savePicker()

        elif ctrl and event.key() == Qt.Key_O:
            self.loadPicker()

        elif ctrl and event.key() == Qt.Key_I:
            self.loadPicker(asImport=True)

        elif ctrl and event.key() == Qt.Key_L:
            self.lockImages()

        elif ctrl and event.key() == Qt.Key_N:
            self.newPicker(window=True)

        elif ctrl and event.key() == Qt.Key_C:
            self.clipboardCopyItems()

        elif ctrl and event.key() == Qt.Key_X:
            self.clipboardCutItems()

        elif ctrl and event.key() == Qt.Key_V:
            self.clipboardPasteItems()

        elif event.key() == Qt.Key_Equal:
            self.alignItems("hcenter")

        elif event.key() == Qt.Key_Minus:
            self.alignItems("vcenter")

        elif event.key() == Qt.Key_BracketLeft:
            self.alignItems("left")

        elif event.key() == Qt.Key_BracketRight:
            self.alignItems("right")

        elif event.key() == Qt.Key_Underscore:
            self.alignItems("top")

        elif event.key() == Qt.Key_Period:# dot
            self.snapToGridItems()

        elif event.key() == Qt.Key_Asterisk:
            self.setSameSize()

        elif alt and event.key() == Qt.Key_1:
            self.setItemsSize(-19)

        elif alt and event.key() == Qt.Key_2:
            self.setItemsSize(-15)

        elif event.key() == Qt.Key_1:
            self.makeRowColumnFromSelected("row", 10)

        elif event.key() == Qt.Key_2:
            self.makeRowColumnFromSelected("column", 10)

        elif event.key() == Qt.Key_3:
            self.makeRowColumnFromSelected("ldiag", 10)

        elif event.key() == Qt.Key_4:
            self.makeRowColumnFromSelected("rdiag", 10)

        elif event.key() == Qt.Key_Insert:
            self.insertItem()

        elif event.key() == Qt.Key_Delete:
            self.removeItems()

        elif event.key() == Qt.Key_F: # frame all
            self.frameAll()

        else:
            super(View, self).keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if event.modifiers() & Qt.ShiftModifier:
                event.setModifiers(Qt.ControlModifier)

            self.selectionBeforeRubberBand = self.scene().sortedSelection()
            super(View, self).mousePressEvent(event)

            itemAt = self.itemAt(event.pos())
            # check if it's a simple SceneItem or image with conditions
            if isinstance(itemAt, ScaleAnchorItem):
                return

            if itemAt and\
               (not itemAt.pickerItem.image or
                (itemAt.pickerItem.image and
                 not (self.scene().isImagesLocked or not self.scene().editMode()))): 
               return

            self._startDrag = event.pos()

            if not self.rubberBand:            
                self.rubberBand = MyRubberBand(parent=self.viewport())

            self.rubberBand.setGeometry(QRect(self._startDrag, QSize()))
            self.rubberBand.show()

        elif event.buttons() == Qt.MiddleButton:
            self._isPanning = True
            self._panningPos = event.pos()

        else:
            super(View, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super(View, self).mouseMoveEvent(event)
        if self.rubberBand:
            self.rubberBand.setGeometry(QRect(self._startDrag, event.pos()).normalized())

        if self._isPanning:            
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - (event.x() - self._panningPos.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - (event.y() - self._panningPos.y()))              
            self._panningPos = event.pos()

    def mouseReleaseEvent(self, event):
        ctrl = event.modifiers() & Qt.ControlModifier
        shift = event.modifiers() & Qt.ShiftModifier

        self._isPanning = False

        if shift:
            event.setModifiers(Qt.ControlModifier)

        super(View, self).mouseReleaseEvent(event)

        if self.rubberBand:
            rect = self.mapToScene(self.rubberBand.geometry().normalized()).boundingRect()
            if rect.width() > 5 and rect.height() > 5:
                scene = self.scene()
                oldSelection = scene.selectedItems()

                scene.beginEditBlock()

                area = QPainterPath()
                area.addRect(rect)
                scene.setSelectionArea(area)

                newSelected = scene.selectedItems()
                scene.clearSelection()

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

                scene.endEditBlock()
                scene.selectionChangedCallback()

                if self.selectionBeforeRubberBand:
                    undoFunc = lambda scene=scene, items=self.selectionBeforeRubberBand[:]: (scene.clearSelection(), [item.setSelected(True) for item in items])
                    scene.undoAppend("selection", undoFunc, str([id(item) for item in oldSelection]))

            self.rubberBand.deleteLater()
            self.rubberBand = None
        else:
            itemAt = self.itemAt(event.pos())
            if isinstance(itemAt, SceneItem):
                if shift and ctrl: 
                    itemAt.setSelected(True)
                elif shift:
                    itemAt.setSelected(itemAt.isSelected()) # toggle
                elif ctrl:
                    itemAt.setSelected(False)

    def drawBackground(self, painter, rect):
        def isRectEqual(r1, r2, rough=1.5): 
            return abs(r1.width() - r2.width())<rough and abs(r1.height() - r2.height())<rough

        modifiers = QApplication.keyboardModifiers()
        shift = modifiers & Qt.ShiftModifier

        scene = self.scene()
        if scene.editMode() and isRectEqual(rect, self.getViewportActualRect()):
            painter.fillRect(self.sceneRect(), QColor(0,0,0,30))

            editText = "EDIT"
            painter.setPen(QColor(30,30,30))
            font = painter.font()
            font.setPointSize(50)
            painter.setFont(font)
            fontMetrics = QFontMetrics(font)
            textSize = fontMetrics.size(0, editText)
            painter.drawText(rect.right()-textSize.width(), rect.bottom()-10, editText)

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
        self.color = QColor(color or NiceColors[3])

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
        if IsInsideMaya:
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
        if pickerItem is not None:
            self.pickerItem = pickerItem.duplicate()

        if not self.pickerItem:
            self.setEnabled(False)
            return

        self.setEnabled(True)
        
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
        self.ignoreDoubleSelection = False
        self.attributeToSave = "" # within picker node
        self.doSaveInMayaNode = True

class PickerWindow(QFrame): # MayaQWidgetDockableMixin
    def __init__(self):
        super(PickerWindow, self).__init__(parent=mayaMainWindow if IsInsideMaya else None)

        self.mayaVisibilityCallbackIds = []
        self.mayaSelectionChangedCallbackId = []        
        self.mayaParameters = MayaParameters()

        self._stayOnTopEnabled = False

        self.setWindowTitle("Picker")
        self.setGeometry(600, 200, 600, 700)
        
        if IsInsideMaya:
            self.setWindowFlags(self.windowFlags() | Qt.Window)
        else:
            self.setWindowFlags(self.windowFlags() | Qt.Window)

        mainLayout = QVBoxLayout()
        self.setLayout(mainLayout)

        self.propertiesWidget = PropertiesWidget()
        propsScrollArea = QScrollArea()
        propsScrollArea.setWidget(self.propertiesWidget)
        propsScrollArea.setWidgetResizable(True)

        self.scene = Scene(self.propertiesWidget, self.mayaParameters)
        self.scene.editModeChanged.connect(self.editModeChanged)
        
        self.view = View(self.scene)
        self.view.pickerLoaded.connect(self.pickerLoaded)

        self.splitter = MySplitter(Qt.Horizontal)
        self.splitter.addWidget(propsScrollArea)
        self.splitter.addWidget(self.view)
        self.splitter.setSizes([200, 600])
        self.splitter.setStretchFactor(0,0)
        self.splitter.setStretchFactor(1,1)

        mainLayout.addWidget(self.splitter)

        hlayout = QHBoxLayout()

        self.namespaceWidget = QComboBox()
        self.namespaceWidget.activated.connect(self.namespaceChanged)
        self.namespaceWidget.mousePressEvent = self.namespaceMousePressEvent
        hlayout.addWidget(self.namespaceWidget)

        self.pinBtn = QPushButton("Pin")
        self.pinBtn.clicked.connect(self.toggleStayOnTop)
        hlayout.addWidget(self.pinBtn)
        hlayout.setStretch(0,1)
        hlayout.setStretch(1,0)

        mainLayout.addLayout(hlayout)

        self.updateNamespaces()

        setStylesheet(self)

        global PickerWindows
        PickerWindows.append(self)

    def pickerLoaded(self, picker, asImport):
        if not asImport:
            rect = self.geometry()
            attributesSize = self.splitter.sizes()[0]
            self.setGeometry(rect.x(),rect.y(),picker.size[0]+attributesSize+30,picker.size[1]+65) # +namespaceWidget.height

            if self.scene.editMode():
                self.scene.setEditMode(False)
            else:
                self.installCallbacks()

    def updateNamespaces(self):
        if not IsInsideMaya:return
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
        if not IsInsideMaya:return
        if event.buttons() in [Qt.LeftButton]:
            self.updateNamespaces()
        QComboBox.mousePressEvent(self.namespaceWidget, event)

    def namespaceChanged(self, idx):
        self.mayaParameters.namespace = self.namespaceWidget.itemText(idx)
        self.installCallbacks()

    def editModeChanged(self, v):
        for i in range(self.splitter.count()):
            h = self.splitter.handle(i)
            h.setEnabled(v)

        attributesWidth = self.splitter.sizes()[0] if self.splitter.sizes()[0] > 0 else 200
        rect = self.geometry()
        if v:
            self.setGeometry(rect.x()-attributesWidth, rect.y(), rect.width()+attributesWidth, rect.height())
            self.splitter.setSizes([attributesWidth,600])
            self.splitter.setHandleWidth(3)
            self.uninstallCallbacks()
        else:
            self.setGeometry(rect.x()+attributesWidth, rect.y(), rect.width()-attributesWidth, rect.height())
            self.splitter.setSizes([0,600])
            self.splitter.setHandleWidth(0)
            self.installCallbacks()

            self.saveToMayaNode()

    def saveToMayaNode(self):        
        if not IsInsideMaya or not self.mayaParameters.doSaveInMayaNode: 
            return

        pickerNode = "picker"
        if not pm.objExists(pickerNode):
            pickerNode = pm.createNode("network", n=pickerNode)
        else:
            pickerNode = pm.PyNode(pickerNode)

        def getUniqueAttributeName():
            idx = 0
            while pickerNode.hasAttr("data%d"%idx):
                idx+=1
            return "data%d"%idx

        picker = self.view.toPicker()
        if not picker.isEmpty():
            if not self.mayaParameters.attributeToSave:
                self.mayaParameters.attributeToSave = getUniqueAttributeName()

            if not pickerNode.hasAttr(self.mayaParameters.attributeToSave):
                pickerNode.addAttr(self.mayaParameters.attributeToSave, dt="string")

            pickerNode.attr(self.mayaParameters.attributeToSave).set(json.dumps(picker.toJson()))

            #print("save in maya", PickerWindows.index(self))

    def installCallbacks(self):
        if not IsInsideMaya:return
        
        if self.mayaVisibilityCallbackIds:
            self.uninstallCallbacks()

        controlItemDict = {} # {"namespace:M_spine_1_control": SceneItem, ...}

        ls = set(cmds.ls(sl=True))

        for item in self.scene.items():
            if isinstance(item, SceneItem) and item.pickerItem.control: # for items with controls
                if len(splitString(item.pickerItem.control)) > 1: # skip multiple selection
                    continue

                node = self.mayaParameters.namespace+item.pickerItem.control

                if pm.objExists(node):
                    node = pm.PyNode(node)

                    item.setSelected(node.name() in ls)

                    controlItemDict[node.name()] = item
                    hierarchy = [node]+node.getAllParents()
                    for n in hierarchy:
                        data = {"hierarchy":hierarchy, "item":item}
                        callback = pm.scriptJob(ac=[n+".v", pm.Callback(mayaVisibilityCallback, n+".v", data)]) # attribute change on visibility
                        self.mayaVisibilityCallbackIds.append(callback)

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
        self.mayaSelectionChangedCallbackId = pm.scriptJob(e=["SelectionChanged", f])
        #print("install", PickerWindows.index(self))

    def uninstallCallbacks(self):
        if not IsInsideMaya:return

        if self.mayaSelectionChangedCallbackId and pm.scriptJob(exists=self.mayaSelectionChangedCallbackId):
            pm.scriptJob(kill=self.mayaSelectionChangedCallbackId)

        for callback in self.mayaVisibilityCallbackIds:
            pm.scriptJob(kill=callback)

        self.mayaVisibilityCallbackIds = []
        #print("uninstall",PickerWindows.index(self))

    def closeEvent(self, event):
        self.uninstallCallbacks()

    def toggleStayOnTop(self):
        if self._stayOnTopEnabled:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.pinBtn.setText("Pin")
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.pinBtn.setText("Unpin")

        self._stayOnTopEnabled = not self._stayOnTopEnabled
        self.show()

def setStylesheet(w):    
    with open(RootDirectory+"/qss/qstyle.qss", "r") as f:
        iconsDir = (RootDirectory+"/qss/icons/").replace("\\","/")
        style = f.read().replace("icons/", iconsDir)
        w.setStyleSheet(style)

def restoreFromMayaNode():
    pickerNode = "picker"
    if pm.objExists(pickerNode):

        global PickerWindows
        for w in PickerWindows:
            w.close()
        PickerWindows = []

        pickerNode = pm.PyNode(pickerNode)
        for attr in pickerNode.listAttr(ud=True, st="data*"):
            picker = Picker()
            picker.fromJson(json.loads(attr.get()))

            w = PickerWindow()
            w.mayaParameters.attributeToSave = attr.longName()
            w.mayaParameters.doSaveInMayaNode = False
            w.view.loadPicker(picker)
            w.mayaParameters.doSaveInMayaNode = True
            w.show()

if __name__ == '__main__':
    app = QApplication([])
    w = PickerWindow()
    w.show()
    app.exec_()
else:
    pickerWindow = PickerWindow()    
