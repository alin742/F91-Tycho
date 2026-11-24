"""GND pours on both layers + antenna keep-out, then stitch every GND pad that the pour
does not reach (router2 with only the GND net, pours counted as GND copper).

Usage: python3 pour.py [board.kicad_pcb]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew
import router as R1
import router2 as R2

MM = lambda v: pcbnew.FromMM(float(v))
ANT_RULE = (-3.0, 10.9, 7.9, 15.6)    # no pour over/around the meander (both layers)


def rect_outline(x1, y1, x2, y2):
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        ch.Append(MM(x), MM(y))
    ch.SetClosed(True)
    return ch


def add_zones(b):
    # read the outline BEFORE removing old zones: removing them first leaves the SWIG wrappers of
    # later BOARD calls unusable in this KiCad build (re-running pour.py on a poured board crashed)
    bb = b.GetBoardEdgesBoundingBox()
    bb = (bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom())
    for z in list(b.Zones()):
        b.Remove(z)
    x1, y1 = bb[0] / 1e6 - 1, bb[1] / 1e6 - 1
    x2, y2 = bb[2] / 1e6 + 1, bb[3] / 1e6 + 1
    gnd = b.FindNet('GND')
    for L in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(L)
        z.SetNet(gnd)
        z.Outline().AddOutline(rect_outline(x1, y1, x2, y2))
        z.SetLocalClearance(MM(0.15))
        z.SetMinThickness(MM(0.12))
        z.SetThermalReliefGap(MM(0.2))
        z.SetThermalReliefSpokeWidth(MM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)   # tiny pads: spokes often can't fit
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetZoneName('GND_' + ('F' if L == pcbnew.F_Cu else 'B'))
        b.Add(z)
    ka = pcbnew.ZONE(b)
    ka.SetIsRuleArea(True)
    ka.SetDoNotAllowZoneFills(True)
    ka.SetDoNotAllowTracks(False)
    ka.SetDoNotAllowVias(True)
    ka.SetDoNotAllowPads(False)
    ka.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu)
    ka.SetLayerSet(ls)
    ka.Outline().AddOutline(rect_outline(*ANT_RULE))
    ka.SetZoneName('antenna keep-out')
    b.Add(ka)


def fill(b):
    zf = pcbnew.ZONE_FILLER(b)
    zf.Fill(b.Zones())


def stitch(pf):
    """Connect every small GND copper island (pad, pad group) to the largest one (the pour),
    searching from the small island outwards (the pour is huge; searching from it is too slow)."""
    raw = pf.base.net_raw['GND']
    comps = R1.components(raw, pf.base.pth_raw['GND'])
    comps.sort(key=lambda m: -m.sum())
    if len(comps) <= 1:
        return True, 0
    big = comps[0].copy()
    bl = pf.fixed_bl['GND']
    vok = pf.via_fixed_ok['GND']
    cost = np.ones(pf.shape, np.float32)
    vcost = np.full(pf.shape[1:], R2.VIA_COST, np.float32)
    made, ok = 0, True
    for m in comps[1:]:
        if (m & big).any():
            continue
        src = R2.erode1(m)
        if not src.any():
            src = m
        dst = R2.erode1(big)
        path = R2.astar_cost(src, dst, bl, vok, cost, vcost, max_exp=300000)
        if path is None:
            ok = False
            print('   could not reach the pour from island at', pf.g.cell_xy(*np.argwhere(m)[0][1:]))
            continue
        pf.paths['GND'].append(path)
        for l, r, c in path:
            big[l, r, c] = True
        big |= m
        made += 1
    return ok, made


def island_vias(b, pf, vok):
    """Drop one GND via into every pour island (each layer) that overlaps the other layer's pour."""
    g = pf.g
    fills = {}
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != 'GND':
            continue
        for li, L in enumerate(R1.LAYERS):
            if z.IsOnLayer(L):
                fills[li] = z.GetFilledPolysList(L)
    if len(fills) < 2:
        return 0
    full = {li: g.raster(fills[li]) for li in fills}
    existing = []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND':
            existing.append(t.GetPosition())
    added = 0
    gnd = b.FindNet('GND')
    for li in (0, 1):
        other = full[1 - li]
        polys = fills[li]
        for i in range(polys.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET()
            one.AddOutline(polys.Outline(i))
            for h in range(polys.HoleCount(i)):
                one.AddHole(polys.Hole(i, h))
            # skip islands that already contain a GND via or a GND PTH
            hit = any(one.Contains(p) for p in existing)
            if hit:
                continue
            m = g.raster(one)
            # the via only has to touch both pours (clearance to other nets is in vok);
            # the refill flows around it
            cand = R2.erode1(np.stack([m, m]))[0] & R2.erode1(np.stack([other, other]))[0] & vok
            if not cand.any():
                continue
            rs, cs = np.nonzero(cand)
            k = len(rs) // 2
            x, y = g.cell_xy(rs[k], cs[k])
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            v.SetWidth(MM(R2.VIA_D)); v.SetDrill(MM(R2.VIA_DR))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd)
            b.Add(v)
            existing.append(v.GetPosition())
            # keep later vias away from this one
            vok[max(rs[k] - 16, 0):rs[k] + 17, max(cs[k] - 16, 0):cs[k] + 17] = False
            added += 1
    return added


