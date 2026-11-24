"""Build F91-Main_board_v2.kicad_pcb from design.py, reusing v1 geometry.

- outline, holes, antenna, castellations, battery pads, test-pad positions: copied from v1
- kept parts: placed at their v1 spot, rotation chosen so pads land on the v1 pads of the same net
- RF chain tracks/vias: copied from v1 (nets renamed)
- new parts: placed from the PLACE table below (hand-chosen spots in v1's free areas)
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
import design

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V1 = os.path.join(ROOT, 'work', 'v1_import.kicad_pcb')
OUT = os.path.join(ROOT, 'F91-Main_board_v2.kicad_pcb')
SYSFP = '/usr/share/kicad/footprints'
FPLIBS = {'F91_LCSC': os.path.join(ROOT, 'lib', 'F91_LCSC.pretty'),
          'F91_custom': os.path.join(ROOT, 'lib', 'F91_custom.pretty')}

MM = pcbnew.FromMM
mm = lambda v: v / 1e6
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))

# v1 net -> v2 net (only where the meaning is unchanged)
V1NET = {'Net 0': 'GND', 'Net 2': 'VDDS', 'Net 4': 'VDDR', 'Net 7': 'RESET_N', 'Net 8': 'X32K_1',
         'Net 9': 'X32K_2', 'Net 10': 'DCOUPL', 'Net 11': 'X24M_P', 'Net 12': 'X24M_N',
         'Net 13': 'RF_N', 'Net 14': 'RF_P', 'Net 15': 'RF_15', 'Net 16': 'RF_16', 'Net 17': 'RF_17',
         'Net 18': 'RF_18', 'Net 19': 'RF_19', 'Net 20': 'ANT', 'Net 5': 'TCKC', 'Net 6': 'TMSC',
         'Net 21': 'UART_RX', 'Net 22': 'UART_TX', 'Net 30': 'SDA', 'Net 31': 'SCL', 'Net 26': 'BUZZ',
         'Net 35': 'BTN1_PAD', 'Net 36': 'BTN2_PAD', 'Net 37': 'BTN3_PAD'}
RF_NETS = ['RF_N', 'RF_P', 'RF_15', 'RF_16', 'RF_17', 'RF_18', 'RF_19', 'ANT']

# New parts: (x, y, rot, side). Chosen in v1 free areas (top unless 'B'); see notes in TASKS/plan.
PLACE = {
    # charger: pocket left of the display connector. rot 90: SCL/SDA/INT balls on the right column
    # (towards J1 and the MCU), IN/SYS/BAT on the left column next to their caps, GND/TS on top.
    'U2':  (0.45, 7.95, 90, 'F'),   # BQ25180
    'C30': (-0.70, 9.15, 270, 'F'), # VIN 1u: pad 1 (VIN) up next to A2, GND pad down towards open pour
    'C33': (-0.70, 6.95, 90, 'F'),  # BAT 1u (pad 1 down, next to C2 = BAT)
    'Y2':  (-3.30, 7.35, 90, 'F'),  # 24 MHz crystal, turned orthogonal (v1 had it at 135 deg)
    # buck: pocket right of the display connector. rot 180: SW (B2) exits down to L1, VIN (B1) up
    # to C32, VOS/GND (A2/A1) right to C34, VSET (C2) left to R11.
    'U3':  (7.02, 9.25, 180, 'F'),  # TPS62840
    'C32': (7.10, 7.92, 0, 'F'),    # SYS 10u (TPS62840 input; also the BQ25180 SYS cap)
    'C34': (8.20, 9.10, 90, 'F'),   # VDD 10u
    'L1':  (7.25, 10.48, 0, 'F'),   # 2.2u
    'R11': (5.98, 9.10, 90, 'F'),   # VSET 1.74k, between J1 and U3 (pad 1 next to C2 = VSET)
    'C17': (8.30, 7.30, 90, 'F'),   # 32 kHz load cap, moved from v1 to make room
    # FFC solder pads, bottom right strip (clear of the antenna feed at x = 12.8)
    'J2':  (13.95, 1.50, 0, 'B'),
}
FLIP = set()   # normal footprints that must be flipped to the bottom


_pj = os.path.join(ROOT, 'work', 'place.json')
if not os.path.exists(_pj):
    _pj = os.path.join(ROOT, 'placement', 'place.json')   # committed copy
if os.path.exists(_pj):
    import json
    for _k, _v in json.load(open(_pj)).items():
        PLACE[_k] = tuple(_v)


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = FPLIBS.get(lib, os.path.join(SYSFP, lib + '.pretty'))
    f = pcbnew.FootprintLoad(path, name)
    assert f, fpid
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    return f


def main():
    v1b = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.KICAD_SEXP, V1)
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(2)
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(MM(0.8))
    # JLCPCB 2-layer limits (capabilities page, 2026-11): 0.1/0.1 mm, via 0.3/0.5 (cheap tier), edge 0.2
    ds.m_TrackMinWidth = MM(0.1)
    ds.m_MinClearance = MM(0.1)
    ds.m_ViasMinSize = MM(0.45)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_ViasMinAnnularWidth = MM(0.1)
    ds.m_CopperEdgeClearance = MM(0.2)
    ds.m_HoleClearance = MM(0.2)
    ds.m_HoleToHoleMin = MM(0.2)
    ds.m_SolderMaskMinWidth = MM(0.1)
    ds.m_MinSilkTextHeight = MM(0.6)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(MM(0.1)); nc.SetTrackWidth(MM(0.15)); nc.SetViaDiameter(MM(0.6)); nc.SetViaDrill(MM(0.3))

    # nets
    nets = {}
    for n in design.nets():
        ni = pcbnew.NETINFO_ITEM(b, n)
        b.Add(ni)
        nets[n] = ni

    # outline
    edges = [d.Duplicate() for d in v1b.GetDrawings() if d.GetLayerName() == 'Edge.Cuts']
    # v1 outline has a 0.7 um segment: drop zero-length lines and snap neighbours together
    edges = [e for e in edges if not (e.GetShape() == pcbnew.SHAPE_T_SEGMENT and
                                      (e.GetStart() - e.GetEnd()).EuclideanNorm() < MM(0.01))]
    pts = []
    for e in edges:
        pts += [e.GetStart(), e.GetEnd()]
    def snap(p):
        for q in pts:
            if q != p and (q - p).EuclideanNorm() < MM(0.01):
                return q
        return p
    for e in edges:
        if e.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            e.SetStart(snap(e.GetStart())); e.SetEnd(snap(e.GetEnd()))
        b.Add(e)

    v1fp = {f.GetReference(): f for f in v1b.GetFootprints()}
    v1fp['MCU'] = [f for f in v1b.GetFootprints() if f.GetReference() == ''][0]

    def v1_netpads(f):
        out = {}
        for p in f.Pads():
            n = V1NET.get(p.GetNetname())
            if n and p.GetNumber() != '49':
                out.setdefault(n, []).append(p.GetPosition())
        return out

    for c in design.C:
        f = load_fp(c['fp'])
        f.SetReference(c['ref'])
        f.SetValue(c['value'])
        if c['lcsc']:
            f.SetField('LCSC', c['lcsc'])
        b.Add(f)
        for p in f.Pads():
            n = c['pins'].get(p.GetNumber())
            if n:
                p.SetNet(nets[n])
        if not c['bom']:
            f.SetAttributes(f.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        if 'DNP' in c['note']:
            f.SetDNP(True)

        v1 = c['v1']
        if c['ref'] in PLACE:
            x, y, r, side = PLACE[c['ref']]
            # J2's custom footprint already has B.Cu pads; library parts in FLIP get flipped
            if side == 'B' and c['ref'] in FLIP:
                f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            f.SetPosition(P(x, y))
            f.SetOrientationDegrees(r)
            continue
        if v1 is None:
            print('  (no placement yet, parked at origin):', c['ref'])
            f.SetPosition(P(0, -20))
            continue
        if isinstance(v1, tuple) and v1[0] == 'ABS':
            f.SetPosition(P(v1[1], v1[2]))
            continue
        if isinstance(v1, tuple) and v1[0] == 'MCU':
            src = v1fp['MCU']
            target = P(v1[1], v1[2])
        else:
            src = v1fp[v1]
            target = src.GetPosition()
        f.SetPosition(target)
        ref_pads = v1_netpads(src)
        # choose rotation so same-net pads coincide with v1
        best = None
        base = src.GetOrientationDegrees() % 90
        for rot in [base + k * 90 for k in range(4)]:
            f.SetOrientationDegrees(rot)
            err = 0
            for p in f.Pads():
                n = c['pins'].get(p.GetNumber())
                if n in ref_pads:
                    err += min((p.GetPosition() - q).EuclideanNorm() for q in ref_pads[n])
            if best is None or err < best[0]:
                best = (err, rot)
        f.SetOrientationDegrees(best[1])
        if c['ref'] in ('U1', 'Y1', 'Y2', 'J1') or c['ref'].startswith(('C', 'L', 'R')):
            print(f'{c["ref"]:4s} rot {best[1]:5.1f}  pad mismatch {mm(best[0]):.3f} mm')

    # antenna footprint must not flip: its pads are already defined on B.Cu at the v1 spot
    # RF tracks + vias from v1
    copied = 0
    for t in v1b.GetTracks():
        n = V1NET.get(t.GetNetname())
        if n in RF_NETS:
            tt = t.Duplicate()
            b.Add(tt)
            tt.SetNet(nets[n])
            copied += 1
    print('copied RF track items:', copied)

    # Fixed escape for the 32 kHz crystal pair: U1 pins 3/4 sit left of the I2C/INT bundle
    # (pins 8-10) but the crystal is on the right, so the pair has to cross the bundle. Two
    # staggered vias (clear of the v1 RF vias) take it to the bottom layer right away.
    def trk(pts, net):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(MM(0.15))
            t.SetLayer(pcbnew.F_Cu); t.SetNet(nets[net]); b.Add(t)

    def via(x, y, net):
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(P(x, y)); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets[net]); b.Add(v)
    u1 = b.FindFootprintByReference('U1')
    p3 = [q for q in u1.Pads() if q.GetNumber() == '3'][0].GetPosition()
    p4 = [q for q in u1.Pads() if q.GetNumber() == '4'][0].GetPosition()
    x3, y3, x4, y4 = mm(p3.x), mm(p3.y), mm(p4.x), mm(p4.y)
    trk([(x3, y3), (x3, 5.75), (0.85, 5.81), (0.85, 6.80)], 'X32K_1'); via(0.85, 6.80, 'X32K_1')
    trk([(x4, y4), (x4, 6.09), (1.55, 6.35)], 'X32K_2'); via(1.55, 6.35, 'X32K_2')

    # J1 pin 1 (display GND) is linked to J1's GND mounting pad under the connector body before
    # routing; otherwise signals routed under the body can box pin 1 in.
    j1 = b.FindFootprintByReference('J1')
    jp1 = [q for q in j1.Pads() if q.GetNumber() == '1'][0].GetPosition()
    jp7 = [q for q in j1.Pads() if q.GetNumber() == '7'][0].GetPosition()
    ax, ay, cx, cy = mm(jp1.x), mm(jp1.y), mm(jp7.x), mm(jp7.y)
    jp8 = [q for q in j1.Pads() if q.GetNumber() == '8'][0].GetPosition()
    trk([(ax, ay), (ax, ay + 0.30), (cx + 0.45, ay + 0.30), (cx, cy), (mm(jp8.x), mm(jp8.y))], 'GND')

    # Fixed SYS escape from the charger: B2 (SYS) is a middle ball that can only leave to the
    # left, between the BAT and VIN caps, so give it its track + via before anything else.
    u2 = b.FindFootprintByReference('U2')
    pb2 = [q for q in u2.Pads() if q.GetNumber() == 'B2'][0].GetPosition()
    bx, by = mm(pb2.x), mm(pb2.y)
    trk([(bx, by), (-1.35, by)], 'SYS')
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(-1.35, by)); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.25))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets['SYS']); b.Add(v)

    pcbnew.SaveBoard(OUT, b)
    print('saved', OUT)


if __name__ == '__main__':
    main()
