# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a flexible picker tool for Maya animators that allows creation of customizable control interfaces. The picker creates interactive UI elements that can select Maya controls, run Python scripts, and display custom backgrounds.

## Maya Version Compatibility

The project supports Maya 2022+ with automatic PySide version detection:
- Maya versions < 2025: Uses PySide2
- Maya 2025+: Uses PySide6

## Key Architecture

### Core Classes
- `PickerItem`: Individual picker elements with properties like position, color, image, control bindings, and custom scripts
- `Picker`: Container for multiple PickerItems with size and metadata
- `PickerWindow`: Main Qt interface inheriting from QFrame
- `Scene`/`View`: Qt Graphics framework for rendering picker items
- `SceneItem`: Graphics representation of PickerItems with Qt painting

### Main Entry Points
- `restoreFromMayaNode()`: Primary function to restore pickers from Maya scene or create new ones
- `animschool_converter.convertFromPkrFile()`: Convert AnimSchool .pkr files to this picker format

### Data Storage
- Pickers are stored as Maya scene nodes (persistent in .ma/.mb files)
- Custom shapes defined in `shapes.json` as SVG paths
- Images stored as base64-encoded strings within picker data

## Common Commands

### Running the Picker
```python
import picker
picker.restoreFromMayaNode()  # Restore from scene or create new
```

### Converting AnimSchool Pickers
```python
import picker.animschool_converter
picker.animschool_converter.convertFromPkrFile("D:/somepicker.pkr")
```

## File Structure
- `__init__.py`: Main picker implementation (2600+ lines)
- `animschool_converter.py`: AnimSchool PKR file converter
- `animschool_parser.py`: PKR file format parser
- `shapes.json`: SVG path definitions for picker shapes
- `icons/`: UI icons for the picker interface

## Development Notes
- No test files or build system detected
- Uses PyMel and Maya.cmds for Maya integration
- Qt Graphics View framework for rendering
- Custom undo support implementation
- Selection/visibility synchronization with Maya through callbacks