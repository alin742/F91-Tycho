/******************************************************************************

 @file  f91_kepler.c

 @brief This file contains the F91 Kepler Smart Watch application

 Target Device: cc2640r2

 ******************************************************************************
 
 Copyright (c) 2013-2021, Texas Instruments Incorporated
 All rights reserved.

 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions
 are met:

 *  Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

 *  Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

 *  Neither the name of Texas Instruments Incorporated nor the names of
    its contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

 ******************************************************************************
 
 
 *****************************************************************************/

/*********************************************************************
 * INCLUDES
 */
#include <string.h>

#include <ti/sysbios/knl/Task.h>
#include <ti/sysbios/knl/Clock.h>
#include <ti/sysbios/knl/Event.h>
#include <ti/sysbios/knl/Queue.h>
#include <ti/display/Display.h>
#include <ti/sysbios/BIOS.h>

#if defined( USE_FPGA ) || defined( DEBUG_SW_TRACE )
#include <driverlib/ioc.h>
#endif // USE_FPGA | DEBUG_SW_TRACE

#include <icall.h>
#include "util.h"
#include "att_rsp.h"

/* This Header file contains all BLE API and icall structure definition */
#include "icall_ble_api.h"

#include "devinfoservice.h"
#include "ll_common.h"

#include "peripheral.h"

#ifdef USE_RCOSC
#include "rcosc_calibration.h"
#endif //USE_RCOSC

#include "board_key.h"

#include "board.h"

#include "f91_kepler.h"
#include "f91_notification.h"
#include "f91_notification_service.h"
#include "f91_clock.h"
#include "f91_clock_service.h"
#include "f91_buttons.h"
#include "f91_utils.h"
#include "ssd1306.h"
#include "f91_power.h"
#include "f91_battery_service.h"


/*********************************************************************
 * CONSTANTS
 */

// Advertising interval when device is discoverable (units of 625us, 1636=1022.5ms)
// POWER: was 160 (100 ms). Advertising runs whenever no phone is connected, so a
// 10x longer interval cuts that cost ~10x. 1022.5 ms is one of the intervals
// Apple recommends, so iOS still finds the watch quickly (typically 1-3 s).
#define DEFAULT_ADVERTISING_INTERVAL          1636

// General discoverable mode: advertise indefinitely
#define DEFAULT_DISCOVERABLE_MODE             GAP_ADTYPE_FLAGS_GENERAL

// POWER: Connection parameters. These values satisfy Apple's accessory
// guidelines (Max >= Min + 15 ms, Max * (Latency + 1) <= 2 s,
// Max * (Latency + 1) * 3 < Timeout <= 6 s) and are accepted by Android.
// With latency 3 the watch only has to wake for ~1 in 4 connection events
// (about every 1.9 s) while idle, but still answers within ~0.5 s whenever the
// phone has data queued.

// Minimum connection interval (units of 1.25ms, 360=450ms) for automatic
// parameter update request
#define DEFAULT_DESIRED_MIN_CONN_INTERVAL     360

// Maximum connection interval (units of 1.25ms, 384=480ms) for automatic
// parameter update request
#define DEFAULT_DESIRED_MAX_CONN_INTERVAL     384

// Slave latency to use for automatic parameter update request
#define DEFAULT_DESIRED_SLAVE_LATENCY         3

// Supervision timeout value (units of 10ms, 600=6s) for automatic parameter
// update request
#define DEFAULT_DESIRED_CONN_TIMEOUT          600

// POWER: was GAPROLE_LINK_PARAM_UPDATE_WAIT_REMOTE_PARAMS, which meant the
// parameters above were never requested and the link stayed at the phone's
// default (typically 30-50 ms interval, latency 0). Now the watch asks for
// them DEFAULT_CONN_PAUSE_PERIPHERAL seconds after connecting.
#define DEFAULT_ENABLE_UPDATE_REQUEST         GAPROLE_LINK_PARAM_UPDATE_INITIATE_APP_PARAMS

// Connection Pause Peripheral time value (in seconds)
#define DEFAULT_CONN_PAUSE_PERIPHERAL         6

// Application specific event ID for HCI Connection Event End Events
#define F91_HCI_CONN_EVT_END_EVT              0x0001

// Task configuration
#define F91_TASK_PRIORITY                     2

#ifndef F91_TASK_STACK_SIZE
#define F91_TASK_STACK_SIZE                   644
#endif

// Application events
#define F91_STATE_CHANGE_EVT                  (1 << 0)
#define F91_NOTIFICATION_CHAR_CHANGE_EVT      (1 << 1)
#define F91_PAIRING_STATE_EVT                 (1 << 2)
#define F91_PASSCODE_NEEDED_EVT               (1 << 3)
#define F91_CONN_EVT                          (1 << 4)
#define F91_CLOCK_CHAR_CHANGE_EVT             (1 << 5)
#define F91_BUTTON_PRESS_EVT                  (1 << 6)
#define F91_SSD1306_DISPLAY_EVT               (1 << 7)
#define F91_POWER_EVT                         0x03       // BQ25180 /INT or the 60 s battery tick (hdr.event is uint8_t: any unused code)

// Battery/charger check period (v2 board)
#define F91_POWER_PERIOD_MS                   60000

// Internal Events for RTOS application
#define F91_ICALL_EVT                         ICALL_MSG_EVENT_ID // Event_Id_31
#define F91_QUEUE_EVT                         UTIL_QUEUE_EVENT_ID // Event_Id_30

// Bitwise OR of all events to pend on
#define F91_ALL_EVENTS                        (F91_ICALL_EVT        | \
                                               F91_QUEUE_EVT)


// Set the register cause to the registration bit-mask
#define CONNECTION_EVENT_REGISTER_BIT_SET(RegisterCause) (connectionEventRegisterCauseBitMap |= RegisterCause )
// Remove the register cause from the registration bit-mask
#define CONNECTION_EVENT_REGISTER_BIT_REMOVE(RegisterCause) (connectionEventRegisterCauseBitMap &= (~RegisterCause) )
// Gets whether the current App is registered to the receive connection events
#define CONNECTION_EVENT_IS_REGISTERED (connectionEventRegisterCauseBitMap > 0)
// Gets whether the RegisterCause was registered to recieve connection event
#define CONNECTION_EVENT_REGISTRATION_CAUSE(RegisterCause) (connectionEventRegisterCauseBitMap & RegisterCause )

