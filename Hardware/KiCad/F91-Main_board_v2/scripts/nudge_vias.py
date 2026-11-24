"""Fix tiny DRC clearance misses (grid rounding) by moving a via or a track joint a few tens of
um away from the other item, dragging the track ends attached to it.
Usage: python3 nudge_vias.py board.kicad_pcb drc.rpt"""
import re, sys, math
import pcbnew

MM = pcbnew.FromMM
board, rpt = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(board)
blocks = open(rpt).read().split('\n[')


def move_point(old, new):
    """move every via at `old` and every track end at `old` to `new`"""
    n = 0
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            if (t.GetPosition() - old).EuclideanNorm() < MM(0.002):
                t.SetPosition(new); n += 1
        else:
            if (t.GetStart() - old).EuclideanNorm() < MM(0.002):
                t.SetStart(new); n += 1
            if (t.GetEnd() - old).EuclideanNorm() < MM(0.002):
                t.SetEnd(new); n += 1
    return n


def on_pad(pt):
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.HitTest(pt, 0):
                return True
    return False


seen = set()
for blk in blocks:
    if not (blk.startswith('clearance') or blk.startswith('hole_clearance')):
        continue
    m = re.search(r'actual ([0-9.]+) mm', blk)
    need_mm = re.search(r'clearance ([0-9.]+) mm;', blk)
    if not m:
        continue
    need = (float(need_mm.group(1)) if need_mm else 0.1) - float(m.group(1)) + 0.012
    items = re.findall(r'@\(([-0-9.]+) mm, ([-0-9.]+) mm\): (Via|Track|Pad|PTH pad|NPTH pad)[^\n]*', blk)
    if len(items) != 2:
        continue
    (x1, y1, k1), (x2, y2, k2) = [(float(a), float(c), k) for a, c, k in items]
    key = (round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3))
    if key in seen:
        continue
    seen.add(key)
    # pick the movable item: a via first, else a track
    if k1 == 'Via' or (k1 == 'Track' and k2 not in ('Via',)):
        mx, my, ox, oy, kind = x1, y1, x2, y2, k1
    else:
        mx, my, ox, oy, kind = x2, y2, x1, y1, k2
    d = math.hypot(mx - ox, my - oy) or 1.0
    dx, dy = (mx - ox) / d * need, (my - oy) / d * need
    if kind == 'Via':
        old = pcbnew.VECTOR2I(MM(mx), MM(my))
        n = move_point(old, pcbnew.VECTOR2I(MM(mx + dx), MM(my + dy)))
        print(f'via ({mx:.3f},{my:.3f}) moved {dx*1000:.0f},{dy*1000:.0f} um ({n} items)')
    elif kind == 'Track':
        # the DRC marker is the track's start; move both of its free ends (not sitting on a pad)
        start = pcbnew.VECTOR2I(MM(mx), MM(my))
        tr = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T and
              (t.GetStart() - start).EuclideanNorm() < MM(0.002)]
        if not tr:
            continue
        t = tr[0]
        for end in (t.GetStart(), t.GetEnd()):
            if not on_pad(end):
                move_point(end, pcbnew.VECTOR2I(int(end.x + MM(dx)), int(end.y + MM(dy))))
        print(f'track at ({mx:.3f},{my:.3f}) shifted {dx*1000:.0f},{dy*1000:.0f} um')
pcbnew.SaveBoard(board, b)
