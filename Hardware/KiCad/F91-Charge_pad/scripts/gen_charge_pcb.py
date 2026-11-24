"""F91 Kepler charging PCB: glued inside the steel case back, behind one 4.3 mm hole.

Outer face (B.Cu): two flush ENIG contact pads at the 2.50 mm pitch of the bought magnetic pogo
plug (Samzo PR5L5015-2P-C-H), plus two 3.1 mm holes 8.0 mm apart for 3 x 1 mm magnets.
Inner face (F.Cu, assembled by JLC with the panel): reverse-polarity Schottky, ESD diode,
1 M pull-down and four solder pads for a 1.0 mm-pitch FFC to the main board.
No vias inside the 4.3 mm window (r < 2.15 mm): the window is the wet zone.
"""
import os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAIN = os.path.join(os.path.dirname(ROOT), 'F91-Main_board_v2')
OUT = os.path.join(ROOT, 'F91-Charge_pad.kicad_pcb')
MM = lambda v: pcbnew.FromMM(float(v))
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
LEN, WID = 13.0, 5.0            # rounded oblong
MAG_X, MAG_D = 4.0, 3.1
PAD_X, PAD_D = 1.25, 1.6        # contact pads at +-1.25 (2.50 mm pitch)


def fp(lib, name):
    path = os.path.join(MAIN, 'lib', lib + '.pretty') if lib.startswith('F91') else f'/usr/share/kicad/footprints/{lib}.pretty'
    f = pcbnew.FootprintLoad(path, name)
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    return f


def main():
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(2)
    b.GetDesignSettings().SetBoardThickness(MM(0.8))
    nets = {}
    for n in ['CHG_IN', 'VIN_CHG', 'GND']:
        ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni

    # outline: two semicircles + two lines
    r = WID / 2
    cx = LEN / 2 - r
    for sx in (-1, 1):
        a = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
        a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(MM(0.1))
        a.SetArcGeometry(P(sx * cx, -r), P(sx * (cx + r), 0), P(sx * cx, r))
        b.Add(a)
    for sy in (-1, 1):
        s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        s.SetStart(P(-cx, sy * r)); s.SetEnd(P(cx, sy * r))
        b.Add(s)

    def add(f, ref, value, x, y, rot, pinnets, lcsc=''):
        f.SetReference(ref); f.SetValue(value)
        if lcsc:
            f.SetField('LCSC', lcsc)
        b.Add(f)
        f.SetPosition(P(x, y)); f.SetOrientationDegrees(rot)
        for p in f.Pads():
            n = pinnets.get(p.GetNumber())
            if n:
                p.SetNet(nets[n])
        return f

    # outer contact pads + magnet holes (bottom), not assembled
    cp = pcbnew.FOOTPRINT(b); cp.SetReference('J1'); cp.SetValue('pogo contacts 2.5 mm')
    cp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    b.Add(cp)
    for num, x, net in (('1', -PAD_X, 'CHG_IN'), ('2', PAD_X, 'GND')):
        pd = pcbnew.PAD(cp)
        pd.SetNumber(num); pd.SetShape(pcbnew.PAD_SHAPE_CIRCLE); pd.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pd.SetSize(pcbnew.VECTOR2I(MM(PAD_D), MM(PAD_D)))
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.B_Cu); ls.AddLayer(pcbnew.B_Mask)
        pd.SetLayerSet(ls)
        pd.SetPosition(P(x, 0)); pd.SetNet(nets[net])
        cp.Add(pd)
    for x in (-MAG_X, MAG_X):
        h = pcbnew.FOOTPRINT(b); h.SetReference('MAG' + ('L' if x < 0 else 'R')); h.SetValue('3x1 magnet')
        h.SetAttributes(pcbnew.FP_THROUGH_HOLE | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        b.Add(h)
        pd = pcbnew.PAD(h); pd.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pd.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pd.SetSize(pcbnew.VECTOR2I(MM(MAG_D), MM(MAG_D))); pd.SetDrillSize(pcbnew.VECTOR2I(MM(MAG_D), MM(MAG_D)))
        ls = pcbnew.LSET.AllCuMask(); ls.AddLayer(pcbnew.F_Mask); ls.AddLayer(pcbnew.B_Mask)
        pd.SetLayerSet(ls); pd.SetPosition(P(x, 0))
        h.Add(pd)

    # inner face parts (top)
    add(fp('F91_custom', 'FFC4_P1.0_SOLDER_B'), 'J2', 'FFC to main board', 0, -1.55, 90,
        {'1': 'VIN_CHG', '2': 'VIN_CHG', '3': 'GND', '4': 'GND'})
    j2 = b.FindFootprintByReference('J2')
    j2.Flip(j2.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)   # its pads are drawn on B.Cu: move to top
    j2.SetAttributes(j2.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    add(fp('F91_LCSC', 'SOD-882_L1.0-W0.6-RD'), 'D1', 'PMEG3002AEL', -1.20, 1.05, 0,
        {'1': 'VIN_CHG', '2': 'CHG_IN'}, 'C478015')
    add(fp('F91_LCSC', 'X1SON-2_L1.0-W0.6-P0.65-BI-1'), 'D2', 'TPD1E10B06', 1.25, 1.05, 0,
        {'1': 'CHG_IN', '2': 'GND'}, 'C48260')
    add(fp('Resistor_SMD', 'R_0402_1005Metric'), 'R1', '1M', 0.05, 0.25, 0,
        {'1': 'CHG_IN', '2': 'GND'}, 'C26083')

    # vias from the outer pads to the inner face, outside the 4.5 mm window (r >= 2.3)
    def via(x, y, net):
        v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(nets[net]); b.Add(v)

    def trk(pts, layer, net, w=0.25):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2))
            t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(nets[net]); b.Add(t)
    # window in the steel is 4.3 mm (r 2.15): vias at r = 2.36 stay under the rubber ring, tented
    via(-PAD_X, 2.0, 'CHG_IN')
    via(PAD_X, 2.0, 'GND')
    trk([(-PAD_X, 0), (-PAD_X, 2.0)], pcbnew.B_Cu, 'CHG_IN')
    trk([(PAD_X, 0), (PAD_X, 2.0)], pcbnew.B_Cu, 'GND')
    pcbnew.SaveBoard(OUT, b)
    print('saved', OUT)


if __name__ == '__main__':
    main()
