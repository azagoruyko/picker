# Picker
Yet another flexible picker for animators in Maya.<br>

![image](https://user-images.githubusercontent.com/9614751/226429549-0582ae4a-92db-4aa0-a97c-8719848fdd07.png)

Youtube: https://www.youtube.com/watch?v=TJN8QXDixv8

## Features
* Highly customizable.<br>
  Animators can add new controls, import pickers and combine them.
* Image backgrounds. <br>
  Stored in picker files.
* Multiple selections.
* Double click selection groups.
* Custom python scripts.
* Selection and visibility are fully synchronized with Maya.<br>
  This works for widgets that have a single control.
* Undo support.
* Multiple pickers.
* Scalable

## How to run
Add *picker* folder to your script path and run as
```python
import picker
picker.restoreFromMayaNode() # restore pickers from current scene or create a new one
```

## Custom shapes
All shapes are kept in *shapes.json* as SVG-path items. So you can use any SVG-path editor to draw what you need and insert it here in *shape.json*.
Currently picker doesn't support A/a command for paths.

## Animschool picker converter
Use `animschool_converter.py` script for this purpose.
Run the following.
```python
import picker.animschool_converter
picker.animschool_converter.convertFromPkrFile("D:/somepicker.pkr")
```
