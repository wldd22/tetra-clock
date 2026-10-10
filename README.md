# Tetra Clock

A custom alarm clock loosely based on the Blare guide.

## Details
PCB made using KiCAD<br>
Firmware uses CircuitPython

## About
Originally made for week 1 (PCB week) of Hack Club's Half Life.
The idea and some of the components used were based on the Blare guide,
but the design and firmware were created from scratch by me.

The design uses a XIAO ESP32-S3 as the microcontroller, and a
0.91 inch 128x32 OLED display (that uses the SSD1306 driver) to
display the time. The alarm sound is played by a piezo buzzer.
Capacitive touchpads are used to set interact with the clock.

## Images

### Schematic

![Schematic](images/schematic.png)

### PCB

![PCB](images/routing.png)