/*********************************************************************
 * TYPEDEFS
 */

// App event passed from profiles.
typedef struct
{
  appEvtHdr_t hdr;  // event header.
  uint8_t *pData;  // event data
} f91Evt_t;

/*********************************************************************
 * GLOBAL VARIABLES
 */

// Display Interface
Display_Handle dispHandle = NULL;

// v2 board: periodic battery/charger check
static Clock_Struct powerClock;

/*********************************************************************
 * LOCAL VARIABLES
 */

// Entity ID globally used to check for source and/or destination of messages
static ICall_EntityID selfEntity;

// Event globally used to post local events and pend on system and
// local events.
static ICall_SyncHandle syncEvent;

// Queue object used for app messages
static Queue_Struct appMsg;
static Queue_Handle appMsgQueue;

// Task configuration
Task_Struct f91Task;
Char f91TaskStack[F91_TASK_STACK_SIZE];

// Scan response data (max size = 31 bytes)
static uint8_t scanRspData[] =
{
  // complete name
  0x07,   // length of this data
  GAP_ADTYPE_LOCAL_NAME_COMPLETE,
  'F',
  '9',
  '1',
  '-',
  'S',
  'W',

  // connection interval range
  0x05,   // length of this data
  GAP_ADTYPE_SLAVE_CONN_INTERVAL_RANGE,
  LO_UINT16(DEFAULT_DESIRED_MIN_CONN_INTERVAL),   // 450ms
  HI_UINT16(DEFAULT_DESIRED_MIN_CONN_INTERVAL),
  LO_UINT16(DEFAULT_DESIRED_MAX_CONN_INTERVAL),   // 480ms
  HI_UINT16(DEFAULT_DESIRED_MAX_CONN_INTERVAL),

  // Tx power level
  0x02,   // length of this data
  GAP_ADTYPE_POWER_LEVEL,
  0       // 0dBm
};

// Advertisement data (max size = 31 bytes, though this is
// best kept short to conserve power while advertising)
static uint8_t advertData[] =
{
  // Flags: this field sets the device to use general discoverable
  // mode (advertises indefinitely) instead of general
  // discoverable mode (advertise for 30 seconds at a time)
  0x02,   // length of this data
  GAP_ADTYPE_FLAGS,
  DEFAULT_DISCOVERABLE_MODE | GAP_ADTYPE_FLAGS_BREDR_NOT_SUPPORTED,

  // service UUID, to notify central devices what services are included
  // in this peripheral
  0x03,   // length of this data
  GAP_ADTYPE_16BIT_MORE,      // some of the UUID's, but not all
  LO_UINT16(F91_NOTIFICATION_SERVICE_UUID),
  HI_UINT16(F91_NOTIFICATION_SERVICE_UUID)
};

// GAP GATT Attributes
static uint8_t attDeviceName[GAP_DEVICE_NAME_LEN_KEPLER] = "F91 Kepler";


/*********************************************************************
 * LOCAL FUNCTIONS
 */

static void F91Kepler_init( void );
static void F91Kepler_taskFxn(UArg a0, UArg a1);

static uint8_t F91Kepler_processStackMsg(ICall_Hdr *pMsg);
static uint8_t F91Kepler_processGATTMsg(gattMsgEvent_t *pMsg);
static void F91Kepler_processAppMsg(f91Evt_t *pMsg);
static void F91Kepler_processPowerEvt(void);
static void F91Kepler_powerIntCB(void);
static void F91Kepler_powerClockCB(UArg arg);
static void F91Kepler_processStateChangeEvt(gaprole_States_t newState);
static void F91Kepler_processCharValueChangeEvt(uint8_t serviceID, uint8_t paramID);

static void F91Kepler_passcodeCB(uint8_t *deviceAddr,
                                        uint16_t connHandle,
                                        uint8_t uiInputs, uint8_t uiOutputs,
                                        uint32_t numComparison);
static void F91Kepler_pairStateCB(uint16_t connHandle, uint8_t state,
                                         uint8_t status);
static void F91Kepler_processPairState(uint8_t state, uint8_t status);
static void F91Kepler_processPasscode(uint8_t uiOutputs);

static void F91Kepler_stateChangeCB(gaprole_States_t newState);
static uint8_t F91Kepler_enqueueMsg(uint8_t event, uint8_t state,
                                              uint8_t *pData);
static void F91Kepler_connEvtCB(Gap_ConnEventRpt_t *pReport);
static void F91Kepler_processConnEvt(Gap_ConnEventRpt_t *pReport);

/*********************************************************************
 * EXTERN FUNCTIONS
 */
extern void AssertHandler(uint8 assertCause, uint8 assertSubcause);

/*********************************************************************
 * PROFILE CALLBACKS
 */

// Peripheral GAPRole Callbacks
static gapRolesCBs_t F91Kepler_gapRoleCBs =
{
  F91Kepler_stateChangeCB     // GAPRole State Change Callbacks
};

// GAP Bond Manager Callbacks
// These are set to NULL since they are not needed. The application
// is set up to only perform justworks pairing.
static gapBondCBs_t f91Kepler_BondMgrCBs =
{
  F91Kepler_passcodeCB,  // Passcode callback
  F91Kepler_pairStateCB  // Pairing / Bonding state Callback
};
/*********************************************************************
 * PUBLIC FUNCTIONS
 */

/*********************************************************************
 * The following typedef and global handle the registration to connection event
 */
typedef enum
{
   NOT_REGISTER       = 0,
   FOR_AOA_SCAN       = 1,
   FOR_ATT_RSP        = 2,
   FOR_AOA_SEND       = 4,
   FOR_TOF_SEND       = 8
}connectionEventRegisterCause_u;

// Handle the registration and un-registration for the connection event, since only one can be registered.
uint32_t       connectionEventRegisterCauseBitMap = NOT_REGISTER; //see connectionEventRegisterCause_u

/*********************************************************************
 * @fn      F91Kepler_RegistertToAllConnectionEvent()
 *
 * @brief   register to receive connection events for all the connection
 *
 * @param connectionEventRegisterCause represents the reason for registration
 *
 * @return @ref SUCCESS
 *
 */
