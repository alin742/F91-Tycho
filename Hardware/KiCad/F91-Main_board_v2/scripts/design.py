"""F91 Kepler v2 main board: single source of truth for schematic + PCB generation.

Each component: ref, symbol (lib:name), footprint (lib:name), value, LCSC, pin->net map,
v1 placement (x, y, rot, side) when the part is kept from the v1 layout, or None to auto-place.
Board coordinates are the v1 KiCad import coordinates (mm, y down).
"""

# ---------------------------------------------------------------- nets
# Power
GND, VBAT, SYS, VDD, VDDS, VDDR = 'GND', 'VBAT', 'SYS', 'VDD', 'VDDS', 'VDDR'
CHG_IN, VIN = 'CHG_IN', 'VIN_CHG'          # ribbon pad (+) / after the Schottky
SW_BUCK, VSET = 'SW_BUCK', 'VSET'

C = []  # component list


def comp(ref, sym, fp, value, lcsc, pins, v1=None, bom=True, note=''):
    C.append(dict(ref=ref, sym=sym, fp=fp, value=value, lcsc=lcsc, pins=pins,
                  v1=v1, bom=bom, note=note))


R0402 = 'Resistor_SMD:R_0402_1005Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'

# ---------------------------------------------------------------- MCU
mcu_pins = {
    '1': 'RF_P', '2': 'RF_N', '3': 'X32K_1', '4': 'X32K_2',
    '5': None,            # DIO0 spare
    '6': None,            # DIO1 spare
    '7': None,            # DIO2 (UART RX on the LaunchPad) spare, no pad
    '8': None,            # DIO3 spare (was PMIC_INT: moved to DIO6 so it does not cross SCL at U2)
    '9': 'SCL',           # DIO4
    '10': 'SDA',          # DIO5
    '11': 'PMIC_INT',     # DIO6 <- BQ25180 /INT (open drain, MCU pull-up); outermost, like A1 on U2
    '12': None,           # DIO7 (LaunchPad LED) spare
    '13': VDDS,
    '14': None,  # spare (was ext-flash pin on the LaunchPad)
    '15': None,  # spare (was ext-flash pin on the LaunchPad)
    '16': None,  # spare (was ext-flash pin on the LaunchPad)
    '17': None, '18': None, '19': None, '20': None,   # DIO11..14 spare
    '21': 'BTN3',         # DIO15 (SW3, as v1)
    '22': VDDS, '23': 'DCOUPL',
    '24': 'TMSC', '25': 'TCKC',
    '26': None, '27': None,   # DIO16/17 (TDO/TDI, 4-wire JTAG only) spare
    '28': None, '29': None,   # DIO18/19 spare
    '30': None,  # spare (was ext-flash pin on the LaunchPad)
    '31': None, '32': None,   # DIO21/22 spare
    '33': None,           # DCDC_SW unconnected: internal LDO mode (no inductor)
    '34': VDDS,           # VDDS_DCDC
    '35': 'RESET_N',
    '36': 'VBAT_SENSE',   # DIO23 (analog AUXIO) <- battery divider
    '37': None,           # DIO24 spare (analog)
    '38': 'BTN2',         # DIO25 (SW2, as v1)
    '39': 'BTN1',         # DIO26 (SW1, as v1)
    '40': 'BUZZ',         # DIO27 -> Pad5 (piezo spring, kept for later)
    '41': None, '42': None, '43': None,       # DIO28..30 spare
    '44': VDDS, '45': VDDR, '46': 'X24M_N', '47': 'X24M_P', '48': VDDR, '49': GND,
}
comp('U1', 'F91_LCSC:CC2640R2FRGZR', 'Package_DFN_QFN:Texas_RGZ0048A_VQFN-48-1EP_7x7mm_P0.5mm_EP5.15x5.15mm_ThermalVias',
     'CC2640R2FRGZR', 'C122885', mcu_pins, v1=('MCU', 2.54, 1.61))

