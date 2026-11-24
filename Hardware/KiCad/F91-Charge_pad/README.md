> **Obsolete since 2026-11-24.** The charging PCB was dropped: the charge contacts are now two brass pins in plated
> holes on the main board (see `TASKS.md`, Rechargeable v2). Kept for reference only; not in the JLC panel.

# F91 Tycho charging PCB

A 13 × 5 mm rigid board (0.8 mm, ENIG) that sits in the round dip of the original steel case back, behind two
Ø1.6 mm holes (one per pogo pin). It is made and assembled in the same JLC panel as the main boards, so it costs no
extra order.

- **Outer face (bottom):** two flush gold pads, Ø1.6 mm, at **2.50 mm pitch** (CHG+ left, GND right as drawn).
  They mate with the bought **Samzo/Einaus 2-pin magnetic pogo male** (`PR5L5015-2P-C-H`: pogos Ø0.9 mm, 8.0 mm magnet spacing).
- **Magnets:** two **Ø3.1 mm holes, 8.0 mm apart**: press in Ø3 × 1 mm N52 magnets with super-glue gel.
  **Check the poles against the cable before gluing:** the bought female half only snaps on one way, so use it to mark the male's N/S ends. Each watch magnet must attract the cable magnet above it.
- **Inner face (top, assembled by JLC):** PMEG3002AEL reverse-polarity Schottky (D1), TPD1E10B06 ESD diode (D2), 1 MΩ pull-down (R1). The outside pad sits at 0 V off the charger.
- **FFC pads (top):** 4 × 1.0 mm pitch (1–2 = VIN to the main board, 3–4 = GND). Solder a ~20 mm piece of 4-way 1.0 mm FFC here and to J2 on the main board's bottom.
- No vias inside the two Ø1.6 mm holes (the wet zone). All four vias are tented and sit under the rubber pad (≥ 0.28 mm from its holes).

## Fitting into the case back (only drill, rubber, tube glue)
1. Practise on a spare F-91W case back.
2. The board goes **inside the round dip** of the case back (Ø23.35, 1.58 deep), flat on the dip floor, under the cell. Peel out the piezo disc (v2 has no buzzer). Drill **two Ø1.6 mm holes, 2.50 mm apart**, one over each gold pad: centred **6.0 mm right of the case-back centre (towards 3 o'clock)**, the two holes stacked 12–6 (1.25 mm above and below that point). The board's long side runs 12–6, FFC edge towards 3 o'clock. Deburr.
   Put Kapton over the board's top: the cell's + can sits ~0.3 mm above it.
3. Cut a 0.5 mm rubber pad (Ø7 mm disc) with **two Ø1.8 mm holes, 2.50 mm apart**, and put it between the PCB and the steel, holes over the pads.
4. Clean and roughen the steel, bed the PCB in **E6000 / MS-polymer**, bead the edges, and cure 24–72 h with the case open.
5. Soak test (30 min, tissue inside) before any electronics go in.

Regenerate: `python3 scripts/gen_charge_pcb.py && python3 scripts/route_charge.py`.