bStatus_t F91Kepler_RegistertToAllConnectionEvent (connectionEventRegisterCause_u connectionEventRegisterCause)
{
  bStatus_t status = SUCCESS;

  // in case  there is no registration for the connection event, make the registration
  if (!CONNECTION_EVENT_IS_REGISTERED)
  {
    status = GAP_RegisterConnEventCb(F91Kepler_connEvtCB, GAP_CB_REGISTER, LINKDB_CONNHANDLE_ALL);
  }
  if(status == SUCCESS)
  {
    //add the reason bit to the bitamap.
    CONNECTION_EVENT_REGISTER_BIT_SET(connectionEventRegisterCause);
  }

  return(status);
}

/*********************************************************************
 * @fn      F91Kepler_UnRegistertToAllConnectionEvent()
 *
 * @brief   Unregister connection events
 *
 * @param connectionEventRegisterCause represents the reason for registration
 *
 * @return @ref SUCCESS
 *
 */
bStatus_t F91Kepler_UnRegistertToAllConnectionEvent (connectionEventRegisterCause_u connectionEventRegisterCause)
{
  bStatus_t status = SUCCESS;

  CONNECTION_EVENT_REGISTER_BIT_REMOVE(connectionEventRegisterCause);
  // in case  there is no more registration for the connection event than unregister
  if (!CONNECTION_EVENT_IS_REGISTERED)
  {
    GAP_RegisterConnEventCb(F91Kepler_connEvtCB, GAP_CB_UNREGISTER, LINKDB_CONNHANDLE_ALL);
  }

  return(status);
}

 /*********************************************************************
 * @fn      F91Kepler_createTask
 *
 * @brief   Task creation function for the F91 Kepler Smart Watch.
 *
 * @param   None.
 *
 * @return  None.
 */
void F91Kepler_createTask(void)
{
  Task_Params taskParams;

  // Configure task
  Task_Params_init(&taskParams);
  taskParams.stack = f91TaskStack;
  taskParams.stackSize = F91_TASK_STACK_SIZE;
  taskParams.priority = F91_TASK_PRIORITY;

  Task_construct(&f91Task, F91Kepler_taskFxn, &taskParams, NULL);
}

/*********************************************************************
 * @fn      F91Kepler_init
 *
 * @brief   Called during initialization and contains application
 *          specific initialization (ie. hardware initialization/setup,
 *          table initialization, power up notification, etc), and
 *          profile initialization/setup.
 *
 * @param   None.
 *
 * @return  None.
 */
