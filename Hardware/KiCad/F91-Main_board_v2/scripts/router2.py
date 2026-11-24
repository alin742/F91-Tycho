"""Negotiated-congestion (PathFinder-style) 2-layer grid router for the F91 v2 board.

Fixed copper (pads, the v1 RF tracks), NPTH holes, the board edge and the antenna keep-out are hard
obstacles. Routed tracks of different nets may overlap during the early iterations at a cost;
the cost of shared cells grows every iteration (present + history), so nets negotiate until no
two nets' tracks violate clearance. GND is left to the copper pours (pour.py).

Rules (JLCPCB 2-layer): track 0.15, clearance 0.1, via 0.6/0.3, edge 0.2, NPTH 0.2, ANT 0.3.
Usage: python3 router2.py [iterations]
"""
import os, sys, math, heapq, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew
import router as R1          # reuse Grid, raster helpers, dilate, components, simplify

ROOT = R1.ROOT
PCB = R1.PCB
RES, TW, CLR, VIA_D, VIA_DR = R1.RES, R1.TW, R1.CLR, R1.VIA_D, R1.VIA_DR
INF = R1.INF
HALF_T = (TW / 2 + CLR / 2) / RES + 0.6         # half-clearance radius of a track (cells)
HALF_V = (VIA_D / 2 + CLR / 2) / RES + 0.6      # ... of a via
VIA_COST = 25.0
MM = lambda v: pcbnew.FromMM(float(v))
SKIP = {'GND', ''}
# keep the escape area under the CC2640R2 32 kHz pins free of other nets' vias
NO_VIA_ZONES = [(0.3, 5.5, 1.9, 6.6)]   # only around the fixed 32 kHz escape vias
# antenna rule area of pour.py: no vias of any net (incl. the crystal nets)
ANT_VIA_ZONE = (-3.0, 10.9, 7.9, 15.6)   # = router keep-out = pour.py rule area
# crystal nets stay on one layer (and their via pair under U1 pins 3/4 cannot fit anyway)
NO_VIA_NETS = {'X24M_P', 'X24M_N'}   # the 32 kHz pair has fixed escape vias (gen_pcb.py)


def disk_dilate(mask, rad):
    return R1.dilate(mask, rad)


def erode1(m):
    """erode a (2,H,W) mask by one cell (4-neighbourhood); keep cells that would vanish entirely"""
    out = m.copy()
    out[:, 1:, :] &= m[:, :-1, :]; out[:, :-1, :] &= m[:, 1:, :]
    out[:, :, 1:] &= m[:, :, :-1]; out[:, :, :-1] &= m[:, :, 1:]
    return out


