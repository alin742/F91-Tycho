"""Generate F91-Main_board_v2.kicad_sch from design.py.

Every pin gets a local net label at its connection point (or a no-connect flag), so the
schematic is fully connected without wires. Components are grouped into functional blocks.
"""
import os, sys, uuid, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, dumps, find, findall, Q
import design

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = 'F91-Main_board_v2'
SYSLIB = '/usr/share/kicad/symbols'
LIBS = {'F91_LCSC': os.path.join(ROOT, 'lib', 'F91_LCSC.kicad_sym')}
ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, 'f91-kepler-v2-root'))


def libpath(lib):
    return LIBS.get(lib, os.path.join(SYSLIB, lib + '.kicad_sym'))


_cache = {}


def get_symbol(libid):
    lib, name = libid.split(':')
    if lib not in _cache:
        _cache[lib] = {s[1]: s for s in findall(parse(open(libpath(lib)).read()), 'symbol')}
    s = copy.deepcopy(_cache[lib][name])
    s[1] = Q(libid)
    # sub-symbols keep their short names (NAME_0_1); KiCad expects that
    return s


def pins_of(sym):
    out = {}
    for sub in findall(sym, 'symbol'):
        for p in findall(sub, 'pin'):
            at = find(p, 'at')
            out[str(find(p, 'number')[1])] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
    return out


def bbox(sym):
    ps = pins_of(sym).values()
    xs = [p[0] for p in ps] or [0]
    ys = [p[1] for p in ps] or [0]
    return min(xs), max(xs), min(ys), max(ys)


def U(*k):
    return Q(str(uuid.uuid5(uuid.NAMESPACE_URL, 'f91v2/' + '/'.join(map(str, k)))))


# ---------------------------------------------------------------- blocks (sheet layout)
BLOCKS = [
    ('MCU', ['U1']),
    ('MCU supply, reset, crystals', ['FL1', 'C3', 'C4', 'C5', 'C7', 'C6', 'C8', 'C9', 'C16', 'C19', 'R1', 'C20',
                                     'Y1', 'C17', 'C18', 'Y2']),
    ('RF front end + antenna (v1 layout)', ['L11', 'C31', 'C11', 'C21', 'L21', 'L12', 'C13', 'L13', 'C24', 'C51', 'AE1']),
    ('Charging input + BQ25180 charger', ['J2', 'C30', 'U2', 'C32', 'C33', 'BT1']),
    ('TPS62840 2.0 V buck + battery sense', ['U3', 'L1', 'R11', 'C34', 'R12', 'R13', 'C35']),
    ('Buttons (clamp = VBAT -> N-FET)', ['Q1', 'R21', 'SW1', 'SW1B', 'Q2', 'R22', 'SW2', 'SW2B', 'Q3', 'R23', 'SW3', 'SW3B']),
    ('Display connector, I2C, test pads', ['J1', 'R2', 'R3', 'TP1', 'TP2', 'TP4', 'TP5',
                                                     'TP9']),
    ('Holder holes', ['MH1', 'MH2', 'MH3', 'MH4', 'MH5', 'MH6']),
]
byref = {c['ref']: c for c in design.C}
assert sorted(r for _, rs in BLOCKS for r in rs) == sorted(byref), \
    set(byref) ^ set(r for _, rs in BLOCKS for r in rs)

G = 2.54
snap = lambda v: round(v / G) * G


