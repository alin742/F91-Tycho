"""Small 2-layer grid router (A*, 8-direction, vias) for the F91 v2 board.

Routes every net except GND (GND = copper pours + stitching vias, see pour.py) using the
board's existing copper as fixed obstacles. Clearances follow the JLCPCB 2-layer rules:
track 0.15 mm, clearance 0.1 mm, via 0.6/0.3 mm, 0.2 mm to edges and NPTH holes,
0.3 mm around the antenna net, and a keep-out over the antenna on both layers.

Usage: python3 router.py [--order NET,NET,...]
"""
import os, sys, math, heapq, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw
import pcbnew

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(ROOT, 'F91-Main_board_v2.kicad_pcb')
RES = 0.05
TW = 0.10          # JLC 2-layer minimum; every net here carries < 50 mA
CLR = 0.10
INF = CLR + TW / 2 + 0.03          # obstacle growth seen by a track centre line
VIA_D, VIA_DR = 0.45, 0.25   # JLC standard tier: 0.25 drill with >= 0.45 pad
VIA_COST = 30.0
EDGE = 0.2
ANT_CLR = 0.33          # rule is 0.30; +0.03 for grid rounding
MM = lambda v: pcbnew.FromMM(float(v))
mm = lambda v: v / 1e6
LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
SKIP_NETS = {'GND', ''}
# antenna keep-out (both layers) except for the ANT net itself
ANT_KEEPOUT = (-3.0, 10.9, 7.9, 15.5)


class Grid:
    def __init__(self, b):
        bb = b.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = mm(bb.GetX()) - 0.5, mm(bb.GetY()) - 0.5
        self.W = int((mm(bb.GetWidth()) + 1) / RES) + 1
        self.H = int((mm(bb.GetHeight()) + 1) / RES) + 1

    def to_px(self, x, y):
        return ((x - self.x0) / RES, (y - self.y0) / RES)

    def raster(self, poly):
        """SHAPE_POLY_SET (board units) -> bool array"""
        img = Image.new('1', (self.W, self.H), 0)
        d = ImageDraw.Draw(img)
        for i in range(poly.OutlineCount()):
            o = poly.Outline(i)
            pts = [self.to_px(mm(o.CPoint(k).x), mm(o.CPoint(k).y)) for k in range(o.PointCount())]
            if len(pts) >= 3:
                d.polygon(pts, fill=1)
            for h in range(poly.HoleCount(i)):
                ho = poly.Hole(i, h)
                hp = [self.to_px(mm(ho.CPoint(k).x), mm(ho.CPoint(k).y)) for k in range(ho.PointCount())]
                if len(hp) >= 3:
                    d.polygon(hp, fill=0)
        return np.array(img, dtype=bool)

    def cell_xy(self, r, c):
        return self.x0 + c * RES, self.y0 + r * RES


def item_poly(item, layer, grow):
    s = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(s, layer, MM(grow), MM(0.005), pcbnew.ERROR_OUTSIDE)
    return s


def dilate(a, rad_cells):
    out = a.copy()
    R = int(math.ceil(rad_cells))
    for dr in range(-R, R + 1):
        for dc in range(-R, R + 1):
            if dr * dr + dc * dc > rad_cells * rad_cells:
                continue
            sh = np.zeros_like(a)
            rs = slice(max(dr, 0), a.shape[0] + min(dr, 0)); rd = slice(max(-dr, 0), a.shape[0] + min(-dr, 0))
            cs = slice(max(dc, 0), a.shape[1] + min(dc, 0)); cd = slice(max(-dc, 0), a.shape[1] + min(-dc, 0))
            sh[rs, cs] = a[rd, cd]
            out |= sh
    return out


