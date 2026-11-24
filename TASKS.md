# F91 Tycho – Open Tasks

## When the F91W is open

### 1. Case interior: taken from 3D files (no caliper measurements, by decision)
Sources: GrabCAD "Casio F-91W watch" STL (`Hardware/reference/grabcad-f91w/`, cm units, approximate, outer case 33.0 × 36.7 mm vs real 35.2 × 38.2 mm), Sensor Watch PCB outline (`Hardware/reference/sensor-watch/`), own holder STEP.
- Internal cavity: **27.0 × 24.0 mm**, constant from 1.5 to 6.5 mm height (GrabCAD STL sliced every 0.5 mm, `Hardware/reference/tools/slice_case.py`).
- Window opening: ~**23 × 14 mm** near the top.
- Original module PCB: 24.40 × 24.38 mm, 0.61 mm thick (Sensor Watch OSO-SWAT-C1).
- Movement holder (`Hardware/3D-Parts/F91-Movement_holder.step`): 27.1 × 25.6 mm. Consistent with the cavity.
- **Caliper photos 2026-11-24** (`Hardware/images/measurements/`, file suffix in brackets): case depth from the back opening to the window **5.68** [895]; round cavity diameter **27.61** [897] (repeats 27.63 / 27.60 [898, 899]); notch-to-notch across the round cavity, 12–6 **25.11** [894] (notches reach in to r ≈ 12.56 mm); original module notch-to-notch **25.70** [900]. The module (25.70) is larger than the case notch reading (25.11) yet fits, so the case readings taken with the main jaws inside the cavity [894, 897–899] read low by ≥ 0.6 mm; re-measure 894 and 897 with the small upper inside jaws. Holder STL: round, r ≈ 12.74 mm, cut back to r ≈ 11.54 mm at 12 and 6 o'clock, so it clears the notches by ~1 mm; original module complete (battery + PCB + module casing + LCD) **5.28** [892], module body without the LCD bump **4.77** [896], so the LCD stands **0.51 mm** proud of the body; case back: steel plate **0.44** [890], plate including its pressed recess **2.02** [891], so the recess is **1.58 mm** deep; **23.35** across [893], = recess diameter (confirmed; piezo sticker sits in it). Inside that circle the depth to the window is ~5.68 + 1.58 ≈ 7.26 mm minus the piezo. **Done 2026-11-24:** the charging PCB moved fully into the dip (centre 6.0 mm right of the case-back centre, long side 12–6, ~1 mm from the dip wall), on the dip floor under the cell; hole Ø4.3 at the same point. Assumes the dip is centred; piezo removed. `gen_watch_v2.py` updated; KiCad boards unchanged.
- **OLED grinding (as in the original build, Hardware/README.md):** the 26.3 × 11.6 mm OLED has a 28.7 mm diagonal, so its corners hit the round cavity (Ø27.61 as read; the true size is larger). With Ø27.61 the corners need ~0.6 mm off each end (or chamfer the four corners). Re-measure the cavity with the inside jaws first; it may be less. The OLED cannot rise into the ~23 × 14 mm window like the LCD (0.51 mm bump); its top stays ~0.4 mm lower than the old LCD (accepted).
- **Measured 2026-11-24 (case open):** module space **4.88 mm**, case back to screen **5.20 mm**. The GrabCAD-based SolidCraft model has 6.83 mm (case-back inner −0.21 → crystal 6.62), so the model is ~1.6 mm too tall. The Kepler stack (cell 1.6 + board 0.8 + holder below its OLED pocket 1.2 + OLED 1.25 = 4.85 mm) fits, with the OLED in the holder's 0.8 mm pocket. `gen_watch_v2.py` puts the OLED on top of the holder (4.44 → 5.69); that is wrong.
- **Result: GDEM0097T61 (30.0 mm glass, needs ≥ 31 mm) does not fit.** Only options: cut it (2b), find a panel with long side ≤ ~25 mm, or section 3.

### 2. If it fits: GDEM0097T61 e-paper (0.97", 184×88, SSD1680)
Datasheet: `datasheets/GDEM0097T61/GDEM0097T61.pdf` (mechanical drawing p. 7, DC characteristics p. 10).
- Glass outline 30.0 × 14.15 × 1.0 mm. **Do not sand the glass**: the 1.75 mm borders hold the seal, the ~6 mm bottom ledge holds the SSD1680 chip-on-glass.
- Flex cable: 11.18 mm long, 9.5 mm wide, 18 pins at 0.5 mm pitch, can be folded behind the panel (marked "bending area").
- [ ] Redesign the movement holder with a 30.0 × 14.15 mm pocket and a slot for the folded FPC.
- [ ] New display adapter board:
  - [ ] 18-pin 0.5 mm FPC connector.
  - [ ] External booster circuit (panel pins GDR = MOSFET gate, RESE = current sense): inductor, N-MOSFET, diodes, sense resistor, caps; follow Good Display's reference circuit.
  - [ ] Bulk low-leakage capacitor: refresh peak is 20 mA typ / 30 mA max, which a CR2016 can't deliver without sagging below the panel's 2.3 V minimum.
  - [ ] SPI (4-wire) + BUSY, RES#, D/C#, CS# to the CC2640R2.
- [ ] Firmware: SPI e-paper driver replacing `ssd1306.c`; partial refresh once a minute, full refresh once an hour; deep sleep between updates.
- Expected battery life: ~5 months per CR2016 with the time always shown (estimate: ~11 µA display + ~11 µA rest of watch).
- Limitations: no seconds, no light, rated 0–50 °C.

