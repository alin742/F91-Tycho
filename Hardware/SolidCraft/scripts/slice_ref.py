"""Slice the GrabCAD F-91W STL meshes to get case outlines/profiles (for checking the solid model)."""
import numpy as np, struct, sys
from PIL import Image, ImageDraw

def load(p):
    d = open(p, 'rb').read(); n = struct.unpack('<I', d[80:84])[0]
    return np.frombuffer(d[84:84 + n * 50], dtype=np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')]))['v'].reshape(-1, 3, 3).astype(float)

def section(tri, axis, val):
    segs = []
    s = tri[:, :, axis] - val
    for t, sv in zip(tri, s):
        pts = []
        for i in range(3):
            a, b = i, (i + 1) % 3
            if (sv[a] < 0) != (sv[b] < 0):
                u = sv[a] / (sv[a] - sv[b]); pts.append(t[a] + u * (t[b] - t[a]))
        if len(pts) == 2: segs.append(pts)
    return np.array(segs)

def draw(segs_list, dims, fname, S=20, box=None):
    (i, j) = dims
    allp = np.concatenate([s.reshape(-1, 3) for s, _ in segs_list if len(s)])
    lo = allp[:, [i, j]].min(0) - 1; hi = allp[:, [i, j]].max(0) + 1
    if box: lo, hi = np.array(box[0]), np.array(box[1])
    W, H = ((hi - lo) * S).astype(int)
    im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
    for g in range(int(lo[0]), int(hi[0]) + 1):
        d.line([((g - lo[0]) * S, 0), ((g - lo[0]) * S, H)], fill=(235, 235, 235) if g % 5 else (190, 190, 190))
    for g in range(int(lo[1]), int(hi[1]) + 1):
        d.line([(0, (hi[1] - g) * S), (W, (hi[1] - g) * S)], fill=(235, 235, 235) if g % 5 else (190, 190, 190))
    for segs, col in segs_list:
        for a, b in segs:
            d.line([((a[i] - lo[0]) * S, (hi[1] - a[j]) * S), ((b[i] - lo[0]) * S, (hi[1] - b[j]) * S)], fill=col, width=2)
    im.save(fname)
