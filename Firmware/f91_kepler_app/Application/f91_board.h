/* F91 Kepler board selection. Kept in its own header so ccfg_app_ble.c can include it. */
#ifndef F91_BOARD_H
#define F91_BOARD_H

/* Board selection (pick one):
 *   IS_DEV_BOARD : CC2640R2 LaunchPad
 *   F91_HW_V2    : rechargeable v2 watch board (BQ25180 + TPS62840, buttons active-low through N-FETs)
 *   neither      : v1 watch board (CR2016, buttons active-high with pull-downs)
 */
//#define IS_DEV_BOARD
#define F91_HW_V2

#endif /* F91_BOARD_H */
