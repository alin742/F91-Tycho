"""Build steps for the solid Casio F-91W + Kepler v2 electronics in SolidCraft.
Writes two batch files (stage1 case/strap, stage2 electronics) into SolidCraft's recovery folder.
Frame: watch centre at X=Y=0, +Y = 12 o'clock (CASIO print side), Z up, display face up.
Z stack: case back outer -0.65 / inner -0.21 (dip floor -1.79, charging PCB -1.29..-0.49 under the cell), clamp gap, cell 0.02-1.62, board 1.64-2.35,
holder top + OLED 4.44-5.69, crystal 6.62-7.40, case top 7.40."""
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
s1 = []
# ---- case body: chamfered main body + lugs
outline = [(-12, 19.1), (12, 19.1), (12, 16), (13.6, 16), (17.6, 12), (17.6, -12), (13.6, -16), (12, -16),
           (12, -19.1), (-12, -19.1), (-12, -16), (-13.6, -16), (-17.6, -12), (-17.6, 12), (-13.6, 16), (-12, 16)]
s1 += poly('Case body', 'XY', [list(p) for p in outline], 7.61, CASE, offset=-0.21)
s1 += box('Lug slot top', (0, 17.8, 3.6), 18.2, 3.0, 8.4, 'cut', targets=[CASE])
s1 += box('Lug slot bottom', (0, -17.8, 3.6), 18.2, 3.0, 8.4, 'cut', targets=[CASE])
s1 += box('Module cavity', (0, 0, 2.65), 27.0, 26.0, 6.3, 'cut', targets=[CASE])
s1 += box('Display window', (0, 0, 6.2), 24.0, 19.0, 1.0, 'cut', targets=[CASE])
s1 += poly('Crystal recess', 'XY', chamfer_rect(28.8, 25.6, 2.6), 1.0, None, 'cut', [CASE], offset=6.6)
for i, (x, y) in enumerate([(11.1, 12.7), (-11.1, 12.7), (-11.1, -12.7), (11.1, -12.7)]):
    s1 += cyl(f'Screw boss {i+1}', (x, y, -0.21), 3.2, 3.2, 'join', targets=[CASE])
    s1 += cyl(f'Screw hole {i+1}', (x, y, -0.3), 1.2, 2.8, 'cut', targets=[CASE])
# ---- case back (steel), Ø4.3 charging hole over the charging PCB pads
BACK = 'Case back (steel, drilled)'
DIP_D = 23.35                 # dip diameter, assumed centred on the case back
CHG_X, CHG_Y = 6.0, 0.0       # charging PCB centre: inside the dip, under the cell, FFC edge facing J2 (3 o'clock)
CHG_Z = -1.79 + 0.5           # dip floor + 0.5 mm rubber ring
# steel 0.44 mm, round dip Ø23.35 (inside) pressed 1.58 mm outward (2.02 total), measured 2026-11-24
s1 += poly('Case back', 'XY', chamfer_rect(31.8, 28.3, 3.2), 0.44, BACK, offset=-0.65)
s1 += cyl('Dip cup', (0, 0, -2.23), DIP_D + 0.88, 2.02, 'join', targets=[BACK])
s1 += cyl('Dip', (0, 0, -1.79), DIP_D, 1.6, 'cut', targets=[BACK])
s1 += cyl('Charging hole', (CHG_X, CHG_Y, -2.4), 4.3, 0.8, 'cut', targets=[BACK])
for i, (x, y) in enumerate([(11.1, 12.7), (-11.1, 12.7), (-11.1, -12.7), (11.1, -12.7)]):
    s1 += cyl(f'Case back screw {i+1}', (x, y, -0.96), 2.2, 0.25, body=f'Case back screw {i+1}')
    s1 += cyl(f'Screw shank {i+1}', (x, y, -0.71), 1.2, 3.0, 'join', targets=[f'Case back screw {i+1}'])
# ---- crystal with the printed face (decal from the GrabCAD print geometry)
s1 += poly('Crystal', 'XY', chamfer_rect(28.6, 25.4, 2.5), 0.78, 'Crystal', offset=6.62)
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
       {'command': 'canvas.decal', 'params': {'path': R + '/f91w_face_print.png', 'face': [0, 0, 7.4], 'width': 28.6}}]