### 2b. Cut the e-paper to ~26 mm (experimental, high risk; needed because the cavity is 27 mm)
- Only the end **opposite** the driver chip can be cut. Never cut the ~6 mm chip/FPC ledge.
- Removing ~3.5 mm (1.75 mm top border + ~2 mm of pixels, ~15–20 of 184 rows lost) gives ~26–26.5 mm of glass.
- Score and snap with a diamond scribe (don't sand), test the panel, then seal the cut edge with UV-cure epoxy against moisture.
- Expect failures: buy several panels. No documented success found for this panel.

### 3. If it doesn't fit
- Option A: keep the OLED, add an always-on mode (HH:MM, low contrast, update once a minute, burn-in pixel shift). ~6–9 days per CR2016 (estimate).
- Option B: reuse the original F91W segment LCD (needs a segment-driver chip). Months of battery life, digits/symbols only.

## Firmware battery optimizations (done in the working tree, not yet compiled or tested)
- [ ] Build in CCS using the **`FlashROM_StackLibrary`** configuration (32.768 kHz crystal, not `_RCOSC`). If it won't start, fall back to `_RCOSC`.
- [ ] Comment out `#define IS_DEV_BOARD` in `Firmware/f91_kepler_app/Application/f91_utils.h` for the real watch.
- [ ] Check in nRF Connect that the phone accepts the new connection parameters (~450–480 ms interval, latency 3), about 6 s after connecting.
- [ ] Tune `SSD1306_CONTRAST` in `ssd1306.c` (now 0x7F) if the screen is too dim.
- [ ] Measure the real current draw (multimeter / PPK2 / EnergyTrace) to replace the estimates (~16 µA → ~200 days with button-to-wake).
- [ ] Commit the firmware changes once verified.

## PCB files (DipTrace → KiCad)
- [x] Build `kicad-nightly` (AUR) – built in `~/.cache/yay/kicad-nightly`; install with `makepkg -eRi` there.
- [x] Imported to `Hardware/KiCad/` (boards + schematics). Geometry correct; many tracks lost their nets (DRC 383, mostly import artefacts). Review only, not for fabrication.
- [ ] PCB review on the imported layout (antenna clearance, chip ground pad, decoupling, battery path).

## 3D model of the case (SolidCraft)
- [ ] Rebuild the F-91W case interior in SolidCraft from the numbers in section 1, with the module, holder and display window.
- SolidCraft launcher fixed 2026-11-21 (pointed to removed 0.30.1 AppImage, now 0.42.0). Live connection needs the app running with AI access on port 27878.

## Rechargeable v2 (designed 2026-11-22; files generated, nothing built yet)
Design: LIR2016 → BQ25180 charger → TPS62840 2.0 V buck; charging through a custom charging PCB glued inside the
original steel case back (one 4.3 mm hole, two flush gold pads at 2.50 mm pitch, 3 × 1 mm magnets in the PCB),
FFC ribbon to the main board, bought Samzo/Einaus magnetic pogo male as the cable.
Docs: `Hardware/KiCad/F91-Main_board_v2/README.md`, `Hardware/KiCad/F91-Charge_pad/README.md`, panel + fab files in `Hardware/KiCad/panel/`.

### Before ordering
- [ ] Open the main board in KiCad, run DRC, and look over the generated routing (U1 pins 1–8, charger and buck pockets).
- [ ] Case open: measure clamp outline/thickness, piezo position, case-back thickness, and check the clamp doesn't touch the case back. Check the battery clamp doesn't cover the dip where the charging PCB sits.
- [ ] Check JLC stock on the day (CC2640R2FRGZR had 600) and the part rotations in JLC's placement preview.
- [ ] Order: upload `Hardware/KiCad/panel/fab/F91-Kepler_panel_gerbers.zip`, 2 layers, 0.8 mm, ENIG, castellated holes, 5 panels; Standard PCBA top side, 2 panels; BOM/CPL from `panel/fab/`.

### Bought separately
- [ ] LIR2016 cells ×3, Samzo/Einaus 2-pin 2.5 mm magnetic pogo pair, short 4-way 1.0 mm FFC, Ø3 × 1 mm N52 magnets (+ Ø3 × 0.5 mm spares), 0.5 mm rubber sheet, E6000 or MS-polymer glue, super-glue gel, Kapton, step drill, spare F-91W case back, TI XDS110 (TMDSEMU110-U).

### Assembly (after the boards arrive)
- [ ] Break out boards, file tab stubs (keep clear of the castellations).
- [ ] Bench: 3.7 V / 20 mA on the battery pads → VDD 2.0 V, sleep current; 5 V on the FFC pads → ~10 mA charge.
- [ ] Program over cJTAG (v1 jig pads), power from the battery pads.
- [ ] Rework the display adapter (VDDB to the free pin next to SCL, see main-board README).
- [ ] Case back: drill 4.3 mm, glue the charging PCB with a rubber ring + E6000, magnets in, solder the FFC, water test.
- [ ] Final assembly and closed-case test.

### Firmware (written 2026-11-22, not compiled: no TI SDK here)
- [ ] Build in CCS (`F91_HW_V2` in `Application/f91_board.h`). New files: `Application/f91_i2c.c/h`, `Application/f91_power.c/h`, `PROFILES/f91_battery_service.c/h`.
- [ ] Check BQ25180 init over I2C, /INT on DIO3, battery % from DIO23, battery icon, Battery Service 0x180F in nRF Connect.
- [ ] Port to TI on-chip OAD (BIM + persistent image; no external flash on v2). Check the app size first.
