# F91 Tycho JLCPCB panel

`F91-Kepler_panel.kicad_pcb`: **4 main boards (2 × 2) + 4 charging PCBs** in an 83.9 × 71.9 mm frame
(5 mm frame, 3 fiducials, 3 tooling holes, mouse-bite tabs, no V-cut because of the castellated button
contacts). Built with KiKit by `panelize.py`. `fab/` holds everything to upload.

## Order (jlcpcb.com)
1. **PCB:** upload `fab/F91-Kepler_panel_gerbers.zip`.
   - Layers 2, thickness **0.8 mm**, surface finish **ENIG**, **castellated holes: yes**.
   - Panel by customer (the file already is the panel), quantity 5.
   - Via covering: tented (the board file tents every via; vias under the cell must stay covered).
2. **PCB Assembly:** **Standard**, **top side only**, assemble 2 panels (= 8 watches).
   - BOM: `fab/F91-Kepler_panel_BOM.csv`. CPL: `fab/F91-Kepler_panel_CPL.csv`.
   - Bottom side: nothing to assemble (FFC pads, battery pads and antenna only).
3. **Check in JLC's placement preview** that every part sits on its pads with pin 1 right, especially
   U1 (QFN), U2/U3 (DSBGA, X-ray is automatic), Q1–Q3 (DFN1006), J1 (Molex), D1/D2 on the charging PCBs.
   The footprints of all LCSC parts come from LCSC itself, so their rotation should already match.
4. Check stock on the day: CC2640R2FRGZR had 600, BQ25180YBGR 2927, TPS62840YBGR 2074 (2026-11-22).

Extended parts (one-time fee each): CC2640R2FRGZR, BQ25180, TPS62840, MPH160809S2R2MT, PMZB290UNE,
PMEG3002AEL, TPD1E10B06, Molex 505066, BLM18HE152SN1D, 24 MHz crystal, 2 nH and 2.4 nH RF inductors,
1.8 pF, 1.74 kΩ. The 1 pF, 6.8 pF and 10 MΩ are "preferred extended" (no fee); the rest are Basic.

## Expected DRC on the panel
Only the castellated button contacts (`SW1–SW3`) are flagged for copper at the board edge: they are
half-holes on purpose (the clamp arm touches them, as on v1). Everything else is clean, 0 unconnected.

Regenerate: `../../../tools/kikit-venv/bin/python panelize.py && python3 export_fab.py`.
