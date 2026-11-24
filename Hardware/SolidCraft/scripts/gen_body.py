"""F-91W case body built from the caliper measurements (2026-11-24), as a solid. Writes body_v2.json (SolidCraft batch)
into the recovery folder. Frame as gen_watch_v2.py: centre X=Y=0, +Y = 12 o'clock, back-plate top (seat) at z -0.21.
Measured: lug-to-lug 37.6; back plate octagon 21 (12/6) / 13 (3/9) / 9 (corners), 0.44 thick, sits flush in the back;
screws 18.7 x 25.4; seat -> window 5.68; round cavity (caliper 27.61, reads low) with notches at 12/6 (module 25.70 passes).
Overall 8.5 (Casio) incl. the 1.58 dip -> glass 5.47-6.27. Not measured: plate rim 1.4, top bevel, lug height 5.0."""
import json, os
R = os.path.expanduser('~/.local/share/solidcraft/recovery/f91_v2')
B = 'F-91W body (measured)'
BOT, SEAT, CAV_TOP, TOP = -0.65, -0.21, 5.47, 6.27   # 8.5 mm overall (Casio) from the dip's outside (-2.23) to the glass top
RIM = 1.4                               # body = back-plate octagon grown outward by this (the real case follows the plate's shape)
LUG_Y = 18.8                             # 37.6 lug to lug
CAV_D, NOTCH = 28.2, 25.9
PLATE = [(-10.5, 14.1), (10.5, 14.1), (15.32, 6.5), (15.32, -6.5), (10.5, -14.1), (-10.5, -14.1), (-15.32, -6.5), (-15.32, 6.5)]
def offset_poly(P, d):
    import math
    n = len(P); lines = []
    for i in range(n):
        (x1, y1), (x2, y2) = P[i], P[(i + 1) % n]; ex, ey = x2 - x1, y2 - y1; L = math.hypot(ex, ey)
        nx, ny = -ey / L, ex / L                    # outward normal for a clockwise polygon
        lines.append(((x1 + nx * d, y1 + ny * d), (ex, ey)))
    out = []
    for i in range(n):
        (p, r), (q, s_) = lines[i - 1], lines[i]
        den = r[0] * s_[1] - r[1] * s_[0]; t = ((q[0] - p[0]) * s_[1] - (q[1] - p[1]) * s_[0]) / den
        out.append((p[0] + t * r[0], p[1] + t * r[1]))
    return out
SCREWS = [(9.35, 12.7), (-9.35, 12.7), (-9.35, -12.7), (9.35, -12.7)]
BAR_Y, BAR_Z = 16.34, 2.55               # spring bars (reference model)

def oct_pts(hw, hh, cx, cy):
    return [[-hw + cx, hh], [hw - cx, hh], [hw, hh - cy], [hw, -hh + cy], [hw - cx, -hh], [-hw + cx, -hh], [-hw, -hh + cy], [-hw, hh - cy]]
def poly(name, pts, dist, offset, op='new', body=None):
    ex = {'distance': dist, 'name': name, 'operation': op}
    if op == 'new': ex['body_name'] = body
    else: ex['targets'] = [B]
    return [{'command': 'sketch.create', 'params': {'plane': 'XY', 'name': name + ' sketch', 'offset': str(offset)}},
            {'command': 'sketch.line', 'params': {'points': [[round(a, 4), round(b, 4)] for a, b in pts], 'closed': True, 'infer': False}},
            {'command': 'sketch.finish', 'params': {}},
            {'command': 'solid.extrude', 'params': ex}]
def box(name, c, l, w, h, op):
    return [{'command': 'solid.box', 'params': {'center': list(c), 'length': l, 'width': w, 'height': h, 'operation': op, 'name': name, 'targets': [B]}}]
def cyl(name, base, d, h, op, axis=None):
    p = {'base': list(base), 'diameter': d, 'height': h, 'operation': op, 'name': name, 'targets': [B]}
    if axis: p['axis'] = axis
    return [{'command': 'solid.cylinder', 'params': p}]

