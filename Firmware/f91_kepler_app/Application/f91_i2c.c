/******************************************************************************
 @file  f91_i2c.c

 @brief Shared I2C0 bus (see f91_i2c.h).
 *****************************************************************************/
#include <stddef.h>
#include "f91_i2c.h"
#include "board.h"

#define F91_I2C_RETRIES   3

static I2C_Handle i2cHandle = NULL;

I2C_Handle F91I2C_init(void)
{
    if (i2cHandle == NULL) {
        I2C_Params params;
        I2C_Params_init(&params);
        params.bitRate = I2C_400kHz;          /* blocking mode (default) */
        i2cHandle = I2C_open(Board_I2C0, &params);
    }
    return i2cHandle;
}

I2C_Handle F91I2C_handle(void)
{
    return i2cHandle;
}

bool F91I2C_writeReg(uint8_t addr, uint8_t reg, uint8_t value)
{
    uint8_t tx[2] = { reg, value };
    I2C_Transaction t;
    uint8_t i;

    if (i2cHandle == NULL) {
        return false;
    }
    t.slaveAddress = addr;
    t.writeBuf = tx;
    t.writeCount = 2;
    t.readBuf = NULL;
    t.readCount = 0;
    for (i = 0; i < F91_I2C_RETRIES; i++) {
        if (I2C_transfer(i2cHandle, &t)) {
            return true;
        }
    }
    return false;
}

bool F91I2C_readReg(uint8_t addr, uint8_t reg, uint8_t *value)
{
    I2C_Transaction t;
    uint8_t i;

    if (i2cHandle == NULL) {
        return false;
    }
    t.slaveAddress = addr;
    t.writeBuf = &reg;
    t.writeCount = 1;
    t.readBuf = value;
    t.readCount = 1;
    for (i = 0; i < F91_I2C_RETRIES; i++) {
        if (I2C_transfer(i2cHandle, &t)) {
            return true;
        }
    }
    return false;
}
