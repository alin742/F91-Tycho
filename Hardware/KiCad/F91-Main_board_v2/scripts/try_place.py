"""Apply PLACE overrides to the current board copy and print only copper-related DRC issues."""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
over = json.loads(sys.argv[1])
b = pcbnew.LoadBoard(os.environ.get('TRY_BOARD', os.path.join(ROOT, 'F91-Main_board_v2.kicad_pcb')))
for ref, (x, y, r) in over.items():
    f = b.FindFootprintByReference(ref)
    f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))); f.SetOrientationDegrees(r)
t = os.path.join(ROOT, 'work', 'try.kicad_pcb')
pcbnew.SaveBoard(t, b)
import shutil
for ext in ('.kicad_pro', '.kicad_dru'):
    shutil.copy(os.path.join(ROOT, 'F91-Main_board_v2' + ext), os.path.join(ROOT, 'work', 'try' + ext))
subprocess.run(['kicad-cli', 'pcb', 'drc', '-o', os.path.join(ROOT, 'work', 'try.rpt'), t], capture_output=True)
rpt = open(os.path.join(ROOT, 'work', 'try.rpt')).read().split('\n[')
for blk in rpt:
    if blk.startswith(('clearance', 'shorting', 'solder_mask', 'hole_clear', 'copper_edge')):
        lines = [l.strip() for l in blk.split('\n') if l.strip().startswith('@')]
        if not any(k in ' '.join(lines) for k in ('SW1', 'SW2', 'SW3', 'RF_N] on B', 'RF_P] on B')):
            print('[' + blk.split('\n')[0][:90]); [print('   ', l[:100]) for l in lines]