# VDDS decoupling (v1 C3/C4/C5/C7/C6) and ferrite (v1 FL1, VBAT->VDDS becomes VDD->VDDS)
for r in ['C3', 'C4', 'C5', 'C7']:
    comp(r, 'Device:C', C0402, '100nF', 'C1525', {'1': VDDS, '2': GND}, v1=r)
comp('C6', 'Device:C', C0603, '10uF', 'C19702', {'1': VDDS, '2': GND}, v1='C6')
comp('FL1', 'F91_LCSC:BLM18HE152SN1D', 'F91_LCSC:L0603', 'BLM18HE152SN1D', 'C82155',
     {'1': VDD, '2': VDDS}, v1='FL1')
# VDDR (internal LDO mode keeps the VDDR decoupling; v1 L1 10uH is removed)
comp('C8', 'Device:C', C0603, '10uF', 'C19702', {'1': VDDR, '2': GND}, v1='C8')
comp('C9', 'Device:C', C0402, '100nF', 'C1525', {'1': VDDR, '2': GND}, v1='C9')
comp('C16', 'Device:C', C0402, '100nF', 'C1525', {'1': VDDR, '2': GND}, v1='C16')
comp('C19', 'Device:C', C0402, '1uF', 'C52923', {'1': 'DCOUPL', '2': GND}, v1='C19')
# Reset
comp('R1', 'Device:R', R0402, '100k', 'C25741', {'1': VDDS, '2': 'RESET_N'}, v1='R1')
comp('C20', 'Device:C', C0402, '100nF', 'C1525', {'1': 'RESET_N', '2': GND}, v1='C20')
# Crystals (32 kHz FC-135 CL=12.5 pF -> 18 pF load caps; 24 MHz uses internal caps)
comp('Y1', 'F91_LCSC:Q13FC1350000400', 'F91_LCSC:FC-135R_L3.2-W1.5', '32.768kHz', 'C32346',
     {'1': 'X32K_1', '2': 'X32K_2'}, v1='Y1')
comp('C17', 'Device:C', C0402, '18pF', 'C1549', {'1': 'X32K_1', '2': GND}, v1='C17')
comp('C18', 'Device:C', C0402, '18pF', 'C1549', {'1': 'X32K_2', '2': GND}, v1='C18')
comp('Y2', 'F91_LCSC:X1E000210127000G', 'F91_LCSC:CRYSTAL-SMD_4P-L3.2-W2.5-BL', '24MHz', 'C89577',
     {'1': 'X24M_P', '2': GND, '3': 'X24M_N', '4': GND}, v1='Y2')

# ---------------------------------------------------------------- RF front end (copied from v1)
comp('L11', 'Device:L', 'Inductor_SMD:L_0402_1005Metric', '2.4nH', 'C97997', {'1': 'RF_P', '2': 'RF_15'}, v1='L11')
comp('C31', 'Device:C', C0402, '6.8pF', 'C1576', {'1': 'RF_15', '2': GND}, v1='C31')
comp('C11', 'Device:C', C0402, '1pF', 'C1550', {'1': 'RF_P', '2': 'RF_16'}, v1='C11')
comp('C21', 'Device:C', C0402, '1pF', 'C1550', {'1': 'RF_N', '2': GND}, v1='C21')
comp('L21', 'Device:L', 'Inductor_SMD:L_0402_1005Metric', '2.4nH', 'C97997', {'1': 'RF_N', '2': 'RF_16'}, v1='L21')
comp('L12', 'Device:L', 'Inductor_SMD:L_0402_1005Metric', '2nH', 'C18216', {'1': 'RF_16', '2': 'RF_17'}, v1='L12')
comp('C13', 'Device:C', C0402, '1pF', 'C1550', {'1': 'RF_17', '2': GND}, v1='C13')
comp('L13', 'Device:L', 'Inductor_SMD:L_0402_1005Metric', '2nH', 'C18216', {'1': 'RF_17', '2': 'RF_18'}, v1='L13')
comp('C24', 'Device:C', C0402, '12pF', 'C1547', {'1': 'RF_18', '2': 'RF_19'}, v1='C24')
comp('C51', 'Device:C', C0402, '1.8pF', 'C1553', {'1': 'RF_19', '2': 'ANT'}, v1='C51')
comp('AE1', 'Device:Antenna', 'F91_custom:ANT_TI_MEANDER_B', 'PCB antenna', '', {'1': 'ANT'}, v1='U2', bom=False)

