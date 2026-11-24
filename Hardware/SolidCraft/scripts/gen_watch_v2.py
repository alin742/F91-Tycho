"""Build steps for the solid Casio F-91W + Kepler v2 electronics in SolidCraft.
Writes two batch files (stage1 case/strap, stage2 electronics) into SolidCraft's recovery folder.
Frame: watch centre at X=Y=0, +Y = 12 o'clock (CASIO print side), Z up, display face up.
Z stack: case back outer -0.65 / inner -0.21 (dip floor -1.79, charging PCB -1.29..-0.49 under the cell), clamp gap, cell 0.02-1.62, board 1.64-2.35,
holder 0.04-4.44, OLED in pocket 3.64-4.89, cavity top 5.47, crystal 5.94-6.72."""
import json, math, os
R = os.path.expanduser('~/.local/share/solidcraft/recovery/f91_v2')


def chamfer_rect(w, h, c, cx=0.0, cy=0.0):
    x, y = w / 2, h / 2
    pts = [(-x + c, y), (x - c, y), (x, y - c), (x, -y + c), (x - c, -y), (-x + c, -y), (-x, -y + c), (-x, y - c)]
    return [[round(cx + a, 4), round(cy + b, 4)] for a, b in pts]


def poly(name, plane, pts, distance, body, op='new', targets=None, offset=None):
    s = {'plane': plane, 'name': name + ' sketch'}
    if offset is not None:
        s['offset'] = str(offset)
    ex = {'distance': distance, 'name': name, 'operation': op}
    if op == 'new':
        ex['body_name'] = body
    if targets:
        ex['targets'] = targets
    return [{'command': 'sketch.create', 'params': s},
            {'command': 'sketch.line', 'params': {'points': pts, 'closed': True, 'infer': False}},
            {'command': 'sketch.finish', 'params': {}},
            {'command': 'solid.extrude', 'params': ex}]


def box(name, c, l, w, h, op='new', body=None, targets=None):
    p = {'center': list(c), 'length': l, 'width': w, 'height': h, 'operation': op, 'name': name}
    if body:
        p['body_name'] = body
    if targets:
        p['targets'] = targets
    return [{'command': 'solid.box', 'params': p}]


def cyl(name, base, d, h, op='new', body=None, targets=None, axis=None):
    p = {'base': list(base), 'diameter': d, 'height': h, 'operation': op, 'name': name}
    if body:
        p['body_name'] = body
    if targets:
        p['targets'] = targets
    if axis:
        p['axis'] = axis
    return [{'command': 'solid.cylinder', 'params': p}]


CASE = 'F-91W case (resin)'
CAV_D = 28.2        # cavity Ø: caliper read 27.61 with the main jaws inside (reads low, >= 0.6 mm), so +0.6
NOTCH = 25.9        # notch tips at 12/6: read 25.11 (low); the 25.70 mm module passes them, so 25.9
CAV_TOP = 5.47      # -0.21 + 5.68 measured depth
CRYS_Z = 5.45      # glass 5.47-6.27 (gen_body.py: 8.5 mm overall incl. the dip)
TOP = 6.27
s1 = []
# ---- case body: chamfered main body + lugs
outline = [(-12, 19.1), (12, 19.1), (12, 16), (13.6, 16), (17.6, 12), (17.6, -12), (13.6, -16), (12, -16),
           (12, -19.1), (-12, -19.1), (-12, -16), (-13.6, -16), (-17.6, -12), (-17.6, 12), (-13.6, 16), (-12, 16)]
s1 += poly('Case body', 'XY', [list(p) for p in outline], TOP + 0.21, CASE, offset=-0.21)
s1 += box('Lug slot top', (0, 17.8, 3.6), 18.2, 3.0, 8.4, 'cut', targets=[CASE])
s1 += box('Lug slot bottom', (0, -17.8, 3.6), 18.2, 3.0, 8.4, 'cut', targets=[CASE])
# measured 2026-11-24: round cavity, depth 5.68 from the case-back seat (z -0.21) to the window lip
s1 += cyl('Module cavity', (0, 0, -0.3), CAV_D, CAV_TOP + 0.3, 'cut', targets=[CASE])
for sgn, nm in ((1, '12'), (-1, '6')):
    s1 += box(f'Cavity notch {nm}', (0, sgn * (NOTCH / 2 + (CAV_D / 2 + 0.3 - NOTCH / 2) / 2), (CAV_TOP - 0.21) / 2), 3.0,
              CAV_D / 2 + 0.3 - NOTCH / 2, CAV_TOP + 0.21, 'join', targets=[CASE])
