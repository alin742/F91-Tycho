"""Export STEP models of the v2 main board and the charging PCB (fixes LCSC model paths first)."""
import math, os, subprocess, sys
import pcbnew
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB3D = os.path.join(ROOT, 'lib', 'F91_LCSC.3dshapes')
OUT = os.path.join(ROOT, '3d')
os.makedirs(OUT, exist_ok=True)


# KiCad's own 3D library is not installed here: use LCSC models for the standard footprints
STD = {'C_0402_1005Metric': 'C0402_L1.0-W0.5-H0.5', 'C_0603_1608Metric': 'C0603_L1.6-W0.8-H0.8',
       'R_0402_1005Metric': 'R0402_L1.0-W0.5-H0.4', 'L_0402_1005Metric': 'C0402_L1.0-W0.5-H0.5',
       'Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm_ThermalVias': 'VQFN-48_L7.0-W7.0-H0.9-P0.50'}


def clip_castellations(b):
    """3D only: KiCad draws the castellated button contacts as full rings and full barrels. Replace
    each by an unplated hole (the half-hole notch) plus copper clipped to the board outline on both
    sides, so the model shows the half-moons the fab actually leaves."""
    outline = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline, False)
    n = 0
    for fp in b.GetFootprints():
        if 'CASTELLATION' not in str(fp.GetFPID().GetLibItemName()):
            continue
        for p in fp.Pads():
            c, r_out, r_in = p.GetPosition(), p.GetSize(pcbnew.F_Cu).x // 2, p.GetDrillSize().x // 2
            ring = pcbnew.SHAPE_POLY_SET()
            p.TransformShapeToPolygon(ring, pcbnew.F_Cu, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
            hole = pcbnew.SHAPE_POLY_SET()
            hole.NewOutline()
            for k in range(72):
                a = 2 * math.pi * k / 72
                hole.Append(int(c.x + r_in * math.cos(a)), int(c.y + r_in * math.sin(a)))
            ring.BooleanSubtract(hole)
            ring.BooleanIntersection(outline)
            net = p.GetNet()
            p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            p.SetSize(pcbnew.F_Cu, p.GetDrillSize())
            p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                z = pcbnew.ZONE(b)
                z.SetLayer(layer)
                z.SetNet(net)
                z.Outline().Append(ring)
                z.SetFilledPolysList(layer, ring)
                z.SetIsFilled(True)
                b.Add(z)
            n += 1
    return n


def fix_models(path):
    b = pcbnew.LoadBoard(path)
    n = 0
    for fp in b.GetFootprints():
        name = str(fp.GetFPID().GetLibItemName())
        if name in STD:
            fp.Models().clear()
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = os.path.join(LIB3D, STD[name] + '.step')
            if name.startswith('Texas_RGZ'):
                m.m_Rotation = pcbnew.VECTOR3D(0, 0, 0)
            fp.Models().append(m)
            n += 1
            continue
        for m in fp.Models():
            f = m.m_Filename
            if 'F91_LCSC.3dshapes' in f:
                base = os.path.splitext(os.path.basename(f))[0]
                m.m_Filename = os.path.join(LIB3D, base + '.step')
                n += 1
    n += clip_castellations(b)
    tmp = os.path.join(OUT, os.path.basename(path))
    pcbnew.SaveBoard(tmp, b)
    return tmp, n


for src, name in [(os.path.join(ROOT, 'F91-Main_board_v2.kicad_pcb'), 'F91-Main_board_v2.step'),
                  (os.path.join(os.path.dirname(ROOT), 'F91-Charge_pad', 'F91-Charge_pad.kicad_pcb'), 'F91-Charge_pad.step')]:
    tmp, n = fix_models(src)
    r = subprocess.run(['kicad-cli', 'pcb', 'export', 'step', '--subst-models', '--force', '--no-dnp',
                        '--include-tracks', '--include-pads', '--include-zones', '--include-soldermask',
                        '-o', os.path.join(OUT, name), tmp], capture_output=True, text=True)
    os.remove(tmp)
    for ext in (".kicad_pro", ".kicad_prl"):
        if os.path.exists(tmp[:-10] + ext):
            os.remove(tmp[:-10] + ext)
    print(name, 'models fixed:', n, 'ok' if r.returncode == 0 else r.stdout[-400:] + r.stderr[-400:])
