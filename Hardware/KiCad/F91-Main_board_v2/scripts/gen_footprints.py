"""Generate F91_custom.pretty footprints, mostly from v1 board geometry."""
import os, sys, uuid
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'lib', 'F91_custom.pretty')
V1 = os.path.join(ROOT, 'work', 'v1_import.kicad_pcb')
os.makedirs(OUT, exist_ok=True)


def u():
    return str(uuid.uuid4())


def fp_text(name, ref_y=-1.5, val_y=1.5, layer='F'):
    return (f'\t(property "Reference" "REF**" (at 0 {ref_y} 0) (layer "{layer}.SilkS") (uuid "{u()}")\n'
            f'\t\t(effects (font (size 0.6 0.6) (thickness 0.1))))\n'
            f'\t(property "Value" "{name}" (at 0 {val_y} 0) (layer "{layer}.Fab") (uuid "{u()}")\n'
            f'\t\t(effects (font (size 0.6 0.6) (thickness 0.1))))\n')


def write(name, body, attr='smd', descr='', exclude=True):
    flags = ' exclude_from_pos_files exclude_from_bom' if exclude else ''
    s = (f'(footprint "{name}"\n\t(version 20260206)\n\t(generator "f91_gen")\n\t(layer "F.Cu")\n'
         f'\t(descr "{descr}")\n' + fp_text(name) + f'\t(attr {attr}{flags})\n' + body + ')\n')
    open(os.path.join(OUT, name + '.kicad_mod'), 'w').write(s)
    print('wrote', name)


def smd(num, shape, x, y, w, h, side='F', paste=False, rr=None):
    layers = f'"{side}.Cu" "{side}.Mask"' + (f' "{side}.Paste"' if paste else '')
    extra = f' (roundrect_rratio {rr})' if rr else ''
    return f'\t(pad "{num}" smd {shape} (at {x:.4f} {y:.4f}) (size {w:.4f} {h:.4f}) (layers {layers}){extra} (uuid "{u()}"))\n'


def tht(num, x, y, size, drill):
    return (f'\t(pad "{num}" thru_hole circle (at {x:.4f} {y:.4f}) (size {size} {size}) (drill {drill}) '
            f'(layers "*.Cu" "*.Mask") (uuid "{u()}"))\n')


def npth(x, y, drill):
    return (f'\t(pad "" np_thru_hole circle (at {x:.4f} {y:.4f}) (size {drill} {drill}) (drill {drill}) '
            f'(layers "*.Cu" "*.Mask") (uuid "{u()}"))\n')


def crt(layer, x1, y1, x2, y2):
    return (f'\t(fp_rect (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) (stroke (width 0.05) (type solid)) '
            f'(fill no) (layer "{layer}") (uuid "{u()}"))\n')


b = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.KICAD_SEXP, V1)
mm = lambda v: v / 1e6


def v1pads(ref):
    f = b.FindFootprintByReference(ref)
    return f, list(f.Pads())


# ---- antenna: v1 U2 pads, moved to B.Cu (photos: the meander is on the bottom), mask open, no paste
f, pads = v1pads('U2')
ox, oy = mm(f.GetPosition().x), mm(f.GetPosition().y)
body = ''
xs, ys = [], []
for p in pads:
    x, y = mm(p.GetPosition().x) - ox, mm(p.GetPosition().y) - oy
    w, h = mm(p.GetSize().x), mm(p.GetSize().y)
    ang = p.GetOrientationDegrees()
    if abs(ang % 180 - 90) < 1:
        w, h = h, w
    body += smd('1', 'rect', x, y, w, h, side='B')
    xs += [x - w / 2, x + w / 2]; ys += [y - h / 2, y + h / 2]
body += crt('B.CrtYd', min(xs) - .25, min(ys) - .25, max(xs) + .25, max(ys) + .25)
write('ANT_TI_MEANDER_B', body, descr='v1 2.4 GHz meander antenna, bottom copper, exposed (from F91-Main_board_NF)')

# ---- battery: clamp-leg pads (+) and cell (-) pads, plus the two GND vias. Footprint origin = board origin.
body = ''
for r, num in [('Pad1', '1'), ('Pad2', '1'), ('Pad3', '2'), ('Pad4', '2')]:
    _, (p,) = v1pads(r)
    body += smd(num, 'rect', mm(p.GetPosition().x), mm(p.GetPosition().y), mm(p.GetSize().x), mm(p.GetSize().y), side='B')
# v1 had two 0.9 mm GND holes here, inside the CC2640R2 exposed pad: they would wick solder in
# reflow. v2 uses the TI thermal-via land pattern on U1 instead, so they are left out.
write('BAT_LIR2016_CLAMP', body, descr='LIR2016 under the original F-91W clamp: + = clamp legs, - = cell face')

# ---- button castellation (v1 P5-P7: 4.0 mm ring, 2.8 mm drill, cut by the board edge)
write('BTN_CASTELLATION_D4', tht('1', 0, 0, 4.0, 2.8) + crt('F.CrtYd', -2.1, -2.1, 2.1, 2.1), attr='through_hole',
      descr='half-hole button contact touched by the clamp arm')
write('BTN_PAD_0.7x0.6', smd('1', 'rect', 0, 0, 0.7, 0.6) + crt('F.CrtYd', -0.5, -0.45, 0.5, 0.45),
      descr='button contact pad (v1 SingleConnect)')
# ---- test pads
write('TP_ROUND_D0.7', smd('1', 'circle', 0, 0, 0.7, 0.7) + crt('F.CrtYd', -0.5, -0.5, 0.5, 0.5),
      descr='pogo test pad, v1 jig position')
write('PAD_ROUND_D1.5_B', smd('1', 'circle', 0, 0, 1.5, 1.5, side='B') + crt('B.CrtYd', -0.9, -0.9, 0.9, 0.9),
      descr='bottom spring contact pad (piezo)')
# ---- holes
for d in ['0.8', '1.1']:
    write(f'NPTH_D{d}', npth(0, 0, float(d)) + crt('F.CrtYd', -0.95, -0.95, 0.95, 0.95), attr='through_hole',
          descr='holder peg hole')
# ---- FFC solder pads, 4 x 1.0 mm pitch, bottom
body = ''.join(smd(str(i + 1), 'roundrect', 0, (i - 1.5) * 1.0, 1.3, 0.6, side='B', rr=0.25) for i in range(4))
body += crt('B.CrtYd', -0.85, -2.15, 0.85, 2.15)
write('FFC4_P1.0_SOLDER_B', body, descr='hand-solder pads for a 4-way 1.0 mm FFC to the charging PCB')
