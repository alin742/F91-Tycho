"""Export JLCPCB fabrication + assembly files for the F91 Kepler panel.

Output in Hardware/KiCad/panel/fab/:
  F91-Kepler_panel_gerbers.zip   Gerbers + Excellon drill (upload to JLCPCB)
  F91-Kepler_panel_BOM.csv       Comment, Designator, Footprint, LCSC Part #   (JLC format)
  F91-Kepler_panel_CPL.csv       Designator, Mid X, Mid Y, Layer, Rotation     (JLC format)
Run with the system python (pcbnew) from anywhere.
"""
import csv, os, subprocess, zipfile
from collections import defaultdict
from pathlib import Path
import pcbnew

HERE = Path(__file__).resolve().parent
PCB = HERE / 'F91-Kepler_panel.kicad_pcb'
OUT = HERE / 'fab'
LAYERS = 'F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts'


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stdout + r.stderr)


def main():
    OUT.mkdir(exist_ok=True)
    g = OUT / 'gerbers'
    g.mkdir(exist_ok=True)
    for f in g.iterdir():
        f.unlink()
    run('kicad-cli', 'pcb', 'export', 'gerbers', '--layers', LAYERS, '--subtract-soldermask',
        '--use-drill-file-origin', '-o', str(g) + '/', str(PCB))
    run('kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th',
        '--generate-map', '--map-format', 'gerberx2', '-o', str(g) + '/', str(PCB))
    with zipfile.ZipFile(OUT / 'F91-Kepler_panel_gerbers.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(g.iterdir()):
            z.write(f, f.name)

    b = pcbnew.LoadBoard(str(PCB))
    origin = b.GetDesignSettings().GetAuxOrigin()
    bom = defaultdict(list)
    rows = []
    for fp in b.GetFootprints():
        if fp.GetAttributes() & (pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM):
            continue
        if fp.IsDNP():
            continue
        lcsc = fp.GetFieldText('LCSC') if fp.HasField('LCSC') else ''
        if not lcsc:
            continue
        ref = fp.GetReference()
        bom[(fp.GetValue(), str(fp.GetFPID().GetLibItemName()), lcsc)].append(ref)
        pos = fp.GetPosition() - origin
        rows.append([ref, f'{pos.x / 1e6:.4f}mm', f'{-pos.y / 1e6:.4f}mm',
                     'Bottom' if fp.IsFlipped() else 'Top', f'{fp.GetOrientationDegrees() % 360:.1f}'])
    with open(OUT / 'F91-Kepler_panel_BOM.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (val, fpn, lcsc), refs in sorted(bom.items(), key=lambda kv: kv[0][2]):
            w.writerow([val, ','.join(sorted(refs)), fpn, lcsc])
    with open(OUT / 'F91-Kepler_panel_CPL.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        w.writerows(sorted(rows))
    print(f'{len(bom)} BOM lines, {len(rows)} placements ->', OUT)


if __name__ == '__main__':
    main()