# ---------------------------------------------------------------- display connector (v1 U3)
# Physical positions kept from v1 (the display adapter is reused). LCSC pad numbers alternate rows:
# top row  pads 1/3/5 = GND / SCL / VDDB (was NC, now battery for the SSD1306 charge pump)
# bottom row pads 2/4/6 = VDD (was VBAT) / SDA / NC
comp('J1', 'F91_LCSC:5050660622', 'F91_LCSC:CONN-SMD_5050660622', '505066-0622', 'C724122',
     {'1': GND, '3': 'SCL', '5': VBAT, '2': VDD, '4': 'SDA', '6': None,
      '7': GND, '8': GND, '9': GND, '10': GND}, v1='U3')
comp('R2', 'Device:R', R0402, '10k', 'C25744', {'1': VDD, '2': 'SCL'})  # moved out of the antenna area
comp('R3', 'Device:R', R0402, '10k', 'C25744', {'1': VDD, '2': 'SDA'})

# ---------------------------------------------------------------- battery + clamp pads
comp('BT1', 'Device:Battery_Cell', 'F91_custom:BAT_LIR2016_CLAMP', 'LIR2016', '', {'1': VBAT, '2': GND},
     v1=('ABS', 0, 0), bom=False, note='Pads under the cell (-) and under the clamp legs (+)')

# ---------------------------------------------------------------- charger + buck
# charging input: two hand-soldered Ø1.2 brass pins in plated holes reach the magnetic pogo cable through
# two Ø1.8 holes in the case back (no separate charging PCB). Reverse-polarity Schottky, ESD diode and
# pull-down sit here, next to the pins.
comp('P1', 'Connector:TestPoint', 'F91_custom:PIN_PTH_D1.25', 'charge + pin', '', {'1': CHG_IN}, bom=False)
comp('P2', 'Connector:TestPoint', 'F91_custom:PIN_PTH_D1.25', 'charge GND pin', '', {'1': GND}, bom=False)
comp('D1', 'Device:D_Schottky', 'F91_LCSC:SOD-882_L1.0-W0.6-RD', 'PMEG3002AEL', 'C478015', {'1': VIN, '2': CHG_IN})
comp('D2', 'Device:D_TVS', 'F91_LCSC:X1SON-2_L1.0-W0.6-P0.65-BI-1', 'TPD1E10B06', 'C48260', {'1': CHG_IN, '2': GND})
comp('R24', 'Device:R', R0402, '1M', 'C26083', {'1': CHG_IN, '2': GND})
comp('C30', 'Device:C', C0402, '1uF', 'C52923', {'1': VIN, '2': GND})
comp('U2', 'F91_LCSC:BQ25180YBGR', 'F91_LCSC:DSBGA-8_L1.6-W0.9-R2-C4-P0.40-BL', 'BQ25180', 'C3682423',
     {'A1': 'PMIC_INT', 'A2': VIN, 'B1': 'SCL', 'B2': SYS, 'C1': 'SDA', 'C2': VBAT, 'D1': None, 'D2': GND})  # TS/MR open: TS function off
comp('C32', 'Device:C', C0402, '10uF', 'C15525', {'1': SYS, '2': GND})
comp('C33', 'Device:C', C0402, '1uF', 'C52923', {'1': VBAT, '2': GND})
comp('U3', 'F91_LCSC:TPS62840YBGR', 'F91_LCSC:DSBGA-6_L1.4-W1.0-R2-C3-P0.40-BL', 'TPS62840', 'C2071139',
     {'A1': GND, 'A2': VDD, 'B1': SYS, 'B2': SW_BUCK, 'C1': SYS, 'C2': VSET})