static void F91Kepler_init(void)
{
  // ******************************************************************
  // N0 STACK API CALLS CAN OCCUR BEFORE THIS CALL TO ICall_registerApp
  // ******************************************************************
  // Register the current thread as an ICall dispatcher application
  // so that the application can send and receive messages.
  ICall_registerApp(&selfEntity, &syncEvent);

#ifdef USE_RCOSC
  RCOSC_enableCalibration();
#endif // USE_RCOSC

#if defined( USE_FPGA )
  // configure RF Core SMI Data Link
  IOCPortConfigureSet(IOID_12, IOC_PORT_RFC_GPO0, IOC_STD_OUTPUT);
  IOCPortConfigureSet(IOID_11, IOC_PORT_RFC_GPI0, IOC_STD_INPUT);

  // configure RF Core SMI Command Link
  IOCPortConfigureSet(IOID_10, IOC_IOCFG0_PORT_ID_RFC_SMI_CL_OUT, IOC_STD_OUTPUT);
  IOCPortConfigureSet(IOID_9, IOC_IOCFG0_PORT_ID_RFC_SMI_CL_IN, IOC_STD_INPUT);

  // configure RF Core tracer IO
  IOCPortConfigureSet(IOID_8, IOC_PORT_RFC_TRC, IOC_STD_OUTPUT);
#else // !USE_FPGA
  #if defined( DEBUG_SW_TRACE )
    // configure RF Core tracer IO
    IOCPortConfigureSet(IOID_8, IOC_PORT_RFC_TRC, IOC_STD_OUTPUT | IOC_CURRENT_4MA | IOC_SLEW_ENABLE);
  #endif // DEBUG_SW_TRACE
#endif // USE_FPGA

  // Create an RTOS queue for message from profile to be sent to app.
  appMsgQueue = Util_constructQueue(&appMsg);

  // POWER: the 5 s periodic clock that used to be created here did no work
  // but woke the CPU every 5 s while connected, so it has been removed.

  Display_init();
  F91_LOGGER = Display_open(Display_Type_UART, NULL);
  Display_print0(F91_LOGGER, 7, 0, ">>>LOGGER INITIALIZED<<<");

  // Set GAP Parameters: After a connection was established, delay in seconds
  // before sending when GAPRole_SetParameter(GAPROLE_PARAM_UPDATE_ENABLE,...)
  // uses GAPROLE_LINK_PARAM_UPDATE_INITIATE_BOTH_PARAMS or
  // GAPROLE_LINK_PARAM_UPDATE_INITIATE_APP_PARAMS
  // For current defaults, this has no effect.
  GAP_SetParamValue(TGAP_CONN_PAUSE_PERIPHERAL, DEFAULT_CONN_PAUSE_PERIPHERAL);

  // Setup the Peripheral GAPRole Profile. For more information see the User's
  // Guide:
  // http://software-dl.ti.com/lprf/sdg-latest/html/
  {
    // By setting this to zero, the device will go into the waiting state after
    // being discoverable for 30.72 second, and will not being advertising again
    // until re-enabled by the application
    uint16_t advertOffTime = 0;

    uint8_t enableUpdateRequest = DEFAULT_ENABLE_UPDATE_REQUEST;
    uint16_t desiredMinInterval = DEFAULT_DESIRED_MIN_CONN_INTERVAL;
    uint16_t desiredMaxInterval = DEFAULT_DESIRED_MAX_CONN_INTERVAL;
    uint16_t desiredSlaveLatency = DEFAULT_DESIRED_SLAVE_LATENCY;
    uint16_t desiredConnTimeout = DEFAULT_DESIRED_CONN_TIMEOUT;

    GAPRole_SetParameter(GAPROLE_ADVERT_OFF_TIME, sizeof(uint16_t),
                         &advertOffTime);

    GAPRole_SetParameter(GAPROLE_SCAN_RSP_DATA, sizeof(scanRspData),
                         scanRspData);
    GAPRole_SetParameter(GAPROLE_ADVERT_DATA, sizeof(advertData), advertData);

    GAPRole_SetParameter(GAPROLE_PARAM_UPDATE_ENABLE, sizeof(uint8_t),
                         &enableUpdateRequest);
    GAPRole_SetParameter(GAPROLE_MIN_CONN_INTERVAL, sizeof(uint16_t),
                         &desiredMinInterval);
    GAPRole_SetParameter(GAPROLE_MAX_CONN_INTERVAL, sizeof(uint16_t),
                         &desiredMaxInterval);
    GAPRole_SetParameter(GAPROLE_SLAVE_LATENCY, sizeof(uint16_t),
                         &desiredSlaveLatency);
    GAPRole_SetParameter(GAPROLE_TIMEOUT_MULTIPLIER, sizeof(uint16_t),
                         &desiredConnTimeout);
  }

  // Set the Device Name characteristic in the GAP GATT Service
  // For more information, see the section in the User's Guide:
  // http://software-dl.ti.com/lprf/sdg-latest/html
  GGS_SetParameter(GGS_DEVICE_NAME_ATT, GAP_DEVICE_NAME_LEN_KEPLER, attDeviceName);

  // Set GAP Parameters to set the advertising interval
  // For more information, see the GAP section of the User's Guide:
  // http://software-dl.ti.com/lprf/sdg-latest/html
  {
    // Use the same interval for general and limited advertising.
    // Note that only general advertising will occur based on the above configuration
    uint16_t advInt = DEFAULT_ADVERTISING_INTERVAL;

    GAP_SetParamValue(TGAP_LIM_DISC_ADV_INT_MIN, advInt);
    GAP_SetParamValue(TGAP_LIM_DISC_ADV_INT_MAX, advInt);
    GAP_SetParamValue(TGAP_GEN_DISC_ADV_INT_MIN, advInt);
    GAP_SetParamValue(TGAP_GEN_DISC_ADV_INT_MAX, advInt);
  }

  // Setup the GAP Bond Manager. For more information see the section in the
  // User's Guide:
  // http://software-dl.ti.com/lprf/sdg-latest/html/
  {
    // Don't send a pairing request after connecting; the peer device must
    // initiate pairing
    uint8_t pairMode = GAPBOND_PAIRING_MODE_WAIT_FOR_REQ;
    // Use authenticated pairing: require passcode.
    uint8_t mitm = TRUE;
    // This device only has display capabilities. Therefore, it will display the
    // passcode during pairing. However, since the default passcode is being
    // used, there is no need to display anything.
    uint8_t ioCap = GAPBOND_IO_CAP_DISPLAY_ONLY;
    // Request bonding (storing long-term keys for re-encryption upon subsequent
    // connections without repairing)
    uint8_t bonding = TRUE;
    // Whether to replace the least recently used entry when bond list is full,
    // and a new device is bonded.
    // Alternative is pairing succeeds but bonding fails, unless application has
    // manually erased at least one bond.
    uint8_t replaceBonds = FALSE;

    GAPBondMgr_SetParameter(GAPBOND_PAIRING_MODE, sizeof(uint8_t), &pairMode);
    GAPBondMgr_SetParameter(GAPBOND_MITM_PROTECTION, sizeof(uint8_t), &mitm);
    GAPBondMgr_SetParameter(GAPBOND_IO_CAPABILITIES, sizeof(uint8_t), &ioCap);
    GAPBondMgr_SetParameter(GAPBOND_BONDING_ENABLED, sizeof(uint8_t), &bonding);
    GAPBondMgr_SetParameter(GAPBOND_LRU_BOND_REPLACEMENT, sizeof(uint8_t), &replaceBonds);
  }

  // Initialize GATT attributes
  GGS_AddService(GATT_ALL_SERVICES);           // GAP GATT Service
  GATTServApp_AddService(GATT_ALL_SERVICES);   // GATT Service
  DevInfo_AddService();                        // Device Information Service
  F91_battery_service_AddService();            // Battery Service 0x180F (v2 board)

#ifdef F91_HW_V2
  // v2 board: charger + battery sense. Opens the shared I2C bus before the display uses it.
  F91Power_init(F91Kepler_powerIntCB);
  F91_battery_service_SetLevel(F91Power_status()->percent);
  Util_constructClock(&powerClock, F91Kepler_powerClockCB, F91_POWER_PERIOD_MS, F91_POWER_PERIOD_MS, true, 0);
#endif

  //Display_print0(F91_LOGGER, 0, 0, "Starting F91 Notification module.");
  F91Notification_init();

  //Display_print0(F91_LOGGER, 0, 0, "Starting F91 Clock module.");
  F91Clock_init();

  //Setup the buttons
  F91Buttons_init();

  // Start the Device:
  // Please Notice that in case of wanting to use the GAPRole_SetParameter
  // function with GAPROLE_IRK or GAPROLE_SRK parameter - Perform
  // these function calls before the GAPRole_StartDevice use.
  // (because Both cases are updating the gapRole_IRK & gapRole_SRK variables).
  VOID GAPRole_StartDevice(&F91Kepler_gapRoleCBs);

  // Start Bond Manager and register callback
  VOID GAPBondMgr_Register(&f91Kepler_BondMgrCBs);

  // Register with GAP for HCI/Host messages. This is needed to receive HCI
  // events. For more information, see the section in the User's Guide:
  // http://software-dl.ti.com/lprf/sdg-latest/html
  GAP_RegisterForMsgs(selfEntity);

  // Register for GATT local events and ATT Responses pending for transmission
  GATT_RegisterForMsgs(selfEntity);

  //Set default values for Data Length Extension
  {
    //Set initial values to maximum, RX is set to max. by default(251 octets, 2120us)
    #define APP_SUGGESTED_PDU_SIZE 251 //default is 27 octets(TX)
    #define APP_SUGGESTED_TX_TIME 2120 //default is 328us(TX)

    //This API is documented in hci.h
    //See the LE Data Length Extension section in the BLE-Stack User's Guide for information on using this command:
    //http://software-dl.ti.com/lprf/sdg-latest/html/cc2640/index.html
    //HCI_LE_WriteSuggestedDefaultDataLenCmd(APP_SUGGESTED_PDU_SIZE, APP_SUGGESTED_TX_TIME);
  }

#if !defined (USE_LL_CONN_PARAM_UPDATE)
  // Get the currently set local supported LE features
  // The HCI will generate an HCI event that will get received in the main
  // loop
  HCI_LE_ReadLocalSupportedFeaturesCmd();
#endif // !defined (USE_LL_CONN_PARAM_UPDATE)

  Display_print0(F91_LOGGER, 0, 0, "F91 Smart Watch");
}

