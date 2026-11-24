"""Join small GND clusters (as KiCad's connectivity sees them) to the main GND cluster with an
A*-routed track/via, then refill. Also removes orphan GND vias. Usage: python3 link_gnd_clusters.py [board]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew
import router as R1
import router2 as R2

MM = lambda v: pcbnew.FromMM(float(v))
path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else R1.PCB
b = pcbnew.LoadBoard(path)
for rnd in range(4):
    b.BuildConnectivity()
    c = b.GetConnectivity()
    for t in list(b.GetTracks()):
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND' and len(c.GetConnectedItems(t)) <= 1:
            b.Remove(t)
    b.BuildConnectivity(); c = b.GetConnectivity()
    # clusters of GND pads
    pads = [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == 'GND']
    clusters, seen = [], set()
    for p in pads:
        if id(p) in seen:
            continue
        items = c.GetConnectedItems(p)
        group = [p] + [i for i in items]
        for i in group:
            seen.add(id(i))
        clusters.append(group)
    clusters.sort(key=len, reverse=True)
    # GetConnectedItems does not return pads reached only through a pour, so groups overlap:
    # treat everything that is not a genuinely small group as 'main'
    small = [cl for cl in clusters if len(cl) < 30]
    if not small:
        print('GND fully connected'); break
    big = [cl for cl in clusters if len(cl) >= 30]
    clusters = [[i for cl in big for i in cl]] + small
    R = R1.Router(b)
    g = R.g

    def raster_items(items):
        m = np.zeros(R.shape, bool)
        for it in items:
            for li, L in enumerate(R1.LAYERS):
                if it.Type() == pcbnew.PCB_ZONE_T:
                    if it.IsOnLayer(L):
                        m[li] |= g.raster(it.GetFilledPolysList(L)) & False   # zones handled below
                    continue
                if it.IsOnLayer(L):
                    m[li] |= g.raster(R1.item_poly(it, L, 0))
        return m
    main = raster_items(clusters[0])
    # main cluster's pour: every filled GND island that contains a main-cluster pad/via
    pts = [i.GetPosition() for i in clusters[0] if i.Type() in (pcbnew.PCB_PAD_T, pcbnew.PCB_VIA_T)]
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != 'GND':
            continue
        for li, L in enumerate(R1.LAYERS):
            if not z.IsOnLayer(L):
                continue
            fp = z.GetFilledPolysList(L)
            for i in range(fp.OutlineCount()):
                one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(fp.Outline(i))
                if any(one.Contains(p) for p in pts):
                    main[li] |= g.raster(one)
    bl = R.blocked_for('GND')
    own = R.net_grown.get('GND', np.zeros(R.shape, bool))
    hard = ((R.count - own.astype(np.int16)) > 0) | R.fixed
    hard[0] |= R.antko; hard[1] |= R.antko
    vb = R1.dilate(hard[0] | hard[1], (R1.VIA_D / 2 + R1.CLR - R1.INF) / R1.RES + 1.0)
    vok = ~vb
    cost = np.ones(R.shape, np.float32); vcost = np.full(R.shape[1:], R2.VIA_COST, np.float32)
    pf = R2.PF.__new__(R2.PF); pf.b = b; pf.g = g; pf.base = R; pf.nets = ['GND']; pf.paths = {'GND': []}
    linked = 0
    def islands_of(items):
        m = np.zeros(R.shape, bool)
        ps = [i.GetPosition() for i in items if i.Type() in (pcbnew.PCB_PAD_T, pcbnew.PCB_VIA_T, pcbnew.PCB_TRACE_T)]
        for z in b.Zones():
            if z.GetIsRuleArea() or z.GetNetname() != 'GND':
                continue
            for li, L in enumerate(R1.LAYERS):
                if not z.IsOnLayer(L):
                    continue
                fp = z.GetFilledPolysList(L)
                for i in range(fp.OutlineCount()):
                    one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(fp.Outline(i))
                    if any(one.Contains(p) for p in ps):
                        m[li] |= g.raster(one)
        return m
    for cl in clusters[1:]:
        src = raster_items(cl) | islands_of(cl)
        if not src.any():
            continue
        path_ = R2.astar_cost(R2.erode1(src) if R2.erode1(src).any() else src, R2.erode1(main), bl, vok, cost, vcost, 400000)
        if path_ is None:
            print('  cannot link cluster at', cl[0].GetPosition().x / 1e6, cl[0].GetPosition().y / 1e6)
            continue
        pf.paths['GND'].append(path_)
        linked += 1
    pf.commit()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    print('round', rnd, 'linked', linked, 'of', len(clusters) - 1)
    if linked == 0:
        break
pcbnew.SaveBoard(path, b)
