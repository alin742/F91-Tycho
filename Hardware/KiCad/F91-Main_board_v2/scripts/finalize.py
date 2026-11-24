"""Final touches on a routed board: hide reference designators on silk (unreadable at this size;
assembly uses the CPL file), add a board label on the bottom, set the title block."""
import os, sys
import pcbnew

MM = lambda v: pcbnew.FromMM(float(v))
path = os.path.abspath(sys.argv[1])
label = sys.argv[2] if len(sys.argv) > 2 else 'F91 Kepler v2'
pos = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (2.6, -6.0)
b = pcbnew.LoadBoard(path)
for fp in b.GetFootprints():
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
for d in list(b.GetDrawings()):
    if isinstance(d, pcbnew.PCB_TEXT) and d.GetText().startswith('F91 Kepler'):
        b.Remove(d)
t = pcbnew.PCB_TEXT(b)
t.SetText(label)
t.SetLayer(pcbnew.B_SilkS)
t.SetPosition(pcbnew.VECTOR2I(MM(pos[0]), MM(pos[1])))
t.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))
t.SetTextThickness(MM(0.15))
t.SetMirrored(True)
b.Add(t)
tb = b.GetTitleBlock()
tb.SetTitle(label)
tb.SetDate('2026-11-22')
tb.SetRevision('2.0')
pcbnew.SaveBoard(path, b)
print('finalized', path)