/*********************************************************************
 * @fn      F91Kepler_taskFxn
 *
 * @brief   Application task entry point for the F91 Kepler Smart Watch.
 *
 * @param   a0, a1 - not used.
 *
 * @return  None.
 */
static void F91Kepler_taskFxn(UArg a0, UArg a1)
{
  // Initialize application
  F91Kepler_init();

  // Application main loop
  for (;;)
  {
    uint32_t events;

    // Waits for an event to be posted associated with the calling thread.
    // Note that an event associated with a thread is posted when a
    // message is queued to the message receive queue of the thread
    events = Event_pend(syncEvent, Event_Id_NONE, F91_ALL_EVENTS,
                        ICALL_TIMEOUT_FOREVER);
    
    if (events)
    {
      ICall_EntityID dest;
      ICall_ServiceEnum src;
      ICall_HciExtEvt *pMsg = NULL;

      // Fetch any available messages that might have been sent from the stack
      if (ICall_fetchServiceMsg(&src, &dest,
                                (void **)&pMsg) == ICALL_ERRNO_SUCCESS)
      {
        uint8 safeToDealloc = TRUE;

        if ((src == ICALL_SERVICE_CLASS_BLE) && (dest == selfEntity))
        {
          ICall_Stack_Event *pEvt = (ICall_Stack_Event *)pMsg;

          if (pEvt->signature != 0xffff)
          {
            // Process inter-task message
            safeToDealloc = F91Kepler_processStackMsg((ICall_Hdr *)pMsg);
          }
        }

        if (pMsg && safeToDealloc)
        {
          ICall_freeMsg(pMsg);
        }
      }

      // If RTOS queue is not empty, process app message.
      if (events & F91_QUEUE_EVT)
      {
        while (!Queue_empty(appMsgQueue))
        {
          f91Evt_t *pMsg = (f91Evt_t *)Util_dequeueMsg(appMsgQueue);
          if (pMsg)
          {
            // Process message.
            F91Kepler_processAppMsg(pMsg);

            // Free the space from the message.
            ICall_free(pMsg);
          }
        }
      }

      // Process event if available
      F91Notification_processEvent();
    }
  }
}

/*********************************************************************
 * @fn      F91Kepler_processStackMsg
 *
 * @brief   Process an incoming stack message.
 *
 * @param   pMsg - message to process
 *
 * @return  TRUE if safe to deallocate incoming message, FALSE otherwise.
 */
static uint8_t F91Kepler_processStackMsg(ICall_Hdr *pMsg)
{
  uint8_t safeToDealloc = TRUE;

  switch (pMsg->event)
  {
    case GATT_MSG_EVENT:
      // Process GATT message
      safeToDealloc = F91Kepler_processGATTMsg((gattMsgEvent_t *)pMsg);
      break;

    case HCI_GAP_EVENT_EVENT:
      {

        // Process HCI message
        switch(pMsg->status)
        {
          case HCI_COMMAND_COMPLETE_EVENT_CODE:
            // Process HCI Command Complete Event
            {

#if !defined (USE_LL_CONN_PARAM_UPDATE)
              // This code will disable the use of the LL_CONNECTION_PARAM_REQ
              // control procedure (for connection parameter updates, the
              // L2CAP Connection Parameter Update procedure will be used
              // instead). To re-enable the LL_CONNECTION_PARAM_REQ control
              // procedures, define the symbol USE_LL_CONN_PARAM_UPDATE
              // The L2CAP Connection Parameter Update procedure is used to
              // support a delta between the minimum and maximum connection
              // intervals required by some iOS devices.

              // Parse Command Complete Event for opcode and status
              hciEvt_CmdComplete_t* command_complete = (hciEvt_CmdComplete_t*) pMsg;
              uint8_t   pktStatus = command_complete->pReturnParam[0];

              //find which command this command complete is for
              switch (command_complete->cmdOpcode)
              {
                case HCI_LE_READ_LOCAL_SUPPORTED_FEATURES:
                  {
                    if (pktStatus == SUCCESS)
                    {
                      uint8_t featSet[8];

                      // Get current feature set from received event (bits 1-9
                      // of the returned data
                      memcpy( featSet, &command_complete->pReturnParam[1], 8 );

                      // Clear bit 1 of byte 0 of feature set to disable LL
                      // Connection Parameter Updates
                      CLR_FEATURE_FLAG( featSet[0], LL_FEATURE_CONN_PARAMS_REQ );

                      // Update controller with modified features
                      HCI_EXT_SetLocalSupportedFeaturesCmd( featSet );
                    }
                  }
                  break;

                default:
                  //do nothing
                  break;
              }
#endif // !defined (USE_LL_CONN_PARAM_UPDATE)

            }
            break;

          case HCI_BLE_HARDWARE_ERROR_EVENT_CODE:
            AssertHandler(HAL_ASSERT_CAUSE_HARDWARE_ERROR,0);
            break;

          default:
            break;
        }
      }
      break;

      default:
        // do nothing
        break;

    }

  return (safeToDealloc);
}

/*********************************************************************
 * @fn      F91Kepler_processGATTMsg
 *
 * @brief   Process GATT messages and events.
 *
 * @return  TRUE if safe to deallocate incoming message, FALSE otherwise.
 */
