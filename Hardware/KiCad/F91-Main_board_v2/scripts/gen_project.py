"""Write F91-Main_board_v2.kicad_pro (design rules + net classes) and the custom .kicad_dru.

Numbers: JLCPCB capabilities page (2026-11) for 2-layer 1 oz 0.8 mm ENIG:
trace/space 0.10/0.10, vias 0.25 drill / 0.45 pad (no extra cost) or 0.3/0.6, annular >= 0.15 preferred,
hole-to-hole 0.2 (vias) / 0.45 (pads), via hole to track 0.2, copper to routed edge 0.2,
soldermask bridge 0.1 (green), silk line 0.15 / text 1.0 mm.
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'F91-Main_board_v2'

pro = {
    "meta": {"filename": NAME + ".kicad_pro", "version": 3},
    "board": {
        "design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.15, "silk_line_width": 0.15,
                         "silk_text_size_h": 0.8, "silk_text_size_v": 0.8, "silk_text_thickness": 0.15},
            "rules": {
                "min_clearance": 0.1, "min_track_width": 0.1, "min_connection": 0.1,
                "min_via_diameter": 0.45, "min_via_annular_width": 0.1, "min_through_hole_diameter": 0.2,  # U1 thermal vias (JLC min 0.15 with ENIG <= 1 mm)
                "min_hole_clearance": 0.2, "min_hole_to_hole": 0.2, "min_copper_edge_clearance": 0.2,
                "solder_mask_to_copper_clearance": 0.0, "min_microvia_diameter": 0.2,
                "min_microvia_drill": 0.1, "min_silk_clearance": 0.0, "min_text_height": 0.6,
                "min_text_thickness": 0.1, "min_resolved_spokes": 1, "max_error": 0.005,
                "allow_blind_buried_vias": False, "allow_microvias": False, "use_height_for_length_calcs": True,
            },
            "rule_severities": {"courtyards_overlap": "warning", "silk_overlap": "ignore", "silk_over_copper": "ignore", "silk_edge_clearance": "ignore",
                                "text_height": "ignore", "lib_footprint_issues": "ignore",
                                "lib_footprint_mismatch": "ignore", "footprint_symbol_mismatch": "warning"},
            "track_widths": [0.0, 0.15, 0.2, 0.3, 0.4],
            "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.45, "drill": 0.25}, {"diameter": 0.6, "drill": 0.3}],
        }
    },
    "net_settings": {
        "classes": [
            {"name": "Default", "clearance": 0.1, "track_width": 0.15, "via_diameter": 0.6, "via_drill": 0.3,
             "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.18, "diff_pair_gap": 0.1,
             "wire_width": 6, "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
             "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647},
            {"name": "Power", "clearance": 0.1, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3,
             "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.1,
             "wire_width": 6, "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
             "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1},
        ],
        "meta": {"version": 4},
        "net_colors": None,
        "netclass_assignments": None,
        "netclass_patterns": [{"netclass": "Power", "pattern": p} for p in
                              ["GND", "VBAT", "SYS", "VDD", "VDDS", "VDDR", "VIN_CHG", "CHG_IN", "SW_BUCK"]],
    },
    "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
    "sheets": [["", "Root"]],
    "text_variables": {},
}
json.dump(pro, open(os.path.join(ROOT, NAME + '.kicad_pro'), 'w'), indent=2)

dru = """(version 1)
# The button contacts are castellated half-holes on purpose (clamp arm touches them, as in v1).
(rule "castellations may touch the edge"
    (condition "A.memberOfFootprint('SW1') || A.memberOfFootprint('SW2') || A.memberOfFootprint('SW3')")
    (constraint edge_clearance (min -10mm)))
# v1 RF chain copied verbatim; it was built and works. Allow its 0.18/0.28 mm geometry and tight pair spacing.
(rule "v1 RF pair"
    (condition "A.NetName == 'RF_P' && B.NetName == 'RF_N'")
    (constraint clearance (min 0.07mm)))
# No copper of other nets near the antenna feed / meander (both layers)
(rule "antenna keep-clear"
    (condition "A.NetName == 'ANT' && B.NetName != 'ANT'")
    (constraint clearance (min 0.3mm)))
"""
open(os.path.join(ROOT, NAME + '.kicad_dru'), 'w').write(dru)
print('wrote project + rules')
