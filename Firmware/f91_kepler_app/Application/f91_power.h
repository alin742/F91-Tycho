/******************************************************************************
 @file  f91_power.h

 @brief v2 board power: BQ25180 charger (I2C 0x6A, /INT on DIO3) and battery voltage
        (10M/1M divider on DIO23 = Board_ADC0 of the LaunchPad board file).

 Hardware (Hardware/KiCad/F91-Main_board_v2): LIR2016 -> BQ25180 BAT -> SYS -> TPS62840 -> 2.0 V.
 The BQ25180 power-up defaults are already safe (4.20 V, 10 mA, BUVLO 3.0 V); F91Power_init()
 only tightens them and turns off the watchdog and the push-button poll (saves ~1 uA).
 *****************************************************************************/
#ifndef F91_POWER_H
#define F91_POWER_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    F91_CHG_NONE = 0,     /* no charger, running from the cell */
    F91_CHG_CHARGING,     /* constant current or constant voltage phase */
    F91_CHG_DONE,         /* charger present, charge complete */
    F91_CHG_FAULT         /* OVP, safety timer, ... */
} F91ChargeState_t;

typedef struct {
    uint16_t          vbat_mV;   /* 0 if not measured */
    uint8_t           percent;   /* 0..100 */
    F91ChargeState_t  charge;
    bool              pmicOk;    /* BQ25180 answered on I2C */
} F91PowerStatus_t;

/* Low-battery thresholds (LIR2016, BQ25180 BUVLO = 3.0 V) */
#define F91_VBAT_WARN_MV      3450
#define F91_VBAT_SHUTDOWN_MV  3150

/* Callback type, called from the PIN driver (Hwi) on a /INT falling edge.
   Must only post an event to a task (I2C is blocking). */
typedef void (*F91Power_intCb_t)(void);

/* Opens the shared I2C bus, configures the BQ25180, sets up /INT and the ADC.
   Call from task context before the display is used. */
void F91Power_init(F91Power_intCb_t intCb);

/* Re-read charger status and battery voltage (task context only). */
void F91Power_update(void);

/* Last values from F91Power_update(). */
const F91PowerStatus_t *F91Power_status(void);

/* Disconnect SYS: 15 nA shutdown, the watch wakes only when a charger is plugged in.
   Only call when no charger is present (with a charger present the BQ25180 stays on). */
void F91Power_shutdown(void);

#endif /* F91_POWER_H */