static uint8_t F91Kepler_processGATTMsg(gattMsgEvent_t *pMsg)
{
  // See if GATT server was unable to transmit an ATT response
  if (attRsp_isAttRsp(pMsg))
  {
    // No HCI buffer was available. Let's try to retransmit the response
    // on the next connection event.
    if( F91Kepler_RegistertToAllConnectionEvent(FOR_ATT_RSP) == SUCCESS)
    {
      // Don't free the response message yet
      return (FALSE);
    }
  }
  else if (pMsg->method == ATT_FLOW_CTRL_VIOLATED_EVENT)
  {
    // ATT request-response or indication-confirmation flow control is
    // violated. All subsequent ATT requests or indications will be dropped.
    // The app is informed in case it wants to drop the connection.

    // Display the opcode of the message that caused the violation.
    Display_print1(F91_LOGGER, 5, 0, "FC Violated: %d", pMsg->msg.flowCtrlEvt.opcode);
  }
  else if (pMsg->method == ATT_MTU_UPDATED_EVENT)
  {
    // MTU size updated
    Display_print1(F91_LOGGER, 5, 0, "MTU Size: %d", pMsg->msg.mtuEvt.MTU);
  }

  // Free message payload. Needed only for ATT Protocol messages
  GATT_bm_free(&pMsg->msg, pMsg->method);

  // It's safe to free the incoming message
  return (TRUE);
}

/*********************************************************************
 * @fn      F91Kepler_processConnEvt
 *
 * @brief   Process connection event.
 *
 * @param pReport pointer to connection event report
 */
static void F91Kepler_processConnEvt(Gap_ConnEventRpt_t *pReport)
{

  if( CONNECTION_EVENT_REGISTRATION_CAUSE(FOR_ATT_RSP))
  {
    // The GATT server might have returned a blePending as it was trying
    // to process an ATT Response. Now that we finished with this
    // connection event, let's try sending any remaining ATT Responses
    // on the next connection event.
    // Try to retransmit pending ATT Response (if any)
    if (attRsp_sendAttRsp() == SUCCESS)
    {
        // Disable connection event end notice
        F91Kepler_UnRegistertToAllConnectionEvent (FOR_ATT_RSP);
    }
  }

}

/*********************************************************************
 * @fn      F91Kepler_processAppMsg
 *
 * @brief   Process an incoming callback from a profile.
 *
 * @param   pMsg - message to process
 *
 * @return  None.
 */
static void F91Kepler_processAppMsg(f91Evt_t *pMsg)
{
  switch (pMsg->hdr.event)
  {
    case F91_STATE_CHANGE_EVT:
      {
        F91Kepler_processStateChangeEvt((gaprole_States_t)pMsg->
                                                hdr.state);
      }
      break;

    case F91_NOTIFICATION_CHAR_CHANGE_EVT:
      {
        F91Kepler_processCharValueChangeEvt(SERVICE_ID_NOTIFICATION, pMsg->hdr.state);
      }
      break;

    case F91_CLOCK_CHAR_CHANGE_EVT:
      {
        F91Kepler_processCharValueChangeEvt(SERVICE_ID_CLOCK, pMsg->hdr.state);
      }
      break;

    case F91_BUTTON_PRESS_EVT:
      {
        F91Buttons_processButtonPress((button_state_t *)(pMsg->pData));

        ICall_free(pMsg->pData);
        break;
      }

    case F91_SSD1306_DISPLAY_EVT:
      {
        ssd1306_toggle_display(false);
        ssd1306_clear();
        ssd1306_update();
      }
      break;

    case F91_POWER_EVT:
      {
        F91Kepler_processPowerEvt();
      }
      break;
    // Pairing event
    case F91_PAIRING_STATE_EVT:
      {
        F91Kepler_processPairState(pMsg->hdr.state, *pMsg->pData);

        ICall_free(pMsg->pData);
        break;
      }

    // Passcode event
    case F91_PASSCODE_NEEDED_EVT:
      {
        F91Kepler_processPasscode(*pMsg->pData);

        ICall_free(pMsg->pData);
        break;
      }

	case F91_CONN_EVT:
      {
        F91Kepler_processConnEvt((Gap_ConnEventRpt_t *)(pMsg->pData));

        ICall_free(pMsg->pData);
        break;
	  }

    default:
      // Do nothing.
      break;
  }
}

/*********************************************************************
 * @fn      F91Kepler_stateChangeCB
 *
 * @brief   Callback from GAP Role indicating a role state change.
 *
 * @param   newState - new state
 *
 * @return  None.
 */
static void F91Kepler_stateChangeCB(gaprole_States_t newState)
{
  F91Kepler_enqueueMsg(F91_STATE_CHANGE_EVT, newState, NULL);
}

/*********************************************************************
 * @fn      F91Kepler_processStateChangeEvt
 *
 * @brief   Process a pending GAP Role state change event.
 *
 * @param   newState - new state
 *
 * @return  None.
 */
