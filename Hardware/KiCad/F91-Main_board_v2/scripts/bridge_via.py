"""Find a GND via spot that joins two GND clusters: try candidate points in a box, keep those with
DRC-clean clearance to all non-GND copper, add the via, refill, keep it if the number of GND
clusters drops. Usage: python3 bridge_via.py board x1 y1 x2 y2"""
import sys, math
import pcbnew
MM = pcbnew.FromMM
path = sys.argv[1]
x1, y1, x2, y2 = map(float, sys.argv[2:6])
b = pcbnew.LoadBoard(path)


def n_unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)


def margin(x, y):
    p = pcbnew.VECTOR2I(MM(x), MM(y))
    m = 1e9
    for t in b.GetTracks():
        if t.GetNetname() == 'GND':
            continue
        need = 0.225 + (0.3 if t.GetNetname() == 'ANT' else 0.1)
        for L in (pcbnew.F_Cu, pcbnew.B_Cu):
            if t.IsOnLayer(L):
                d = math.sqrt(t.GetEffectiveShape(L).SquaredDistance(p)) / 1e6
                m = min(m, d - need)
    for f in b.GetFootprints():
        for pd in f.Pads():
            if pd.GetNetname() == 'GND' and pd.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                continue
            for L in (pcbnew.F_Cu, pcbnew.B_Cu):
                if pd.IsOnLayer(L) or pd.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    d = math.sqrt(pd.GetEffectiveShape(L).SquaredDistance(p)) / 1e6
                    need = 0.225 + (0.2 if pd.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else 0.1)
                    m = min(m, d - need)
                    break
    for t in b.GetTracks():   # other GND vias: keep holes apart
        if t.Type() == pcbnew.PCB_VIA_T:
            d = math.hypot(t.GetPosition().x / 1e6 - x, t.GetPosition().y / 1e6 - y)
            m = min(m, d - 0.45 - 0.2 + 0.225)
    return m


base = n_unconnected(b)
cands = []
x = x1
while x <= x2:
    y = y1
    while y <= y2:
        mg = margin(x, y)
        if mg >= 0.01:
            cands.append((mg, x, y))
        y += 0.05
    x += 0.05
cands.sort(reverse=True)
print('baseline unconnected', base, 'candidates', len(cands))
for mg, x, y in cands[:60]:
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.25))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(b.FindNet('GND'))
    b.Add(v)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    n = n_unconnected(b)
    if n < base:
        print(f'bridge via at ({x:.2f},{y:.2f}) margin {mg*1000:.0f} um: unconnected {base} -> {n}')
        pcbnew.SaveBoard(path, b)
        sys.exit(0)
    b.Remove(v)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
print('no bridging spot found')
