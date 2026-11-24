"""Scale the GrabCAD F-91W meshes (local only, git-ignored) to the measured 37.6 mm length (34.5 wide) and open the case for the v2 model.
Case seat (GrabCAD z 0) goes to z -0.21. The fused glass caps and GrabCAD's own module are removed so the
real electronics show through. Writes into SolidCraft's recovery folder (grabcad_real/)."""
import numpy as np, struct, os
SRC = os.path.join(os.path.dirname(__file__), '../../reference/grabcad-f91w/parts_mm')
OUT = os.path.expanduser('~/.local/share/solidcraft/recovery/f91_v2/grabcad_real')
SX, SY, DZ = 34.5 / 33.0, 37.6 / 36.7, -0.21   # 37.60 lug-to-lug measured (photo 913), 34.5 wide (Casio/Wikipedia 37.5 x 34.5)
DT = np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')])


# Fit the GrabCAD body to the caliper measurements (2026-11-24):
#  - its underside (z 0.69 at the 3/9 sides after scaling) sits on the back plate's top (z -0.21)
#  - back face -> window frame underside (GrabCAD 4.79) becomes the measured 5.68 deep (frame + glass keep their thickness)
#  - the four screw bosses move from GrabCAD's (±10.98, ±12.29) to the measured (±9.35, ±12.7)
# Only the watch head is warped (|y| < 17, blending out to |y| = 21), so the strap keeps its shape.
Z_BOT, Z_LIP, SEAT, DEPTH = 0.69, 4.79, -0.21, 5.68   # 0.69 = underside of the 3/9 sides after scaling
G_SCREW, M_SCREW = (10.98, 12.29), (9.35, 12.7)
def warp(v):
    v = v.copy(); x, y, z = v[..., 0], v[..., 1], v[..., 2]
    w = np.clip((21.0 - np.abs(y)) / 4.0, 0, 1)
    k = DEPTH / (Z_LIP - Z_BOT)
    zn = np.where(z < Z_BOT, z + (SEAT - Z_BOT),
         np.where(z < Z_LIP, SEAT + (z - Z_BOT) * k, SEAT + DEPTH + (z - Z_LIP)))
    v[..., 2] = z + w * (zn - z)
    return v

# Back rim: GrabCAD's case-back octagon (30.0 x 26.74 before scaling) -> the measured plate octagon (gen_watch_v2.py BACK_PTS).
# Radial map per direction: the rim (r up to the GrabCAD octagon) moves onto the plate octagon, fading out 1.5 mm further out,
# applied to the bottom of the head (z < 0.7, fading out by z 1.5).
G_OCT = [(-14.96, -8.27), (-11.46, -13.37), (11.54, -13.37), (15.04, -8.27), (15.04, 8.23), (11.54, 13.37), (-11.46, 13.37), (-14.96, 8.23)]
P_OCT = [(-10.5, 14.1), (10.5, 14.1), (15.32, 6.5), (15.32, -6.5), (10.5, -14.1), (-10.5, -14.1), (-15.32, -6.5), (-15.32, 6.5)]
def oct_r(poly, th):
    """distance from the origin to the polygon edge along the directions th"""
    P = np.array(poly, float); r = np.full(th.shape, np.inf); d = np.stack([np.cos(th), np.sin(th)], -1)
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]; e = b - a
        den = d[..., 0] * e[1] - d[..., 1] * e[0]
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (a[0] * e[1] - a[1] * e[0]) / den; u = (a[0] * d[..., 1] - a[1] * d[..., 0]) / den
        ok = (t > 0) & (u >= -1e-9) & (u <= 1 + 1e-9); r = np.where(ok & (t < r), t, r)
    return r
def warp_rim(v):
    v = v.copy(); x, y, z = v[..., 0], v[..., 1], v[..., 2]
    th = np.arctan2(y, x); r = np.hypot(x, y)
    rg = oct_r([(px * SX, py * SY) for px, py in G_OCT], th); rp = oct_r(P_OCT, th)
    rn = np.where(r <= rg, r * rp / rg, np.where(r < rg + 1.5, r + (rp - rg) * (rg + 1.5 - r) / 1.5, r))
    wz = np.clip((1.5 - z) / 0.8, 0, 1) * (np.abs(y) < 17)
    k = 1 + wz * (rn / np.maximum(r, 1e-9) - 1)
    v[..., 0] = x * k; v[..., 1] = y * k
    return v
os.makedirs(OUT, exist_ok=True)
for f in ['case_and_strap', 'button_right', 'button_left_1', 'button_left_2', 'spring_bar_1', 'spring_bar_2',
          'buckle', 'buckle_pin', 'crystal_print']:
    d = open(os.path.join(SRC, f + '.stl'), 'rb').read(); n = struct.unpack('<I', d[80:84])[0]
    a = np.frombuffer(d[84:84 + n * 50], dtype=DT).copy(); v = a['v'].reshape(-1, 3, 3)
    v[:, :, 0] *= SX; v[:, :, 1] *= SY; v[:, :, 2] += DZ
    a['v'] = v.reshape(-1, 9); a['n'] = 0
    if f == 'case_and_strap':
        x, y, z = v[:, :, 0], v[:, :, 1], v[:, :, 2]
        cap = np.all((abs(x) <= 13.5 * SX + 0.01) & (abs(y) <= 12.0 * SY + 0.01), 1) & (np.all(abs(z - 6.99) < .005, 1) | np.all(abs(z - 5.79) < .005, 1))
        inside = np.all((abs(x) < 13.5 * SX - 0.1) & (abs(y) < 12.0 * SY - 0.1) & (z > -0.1) & (z < 5.7), 1)   # GrabCAD cavity is 27 x 24
        print('removed caps', cap.sum(), 'internals', inside.sum()); a = a[~(cap | inside)]; f = 'case_and_strap_open'
    vv = a['v'].reshape(-1, 3, 3).copy()
    if f != 'buckle' and f != 'buckle_pin':
        vv = warp(vv)
        if f == 'case_and_strap_open':
            vv = warp_rim(vv)
            g = warp_rim(np.array([[G_SCREW[0], G_SCREW[1], 0.0]]))[0]   # where the rim map put GrabCAD's boss
            x, y = vv[..., 0], vv[..., 1]
            dist = np.hypot(np.abs(x) - g[0], np.abs(y) - g[1])
            fz = np.clip((2.2 - dist) / 1.0, 0, 1) * (np.abs(y) < 17)     # full shift within 1.2 mm of the boss axis
            vv[..., 0] = x + fz * np.sign(x) * (M_SCREW[0] - g[0])
            vv[..., 1] = y + fz * np.sign(y) * (M_SCREW[1] - g[1])
    a['v'] = vv.reshape(-1, 9)
    open(os.path.join(OUT, f + '.stl'), 'wb').write(d[:80] + struct.pack('<I', len(a)) + a.tobytes())
print('written to', OUT)