static void F91Kepler_processStateChangeEvt(gaprole_States_t newState)
{
#ifdef PLUS_BROADCASTER
  static bool firstConnFlag = false;
#endif // PLUS_BROADCASTER

  switch ( newState )
  {
    case GAPROLE_STARTED:
      {
        uint8_t ownAddress[B_ADDR_LEN];
        uint8_t systemId[DEVINFO_SYSTEM_ID_LEN];

        GAPRole_GetParameter(GAPROLE_BD_ADDR, ownAddress);

        // use 6 bytes of device address for 8 bytes of system ID value
        systemId[0] = ownAddress[0];
        systemId[1] = ownAddress[1];
        systemId[2] = ownAddress[2];

        // set middle bytes to zero
        systemId[4] = 0x00;
        systemId[3] = 0x00;

        // shift three bytes up
        systemId[7] = ownAddress[5];
        systemId[6] = ownAddress[4];
        systemId[5] = ownAddress[3];

        DevInfo_SetParameter(DEVINFO_SYSTEM_ID, DEVINFO_SYSTEM_ID_LEN, systemId);

        // Display device address
        Display_print0(F91_LOGGER, 1, 0, Util_convertBdAddr2Str(ownAddress));
        Display_print0(F91_LOGGER, 2, 0, "Initialized");

        // Device starts advertising upon initialization of GAP
        uint8_t initialAdvertEnable = TRUE;
        // Set the Peripheral GAPRole Parameters
        GAPRole_SetParameter(GAPROLE_ADVERT_ENABLED, sizeof(uint8_t),
                         &initialAdvertEnable);
      }
      break;

    case GAPROLE_ADVERTISING:
      Display_print0(F91_LOGGER, 2, 0, "Advertising");
      break;

#ifdef PLUS_BROADCASTER
    // After a connection is dropped, a device in PLUS_BROADCASTER will continue
    // sending non-connectable advertisements and shall send this change of
    // state to the application.  These are then disabled here so that sending
    // connectable advertisements can resume.
    case GAPROLE_ADVERTISING_NONCONN:
      {
        uint8_t advertEnabled = FALSE;

        // Disable non-connectable advertising.
        GAPRole_SetParameter(GAPROLE_ADV_NONCONN_ENABLED, sizeof(uint8_t),
                           &advertEnabled);

        advertEnabled = TRUE;

        // Enabled connectable advertising.
        GAPRole_SetParameter(GAPROLE_ADVERT_ENABLED, sizeof(uint8_t),
                             &advertEnabled);

        // Reset flag for next connection.
        firstConnFlag = false;

        attRsp_freeAttRsp(bleNotConnected);
      }
      break;
#endif //PLUS_BROADCASTER

    case GAPROLE_CONNECTED:
      {
        linkDBInfo_t linkInfo;
        uint8_t numActive = 0;

        numActive = linkDB_NumActive();

        // Use numActive to determine the connection handle of the last
        // connection
        if ( linkDB_GetInfo( numActive - 1, &linkInfo ) == SUCCESS )
        {
          Display_print1(F91_LOGGER, 2, 0, "Num Conns: %d", (uint16_t)numActive);
          Display_print0(F91_LOGGER, 3, 0, Util_convertBdAddr2Str(linkInfo.addr));
        }
        else
        {
          uint8_t peerAddress[B_ADDR_LEN];

          GAPRole_GetParameter(GAPROLE_CONN_BD_ADDR, peerAddress);

          Display_print0(F91_LOGGER, 2, 0, "Connected");
          Display_print0(F91_LOGGER, 3, 0, Util_convertBdAddr2Str(peerAddress));
        }

        #ifdef PLUS_BROADCASTER
          // Only turn advertising on for this state when we first connect
          // otherwise, when we go from connected_advertising back to this state
          // we will be turning advertising back on.
          if (firstConnFlag == false)
          {
            uint8_t advertEnabled = FALSE; // Turn on Advertising

            // Disable connectable advertising.
            GAPRole_SetParameter(GAPROLE_ADVERT_ENABLED, sizeof(uint8_t),
                                 &advertEnabled);

            // Set to true for non-connectable advertising.
            advertEnabled = TRUE;

            // Enable non-connectable advertising.
            GAPRole_SetParameter(GAPROLE_ADV_NONCONN_ENABLED, sizeof(uint8_t),
                                 &advertEnabled);
            firstConnFlag = true;
          }
        #endif // PLUS_BROADCASTER
      }
      break;

    case GAPROLE_CONNECTED_ADV:
      Display_print0(F91_LOGGER, 2, 0, "Connected Advertising");
      break;

    case GAPROLE_WAITING:
      {
        uint8_t advertReEnable = TRUE;

        attRsp_freeAttRsp(bleNotConnected);

        // Clear remaining lines
        Display_clearLines(F91_LOGGER, 3, 5);
        
        GAPRole_SetParameter(GAPROLE_ADVERT_ENABLED, sizeof(uint8_t), &advertReEnable);
        Display_print0(F91_LOGGER, 2, 0, "Advertising");
      }
      break;

    case GAPROLE_WAITING_AFTER_TIMEOUT:
      attRsp_freeAttRsp(bleNotConnected);

      Display_print0(F91_LOGGER, 2, 0, "Timed Out");

      // Clear remaining lines
      Display_clearLines(F91_LOGGER, 3, 5);

      #ifdef PLUS_BROADCASTER
        // Reset flag for next connection.
        firstConnFlag = false;
      #endif // PLUS_BROADCASTER
      break;

    case GAPROLE_ERROR:
      Display_print0(F91_LOGGER, 2, 0, "Error");
      break;

    default:
      Display_clearLine(F91_LOGGER, 2);
      break;
  }

}

/*********************************************************************
 * @fn      F91Kepler_notificationCharValueChangeCB
 *
 * @brief   Callback indicating a characteristic
 *          value change.
 *
 * @param   paramID - parameter ID of the value that was changed.
 *
 * @return  None.
 */
void F91Kepler_notificationCharValueChangeCB(uint8_t paramID)
{
  F91Kepler_enqueueMsg(F91_NOTIFICATION_CHAR_CHANGE_EVT, paramID, 0);
}

/*********************************************************************
 * @fn      F91Kepler_clockCharValueChangeCB
 *
 * @brief   Callback indicating a characteristic
 *          value change.
 *
 * @param   paramID - parameter ID of the value that was changed.
 *
 * @return  None.
 */
void F91Kepler_clockCharValueChangeCB(uint8_t paramID)
{
  F91Kepler_enqueueMsg(F91_CLOCK_CHAR_CHANGE_EVT, paramID, 0);
}

/*********************************************************************
 * @fn      F91Kepler_buttonValueChangeCB
 *
 * @brief   Callback indicating a button
 *          value change.
 *
 * @param   paramID - parameter ID of the value that was changed.
 *
 * @return  None.
 */
void F91Kepler_buttonValueChangeCB(uint8_t *pData)
{
  F91Kepler_enqueueMsg(F91_BUTTON_PRESS_EVT, 0, (uint8_t *) pData);
}

/*********************************************************************
 * @fn      F91Kepler_displayStateChangeCB
 *
 * @brief   Callback indicating the display state has been requested.
 *
 * @param   None.
 * 
 * @return  None.
 */
void F91Kepler_displayStateChangeCB( void )
{
  F91Kepler_enqueueMsg(F91_SSD1306_DISPLAY_EVT, 0, 0);
}

/*********************************************************************
 * @fn      F91Kepler_processCharValueChangeEvt
 *
 * @brief   Process a pending Simple Profile characteristic value change
 *          event.
 *
 * @param   paramID - parameter ID of the value that was changed.
 *
 * @return  None.
 */
static void F91Kepler_processCharValueChangeEvt(uint8_t serviceID, uint8_t paramID)
{
  switch (serviceID)
  {
    case SERVICE_ID_NOTIFICATION:
      F91Notification_processCharChangeEvt(paramID);
      break;
    case SERVICE_ID_CLOCK:
      F91Clock_processCharChangeEvt(paramID);
      break;
    default:
      break;
  }
}