s1 += box('Display window', (0, 0, CAV_TOP + 0.5), 23.0, 14.0, 1.2, 'cut', targets=[CASE])
s1 += poly('Crystal recess', 'XY', chamfer_rect(28.8, 25.6, 2.6), 1.0, None, 'cut', [CASE], offset=CRYS_Z)
for i, (x, y) in enumerate([(11.1, 12.7), (-11.1, 12.7), (-11.1, -12.7), (11.1, -12.7)]):
    s1 += cyl(f'Screw boss {i+1}', (x, y, -0.21), 3.2, 3.2, 'join', targets=[CASE])
    s1 += cyl(f'Screw hole {i+1}', (x, y, -0.3), 1.2, 2.8, 'cut', targets=[CASE])
# ---- case back (steel), Ø4.3 charging hole over the charging PCB pads
BACK = 'Case back (steel, drilled)'
PINS = [(9.75, 6.17), (8.14, 8.09)]   # charge contact pins (+, GND): Ø1.2 brass in plated holes, 1.85 mm below the board (flush with the back's inner face)
# steel 0.44 mm, round dip Ø23.35 (inside) pressed 1.58 mm outward (2.02 total), measured 2026-11-24
# octagon measured 2026-11-24: 12/6 edges (strap side) 21.0, 3/9 edges (button side) 13.0, slanted corners 9.0;
# screws 18.7 across x 25.4 along the strap (measured); plate edge 1.4 mm beyond the screws (as on the GrabCAD part) -> 30.6 x 28.2
BW, BH, BCX, BCY = 15.32, 14.10, 4.82, 7.60
BACK_PTS = [[-BW + BCX, BH], [BW - BCX, BH], [BW, BH - BCY], [BW, -BH + BCY], [BW - BCX, -BH], [-BW + BCX, -BH], [-BW, -BH + BCY], [-BW, BH - BCY]]
SCREWS = [(9.35, 12.7), (-9.35, 12.7), (-9.35, -12.7), (9.35, -12.7)]   # 18.7 x 25.4 mm (measured)
s1 += poly('Case back', 'XY', BACK_PTS, 0.44, BACK, offset=-0.65)
# flat back (no dip, 2026-11-24): two Ø1.8 holes under the charge pins
for i, (x, y) in enumerate(PINS):
    s1 += cyl(f'Charge pin hole {i+1}', (x, y, -0.8), 1.8, 0.8, 'cut', targets=[BACK])
for i, (x, y) in enumerate(SCREWS):
    s1 += cyl(f'Screw hole plate {i+1}', (x, y, -0.8), 1.25, 0.8, 'cut', targets=[BACK])
    s1 += cyl(f'Case back screw {i+1}', (x, y, -0.90), 2.2, 0.25, body=f'Case back screw {i+1}')
    s1 += cyl(f'Screw shank {i+1}', (x, y, -0.65), 1.2, 3.0, 'join', targets=[f'Case back screw {i+1}'])
# ---- crystal with the printed face (decal from the GrabCAD print geometry)
s1 += poly('Crystal', 'XY', chamfer_rect(28.6, 25.4, 2.5), 0.8, 'Crystal', offset=CRYS_Z + 0.02)
# ---- buttons
s1 += cyl('Button right', (17.1, -4.77, 3.7), 2.0, 1.8, body='Button right (mode)', axis='X')
s1 += cyl('Button left top', (-18.9, 4.77, 3.7), 2.0, 1.8, body='Button left top (light)', axis='X')
s1 += cyl('Button left bottom', (-18.9, -4.77, 3.7), 2.0, 1.8, body='Button left bottom (alarm)', axis='X')
# ---- spring bars and straps (YZ sketch: x = world Y, y = world Z)
for sgn, nm in ((1, 'top'), (-1, 'bottom')):
    s1 += cyl(f'Spring bar {nm}', (-10.5, sgn * 17.8, 2.4), 0.9, 21.0, body=f'Spring bar {nm}', axis='X')
    zt, zb, y0, y1, Ro, t = 3.6, 1.2, 16.5, 22.0, 24.0, 2.4
    cz = zt - Ro
    tail = 25.0 if sgn > 0 else 40.0
    outer, inner = [], []
    for k in range(0, 12):
        f = math.radians(10 * k)
        outer.append((y1 + Ro * math.sin(f), cz + Ro * math.cos(f)))
        inner.append((y1 + (Ro - t) * math.sin(f), cz + (Ro - t) * math.cos(f)))
    f = math.radians(110)
    d = (math.cos(f), -math.sin(f))
    outer.append((outer[-1][0] + tail * d[0], outer[-1][1] + tail * d[1]))
    inner.append((inner[-1][0] + tail * d[0], inner[-1][1] + tail * d[1]))
    pts = [(y0, zt)] + outer + inner[::-1] + [(y0, zb)]
    pts = [[round(sgn * a, 4), round(b, 4)] for a, b in pts]
    s1 += poly(f'Strap {nm}', 'YZ', pts, 18.0, f'Strap {nm}', offset=-9)
