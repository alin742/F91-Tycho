/******************************************************************************
 @file  f91_i2c.h

 @brief Shared I2C0 bus for the SSD1306 display and the BQ25180 charger (v2 board).

 The TI I2C driver serialises transfers between tasks, so both drivers can use the
 same handle. Each driver must use its own I2C_Transaction.
 *****************************************************************************/
#ifndef F91_I2C_H
#define F91_I2C_H

#include <stdbool.h>
#include <stdint.h>
#include <ti/drivers/I2C.h>

/* Open the bus once (idempotent). Returns NULL on failure. */
I2C_Handle F91I2C_init(void);

/* The open handle (NULL before F91I2C_init). */
I2C_Handle F91I2C_handle(void);

/* Register helpers with bounded retries. Return true on success. */
bool F91I2C_writeReg(uint8_t addr, uint8_t reg, uint8_t value);
bool F91I2C_readReg(uint8_t addr, uint8_t reg, uint8_t *value);

#endif /* F91_I2C_H */
