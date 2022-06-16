def color2hex(r,g,b):
    return "#%0.2x%0.2x%0.2x"%(r,g,b)

def size2scale(s):
    return 25 * (s/100.0 - 1.0)

class PickerItem(object):
    def __init__(self, svgpath="M 0 0 h 100 v 100 h -100 v -100 Z"):
        self.position = [0,0]
        self.background = "#eaa763" #getNiceColor()
        self.foreground = "#000000"
        self.image = "" # pixmap bytes
        self.imageAspectRatio = 2 # 0-IgnoreAspectRatio, 1-KeepAspectRatio, 2-KeepAspectRatioByExpanding
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