comp('L1', 'F91_LCSC:MPH160809S2R2MT', 'F91_LCSC:L0603', '2.2uH', 'C98342', {'1': SW_BUCK, '2': VDD})
comp('R11', 'Device:R', R0402, '1.74k', 'C226859', {'1': VSET, '2': GND}, note='VOUT 2.0 V (TPS62840 table 1)')
comp('C34', 'Device:C', C0402, '10uF', 'C15525', {'1': VDD, '2': GND})
# battery sense divider 10M/1M (ratio 1/11, 0.38 uA; Preferred + Basic parts) for the CC2640R2 ADC
comp('R12', 'Device:R', R0402, '10M', 'C26082', {'1': VBAT, '2': 'VBAT_SENSE'})
comp('R13', 'Device:R', R0402, '1M', 'C26083', {'1': 'VBAT_SENSE', '2': GND})
comp('C35', 'Device:C', C0402, '100nF', 'C1525', {'1': 'VBAT_SENSE', '2': GND})

# ---------------------------------------------------------------- buttons: clamp (VBAT) -> N-FET gate
for i, (v1sw, v1p, gate) in enumerate([('Switch1', 'P6', 'BTN1_PAD'), ('Switch2', 'P5', 'BTN2_PAD'),
                                       ('Switch3', 'P7', 'BTN3_PAD')], start=1):
    comp(f'Q{i}', 'F91_LCSC:PMZB290UNE,315', 'F91_LCSC:X1-DFN1006-3_L1.0-W0.6-BR', 'PMZB290UNE', 'C222570',
         {'1': gate, '2': GND, '3': f'BTN{i}'})
    comp(f'R{20+i}', 'Device:R', R0402, '1M', 'C26083', {'1': gate, '2': GND})
    comp(f'SW{i}', 'Connector:TestPoint', 'F91_custom:BTN_CASTELLATION_D4', f'button {i} edge contact', '',
         {'1': gate}, v1=v1p, bom=False)
    comp(f'SW{i}B', 'Connector:TestPoint', 'F91_custom:BTN_PAD_0.7x0.6', f'button {i} pad', '',
         {'1': gate}, v1=v1sw, bom=False)

# OAD: no room for an external flash (bottom corners are taken by the board chamfer and the charging PCB),
# so firmware updates use TI on-chip OAD. DIO8/9/10/20 (LaunchPad flash pins) are left free.

# ---------------------------------------------------------------- test pads (v1 positions -> old jig still fits)
for ref, net, v1 in [('TP1', GND, 'GND'), ('TP2', VDD, 'WMCU_VDD'),
                     ('TP4', 'TMSC', 'WMCU_TMS'), ('TP5', 'TCKC', 'WMCU_TCK')]:
    # no RESET pad: cJTAG resets the CC2640R2 itself, and a long RESET_N trace to the v1 pad
    # position (next to the antenna) walls off the right-hand GND area
    # UART pads dropped for space: recovery/programming is via cJTAG (TMSC/TCKC)
    comp(ref, 'Connector:TestPoint', 'F91_custom:TP_ROUND_D0.7', net, '', {'1': net}, v1=v1, bom=False)
comp('TP9', 'Connector:TestPoint', 'F91_custom:PAD_ROUND_D1.5_B', 'BUZZ', '', {'1': 'BUZZ'}, v1='Pad5', bom=False,
     note='piezo spring contact (bottom), unused in firmware')

# ---------------------------------------------------------------- mounting holes (holder pegs)
for ref in ['MH1', 'MH2', 'MH3', 'MH4', 'MH5', 'MH6']:
    d = '0.8' if ref in ('MH1', 'MH2') else '1.1'
    comp(ref, 'Mechanical:MountingHole', f'F91_custom:NPTH_D{d}', 'hole', '', {}, v1=ref, bom=False)


def nets():
    s = set()
    for c in C:
        s.update(n for n in c['pins'].values() if n)
    return sorted(s)


if __name__ == '__main__':
    from collections import Counter
    cnt = Counter(n for c in C for n in c['pins'].values() if n)
    for n in sorted(cnt):
        print(f'{n:12s} {cnt[n]}', '  <-- single pin!' if cnt[n] == 1 else '')
    print(len(C), 'components')
