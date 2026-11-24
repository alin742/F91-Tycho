/******************************************************************************
 @file  f91_power.c

 @brief BQ25180 charger + battery measurement for the F91 Kepler v2 board.

 Register map: TI BQ25180 datasheet SLUSE99C, section 8.5.
 Not yet compiled or tested on hardware.
 *****************************************************************************/
#include "f91_power.h"
#include "f91_i2c.h"
#include "board.h"

#include <ti/drivers/PIN.h>
#include <ti/drivers/ADC.h>

/* ---------------------------------------------------------------- BQ25180 */
#define BQ_ADDR            0x6A
#define BQ_STAT0           0x00   /* [6:5] CHG_STAT, [0] VIN_PGOOD */
#define BQ_STAT1           0x01   /* [7] VIN_OVP, [6] BUVLO, [2] SAFETY_TMR_FAULT */
#define BQ_FLAG0           0x02   /* read-clear fault flags */
#define BQ_VBAT_CTRL       0x03   /* VBATREG = 3.5 V + code * 10 mV */
#define BQ_ICHG_CTRL       0x04   /* [7] CHG_DIS, [6:0] code: I = code + 5 mA (<= 35 mA) */
#define BQ_CHARGECTRL0     0x05
#define BQ_CHARGECTRL1     0x06   /* [5:3] BUVLO, [2] CHG_STATUS_INT_MASK */
#define BQ_IC_CTRL         0x07   /* [7] TS_EN, [1:0] WATCHDOG_SEL */
#define BQ_TMR_ILIM        0x08
#define BQ_SHIP_RST        0x09   /* [6:5] EN_RST_SHIP, [0] EN_PUSH */
#define BQ_SYS_REG         0x0A   /* [7:5] SYS_REG_CTRL */
#define BQ_MASK_ID         0x0C

#define F91_VBATREG_CODE   70     /* 3.5 V + 70 * 10 mV = 4.20 V (LIR2016) */
#define F91_ICHG_CODE      3      /* 3 + 5 = 8 mA, ~0.5C for a 16 mAh cell */
#define F91_BUVLO_3V0      0x0    /* CHARGECTRL1[5:3] = 000 -> 3.0 V */

/* ---------------------------------------------------------------- pins */
#define F91_PMIC_INT_PIN   IOID_3          /* BQ25180 /INT, open drain (DIO3) */

static PIN_State        intPinState;
static PIN_Handle       intPinHandle;
static PIN_Config       intPinTable[] = {
    F91_PMIC_INT_PIN | PIN_INPUT_EN | PIN_PULLUP | PIN_IRQ_NEGEDGE,
    PIN_TERMINATE
};
static F91Power_intCb_t userIntCb;

/* ---------------------------------------------------------------- ADC */
/* VBAT -> 10 M -> DIO23 -> 1 M -> GND, 100 nF on DIO23. Ratio 1/11. */
#define F91_VBAT_DIVIDER_NUM   11
static ADC_Handle adcHandle;

static F91PowerStatus_t status;

static void intCallback(PIN_Handle handle, PIN_Id pinId)
{
    (void)handle; (void)pinId;
    if (userIntCb) {
        userIntCb();
    }
}

static bool bqUpdateBits(uint8_t reg, uint8_t mask, uint8_t value)
{
    uint8_t v;
    if (!F91I2C_readReg(BQ_ADDR, reg, &v)) {
        return false;
    }
    v = (uint8_t)((v & ~mask) | (value & mask));
    return F91I2C_writeReg(BQ_ADDR, reg, v);
}

/* LIR2016 resting-voltage curve (approximate, 0.2C discharge) */
static uint8_t percentFromMv(uint16_t mv)
{
    static const uint16_t mvTab[] = { 3300, 3500, 3600, 3700, 3750, 3800, 3870, 3950, 4050, 4150 };
    static const uint8_t  pcTab[] = {    0,    5,   10,   20,   30,   40,   55,   70,   85,  100 };
    uint8_t i;
    if (mv <= mvTab[0]) {
        return 0;
    }
    for (i = 1; i < sizeof(mvTab) / sizeof(mvTab[0]); i++) {
        if (mv <= mvTab[i]) {
            return (uint8_t)(pcTab[i - 1] + (uint32_t)(pcTab[i] - pcTab[i - 1]) * (mv - mvTab[i - 1]) /
                             (mvTab[i] - mvTab[i - 1]));
        }
    }
    return 100;
}

