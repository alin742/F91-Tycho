# F91 Tycho v2 main board (rechargeable)

LIR2016 rechargeable coin cell → **BQ25180** charger → **TPS62840** buck → **2.0 V** for the CC2640R2,
OLED logic and I2C. The board keeps the v1 outline, holder holes, castellated button contacts,
PCB antenna and the v1 RF matching network. Every assembled part is in the JLCPCB library.

Status: **design files generated, not yet built or tested.** See "Check before ordering" below.

## Files
| File | What |
|---|---|
| `F91-Main_board_v2.kicad_sch` | Schematic (net labels, generated) |
| `F91-Main_board_v2.kicad_pcb` | Board: 24.4 × 24.4 mm, 2 layers, 0.8 mm |
| `F91-Main_board_v2.kicad_pro/.kicad_dru` | JLCPCB 2-layer rules (0.1/0.1 mm tracks, vias 0.45/0.25 and 0.6/0.3, both standard price) + castellation / RF / antenna rules |
| `lib/F91_LCSC.*` | Symbols, footprints, 3D models pulled from LCSC with easyeda2kicad (the footprints JLC places to) |
| `lib/F91_custom.pretty` | Antenna, battery pads, castellations, holes, FFC pads (from v1 geometry) |
| `scripts/` | The generators (see "Regenerating") |
| `../F91-Charge_pad/` | Charging PCB glued inside the case back |
| `../panel/` | JLC panel (2 × 2 main boards + 4 charging PCBs), fab export |

## Circuit summary
- **Cell:** LIR2016 under the original clamp. Clamp = battery +, the cell's flat side = GND pads (as v1).
- **Charger BQ25180** (U2, DSBGA-8, I2C 0x6A): power-up defaults are safe for the LIR2016 with no firmware (4.20 V, 10 mA, BUVLO 3.0 V). /INT → DIO3. TS/MR left open (TS off, no NTC).
- **Buck TPS62840** (U3, DSBGA-6): EN = SYS, VSET = 1.74 kΩ → 2.0 V, 60 nA Iq. L1 2.2 µH.
- **CC2640R2** in internal-LDO mode: the v1 10 µH DC/DC inductor is removed, DCDC_SW is unconnected. Firmware must disable the DC/DC in ccfg (done in `Startup/ccfg_app_ble.c` for `F91_HW_V2`).
- **Battery sense:** 10 MΩ / 1 MΩ divider + 100 nF into DIO23 (ADC). About 0.38 µA.
- **Buttons:** the clamp arm (battery +) touches the castellation, which drives an N-FET gate (PMZB290UNE, 1 MΩ pull-down); the FET pulls DIO15/25/26 low → buttons are **active-low with internal pull-ups** (firmware `F91_HW_V2`).
- **Display connector J1** (Molex 505066, same position as v1). Top row: GND, SCL, **VBAT (new, for the SSD1306 charge pump VDDB)**. Bottom row: **VDD 2.0 V (was battery)**, SDA, NC.
- **Charging input:** 4 solder pads (J2, bottom right) for a 1.0 mm-pitch FFC ribbon from the charging PCB. Reverse-polarity Schottky, ESD diode and pull-down sit on the charging PCB.
- **Programming:** cJTAG pads at the v1 jig positions: GND, VDD (sense only), TMS, TCK (the v1 jig fits). The v1 UART and RESET pads were dropped for space; the XDS110 resets the chip over cJTAG. Power the board from the battery pads or from 5 V on the FFC pads, never by back-feeding VDD.
- **No external flash:** firmware updates over Bluetooth must use TI **on-chip OAD**. There was no room for an SPI flash: the bottom corners are cut by the board chamfer or taken by the charging PCB.

## Display adapter rework (reuse the v1 adapter, no new board)
The v1 adapter ties SSD1306 VDD (logic, max 3.3 V) and VDDB (charge pump, 3.3–4.2 V) to one connector pin. On v2 that pin carries 2.0 V, so the charge pump needs its own supply:
1. Cut the trace between the SSD1306 **VDDB** pin and VDD/VCC on the adapter.
2. Solder a thin enamelled wire from **VDDB** to the adapter connector pin that mates with J1's **top-right** pin (the free pin next to SCL, carrying VBAT on v2).
3. Optional: remove the adapter's duplicate 10 kΩ I2C pull-ups (the main board has 10 kΩ to VDD).

## Status of the generated board
- **DRC: 0 errors, 0 unconnected pads** (`kicad-cli pcb drc --schematic-parity`). 11 warnings: 10 courtyard overlaps (mostly inherited from v1's placement: castellation vs button pad, MH2 vs C8, TP pads near U1) and one 0.087 mm neck where a track enters Q2's pad.
- **Schematic parity:** all nets match. The only differences reported are KiCad's placeholder names for no-connect pins.
- **ERC:** 0 violations.
- Routing was done by `scripts/router2.py` (own grid router; Freerouting was not available here). Look it over in KiCad before ordering, especially around U1 pins 1–10, the charger (U2) and buck (U3) pockets, and the RF chain (copied unchanged from v1).
- Every via is tented. The cell's negative face sits on Pad3/Pad4 + the U1 thermal-via area (all GND).

## Check before ordering
- JLC stock on order day: CC2640R2FRGZR (600 when checked), BQ25180YBGR, TPS62840YBGR.
- In JLC's placement preview, check the rotation of U1 (QFN), U2/U3 (DSBGA), Q1–Q3 (DFN1006) and J1 (Molex).
- Case-open measurements (TASKS.md): clamp outline, piezo position, case-back thickness, clamp-to-case-back contact. These confirm the charging-PCB corner and the FFC route.

## Regenerating
```
cd Hardware/KiCad/F91-Main_board_v2
python3 scripts/gen_footprints.py     # custom footprints from the v1 board
python3 scripts/gen_project.py        # .kicad_pro rules + .kicad_dru
python3 scripts/gen_sch.py            # schematic from scripts/design.py
python3 scripts/gen_pcb.py            # board: v1 geometry + placement (placement/place.json) + fixed escapes
python3 scripts/fanout_gnd.py         # short track + via for every small GND pad
python3 scripts/router2.py 40         # negotiated-congestion router (all nets but GND)
python3 scripts/nudge_vias.py F91-Main_board_v2.kicad_pcb work/drc.rpt   # after a DRC, fixes ~0.01 mm misses
python3 scripts/pour.py               # GND pours + stitching vias
python3 scripts/link_gnd_clusters.py  # joins any GND piece the pour left isolated
python3 scripts/finalize.py F91-Main_board_v2.kicad_pcb   # hide refdes, board label
../../../tools/kikit-venv/bin/python ../panel/panelize.py
python3 ../panel/export_fab.py        # gerbers zip + JLC BOM/CPL
```
`scripts/design.py` is the single source of truth for parts, values, LCSC numbers and nets.