/*********************************************************************
 * @fn      F91Kepler_pairStateCB
 *
 * @brief   Pairing state callback.
 *
 * @return  none
 */
static void F91Kepler_pairStateCB(uint16_t connHandle, uint8_t state,
                                            uint8_t status)
{
  uint8_t *pData;

  // Allocate space for the event data.
  if ((pData = ICall_malloc(sizeof(uint8_t))))
  {
    *pData = status;

    // Queue the event.
    F91Kepler_enqueueMsg(F91_PAIRING_STATE_EVT, state, pData);
  }
}

/*********************************************************************
 * @fn      F91Kepler_processPairState
 *
 * @brief   Process the new paring state.
 *
 * @return  none
 */
static void F91Kepler_processPairState(uint8_t state, uint8_t status)
{
  if (state == GAPBOND_PAIRING_STATE_STARTED)
  {
    Display_print0(F91_LOGGER, 2, 0, "Pairing started");
  }
  else if (state == GAPBOND_PAIRING_STATE_COMPLETE)
  {
    if (status == SUCCESS)
    {
      Display_print0(F91_LOGGER, 2, 0, "Pairing success");
    }
    else
    {
      Display_print1(F91_LOGGER, 2, 0, "Pairing fail: %d", status);
    }
  }
  else if (state == GAPBOND_PAIRING_STATE_BONDED)
  {
    if (status == SUCCESS)
    {
      Display_print0(F91_LOGGER, 2, 0, "Bonding success");
    }
  }
  else if (state == GAPBOND_PAIRING_STATE_BOND_SAVED)
  {
    if (status == SUCCESS)
    {
      Display_print0(F91_LOGGER, 2, 0, "Bond save success");
    }
    else
    {
      Display_print1(F91_LOGGER, 2, 0, "Bond save failed: %d", status);
    }
  }
}

/*********************************************************************
 * @fn      F91Kepler_passcodeCB
 *
 * @brief   Passcode callback.
 *
 * @return  none
 */
static void F91Kepler_passcodeCB(uint8_t *deviceAddr,
                                        uint16_t connHandle,
                                        uint8_t uiInputs,
                                        uint8_t uiOutputs,
                                        uint32_t numComparison)
{
  uint8_t *pData;

  // Allocate space for the passcode event.
  if ((pData = ICall_malloc(sizeof(uint8_t))))
  {
    *pData = uiOutputs;

    // Enqueue the event.
    F91Kepler_enqueueMsg(F91_PASSCODE_NEEDED_EVT, 0, pData);
  }
}

/*********************************************************************
 * @fn      F91Kepler_processPasscode
 *
 * @brief   Process the Passcode request.
 *
 * @return  none
 */
static void F91Kepler_processPasscode(uint8_t uiOutputs)
{
  // This app uses a default passcode. A real-life scenario would handle all
  // pairing scenarios and likely generate this randomly.
  uint32_t passcode = B_APP_DEFAULT_PASSCODE;

  // Display passcode to user
  if (uiOutputs != 0)
  {
    Display_print1(F91_LOGGER, 4, 0, "Passcode: %d", passcode);
  }

  uint16_t connectionHandle;
  GAPRole_GetParameter(GAPROLE_CONNHANDLE, &connectionHandle);

  // Send passcode response
  GAPBondMgr_PasscodeRsp(connectionHandle, SUCCESS, passcode);
}

/*********************************************************************
 * @fn      F91Kepler_connEvtCB
 *
 * @brief   Connection event callback.
 *
 * @param pReport pointer to connection event report
 */
static void F91Kepler_connEvtCB(Gap_ConnEventRpt_t *pReport)
{
  // Enqueue the event for processing in the app context.
  if( F91Kepler_enqueueMsg(F91_CONN_EVT, 0 ,(uint8_t *) pReport) == FALSE)
  {
    ICall_free(pReport);
  }

}

/*********************************************************************
 *
 * @brief   Creates a message and puts the message in RTOS queue.
 *
 * @param   event - message event.
 * @param   state - message state.
 * @param   pData - message data pointer.
 *
 * @return  TRUE or FALSE
 */
static uint8_t F91Kepler_enqueueMsg(uint8_t event, uint8_t state,
                                           uint8_t *pData)
{
  f91Evt_t *pMsg = ICall_malloc(sizeof(f91Evt_t));

  // Create dynamic pointer to message.
  if (pMsg)
  {
    pMsg->hdr.event = event;
    pMsg->hdr.state = state;
    pMsg->pData = pData;

    // Enqueue the message.
    return Util_enqueueMsg(appMsgQueue, syncEvent, (uint8_t *)pMsg);
  }

  return FALSE;
}

/*********************************************************************
*********************************************************************/


/*********************************************************************
 * v2 board power handling (BQ25180 + battery sense)
 */

// PIN driver (Hwi) context: only queue an event, the I2C access happens in the task.
static void F91Kepler_powerIntCB(void)
{
  F91Kepler_enqueueMsg(F91_POWER_EVT, 0, 0);
}

// Clock (Swi) context: same.
static void F91Kepler_powerClockCB(UArg arg)
{
  (void)arg;
  F91Kepler_enqueueMsg(F91_POWER_EVT, 0, 0);
}

/*********************************************************************
 * @fn      F91Kepler_processPowerEvt
 *
 * @brief   Re-read charger state and battery voltage, update the Battery Service,
 *          warn on low battery and shut down before the BQ25180 undervoltage cut-off.
 */
static void F91Kepler_processPowerEvt(void)
{
  const F91PowerStatus_t *ps;

  F91Power_update();
  ps = F91Power_status();
  F91_battery_service_SetLevel(ps->percent);

  if (ps->pmicOk && ps->charge == F91_CHG_NONE && ps->vbat_mV != 0 && ps->vbat_mV < F91_VBAT_SHUTDOWN_MV)
  {
    // Show why the watch goes dark, then cut SYS (wakes when a charger is plugged in).
    ssd1306_toggle_display(true);
    ssd1306_display_full_notification(TEXT, "Battery empty");
    ssd1306_update();
    Task_sleep(2000 * (1000 / Clock_tickPeriod));
    F91Power_shutdown();
  }
}