def grid_vias(b, pf, vok, pitch=1.5):
    """Stitching vias wherever both pours overlap (greedy, >= pitch mm apart)."""
    g = pf.g
    fills = {}
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != 'GND':
            continue
        for li, L in enumerate(R1.LAYERS):
            if z.IsOnLayer(L):
                fills[li] = g.raster(z.GetFilledPolysList(L))
    if len(fills) < 2:
        return 0
    both = fills[0] & fills[1]
    inner = both.copy()
    for _ in range(int(0.35 / R1.RES) + 1):
        inner = R2.erode1(np.stack([inner, inner]))[0]
    cand = inner & vok
    taken = [(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6) for t in b.GetTracks()
             if t.Type() == pcbnew.PCB_VIA_T]
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                taken.append((p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))
    gnd = b.FindNet('GND')
    added = 0
    step = max(1, int(0.25 / R1.RES))
    rs, cs = np.nonzero(cand)
    for r, c in zip(rs[::step], cs[::step]):
        x, y = g.cell_xy(r, c)
        if any((x - tx) ** 2 + (y - ty) ** 2 < pitch ** 2 for tx, ty in taken):
            continue
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(R2.VIA_D)); v.SetDrill(MM(R2.VIA_DR))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd)
        b.Add(v)
        taken.append((x, y))
        added += 1
    return added


def join_clusters(b, pf, vok):
    """Union-find over GND pour islands (both layers) joined by vias/PTH; drop a via where a top
    island and a bottom island of different clusters overlap. Returns vias added."""
    g = pf.g
    isl = []          # (layer, SHAPE_POLY_SET, raster)
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != 'GND':
            continue
        for li, L in enumerate(R1.LAYERS):
            if not z.IsOnLayer(L):
                continue
            fp = z.GetFilledPolysList(L)
            for i in range(fp.OutlineCount()):
                one = pcbnew.SHAPE_POLY_SET(); one.AddOutline(fp.Outline(i))
                for h in range(fp.HoleCount(i)):
                    one.AddHole(fp.Hole(i, h))
                isl.append((li, one, g.raster(one)))
    par = list(range(len(isl)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    joins = [t.GetPosition() for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == 'GND']
    joins += [p.GetPosition() for f in b.GetFootprints() for p in f.Pads()
              if p.GetNetname() == 'GND' and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    for pt in joins:
        hit = [k for k, (li, one, m) in enumerate(isl) if one.Contains(pt)]
        for k in hit[1:]:
            par[find(k)] = find(hit[0])
    # GND pads touching several islands (same layer only) also join them
    added = 0
    gnd = b.FindNet('GND')
    for a in range(len(isl)):
        for c in range(len(isl)):
            if isl[a][0] != 0 or isl[c][0] != 1 or find(a) == find(c):
                continue
            ov = R2.erode1(np.stack([isl[a][2], isl[a][2]]))[0] & R2.erode1(np.stack([isl[c][2], isl[c][2]]))[0] & vok
            if not ov.any():
                continue
            rs, cs = np.nonzero(ov)
            k = len(rs) // 2
            x, y = g.cell_xy(rs[k], cs[k])
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            v.SetWidth(MM(R2.VIA_D)); v.SetDrill(MM(R2.VIA_DR))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd)
            b.Add(v)
            r0, c0 = rs[k], cs[k]
            vok[max(r0 - 14, 0):r0 + 15, max(c0 - 14, 0):c0 + 15] = False
            par[find(c)] = find(a)
            added += 1
    return added


def main():
    path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else R1.PCB
    b = pcbnew.LoadBoard(path)
    add_zones(b)
    # 1st fill keeps every island, so the stitching vias have pour on both layers to land on
    for z in b.Zones():
        if not z.GetIsRuleArea():
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    fill(b)
    for rnd in range(4):
        pf = R2.PF(b)
        # pour copper is GND copper for the stitching search
        for z in b.Zones():
            if z.GetIsRuleArea() or z.GetNetname() != 'GND':
                continue
            for li, L in enumerate(R1.LAYERS):
                if z.IsOnLayer(L):
                    m = pf.g.raster(z.GetFilledPolysList(L))
                    pf.base.net_raw['GND'][li] |= m
        pf.nets = ['GND']
        pf.H = {'GND': np.zeros(pf.shape, bool)}
        pf.paths = {'GND': []}
        bl = pf.base.blocked_for('GND')
        pf.fixed_bl['GND'] = bl
        # via mask WITHOUT the own-copper exemption (pour cells reach the edge and other nets)
        own = pf.base.net_grown.get('GND', np.zeros(pf.shape, bool))
        hard = ((pf.base.count - own.astype(np.int16)) > 0) | pf.base.fixed
        hard[0] |= pf.base.antko; hard[1] |= pf.base.antko
        vb = R2.disk_dilate(hard[0] | hard[1], (R2.VIA_D / 2 + R2.CLR - R2.INF) / R2.RES + 1.0)
        vb |= R2.disk_dilate(pf.base.smd_raw['GND'][0] | pf.base.smd_raw['GND'][1], (R2.VIA_D / 2) / R2.RES)
        pf.via_fixed_ok['GND'] = ~vb
        nv = grid_vias(b, pf, pf.via_fixed_ok['GND'].copy()) if rnd == 0 else 0
        nv += island_vias(b, pf, pf.via_fixed_ok['GND'].copy())
        if rnd > 0:
            nv += join_clusters(b, pf, pf.via_fixed_ok['GND'].copy())
        ok, n = stitch(pf)
        print(f'round {rnd}: {nv} island vias, stitched {n} GND pads, complete={ok}')
        if rnd == 0:
            # from now on orphan copper is removed again
            for z in b.Zones():
                if not z.GetIsRuleArea():
                    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        if n == 0 and nv == 0 and rnd > 0:
            break
        pf.commit()
        fill(b)
    pcbnew.SaveBoard(path, b)
    print('saved', path)


if __name__ == '__main__':
    main()