class PF:
    def __init__(self, b):
        self.b = b
        self.base = R1.Router(b)     # fixed copper of all nets + edge + NPTH + keep-outs
        g = self.base.g
        self.g = g
        self.shape = self.base.shape
        self.nets = sorted(n for n in self.base.net_raw if n not in SKIP)
        self.O = np.zeros(self.shape, np.int16)       # routed half-masks occupancy
        self.H = {n: np.zeros(self.shape, bool) for n in self.nets}
        self.paths = {n: [] for n in self.nets}
        self.hist = np.zeros(self.shape, np.float32)
        self.fixed_bl = {}
        self.via_fixed_ok = {}
        for n in self.nets:
            bl = self.base.blocked_for(n)
            self.fixed_bl[n] = bl
            vb = disk_dilate(bl[0] | bl[1], (VIA_D / 2 + CLR - INF) / RES + 0.5)
            vb |= disk_dilate(self.base.smd_raw[n][0] | self.base.smd_raw[n][1], (VIA_D / 2) / RES)
            self.via_fixed_ok[n] = ~vb
            if n in NO_VIA_NETS:
                self.via_fixed_ok[n][:] = False
            if n != 'ANT':
                x1, y1, x2, y2 = ANT_VIA_ZONE
                c1, r1 = g.to_px(x1 - 0.35, y1 - 0.35); c2, r2 = g.to_px(x2 + 0.35, y2)
                self.via_fixed_ok[n][int(r1):int(r2) + 1, int(c1):int(c2) + 1] = False
            if True:
                for (x1, y1, x2, y2) in NO_VIA_ZONES:
                    c1, r1 = g.to_px(x1, y1); c2, r2 = g.to_px(x2, y2)
                    self.via_fixed_ok[n][int(r1):int(r2) + 1, int(c1):int(c2) + 1] = False

    def conn_order(self):
        """nets sorted by total pad spread (short nets first)"""
        def spread(n):
            pts = np.argwhere(self.base.net_raw[n].any(0))
            return (pts.max(0) - pts.min(0)).sum() if len(pts) else 0
        return sorted(self.nets, key=spread)

    def rip(self, n):
        self.O -= self.H[n].astype(np.int16)
        self.H[n][:] = False
        self.paths[n] = []

    def route(self, n, pres):
        raw = self.base.net_raw[n]
        comps = R1.components(raw, self.base.pth_raw[n])
        if len(comps) <= 1:
            return True
        others = self.O > 0
        occ_t = np.stack([disk_dilate(others[0], HALF_T), disk_dilate(others[1], HALF_T)])
        occ_v = disk_dilate(others[0] | others[1], HALF_V)
        cost = 1.0 + pres * occ_t + self.hist
        vcost = VIA_COST + pres * 4 * occ_v + self.hist.max(0) * 4
        bl = self.fixed_bl[n]
        vok = self.via_fixed_ok[n].copy()
        own_v = np.zeros(self.shape[1:], bool)
        comps.sort(key=lambda m: -m.sum())
        tree = comps[0].copy()
        rest = comps[1:]
        ok = True
        while rest:
            tg = np.zeros(self.shape, bool)
            for m in rest:
                tg |= m
            # end points must lie strictly inside copper so KiCad registers the connection
            src = erode1(tree)
            if not src.any():
                src = tree
            dst = erode1(tg)
            for m in rest:
                if not (dst & m).any():
                    dst |= m
            path = astar_cost(src, dst, bl, vok, cost, vcost)
            if path is None:
                ok = False
                break
            self.paths[n].append(path)
            for i in range(1, len(path)):
                if path[i][0] != path[i - 1][0]:
                    self.base.pth_raw[n][path[i][1], path[i][2]] = True
                    own_v[path[i][1], path[i][2]] = True
            if own_v.any():
                vok &= ~disk_dilate(own_v, (VIA_D + 0.2) / RES)
            pm = np.zeros(self.shape, bool)
            for l, r, c in path:
                pm[l, r, c] = True
            tree |= pm
            # only the component the path ENDS in is connected (KiCad needs the track end inside
            # the pad); passing close to other copper does not connect it
            el, er, ec = path[-1]
            nrest = []
            for m in rest:
                if m[el, er, ec]:
                    tree |= m
                else:
                    nrest.append(m)
            rest = nrest
        # half-mask of this net's routed copper
        h = np.zeros(self.shape, bool)
        for path in self.paths[n]:
            tm = np.zeros(self.shape, bool)
            vm = np.zeros(self.shape[1:], bool)
            for i, (l, r, c) in enumerate(path):
                tm[l, r, c] = True
                if i and path[i - 1][0] != l:
                    vm[r, c] = True
            h[0] |= disk_dilate(tm[0], HALF_T); h[1] |= disk_dilate(tm[1], HALF_T)
            if vm.any():
                vd = disk_dilate(vm, HALF_V)
                h[0] |= vd; h[1] |= vd
        self.H[n] = h
        self.O += h.astype(np.int16)
        return ok

    def overuse(self):
        return self.O > 1

    def commit(self):
        """Add tracks/vias. Each path end is snapped to its pad centre / track centreline so KiCad
        sees a real connection (the raster end cell may sit on the pad edge)."""
        b, g = self.b, self.g
        anchors = {}   # net -> list of (layer index or None for both, kind, item)
        for f in b.GetFootprints():
            for p in f.Pads():
                anchors.setdefault(p.GetNetname(), []).append(p)
        for t in b.GetTracks():
            anchors.setdefault(t.GetNetname(), []).append(t)

        def snap_target(n, li, x, y):
            pt = pcbnew.VECTOR2I(MM(x), MM(y))
            best = None
            for it in anchors.get(n, []):
                L = R1.LAYERS[li]
                if not it.IsOnLayer(L):
                    continue
                if it.Type() == pcbnew.PCB_PAD_T or it.Type() == pcbnew.PCB_VIA_T:
                    q = it.GetPosition()
                else:
                    q = closest_on_seg(it.GetStart(), it.GetEnd(), pt)
                d = (q - pt).EuclideanNorm()
                hit = it.HitTest(pt, 0)
                if hit and (best is None or d < best[0]):
                    best = (d, q)
            if best is None:
                return None
            # pads: go to the centre only if the straight line stays inside the pad
            return best[1]

        def add_track(n, li, a, bb):
            if (a - bb).EuclideanNorm() < MM(0.005):
                return
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(a); t.SetEnd(bb)
            t.SetWidth(MM(TW)); t.SetLayer(R1.LAYERS[li]); t.SetNet(b.FindNet(n))
            b.Add(t)
            anchors.setdefault(n, []).append(t)

        for n in self.nets:
            ni = b.FindNet(n)
            for path in self.paths[n]:
                segs = R1.simplify(path)
                for kind, a, bp, li in segs:
                    if kind == 'via':
                        v = pcbnew.PCB_VIA(b)
                        x, y = g.cell_xy(*a)
                        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                        v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DR))
                        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                        v.SetNet(ni)
                        b.Add(v)
                        anchors.setdefault(n, []).append(v)
                    else:
                        xa, ya = g.cell_xy(*a); xb, yb = g.cell_xy(*bp)
                        add_track(n, li, pcbnew.VECTOR2I(MM(xa), MM(ya)), pcbnew.VECTOR2I(MM(xb), MM(yb)))
                # snap both ends
                for (l, r, c) in (path[0], path[-1]):
                    x, y = g.cell_xy(r, c)
                    q = snap_target(n, l, x, y)
                    if q is not None:
                        add_track(n, l, pcbnew.VECTOR2I(MM(x), MM(y)), q)