void F91Power_init(F91Power_intCb_t intCb)
{
    uint8_t id;
    userIntCb = intCb;

    F91I2C_init();
    status.pmicOk = F91I2C_readReg(BQ_ADDR, BQ_MASK_ID, &id);
    if (status.pmicOk) {
        /* 1. watchdog off: otherwise the BQ25180 resets these registers 160 s after the last access */
        bqUpdateBits(BQ_IC_CTRL, 0x03, 0x03);
        /* 2. TS function off: there is no NTC on the board (TS/MR pin left open) */
        bqUpdateBits(BQ_IC_CTRL, 0x80, 0x00);
        /* 3. push-button poll off in battery mode: saves ~1 uA (no button on TS/MR) */
        bqUpdateBits(BQ_SHIP_RST, 0x01, 0x00);
        /* 4. charge settings for the LIR2016 */
        F91I2C_writeReg(BQ_ADDR, BQ_VBAT_CTRL, F91_VBATREG_CODE);
        F91I2C_writeReg(BQ_ADDR, BQ_ICHG_CTRL, F91_ICHG_CODE);          /* CHG_DIS = 0 */
        /* 5. BUVLO 3.0 V, unmask charge-status interrupts so /INT fires on plug/unplug/done */
        bqUpdateBits(BQ_CHARGECTRL1, 0x3C, (F91_BUVLO_3V0 << 3) | 0x00);
        /* 6. SYS = VBAT + 225 mV while charging (3.8 V min): keeps the buck input low */
        bqUpdateBits(BQ_SYS_REG, 0xE0, 0x00);
    }

    intPinHandle = PIN_open(&intPinState, intPinTable);
    if (intPinHandle) {
        PIN_registerIntCb(intPinHandle, intCallback);
    }

    {
        ADC_Params p;
        ADC_Params_init(&p);
        adcHandle = ADC_open(Board_ADC0, &p);   /* LaunchPad board file: ADC0 = DIO23 */
    }

    F91Power_update();
}

void F91Power_update(void)
{
    uint8_t s0 = 0, s1 = 0, f0 = 0;

    if (status.pmicOk && F91I2C_readReg(BQ_ADDR, BQ_STAT0, &s0) && F91I2C_readReg(BQ_ADDR, BQ_STAT1, &s1)) {
        F91I2C_readReg(BQ_ADDR, BQ_FLAG0, &f0);      /* clears latched faults */
        if (s1 & (0x80 | 0x04)) {
            status.charge = F91_CHG_FAULT;
        } else if (!(s0 & 0x01)) {
            status.charge = F91_CHG_NONE;
        } else {
            switch ((s0 >> 5) & 0x03) {
                case 1: case 2: status.charge = F91_CHG_CHARGING; break;
                case 3:         status.charge = F91_CHG_DONE;     break;
                default:        status.charge = F91_CHG_NONE;     break;
            }
        }
    }

    if (adcHandle) {
        uint16_t raw;
        if (ADC_convert(adcHandle, &raw) == ADC_STATUS_SUCCESS) {
            uint32_t uv = ADC_convertRawToMicroVolts(adcHandle, raw);
            status.vbat_mV = (uint16_t)((uv * F91_VBAT_DIVIDER_NUM) / 1000);
            status.percent = percentFromMv(status.vbat_mV);
        }
    }
}

const F91PowerStatus_t *F91Power_status(void)
{
    return &status;
}

void F91Power_shutdown(void)
{
    if (status.pmicOk) {
        /* EN_RST_SHIP = 01: shutdown, wake on adapter insert only (15 nA) */
        bqUpdateBits(BQ_SHIP_RST, 0x60, 0x20);
    }
}
