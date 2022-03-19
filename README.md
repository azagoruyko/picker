# Picker
Yet another flexible picker for animators in Maya.<br>

![picker1](https://user-images.githubusercontent.com/9614751/159113298-dfef29ba-7764-4967-a8bb-c7c52469614d.PNG)

Youtube: https://www.youtube.com/watch?v=TJN8QXDixv8

## Features
* Highly customizable.<br>
  Animators can add new controls, import pickers and combine them.
* Image backgrounds.
* Multiple selections.
* Double click selection groups.
* Custom python scripts.
* Selection and visibility are fully synchronized with Maya.<br>
  This works for widgets that have a single control.
* Undo support.
* Multiple pickers.
* Scalable and pannable.

## How to run
Add *picker* folder to your script path and run as
```python
import picker
picker.pickerWindow.show()
```

## Custom shapes
All shapes are kept in *shapes.json* as SVG-path items. So you can use any SVG-path editor to draw what you need and insert it here in *shape.json*.
Currently picker doesn't support A/a command for paths.