# strap holes in the bottom strap tail, keeper on the top strap
s1 += [{'command': 'appearance.assign', 'params': {'bodies': [CASE, 'Strap top', 'Strap bottom'], 'color': '#1d1e20',
                                                    'pbr': {'metallic': 0, 'roughness': 0.55, 'dielectric_ior': 1.5}}},
       {'command': 'appearance.assign', 'params': {'bodies': [BACK, 'Button right (mode)', 'Button left top (light)',
                                                              'Button left bottom (alarm)', 'Spring bar top', 'Spring bar bottom',
                                                              'Case back screw 1', 'Case back screw 2', 'Case back screw 3',
                                                              'Case back screw 4'],
                                                    'color': '#c4c7cb', 'pbr': {'metallic': 1, 'roughness': 0.3, 'dielectric_ior': 1.5}}},
       {'command': 'appearance.assign', 'params': {'bodies': ['Crystal'], 'color': '#dfe8ee', 'opacity': 0.25}},
       {'command': 'canvas.decal', 'params': {'path': R + '/f91w_face_print.png', 'face': [0, 0, TOP], 'width': 28.6}}]

# ---- stage 2: v2 electronics
s2 = []
s2 += [{'command': 'file.insert_step', 'params': {'path': R + '/F91-Movement_holder.step', 'name': 'Movement holder',
                                                  'matrix': [-1, 0, 0, -0.04, 0, 1, 0, 0.0, 0, 0, -1, 4.44]}},
       {'command': 'file.insert_step', 'params': {'path': R + '/F91-Main_board_v2.step', 'name': 'Main board v2',
                                                  'matrix': [1, 0, 0, -3.05, 0, 1, 0, 2.77, 0, 0, 1, 1.64]}}]
s2 += cyl('LIR2016 cell', (-0.40, 1.47, 0.02), 20.0, 1.6, body='LIR2016')
for i, (x, y) in enumerate(PINS):
    s2 += cyl(f'Charge pin {i+1}', (x, y, -0.21), 1.2, 1.85, body=f'Charge pin {i+1} (brass)')
# OLED sits in the holder's 0.8 mm pocket: 3.64 .. 4.89
s2 += box('OLED module', (0, -0.2, 4.265), 26.3, 11.6, 1.25, body='OLED 0.83in 96x39 (approx outline)')
s2 += box('OLED active area', (0, -0.2, 4.895), 19.55, 7.94, 0.01, body='OLED active area')
s2 += [{'command': 'appearance.assign', 'params': {'bodies': ['Movement_holder v16'], 'color': '#e8e4da', 'opacity': 0.35}},
       {'command': 'appearance.assign', 'params': {'bodies': ['LIR2016'], 'color': '#b8bcc0', 'pbr': {'metallic': 1, 'roughness': 0.35, 'dielectric_ior': 1.5}}},
       {'command': 'appearance.assign', 'params': {'bodies': ['Charge pin 1 (brass)', 'Charge pin 2 (brass)'], 'color': '#c9a227', 'pbr': {'metallic': 1, 'roughness': 0.3, 'dielectric_ior': 1.5}}},
       {'command': 'appearance.assign', 'params': {'bodies': ['OLED 0.83in 96x39 (approx outline)'], 'color': '#202226'}},
       {'command': 'canvas.decal', 'params': {'path': R + '/oled_mock.png', 'face': {'face': [0, -0.2, 4.90], 'body': 'OLED active area', 'index': 0}, 'width': 19.55}}]

json.dump({'commands': s1}, open(os.path.join(R, 'watch_stage1.json'), 'w'), indent=0)
json.dump({'commands': s2}, open(os.path.join(R, 'watch_stage2.json'), 'w'), indent=0)
print(len(s1), len(s2))
