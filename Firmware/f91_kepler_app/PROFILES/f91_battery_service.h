/******************************************************************************
 @file  f91_battery_service.h

 @brief Standard BLE Battery Service (0x180F) with the Battery Level characteristic
        (0x2A19, read-only, percent). Value is set by the app from F91Power_status().
 *****************************************************************************/
#ifndef F91_BATTERY_SERVICE_H
#define F91_BATTERY_SERVICE_H

#include <stdint.h>
#include "bcomdef.h"

bStatus_t F91_battery_service_AddService(void);
void      F91_battery_service_SetLevel(uint8_t percent);

#endif /* F91_BATTERY_SERVICE_H */