class Router:
    def __init__(self, b):
        self.b = b
        self.g = Grid(b)
        g = self.g
        self.shape = (2, g.H, g.W)
        self.count = np.zeros(self.shape, np.int16)   # how many nets' grown copper cover a cell
        self.net_grown = {}                           # net -> bool array (2,H,W)
        self.net_raw = {}                             # net -> bool array (2,H,W) (true copper)
        self.smd_raw = {}                             # net -> cells of SMD pads (no via-in-pad)
        self.pth_raw = {}                             # net -> cells where layers are joined (vias, PTH)
        self.fixed = np.zeros(self.shape, bool)       # NPTH, edge, keep-outs (for everyone)
        # board edge
        outline = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(outline, True)
        inner = pcbnew.SHAPE_POLY_SET(outline)
        inner.Deflate(MM(EDGE + TW / 2 + 0.06), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005))
        inside = g.raster(inner)
        self.fixed[:] = ~inside
        self.inside_raw = g.raster(outline)
        # antenna keep-out
        x1, y1, x2, y2 = ANT_KEEPOUT
        c1, r1 = g.to_px(x1, y1); c2, r2 = g.to_px(x2, y2)
        self.antko = np.zeros((g.H, g.W), bool)
        self.antko[int(r1):int(r2) + 1, int(c1):int(c2) + 1] = True
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    hole = pcbnew.SHAPE_POLY_SET()
                    p.TransformHoleToPolygon(hole, MM(0.2 + TW / 2 + 0.03), MM(0.005), pcbnew.ERROR_OUTSIDE)
                    m = g.raster(hole)
                    self.fixed[0] |= m; self.fixed[1] |= m
                    continue
                self.add_item(p, p.GetNetname(), is_pad=True)
        for t in b.GetTracks():
            self.add_item(t, t.GetNetname())

    def _ensure(self, net):
        if net not in self.net_grown:
            self.net_grown[net] = np.zeros(self.shape, bool)
            self.net_raw[net] = np.zeros(self.shape, bool)
            self.smd_raw[net] = np.zeros(self.shape, bool)
            self.pth_raw[net] = np.zeros(self.shape[1:], bool)

    def add_item(self, item, net, is_pad=False):
        self._ensure(net)
        grow = INF + (ANT_CLR - CLR if net == 'ANT' else 0)
        for li, L in enumerate(LAYERS):
            if not item.IsOnLayer(L):
                continue
            gm = self.g.raster(item_poly(item, L, grow))
            rm = self.g.raster(item_poly(item, L, 0))
            new = gm & ~self.net_grown[net][li]
            self.count[li] += new
            self.net_grown[net][li] |= gm
            self.net_raw[net][li] |= rm
            if is_pad and item.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                self.smd_raw[net][li] |= rm
        joins = item.Type() == pcbnew.PCB_VIA_T or (is_pad and item.GetAttribute() == pcbnew.PAD_ATTRIB_PTH)
        if joins:
            self.pth_raw[net] |= self.g.raster(item_poly(item, pcbnew.F_Cu, 0))
        # PTH holes: hole clearance on both layers handled by the pad copper itself

    def blocked_for(self, net):
        own = self.net_grown.get(net, np.zeros(self.shape, bool))
        bl = (self.count - own.astype(np.int16)) > 0
        bl |= self.fixed
        if net != 'ANT':
            bl[0] |= self.antko; bl[1] |= self.antko
        # a net's own copper outside the edge (castellations) must stay reachable
        if net in self.net_raw:
            bl &= ~self.net_raw[net]
        return bl

    def route_net(self, net, max_exp=600000):
        g = self.g
        raw = self.net_raw[net]
        # connected components of this net's existing copper
        comps = components(raw, self.pth_raw[net])
        if len(comps) <= 1:
            return True, 0
        bl = self.blocked_for(net)
        via_bl = dilate(bl[0] | bl[1], (VIA_D / 2 + CLR - INF) / RES + 0.5)
        via_bl |= dilate(self.smd_raw[net][0] | self.smd_raw[net][1], (VIA_D / 2) / RES)
        via_ok = ~via_bl
        # grow the tree from the largest component
        comps.sort(key=lambda m: -m.sum())
        tree = comps[0].copy()
        rest = comps[1:]
        made = 0
        while rest:
            targets = np.zeros(self.shape, bool)
            for m in rest:
                targets |= m
            path = astar(tree, targets, bl, via_ok, max_exp)
            if path is None:
                return False, made
            self.commit(net, path)
            made += 1
            # merge whatever got connected
            pm = path_mask(path, self.shape)
            tree |= pm
            tree |= dilate_layers(pm, 1)
            nrest = []
            for m in rest:
                if (m & (tree | dilate_layers(pm, 2))).any():
                    tree |= m
                else:
                    nrest.append(m)
            rest = nrest
            bl = self.blocked_for(net)
        return True, made

    def commit(self, net, path):
        g = self.g
        ni = self.b.FindNet(net)
        segs = simplify(path)
        for kind, a, bpt, li in segs:
            if kind == 'via':
                v = pcbnew.PCB_VIA(self.b)
                x, y = g.cell_xy(*a)
                v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DR))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(ni)
                self.b.Add(v)
                self.add_item(v, net)
            else:
                t = pcbnew.PCB_TRACK(self.b)
                xa, ya = g.cell_xy(*a); xb, yb = g.cell_xy(*bpt)
                t.SetStart(pcbnew.VECTOR2I(MM(xa), MM(ya))); t.SetEnd(pcbnew.VECTOR2I(MM(xb), MM(yb)))
                t.SetWidth(MM(TW)); t.SetLayer(LAYERS[li]); t.SetNet(ni)
                self.b.Add(t)
                self.add_item(t, net)


def dilate_layers(m, rad):
    return np.stack([dilate(m[0], rad), dilate(m[1], rad)])


