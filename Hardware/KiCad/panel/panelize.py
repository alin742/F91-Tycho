"""JLCPCB panel: 2 x 2 F91 main boards in one >= 70 x 70 mm frame (no charging PCB any more:
the charge contacts are two brass pins in plated holes on the main board).

Standard PCBA needs >= 70 x 70 mm, rails/frame, fiducials and tooling holes. Tabs avoid the
castellated button contacts and the antenna edge; mouse bites (no V-cut: castellations).
Run with the KiKit venv:  tools/kikit-venv/bin/python Hardware/KiCad/panel/panelize.py
"""
import os, sys
from pathlib import Path
import pcbnew
from kikit.panelize import Panel, Origin
from kikit.annotations import TabAnnotation
from kikit.units import mm, deg
from kikit import substrate as ksub

HERE = Path(__file__).resolve().parent
MAIN = HERE.parent / 'F91-Main_board_v2' / 'F91-Main_board_v2.kicad_pcb'
OUT = HERE / 'F91-Kepler_panel.kicad_pcb'

SPACE = 2.0          # mm between boards vertically (mouse-bite slot width)
HSPACE = 5.0         # mm between columns: castellated button rings (4 mm) stick out of each board
FRAME_W = 5.0        # mm frame width
BOARD = 24.4         # main board bounding box
P = lambda x, y: pcbnew.VECTOR2I(int(x * mm), int(y * mm))


def dummy_frame(substrates, space):
    """Thin substrates where the frame will be, so tabs are generated towards it (as KiKit's UI does)."""
    from shapely.geometry import box
    from kikit.panelize_ui_impl import polygonToSubstrate
    minx = min(s.bounds()[0] for s in substrates); miny = min(s.bounds()[1] for s in substrates)
    maxx = max(s.bounds()[2] for s in substrates); maxy = max(s.bounds()[3] for s in substrates)
    w = 1 * mm
    return [polygonToSubstrate(box(minx, miny - 2 * space - w, maxx, miny - 2 * space)),
            polygonToSubstrate(box(minx, maxy + 2 * space, maxx, maxy + 2 * space + w)),
            polygonToSubstrate(box(minx - 2 * space - w, miny, minx - 2 * space, maxy)),
            polygonToSubstrate(box(maxx + 2 * space, miny, maxx + 2 * space + w, maxy))]


def main():
    panel = Panel(str(OUT))
    pitch = BOARD + SPACE
    hpitch = BOARD + HSPACE
    n = 0
    mains = []
    for r in range(2):
        for c in range(2):
            n += 1
            k = n
            panel.appendBoard(str(MAIN), P(c * hpitch, r * pitch), origin=Origin.Center,
                              tolerance=int(1 * mm),
                              netRenamer=lambda i, name, k=k: f'M{k}-{name}',
                              refRenamer=lambda i, ref, k=k: f'{ref}_M{k}')
            mains.append(len(panel.substrates) - 1)
    panel.inheritDesignSettings(pcbnew.LoadBoard(str(MAIN)))
    panel.inheritProperties(pcbnew.LoadBoard(str(MAIN)))

    framingSubstrates = dummy_frame(panel.substrates, int(HSPACE * mm) / 2)
    panel.buildPartitionLineFromBB(framingSubstrates)
    panel.buildTabAnnotationsFixed(hcount=2, vcount=1, hwidth=int(2.5 * mm), vwidth=int(2.5 * mm),
                                   minDistance=int(3 * mm), ghostSubstrates=framingSubstrates)
    # main boards: drop tabs on the antenna edge (bottom, board-local x -3.5..8.3) - add corner ones
    for idx in mains:
        s = panel.substrates[idx]
        minx, miny, maxx, maxy = s.bounds()
        keep = []
        for a in s.annotations:
            if not isinstance(a, TabAnnotation):
                keep.append(a); continue
            ox, oy = a.origin
            on_bottom = abs(oy - maxy) < 0.5 * mm
            if on_bottom:
                continue
            keep.append(a)
        # no tab near the castellated button contacts (board-local SW1/SW2 left, SW3 right)
        cx_b, cy_b = (minx + maxx) / 2, (miny + maxy) / 2
        bc = (2.683, 2.7395)                       # bbox centre of the main board in its own coords
        cast = [(-9.67, 7.556), (-9.67, -2.124), (15.01, 7.756)]
        cast = [(cx_b + (x - bc[0]) * mm, cy_b + (y - bc[1]) * mm) for x, y in cast]
        keep = [a for a in keep if not isinstance(a, TabAnnotation) or
                min(((a.origin[0] - x) ** 2 + (a.origin[1] - y) ** 2) ** 0.5 for x, y in cast) > 4.0 * mm]
        # bottom tabs only at the two lower corners, outside the antenna span
        for fx in (0.12, 0.88):
            keep.append(TabAnnotation(None, (minx + fx * (maxx - minx), maxy), (0, -1), int(2.5 * mm)))
        s.annotations = keep
    tabCuts = panel.buildTabsFromAnnotations(fillet=int(0.5 * mm))
    frameCuts = panel.makeFrame(int(FRAME_W * mm), int(FRAME_W * mm), int(HSPACE * mm), int(SPACE * mm),
                                minWidth=int(70 * mm), minHeight=int(70 * mm))
    panel.makeMouseBites(tabCuts, diameter=int(0.5 * mm), spacing=int(0.75 * mm), offset=int(-0.25 * mm),
                         prolongation=int(0.5 * mm))
    panel.addMillFillets(int(1 * mm))
    panel.addCornerFiducials(3, int(5 * mm), int(2.5 * mm), int(1 * mm), int(2 * mm))
    panel.addCornerTooling(3, int(2.5 * mm), int(2.5 * mm), int(2.0 * mm))
    # KiKit can't merge project settings of two source boards; both use the same JLC rules
    # (the charging-pad project is a copy), so take the main board's project settings.
    panel.sourcePaths = {p for p in panel.sourcePaths if 'F91-Main_board_v2' in str(p)}
    panel.save(reconstructArcs=True, refillAllZones=True)
    bb = pcbnew.LoadBoard(str(OUT)).GetBoardEdgesBoundingBox()   # panel.board is gone after save
    print(f'panel {bb.GetWidth()/mm:.1f} x {bb.GetHeight()/mm:.1f} mm -> {OUT}')


if __name__ == '__main__':
    main()
