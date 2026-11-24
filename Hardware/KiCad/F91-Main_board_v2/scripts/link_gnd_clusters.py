"""Join GND islands to the main GND net with an A*-routed track/via, then refill.
Islands are found geometrically: every filled GND fragment, pad, via and track is a node; nodes that
touch are merged (union-find). This also catches islands that only meet through the pour, which
KiCad's GetConnectedItems() hides (it returns the whole zone). Also removes orphan GND vias.
Usage: python3 link_gnd_clusters.py [board]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew
import router as R1
import router2 as R2

def gnd_groups(b):
    """Return GND groups, largest first. Each group is a list of (kind, obj, extra):
    ('Z', zone, (layer, outline index)) for a fill fragment, ('P', pad, None), ('T', track/via, None)."""
    gnd = b.FindNet('GND').GetNetCode()
    nodes, parent = [], []

    def add(n):
        nodes.append(n); parent.append(len(parent)); return len(nodes) - 1

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a

    def union(a, c):
        parent[find(a)] = find(c)

    frags = []
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() != gnd:
            continue
        for L in R1.LAYERS:
            if z.IsOnLayer(L):
                fp = z.GetFilledPolysList(L)
                for i in range(fp.OutlineCount()):
                    frags.append((add(('Z', z, (L, i))), L, fp.Outline(i)))

    def touch_fill(k, L, p):
        for fk, FL, ol in frags:
            if FL == L and ol.PointInside(p, 1000):
                union(k, fk)

    cu = []   # (node, layer, copper item) for track/pad/via contact tests
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gnd:
                continue
            k = add(('P', pad, None))
            for L in R1.LAYERS:
                if pad.IsOnLayer(L):
                    touch_fill(k, L, pad.GetPosition()); cu.append((k, L, pad))
    for t in b.GetTracks():
        if t.GetNetCode() != gnd:
            continue
        k = add(('T', t, None))
        if t.Type() == pcbnew.PCB_VIA_T:
            for L in R1.LAYERS:
                touch_fill(k, L, t.GetPosition()); cu.append((k, L, t))
        else:
            for p in (t.GetStart(), t.GetEnd()):
                touch_fill(k, t.GetLayer(), p)
            cu.append((k, t.GetLayer(), t))
    # copper-to-copper contacts (track ends on pads/vias/other tracks)
    for i, (ka, La, a) in enumerate(cu):
        pts = [a.GetStart(), a.GetEnd()] if a.Type() == pcbnew.PCB_TRACE_T else [a.GetPosition()]
        for kb, Lb, c in cu:
            if kb == ka or Lb != La or find(ka) == find(kb):
                continue
            if any(c.HitTest(p, 0) for p in pts):
                union(ka, kb)
    groups = {}
    for i, n in enumerate(nodes):
        groups.setdefault(find(i), []).append(n)
    return sorted(groups.values(), key=len, reverse=True)


def main():
    path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else R1.PCB
    b = pcbnew.LoadBoard(path)
    for rnd in range(4):
        b.BuildConnectivity()
        c = b.GetConnectivity()
        for t in list(b.GetTracks()):
            if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND' and len(c.GetConnectedItems(t)) <= 1:
                b.Remove(t)
        groups = gnd_groups(b)
        # a group with no pad is a pour fragment KiCad would just call an island: not an open connection
        groups = [groups[0]] + [g_ for g_ in groups[1:] if any(n[0] == 'P' for n in g_)]
        if len(groups) == 1:
            print('GND fully connected'); break
        R = R1.Router(b)
        g = R.g

        def raster(group):
            m = np.zeros(R.shape, bool)
            for kind, obj, extra in group:
                if kind == 'Z':
                    L, i = extra
                    one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(obj.GetFilledPolysList(L).Outline(i))
                    m[R1.LAYERS.index(L)] |= g.raster(one)
                else:
                    for li, L in enumerate(R1.LAYERS):
                        if obj.IsOnLayer(L):
                            m[li] |= g.raster(R1.item_poly(obj, L, 0))
            return m

        main = raster(groups[0])
        bl = R.blocked_for('GND')
        own = R.net_grown.get('GND', np.zeros(R.shape, bool))
        hard = ((R.count - own.astype(np.int16)) > 0) | R.fixed
        hard[0] |= R.antko; hard[1] |= R.antko
        vb = R1.dilate(hard[0] | hard[1], (R1.VIA_D / 2 + R1.CLR - R1.INF) / R1.RES + 1.0)
        vok = ~vb
        cost = np.ones(R.shape, np.float32); vcost = np.full(R.shape[1:], R2.VIA_COST, np.float32)
        pf = R2.PF.__new__(R2.PF); pf.b = b; pf.g = g; pf.base = R; pf.nets = ['GND']; pf.paths = {'GND': []}
        linked = 0
        for grp in groups[1:]:
            src = raster(grp)
            pads = [o.GetParentFootprint().GetReference() + ':' + o.GetNumber() for k, o, e in grp if k == 'P']
            if not src.any():
                continue
            e = R2.erode1(src)
            path_ = R2.astar_cost(e if e.any() else src, R2.erode1(main), bl, vok, cost, vcost, 400000)
            if path_ is None:
                print('  cannot link island', pads)
                continue
            pf.paths['GND'].append(path_)
            linked += 1
            print('  linked island', pads)
        pf.commit()
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        print('round', rnd, 'linked', linked, 'of', len(groups) - 1)
        if linked == 0:
            break
    pcbnew.SaveBoard(path, b)


if __name__ == '__main__':
    main()
