# F91 Tycho

F91 Tycho is a continuation of **[F91 Kepler](https://github.com/drpykachu/F91_Kepler)** by Pegor (originally on [GitLab](https://gitlab.com/_Pegor/kepler_fw)), a full replacement of the Casio F-91W internals with an OLED display and a Bluetooth CC2640R2 MCU. All credit for the original design goes to them; this repo keeps their full history and MIT license.

What's new here:
- **Rechargeable v2:** LIR2016 cell, BQ25180 charger, TPS62840 buck, and a small charging PCB in the case back's dip with a magnetic pogo cable ([main board](Hardware/KiCad/F91-Main_board_v2/README.md), [charging PCB](Hardware/KiCad/F91-Charge_pad/README.md), [JLC panel](Hardware/KiCad/panel/README.md)).
- **KiCad import** of the original DipTrace boards (`Hardware/KiCad/`).
- **Firmware:** battery-life work, v2 charger/battery support (written, not yet compiled).
- **SolidCraft** case + electronics model (`Hardware/SolidCraft/`).
- Open work: [TASKS.md](TASKS.md).

Code identifiers (`f91_kepler.c`, project names, file names) keep the Kepler name so the original build setup still works.

---

## Original F91 Kepler README

## 8/8/25 - This project hasn't been active for a while, but I have kept it around for anyone interested in it or wants to draw inspiration from it. I have moved it from its [original repo](https://gitlab.com/_Pegor/kepler_fw) since I use GitHub more these days. 
<p align="center">
  <img src="Hardware/images/main.jpg" alt="Main view" width="600"/>
</p>

The F91 Kepler is complete redesign of the classic Casio F91W watch. This project completely replaces the original internals of the watch only keeping the original case and adding an OLED display and a bluetooth capable MCU.

This repo contains all the firmware, hardware, and completely unfinished software (phone app) ;).

## As of 7/18/22 the current state of the project is:
- Bluetooth capable and supports several calls.
- Only operates through bluetooth diagnostic apps such as nRF Connect.
- Full screen notifications for calls/texts.
- Notifications bar.
- Only one button currently supported to wake screen.
- Battery life of roughly 15 days with waking screen several times a day.

## To-do / improvements:
- Create phone app to handle sending BLE calls automatically.
- Add ability to set time through buttons.
- Add sound capabilities (PCB already contains traces). 
- Improve battery life and efficiency.
- Improve programming jig (make it easier to use without having to completely dismantle).
- Make rechargeable



### At this point (read more like a year ago) I am burnt out from this project and now I figured to open it up and hopefully more people can be involved.


<p align="center">
  <img src="Hardware/images/text_from.jpg" alt="Text From Sample" width="500"/>
</p>