# ---- stage 2: v2 electronics
s2 = []
s2 += [{'command': 'file.insert_step', 'params': {'path': R + '/F91-Movement_holder.step', 'name': 'Movement holder',
                                                  'matrix': [-1, 0, 0, -0.04, 0, 1, 0, 0.0, 0, 0, -1, 4.44]}},
       {'command': 'file.insert_step', 'params': {'path': R + '/F91-Main_board_v2.step', 'name': 'Main board v2',
                                                  'matrix': [1, 0, 0, -3.05, 0, 1, 0, 2.77, 0, 0, 1, 1.64]}},
       {'command': 'file.insert_step', 'params': {'path': R + '/F91-Charge_pad.step', 'name': 'Charging PCB (inside case back)',
                                                  'matrix': [0, 1, 0, CHG_X, -1, 0, 0, CHG_Y,
                                                             0, 0, 1, CHG_Z], 'tolerance': 0.001}}]
s2 += cyl('LIR2016 cell', (-0.40, 1.47, 0.02), 20.0, 1.6, body='LIR2016')
s2 += cyl('Rubber ring', (CHG_X, CHG_Y, -1.79), 7.0, 0.5, body='Rubber ring 0.5 mm')
s2 += cyl('Rubber ring hole', (CHG_X, CHG_Y, -1.85), 4.5, 0.6, 'cut', targets=['Rubber ring 0.5 mm'])
s2 += cyl('Magnet 1', (CHG_X, CHG_Y + 4.0, CHG_Z), 3.0, 1.0, body='Magnet 3x1 (1)')
s2 += cyl('Magnet 2', (CHG_X, CHG_Y - 4.0, CHG_Z), 3.0, 1.0, body='Magnet 3x1 (2)')
s2 += box('OLED module', (0, -0.2, 5.065), 26.3, 11.6, 1.25, body='OLED 0.83in 96x39 (approx outline)')
s2 += box('OLED active area', (0, -0.2, 5.695), 19.55, 7.94, 0.01, body='OLED active area')
# FFC: 4-way 1.0 mm ribbon, 4.2 mm wide, from the charging PCB edge (x = CHG_X + 2.5) out along +X,
# up the dip wall, to J2 on the main board's underside at 3 o'clock (world ~ (13.55, 0), z 1.64)
z0 = CHG_Z + 0.8
s2 += box('FFC ribbon', (CHG_X + 2.5 + 1.6, CHG_Y, z0 + 0.05), 3.2, 4.2, 0.1, body='FFC ribbon 4-way 1.0 mm')
s2 += box('FFC ribbon rise', (11.9, CHG_Y, (z0 + 1.64) / 2), 0.1, 4.2, 1.64 - z0, 'join', targets=['FFC ribbon 4-way 1.0 mm'])
s2 += box('FFC ribbon top', (12.95, CHG_Y, 1.59), 2.1, 4.2, 0.1, 'join', targets=['FFC ribbon 4-way 1.0 mm'])
s2 += [{'command': 'appearance.assign', 'params': {'bodies': ['Movement_holder v16'], 'color': '#e8e4da', 'opacity': 0.35}},
       {'command': 'appearance.assign', 'params': {'bodies': ['LIR2016'], 'color': '#b8bcc0', 'pbr': {'metallic': 1, 'roughness': 0.35, 'dielectric_ior': 1.5}}},
       {'command': 'appearance.assign', 'params': {'bodies': ['Magnet 3x1 (1)', 'Magnet 3x1 (2)'], 'color': '#9ea3a8', 'pbr': {'metallic': 1, 'roughness': 0.25, 'dielectric_ior': 1.5}}},
       {'command': 'appearance.assign', 'params': {'bodies': ['OLED 0.83in 96x39 (approx outline)'], 'color': '#202226'}},
       {'command': 'appearance.assign', 'params': {'bodies': ['FFC ribbon 4-way 1.0 mm'], 'color': '#d08a2a'}},
       {'command': 'canvas.decal', 'params': {'path': R + '/oled_mock.png', 'face': {'face': [0, -0.2, 5.70], 'body': 'OLED active area', 'index': 0}, 'width': 19.55}}]

json.dump({'commands': s1}, open(os.path.join(R, 'watch_stage1.json'), 'w'), indent=0)
json.dump({'commands': s2}, open(os.path.join(R, 'watch_stage2.json'), 'w'), indent=0)
print(len(s1), len(s2))