s = []
BODY = offset_poly(PLATE, RIM)
HH = max(y for x, y in BODY); HW = max(x for x, y in BODY)
s += poly('Body', BODY, TOP - BOT, BOT, body=B)
mid = [((BODY[i][0] + BODY[(i + 1) % 8][0]) / 2, (BODY[i][1] + BODY[(i + 1) % 8][1]) / 2) for i in range(8)]
s += [{'command': 'solid.chamfer', 'params': {'edges': [[x, y, TOP] for x, y in mid], 'distance': 1.0, 'distance2': 1.4, 'body': B, 'name': 'Top bevel'}}]
for sg, nm in ((1, '12'), (-1, '6')):
    s += box(f'Lug {nm}', (0, sg * (HH - 0.5 + LUG_Y) / 2, 2.5), 2 * BODY[1][0], LUG_Y - HH + 0.5, 5.0, 'join')
    s += [{'command': 'solid.chamfer', 'params': {'edges': [[0, sg * LUG_Y, 5.0]], 'distance': 1.2, 'distance2': 1.2, 'body': B, 'tangent_chain': False, 'name': f'Lug bevel {nm}'}}]
    s += box(f'Strap slot {nm}', (0, sg * (HH - 0.3 + LUG_Y + 0.5) / 2, 1.6), 18.6, LUG_Y + 0.5 - HH + 0.3, 4.7, 'cut')
    s += cyl(f'Spring bar hole {nm}', (-12.0, sg * BAR_Y, BAR_Z), 1.0, 24.0, 'cut', axis='X')
s += poly('Back plate recess', [(x * 1.007, y * 1.007) for x, y in PLATE], SEAT - BOT + 0.05, BOT - 0.05, op='cut')
s += cyl('Module cavity', (0, 0, SEAT - 0.05), CAV_D, CAV_TOP - SEAT + 0.05, 'cut')
for sg, nm in ((1, '12'), (-1, '6')):
    r0, r1 = NOTCH / 2, CAV_D / 2 + 0.2
    s += box(f'Cavity notch {nm}', (0, sg * (r0 + r1) / 2, (SEAT + CAV_TOP) / 2), 3.0, r1 - r0, CAV_TOP - SEAT, 'join')
cr = lambda w, h, c: [(-w / 2 + c, h / 2), (w / 2 - c, h / 2), (w / 2, h / 2 - c), (w / 2, -h / 2 + c), (w / 2 - c, -h / 2), (-w / 2 + c, -h / 2), (-w / 2, -h / 2 + c), (-w / 2, h / 2 - c)]
GLASS = offset_poly(PLATE, RIM - 1.8)    # glass follows the case octagon, 0.8 mm frame inside the top bevel
s += poly('Glass pocket', GLASS, TOP - CAV_TOP + 0.1, CAV_TOP, op='cut')   # glass sits on the cavity top (5.68 measured to the glass)
for i, (x, y) in enumerate(SCREWS):
    s += cyl(f'Body screw hole {i+1}', (x, y, SEAT - 0.05), 1.2, 3.0, 'cut')
s += [{'command': 'appearance.assign', 'params': {'bodies': [B], 'color': '#ebe9e4', 'pbr': {'metallic': 0, 'roughness': 0.6, 'dielectric_ior': 1.5}}}]
s += poly('Glass', offset_poly(PLATE, RIM - 1.85), TOP - CAV_TOP, CAV_TOP, body='Crystal')
s += [{'command': 'appearance.assign', 'params': {'bodies': ['Crystal'], 'color': '#dfe8ee', 'opacity': 0.15}}]
# strap roots: wrap the spring bar and run out to y 22.6, where the reference strap mesh (cut at |y| 22) takes over
for sg, nm in ((1, '12'), (-1, '6')):
    s += [{'command': 'solid.box', 'params': {'center': [0, sg * 19.175, 2.85], 'length': 17.8, 'width': 6.85, 'height': 1.9, 'operation': 'new', 'name': f'Strap root {nm}', 'body_name': f'Strap root {nm}'}},
          {'command': 'solid.cylinder', 'params': {'base': [-9.0, sg * BAR_Y, BAR_Z], 'diameter': 0.95, 'height': 18.0, 'axis': 'X', 'operation': 'cut', 'targets': [f'Strap root {nm}'], 'name': f'Strap root bar hole {nm}'}}]
s += [{'command': 'appearance.assign', 'params': {'bodies': ['Strap root 12', 'Strap root 6'], 'color': '#ebe9e4', 'pbr': {'metallic': 0, 'roughness': 0.6, 'dielectric_ior': 1.5}}}]
json.dump({'commands': s}, open(os.path.join(R, 'body_v2.json'), 'w'), indent=0)
print('body', [(round(x, 2), round(y, 2)) for x, y in BODY]); print(len(s), 'steps ->', os.path.join(R, 'body_v2.json'))