def build():
    lib_syms = {}
    items = []
    # paper A2: 594 x 420
    x0, y0 = 20 * G / 2, 20 * G / 2
    bx, by = 15.24, 25.4
    row_h = 0
    for title, refs in BLOCKS:
        # block title
        items.append(['text', Q(title), ['exclude_from_sim', 'no'],
                      ['at', snap(bx), snap(by - 7.62), 0],
                      ['effects', ['font', ['size', 2.0, 2.0], ['bold', 'yes']], ['justify', 'left']],
                      ['uuid', U('t', title)]])
        cx, cy = bx, by
        col_h = 0
        for ref in refs:
            c = byref[ref]
            sym = get_symbol(c['sym'])
            lib_syms[c['sym']] = sym
            x1, x2, y1, y2 = bbox(sym)
            w = max(x2 - x1, 2.54) + 30.0
            h = max(y2 - y1, 2.54) + 12.7
            if cx + w > bx + 260:  # wrap inside the block
                cx = bx
                cy += col_h
                col_h = 0
            px, py = snap(cx - x1 + 15.24), snap(cy + y2 + 6.35)
            items.append(place(c, sym, px, py))
            items.extend(labels(c, sym, px, py))
            cx += w
            col_h = max(col_h, h)
        blk_h = (cy - by) + col_h + 15
        row_h = max(row_h, blk_h)
        # two block columns
        if bx < 250:
            bx = 300.0
        else:
            bx = 15.24
            by += row_h
            row_h = 0
    return lib_syms, items


def place(c, sym, x, y):
    props = {p[1]: p for p in findall(sym, 'property')}
    e = ['symbol', ['lib_id', Q(c['sym'])], ['at', x, y, 0], ['unit', 1],
         ['exclude_from_sim', 'no'], ['in_bom', 'yes' if c['bom'] else 'no'], ['on_board', 'yes'],
         ['dnp', 'yes' if 'DNP' in c['note'] else 'no'],
         ['uuid', U('s', c['ref'])]]
    fields = [('Reference', c['ref']), ('Value', c['value']), ('Footprint', c['fp']),
              ('Datasheet', ''), ('Description', c['note']), ('LCSC', c['lcsc'])]
    for i, (k, v) in enumerate(fields):
        hide = k not in ('Reference', 'Value')
        eff = ['effects', ['font', ['size', 1.27, 1.27]]]
        if hide:
            eff.append(['hide', 'yes'])
        e.append(['property', Q(k), Q(v), ['at', x, y - 3.81 + 2.54 * (i if i < 2 else 1), 0], eff])
    for num in pins_of(sym):
        e.append(['pin', Q(num), ['uuid', U('p', c['ref'], num)]])
    e.append(['instances', ['project', Q(NAME), ['path', Q('/' + ROOT_UUID), ['reference', Q(c['ref'])], ['unit', 1]]]])
    return e


def labels(c, sym, x, y):
    out = []
    for num, (px, py, ang) in pins_of(sym).items():
        ax, ay = round(x + px, 4), round(y - py, 4)
        net = c['pins'].get(num)
        if net is None:
            out.append(['no_connect', ['at', ax, ay], ['uuid', U('nc', c['ref'], num)]])
            continue
        # label text points away from the symbol body
        rot = {0: 180, 180: 0, 90: 270, 270: 90}[int(ang) % 360]
        just = 'right' if rot in (180, 270) else 'left'
        # global labels: net names without the '/' sheet prefix, same as the board's nets
        out.append(['global_label', Q(net), ['shape', 'passive'], ['at', ax, ay, rot],
                    ['fields_autoplaced', 'yes'],
                    ['effects', ['font', ['size', 1.0, 1.0]], ['justify', just]],
                    ['uuid', U('l', c['ref'], num)]])
    return out


def main():
    lib_syms, items = build()
    sch = ['kicad_sch', ['version', 20250114], ['generator', Q('eeschema')], ['generator_version', Q('9.0')],
           ['uuid', Q(ROOT_UUID)], ['paper', Q('A2')],
           ['title_block', ['title', Q('F91 Kepler v2 main board (rechargeable)')], ['date', Q('2026-11-22')],
            ['rev', Q('2.0')], ['comment', 1, Q('Generated by scripts/gen_sch.py from scripts/design.py')],
            ['comment', 2, Q('LIR2016 + BQ25180 charger + TPS62840 2.0 V buck; parts from the JLCPCB library')]],
           ['lib_symbols'] + list(lib_syms.values())]
    sch += items
    sch.append(['sheet_instances', ['path', Q('/'), ['page', Q('1')]]])
    sch.append(['embedded_fonts', 'no'])
    path = os.path.join(ROOT, NAME + '.kicad_sch')
    open(path, 'w').write(dumps(sch) + '\n')
    print('wrote', path, len(items), 'items')


if __name__ == '__main__':
    main()