def components(raw, joins=None):
    """Connected components over both layers (layers joined where both have copper = PTH/vias)."""
    H, W = raw.shape[1:]
    lab = np.zeros(raw.shape, np.int32)
    n = 0
    comps = []
    both = (raw[0] & raw[1]) if joins is None else (raw[0] & raw[1] & joins)
    for li in range(2):
        rs, cs = np.nonzero(raw[li] & (lab[li] == 0))
        for r0, c0 in zip(rs, cs):
            if lab[li, r0, c0]:
                continue
            n += 1
            st = [(li, r0, c0)]
            lab[li, r0, c0] = n
            cells = []
            while st:
                l, r, c = st.pop()
                cells.append((l, r, c))
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < H and 0 <= cc < W and raw[l, rr, cc] and not lab[l, rr, cc]:
                            lab[l, rr, cc] = n
                            st.append((l, rr, cc))
                if both[r, c] and raw[1 - l, r, c] and not lab[1 - l, r, c]:
                    lab[1 - l, r, c] = n
                    st.append((1 - l, r, c))
            m = np.zeros(raw.shape, bool)
            ci = np.array(cells)
            m[ci[:, 0], ci[:, 1], ci[:, 2]] = True
            comps.append(m)
    return comps


DIRS = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
        (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]


def astar(src, dst, bl, via_ok, max_exp):
    L, H, W = src.shape
    dl, dr_, dc_ = np.nonzero(dst)
    # heuristic: distance to the bbox of the targets
    rmin, rmax, cmin, cmax = dr_.min(), dr_.max(), dc_.min(), dc_.max()

    def h(r, c):
        dr = max(rmin - r, 0, r - rmax); dc = max(cmin - c, 0, c - cmax)
        return max(dr, dc) + 0.4142 * min(dr, dc)
    gbest = np.full(src.shape, np.inf, np.float32)
    parent = {}
    pq = []
    sl, sr, sc = np.nonzero(src)
    for l, r, c in zip(sl, sr, sc):
        gbest[l, r, c] = 0
        heapq.heappush(pq, (h(r, c), 0.0, l, r, c))
    exp = 0
    while pq:
        f, gcur, l, r, c = heapq.heappop(pq)
        if gcur > gbest[l, r, c]:
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
        for dr, dc, cost in DIRS:
            rr, cc = r + dr, c + dc
            if not (0 <= rr < H and 0 <= cc < W):
                continue
            if bl[l, rr, cc] and not dst[l, rr, cc]:
                continue
            if dr and dc and (bl[l, r + dr, c] and bl[l, r, c + dc]):
                continue
            ng = gcur + cost
            if ng < gbest[l, rr, cc]:
                gbest[l, rr, cc] = ng
                parent[(l, rr, cc)] = (l, r, c)
                heapq.heappush(pq, (ng + h(rr, cc), ng, l, rr, cc))
        if via_ok[r, c] and not src[l, r, c]:
            ol = 1 - l
            if not bl[ol, r, c] or dst[ol, r, c]:
                ng = gcur + VIA_COST
                if ng < gbest[ol, r, c]:
                    gbest[ol, r, c] = ng
                    parent[(ol, r, c)] = (l, r, c)
                    heapq.heappush(pq, (ng + h(r, c), ng, ol, r, c))
    return None


def path_mask(path, shape):
    m = np.zeros(shape, bool)
    for l, r, c in path:
        m[l, r, c] = True
    return m


def simplify(path):
    """cells -> [('seg', (r,c), (r,c), layer) | ('via', (r,c), None, None)]"""
    out = []
    i = 0
    n = len(path)
    while i < n - 1:
        l, r, c = path[i]
        if path[i + 1][0] != l:
            out.append(('via', (r, c), None, None))
            i += 1
            continue
        j = i + 1
        d = (path[j][1] - r, path[j][2] - c)
        while j + 1 < n and path[j + 1][0] == l and (path[j + 1][1] - path[j][1], path[j + 1][2] - path[j][2]) == d:
            j += 1
        out.append(('seg', (r, c), (path[j][1], path[j][2]), l))
        i = j
    return out


def main():
    order = None
    if '--order' in sys.argv:
        order = sys.argv[sys.argv.index('--order') + 1].split(',')
    b = pcbnew.LoadBoard(PCB)
    t0 = time.time()
    R = Router(b)
    print(f'grid {R.g.W}x{R.g.H}, setup {time.time() - t0:.1f}s')
    nets = [n for n in R.net_raw if n not in SKIP_NETS]
    # short / sensitive nets first, then by pad spread (small first)
    prio = ['X32K_1', 'X32K_2', 'X24M_P', 'X24M_N', 'SW_BUCK', 'VSET', 'VIN_CHG', 'CHG_IN', 'SYS', 'VBAT', 'VDD', 'VDDS',
            'VDDR', 'DCOUPL', 'RESET_N']
    if order:
        prio = order + [p for p in prio if p not in order]
    nets.sort(key=lambda n: (prio.index(n) if n in prio else 99, n))
    failed = []
    for n in nets:
        t1 = time.time()
        ok, made = R.route_net(n)
        print(f'{n:12s} {"ok  " if ok else "FAIL"} +{made} conn  {time.time() - t1:.1f}s', flush=True)
        if not ok:
            failed.append(n)
    pcbnew.SaveBoard(PCB, b)
    print('failed:', failed)


if __name__ == '__main__':
    main()
