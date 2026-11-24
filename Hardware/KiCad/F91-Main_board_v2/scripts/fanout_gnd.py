"""GND fan-out before signal routing: every small GND pad gets a short track + via to the
bottom layer (bottom GND pour), so the router keeps room for them and no GND pad ends up in
a pour island enclosed by signal tracks.

Usage: python3 fanout_gnd.py [board]
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew
import router as R1

MM = lambda v: pcbnew.FromMM(float(v))
VIA_D, VIA_DR, TW = 0.45, 0.25, 0.15
SKIP_REFS = ('BT1', 'U1')            # battery pads and the QFN pad (thermal vias) need none


def main():
    path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else R1.PCB
    b = pcbnew.LoadBoard(path)
    R = R1.Router(b)
    g = R.g
    gnd = b.FindNet('GND')
    # hard obstacles for a GND via: every non-GND copper grown by INF, edge, NPTH, antenna keep-out
    own = R.net_grown.get('GND', np.zeros(R.shape, bool))
    hard = ((R.count - own.astype(np.int16)) > 0) | R.fixed
    hard[0] |= R.antko; hard[1] |= R.antko
    via_rad = (VIA_D / 2 + R1.CLR - R1.INF) / R1.RES + 1.0
    via_bl = R1.dilate(hard[0] | hard[1], via_rad)
    # no via on top of any SMD pad (incl. GND ones) and keep vias apart
    smd_all = np.zeros(R.shape[1:], bool)
    for n, m in R.smd_raw.items():
        smd_all |= m[0] | m[1]
    via_bl |= R1.dilate(smd_all, VIA_D / 2 / R1.RES + 1)
    track_bl = hard[0]
    made = 0
    for f in b.GetFootprints():
        if f.GetReference().startswith(SKIP_REFS) or f.IsFlipped():
            continue
        for p in f.Pads():
            if p.GetNetname() != 'GND' or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or not p.IsOnLayer(pcbnew.F_Cu):
                continue
            if p.GetSize().x * p.GetSize().y > MM(1.2) * MM(1.2):
                continue
            px, py = p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
            # prefer directions pointing away from the footprint centre
            fx, fy = f.GetPosition().x / 1e6, f.GetPosition().y / 1e6
            base = math.atan2(py - fy, px - fx) if (px, py) != (fx, fy) else 0.0
            best = None
            for dist in (0.55, 0.65, 0.75, 0.9, 1.05, 1.2):
                for k in range(16):
                    a = base + (k // 2 + 1) * (math.pi / 8) * (-1 if k % 2 else 1) if k else base
                    x, y = px + dist * math.cos(a), py + dist * math.sin(a)
                    c, r = g.to_px(x, y); r, c = int(round(r)), int(round(c))
                    if not (0 <= r < g.H and 0 <= c < g.W) or via_bl[r, c]:
                        continue
                    # the connecting track must not cross other nets' copper
                    ok = True
                    for t in np.linspace(0, 1, 12):
                        xx, yy = px + (x - px) * t, py + (y - py) * t
                        cc, rr = g.to_px(xx, yy)
                        if track_bl[int(round(rr)), int(round(cc))]:
                            ok = False
                            break
                    if ok:
                        best = (x, y)
                        break
                if best:
                    break
            if not best:
                print('  no fan-out room for', f.GetReference(), p.GetNumber())
                continue
            x, y = best
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(p.GetPosition()); t.SetEnd(pcbnew.VECTOR2I(MM(x), MM(y)))
            t.SetWidth(MM(TW)); t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd); b.Add(t)
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DR))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); b.Add(v)
            c, r = g.to_px(x, y)
            via_bl |= R1.dilate(np.pad(np.zeros((1, 1), bool), 0), 0) if False else via_bl
            r, c = int(round(r)), int(round(c))
            R_ = int((VIA_D + R1.CLR) / R1.RES) + 2
            yy, xx = np.ogrid[-R_:R_ + 1, -R_:R_ + 1]
            disk = xx * xx + yy * yy <= R_ * R_
            r0, c0 = max(r - R_, 0), max(c - R_, 0)
            sub = via_bl[r0:r + R_ + 1, c0:c + R_ + 1]
            sub |= disk[(r0 - (r - R_)):(r0 - (r - R_)) + sub.shape[0], (c0 - (c - R_)):(c0 - (c - R_)) + sub.shape[1]]
            made += 1
    pcbnew.SaveBoard(path, b)
    print('GND fan-out vias:', made)


if __name__ == '__main__':
    main()
