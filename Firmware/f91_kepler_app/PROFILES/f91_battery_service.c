/******************************************************************************
 @file  f91_battery_service.c

 @brief Battery Service 0x180F / Battery Level 0x2A19 (read). Same structure as
        f91_clock_service.c. Not yet compiled.
 *****************************************************************************/
#include <string.h>
#include "bcomdef.h"
#include "osal.h"
#include "gatt.h"
#include "gatt_uuid.h"
#include "gattservapp.h"
#include "gatt_profile_uuid.h"
#include "f91_battery_service.h"

static CONST uint8_t battServUUID[ATT_BT_UUID_SIZE]  = { LO_UINT16(BATT_SERV_UUID),  HI_UINT16(BATT_SERV_UUID) };
static CONST uint8_t battLevelUUID[ATT_BT_UUID_SIZE] = { LO_UINT16(BATT_LEVEL_UUID), HI_UINT16(BATT_LEVEL_UUID) };

static CONST gattAttrType_t battService = { ATT_BT_UUID_SIZE, battServUUID };
static uint8_t battLevelProps = GATT_PROP_READ;
static uint8_t battLevel = 100;

static gattAttribute_t battAttrTbl[] =
{
  { { ATT_BT_UUID_SIZE, primaryServiceUUID }, GATT_PERMIT_READ, 0, (uint8_t *)&battService },
  { { ATT_BT_UUID_SIZE, characterUUID },      GATT_PERMIT_READ, 0, &battLevelProps },
  { { ATT_BT_UUID_SIZE, battLevelUUID },      GATT_PERMIT_READ, 0, &battLevel },
};

static bStatus_t battReadAttrCB(uint16_t connHandle, gattAttribute_t *pAttr, uint8_t *pValue,
                                uint16_t *pLen, uint16_t offset, uint16_t maxLen, uint8_t method)
{
  (void)connHandle; (void)maxLen; (void)method;
  if (offset > 0) {
    return ATT_ERR_ATTR_NOT_LONG;
  }
  if (pAttr->type.len == ATT_BT_UUID_SIZE &&
      BUILD_UINT16(pAttr->type.uuid[0], pAttr->type.uuid[1]) == BATT_LEVEL_UUID) {
    *pLen = 1;
    pValue[0] = battLevel;
    return SUCCESS;
  }
  return ATT_ERR_ATTR_NOT_FOUND;
}

static CONST gattServiceCBs_t battCBs = { battReadAttrCB, NULL, NULL };

bStatus_t F91_battery_service_AddService(void)
{
  return GATTServApp_RegisterService(battAttrTbl, GATT_NUM_ATTRS(battAttrTbl),
                                     GATT_MAX_ENCRYPT_KEY_SIZE, &battCBs);
}

void F91_battery_service_SetLevel(uint8_t percent)
{
  battLevel = (percent > 100) ? 100 : percent;
}
