"""Find free spots for the new v2 parts on the top side (spiral search on an occupancy raster).

Usage: python3 autoplace.py  -> prints a PLACE dict to paste into gen_pcb.py and writes work/place.json
Obstacles: courtyards of every placed part (both layers' courtyards for top parts), top copper
(tracks, vias, pads) of kept parts, 1.0 mm edge margin, and the antenna area.
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, 'F91-Main_board_v2.kicad_pcb')
RES = 0.05
MM = pcbnew.FromMM
mm = lambda v: v / 1e6

# new parts in placement order: ref -> (target x, y, allowed rotations)
ORDER = [
    ('R2', (2.4, 10.6), (0, 90)), ('R3', (5.0, 10.6), (0, 90)),
    ('R12', (-2.6, -1.4), (0, 90)), ('R13', (-2.6, -2.6), (0, 90)), ('C35', (-1.6, -2.6), (0, 90)),
    ('Q1', (-7.2, 6.4), (0, 90, 180, 270)), ('R21', (-7.2, 5.2), (0, 90)),
    ('Q2', (-6.6, -4.6), (0, 90, 180, 270)), ('R22', (-6.8, -2.4), (0, 90)),
    ('Q3', (12.4, 6.4), (0, 90, 180, 270)), ('R23', (13.0, 3.8), (0, 90)),
    # charging input next to the pins P1/P2 (12.80,-3.40)/(11.19,-5.32)
    ('D2', (11.0, -3.0), (0, 90, 180, 270)), ('R24', (10.0, -4.6), (0, 90)), ('D1', (10.6, -1.2), (0, 90, 180, 270)),
]


def main():
    b = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.KICAD_SEXP, PCB)
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = mm(bb.GetX()) - 1, mm(bb.GetY()) - 1
    W, H = int((mm(bb.GetWidth()) + 2) / RES), int((mm(bb.GetHeight()) + 2) / RES)
    occ = np.zeros((H, W), bool)

    def rc(x, y):
        return int((y - y0) / RES), int((x - x0) / RES)

    # inside-board mask with 1.0 mm margin
    outline = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline, True)
    inner = pcbnew.SHAPE_POLY_SET(outline)
    inner.Deflate(MM(1.0), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.01))
    ys, xs = np.mgrid[0:H, 0:W]
    for r in range(H):
        for c in range(W):
            if not inner.Contains(pcbnew.VECTOR2I(MM(x0 + c * RES), MM(y0 + r * RES))):
                occ[r, c] = True

    def mark_poly(poly, grow):
        p = pcbnew.SHAPE_POLY_SET(poly)
        if grow:
            p.Inflate(MM(grow), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.01))
        pb = p.BBox()
        r0, c0 = rc(mm(pb.GetX()), mm(pb.GetY()))
        r1, c1 = rc(mm(pb.GetRight()), mm(pb.GetBottom()))
        for r in range(max(r0, 0), min(r1 + 1, H)):
            for c in range(max(c0, 0), min(c1 + 1, W)):
                if not occ[r, c] and p.Contains(pcbnew.VECTOR2I(MM(x0 + c * RES), MM(y0 + r * RES))):
                    occ[r, c] = True

    new = {r for r, _, _ in ORDER}
    F = pcbnew.F_CrtYd

    def fp_poly(f):
        f.BuildCourtyardCaches()
        cy = pcbnew.SHAPE_POLY_SET(f.GetCourtyard(pcbnew.F_CrtYd)) if not f.IsFlipped() else None
        if cy is not None:
            # union with pads grown by 0.12 mm (pads may stick out of easyeda courtyards)
            for p in f.Pads():
                if p.IsOnLayer(pcbnew.F_Cu):
                    s2 = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(s2, pcbnew.F_Cu, MM(0.12), MM(0.01), pcbnew.ERROR_OUTSIDE)
                    cy.BooleanAdd(s2)
        if cy is not None and cy.OutlineCount():
            return cy
        bbx = f.GetBoundingBox(False)
        s = pcbnew.SHAPE_POLY_SET()
        s.NewOutline()
        for (px, py) in [(bbx.GetX(), bbx.GetY()), (bbx.GetRight(), bbx.GetY()), (bbx.GetRight(), bbx.GetBottom()), (bbx.GetX(), bbx.GetBottom())]:
            s.Append(px, py)
        return s

    for f in b.GetFootprints():
        if f.GetReference() in new or f.GetReference() in ('BT1', 'AE1'):
            continue
        if f.IsFlipped():
            continue
        mark_poly(fp_poly(f), 0.12)
    # top copper of everything kept (pads incl. BT1 PTH vias, tracks, vias)
    for f in b.GetFootprints():
        if f.GetReference() in new:
            continue
        for p in f.Pads():
            if p.IsOnLayer(pcbnew.F_Cu):
                s = pcbnew.SHAPE_POLY_SET()
                p.TransformShapeToPolygon(s, pcbnew.F_Cu, MM(0.15), MM(0.01), pcbnew.ERROR_INSIDE)
                mark_poly(s, 0)
    for t in b.GetTracks():
        if t.IsOnLayer(pcbnew.F_Cu):
            s = pcbnew.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(s, pcbnew.F_Cu, MM(0.15), MM(0.01), pcbnew.ERROR_INSIDE)
            mark_poly(s, 0)
    # routing escape bands: MCU courtyard + 1.0 mm, display connector + 0.5 mm
    for ref, band in (('U1', 1.0), ('J1', 0.5)):
        f = b.FindFootprintByReference(ref)
        f.BuildCourtyardCaches()
        mark_poly(f.GetCourtyard(pcbnew.F_CrtYd), band)
    # antenna area: nothing on top above the meander (+0.5 mm)
    r0, c0 = rc(-3.0, 10.8); r1, c1 = rc(7.8, 15.5)
    occ[r0:r1, c0:c1] = True

    from PIL import Image
    Image.fromarray((~occ * 255).astype(np.uint8)).save(os.path.join(ROOT, 'work', 'occ_free.png'))
    result = {}
    for ref, (tx, ty), rots in ORDER:
        f = b.FindFootprintByReference(ref)
        best = None
        for rot in rots:
            f.SetOrientationDegrees(rot)
            f.SetPosition(pcbnew.VECTOR2I(0, 0))
            cy = fp_poly(f)
            pts = []
            pb = cy.BBox()
            for r in range(int(mm(pb.GetY()) / RES) - 1, int(mm(pb.GetBottom()) / RES) + 2):
                for c in range(int(mm(pb.GetX()) / RES) - 1, int(mm(pb.GetRight()) / RES) + 2):
                    if cy.Contains(pcbnew.VECTOR2I(MM(c * RES), MM(r * RES))):
                        pts.append((r, c))
            # also the pads + 0.1 clearance must be free (courtyards are usually larger anyway)
            pts = np.array(pts)
            for rad in np.arange(0, 14, RES):
                found = None
                n = max(8, int(2 * math.pi * rad / RES))
                for k in range(n):
                    a = 2 * math.pi * k / n
                    x, y = tx + rad * math.cos(a), ty + rad * math.sin(a)
                    R, Cc = rc(x, y)
                    rr, cc = pts[:, 0] + R, pts[:, 1] + Cc
                    if rr.min() < 0 or cc.min() < 0 or rr.max() >= H or cc.max() >= W:
                        continue
                    if not occ[rr, cc].any():
                        found = (rad, x, y)
                        break
                if found:
                    if best is None or found[0] < best[0]:
                        best = (found[0], found[1], found[2], rot, pts)
                    break
        if best is None:
            print('NO SPOT for', ref)
            continue
        _, x, y, rot, pts = best
        R, Cc = rc(x, y)
        occ[pts[:, 0] + R, pts[:, 1] + Cc] = True
        # keep 0.1 mm between parts: grow the mark
        g = int(0.2 / RES)
        for dr in (-g, 0, g):
            for dc in (-g, 0, g):
                rr = np.clip(pts[:, 0] + R + dr, 0, H - 1); cc = np.clip(pts[:, 1] + Cc + dc, 0, W - 1)
                occ[rr, cc] = True
        result[ref] = (round(x, 2), round(y, 2), rot, 'F')
        print(f"    '{ref}': ({x:.2f}, {y:.2f}, {rot}, 'F'),   # moved {best[0]:.2f} mm from target")
    json.dump(result, open(os.path.join(ROOT, 'work', 'place.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