def closest_on_seg(a, b, p):
    ax, ay, bx, by, px, py = a.x, a.y, b.x, b.y, p.x, p.y
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return pcbnew.VECTOR2I(ax, ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return pcbnew.VECTOR2I(int(ax + t * dx), int(ay + t * dy))


DIRS = R1.DIRS


def astar_cost(src, dst, bl, vok, cost, vcost, max_exp=900000):
    L, H, W = src.shape
    dl, dr_, dc_ = np.nonzero(dst)
    rmin, rmax, cmin, cmax = dr_.min(), dr_.max(), dc_.min(), dc_.max()

    def h(r, c):
        dr = max(rmin - r, 0, r - rmax); dc = max(cmin - c, 0, c - cmax)
        return max(dr, dc) + 0.4142 * min(dr, dc)
    gbest = np.full(src.shape, np.inf, np.float32)
    parent = {}
    pq = []
    for l, r, c in zip(*np.nonzero(src)):
        gbest[l, r, c] = 0
        heapq.heappush(pq, (h(r, c), 0.0, int(l), int(r), int(c)))
    exp = 0
    while pq:
        f, gc, l, r, c = heapq.heappop(pq)
        if gc > gbest[l, r, c]:
            continue
        if dst[l, r, c] and not src[l, r, c]:
            path = [(l, r, c)]
            while (l, r, c) in parent:
                l, r, c = parent[(l, r, c)]
                path.append((l, r, c))
            return path[::-1]
        exp += 1
        if exp > max_exp:
            return None
        for dr, dc, d in DIRS:
            rr, cc = r + dr, c + dc
            if not (0 <= rr < H and 0 <= cc < W):
                continue
            if bl[l, rr, cc] and not dst[l, rr, cc]:
                continue
            if dr and dc and bl[l, r + dr, c] and bl[l, r, c + dc]:
                continue
            ng = gc + d * float(cost[l, rr, cc])
            if ng < gbest[l, rr, cc]:
                gbest[l, rr, cc] = ng
                parent[(l, rr, cc)] = (l, r, c)
                heapq.heappush(pq, (ng + h(rr, cc), ng, l, rr, cc))
        if vok[r, c] and not src[l, r, c]:
            ol = 1 - l
            if not bl[ol, r, c] or dst[ol, r, c]:
                ng = gc + float(vcost[r, c])
                if ng < gbest[ol, r, c]:
                    gbest[ol, r, c] = ng
                    parent[(ol, r, c)] = (l, r, c)
                    heapq.heappush(pq, (ng + h(r, c), ng, ol, r, c))
    return None


def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    b = pcbnew.LoadBoard(PCB)
    t0 = time.time()
    pf = PF(b)
    order = pf.conn_order()
    print(f'setup {time.time() - t0:.1f}s, {len(order)} nets', flush=True)
    pres = 0.5
    best = None
    for it in range(iters):
        failed = []
        for n in order:
            pf.rip(n)
            if not pf.route(n, pres):
                failed.append(n)
        ov = pf.overuse()
        nov = int(ov.sum())
        bad = sorted({n for n in pf.nets if (pf.H[n] & ov).any()})
        print(f'iter {it:2d} pres {pres:6.2f} overused cells {nov:6d} failed {failed} conflicts {bad}', flush=True)
        if not failed and nov == 0:
            break
        pf.hist += ov.astype(np.float32) * 1.0
        pres *= 1.6
        # route the conflicting nets first next time
        order = bad + [n for n in order if n not in bad]
    pf.commit()
    pcbnew.SaveBoard(PCB, b)
    print('saved; remaining overuse', int(pf.overuse().sum()), 'failed', failed)


if __name__ == '__main__':
    main()
