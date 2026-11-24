"""Route the charging PCB with the main board's router (GND routed too, no antenna keep-out)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'F91-Main_board_v2', 'scripts'))
import pcbnew
import router as R1
import router2 as R2
PCB = os.path.join(HERE, '..', 'F91-Charge_pad.kicad_pcb')
R1.ANT_KEEPOUT = (100, 100, 101, 101)
R1.TW = 0.2
R2.SKIP = {''}
b = pcbnew.LoadBoard(os.path.abspath(PCB))
pf = R2.PF(b)
order = pf.conn_order()
pres = 0.5
for it in range(20):
    failed = []
    for n in order:
        pf.rip(n)
        if not pf.route(n, pres):
            failed.append(n)
    ov = pf.overuse(); nov = int(ov.sum())
    print('iter', it, 'overuse', nov, 'failed', failed)
    if nov == 0 and not failed:
        break
    pf.hist += ov; pres *= 1.6
pf.commit()
pcbnew.SaveBoard(os.path.abspath(PCB), b)
