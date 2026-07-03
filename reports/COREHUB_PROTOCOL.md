# BLOCKS CoreHub — Module Protocol & Firmware Spec (reverse-engineered)

Reconstructed by static analysis of the unstripped `modulecom_daemon`, `chutil`, and `bclient`
binaries (`extracted/strings/*.strings.txt`) and the 7 `EZW2_*` module-firmware blobs. All symbol
names are verbatim from the binaries.

## Two protocol layers

```
  Android apps / BLE companion
        │  api::  (ZeroMQ over TCP — binds tcp://*:6676 & *:6677, no auth)
        ▼
  modulecom_daemon  (root, /system/vendor/bin, libzmq)
        │  corehub::  (SPI bus 5, /dev/corehub/, /sys/bus/spi/devices/spi5.0/st-manager)
        ▼
  CoreHub MCU (STM32L476)  ──►  swappable hardware modules (each its own STM32)
```

- **`corehub::`** — `modulecom_daemon`/`chutil` ↔ the CoreHub MCU over SPI. Framing enum
  `corehub::MessageHeader` = `CH` / `RC` / `RH` (command / response-continue / response-header tags).
- **`api::`** — apps / BLE companion ↔ `modulecom_daemon` over ZeroMQ. `chutil` has **zero** `api::`
  references (it only speaks CoreHub); `bclient` speaks `api::`.

## Layer 1 — `corehub::MessageID` (17 messages)
CoreHub SPI protocol. `chutil`'s `send`/`call` wires up 11; the daemon uses all 17.

| Message | Purpose |
|---|---|
| `ModuleAttachment` / `ModuleDetachment` | module hot-plug events |
| `ModuleTimedSleep` | put a module to sleep for N |
| `ModuleAuxiliarySleep` / `ModuleAuxiliaryWake` | aux-rail power control |
| `FetchRegisteredModuleList` | enumerate attached modules |
| `FetchAuxiliaryAddressList` | aux address map |
| `QueryStandardFunctions` | which StandardFunctions a module supports |
| `RequestDataExecution` / `ReportDataDemand` | request/produce sensor data |
| `FetchEBMList` / `ControlEBMStatus` | Extended Battery Module control |
| `LowBatteryWarning` | battery alert |
| `FetchModuleFirmwareVersion` | per-module FW version |
| `DownloadFirmware` / `ConfirmUpdate` | push module MCU firmware |
| `CoreHubRestart` | reboot the hub MCU |

Firmware-update status enum `E_FW_UPD_STATUS_*` (23 values): `SUCCESS`, `REBOOT`,
`TO_UPD_COREHUB`, `TO_UPD_MODULE`, `MODULE_BUSY_ERROR`, `MODULE_DETACH_ERROR`,
`MODULE_CHECK_SUM_ERROR`, … — carried inside `DownloadFirmware`/`ConfirmUpdate` payloads.

## Layer 2 — `api::MessageIDs` (28 messages) + `api::MessageKind` {Request, Response, Notification}
The ZeroMQ API a new companion app or GadgetBridge integration would speak.

- **Discovery:** `RequestAvailableModules`, `RequestAvailableCapabilities`, `RequestModulesWithCapability`
- **Capability data:** `RequestCapabilityData`, `SubscribeCapability`, `UnsubscribeCapability`,
  `ResubscribeCapability`, `SubscribeCapabilityAvailability`, `UnsubscribeCapabilityAvailability`
- **Module notifications:** `SubscribeModuleNotification`, `UnsubscribeModuleNotification`, `UnsubscribeAll`, `SubscriptionKeepAlive`
- **Direct/raw:** `BeginDirectCommunication`, `EndDirectCommunication`, `InvokeModuleFunction`
- **Config:** `SetConfigValue`, `GetConfigValue`
- **Firmware:** `UpdateFirmware`, `FirmwareUpdateProgress`
- **Events (daemon→app):** `ModuleConnected`, `ModuleDisconnected`, `ModuleError`, `ModuleNotification`,
  `SubscriptionData`, `CapabilityAvailable`, `CapabilityUnavailable`, `SubscriptionDataUnavailable`

ZeroMQ transport (broker/worker pattern): the root daemon **binds `tcp://*:6676` and
`tcp://*:6677`** — wildcard (all interfaces), no authentication; `bclient` connects
`tcp://localhost:6676/6677`; `inproc://backend` + `inproc://brokerctrl` are used internally.
Named code endpoints: `apiSocket`, `controlSocket`, `incomingSocket`, `notifySocket`, `workerSocket`.
⚠️ **Wildcard TCP bind = network-reachable on a WiFi device with zero auth — see SECURITY.md #1.**

## Drivers (in `modulecom_daemon`, `drivers/*.cpp`)
`AdventureDriver` (baro/humidity/ext-temp), `EBMDriver` (Extended Battery Module), `GPSDriver`,
`HeartRateDriver` (PPG), `PBDriver` (Programmable Button), `TorchDriver` (LED), `ModuleDriver`
(generic attach/detach base), `FirmwareUpdate`, `DirectComDriver` (raw passthrough), `StandardDriver`
(dispatches StandardFunctions).

No static `ModuleID` enum — modules are identified at runtime by UBMID + Vendor/Label strings
(the modular/third-party design).

## `blocks::Capability` (8) — the app-facing abstraction
`Altitude`, `Pressure`, `Humidity`, `Temperature`, `HeartRate`, `BatteryLevel`, `BatteryCapacity`,
`BatteryStatus`. Apps query "who can give me X" without knowing the physical module.

## `blocks::StandardFunction` (36)
- **GPS/NMEA:** `GPSGetGGA GLL GNS GSA GST GSV DTM GBS RMC VTG ZDA TXT CN`, `GPSGetLocation`,
  `GPSGetNavStatus`, `GPSGetNMEA`, `GPSStart`, `GPSStop`, `GPSReset`
- **Battery (EBM):** `EBMGetCapacity`, `EBMGetLevel`, `EBMGetStatus`, `EBMSetEnabled`
  (arg enum `corehub::EBMEnable` = `EBMChargingEnabled`/`EBMChargingDisabled`)
- **Heart rate (PPG):** `PPGGetHeartRate`, `PPGReset`, `PPGSetEnabled`
  (arg enum `corehub::PPGStatus` = `PPGOn`/`PPGOff`), `HPTReset`
- **Environment (baro):** `GetBaroPressure`, `GetBaroRelAlt`, `SetBaroRefAlt`, `GetExternalTemp`, `GetHumidity`
- **LED/Torch:** `LEDOn`, `LEDOff`, `LEDGetInfo`
- **Button:** `ButtonGetInfo`

## Module MCU firmware (`/system/etc/firmware/modules/EZW2_*.bin`)
7 blobs — **plaintext, unencrypted STM32 Cortex-M firmware** (moderate/varying entropy, in-binary
part strings, valid Cortex-M reset vectors). Reflashable/reversible.

| Blob (seq) | MCU (named in-binary) | Core | Init string |
|---|---|---|---|
| CoreHub_00 | **STM32L476JGY6** | M4 | `STM32L476JGY6 CoreHub Init OK!!` |
| FLASHLIGHT_01 | STM32L052T8Y6 | M0+ | `Flash_Light_Sensor Init OK!!` |
| BAROMETER_02 | STM32L052T8Y6 | M0+ | `HPT Module Init OK!!` |
| GPS_03 | (unnamed, same format) | M0+ | I²C struct strings |
| HRM_04 | **STM32L476JGY6** | M4 | `PPG Module Init OK!!` |
| BUTTON_05 | STM32L052T8Y6 | M0+ | `Programmable_Key Module Init OK!!` |
| EXTRA_BATT_06 | STM32L052T8Y6 | M0+ | `Extra_Battery Module Init OK!!` |

- **16-byte proprietary header:** `[0]`=seq index, `[1..3]`=magic `10 2B 01`, `[4..7]`=undetermined
  (load-addr/checksum), `[8..15]`=zero. Real Cortex-M **vector table at file offset +0x10** (SP inside
  SRAM, PC in `0x0800_xxxx` flash-alias, Thumb bit set).
- **Version encoding solved:** CoreHub format string is
  `Firmware version (Retail): %d(Type), %d(Year), %d(Week), %d(Sequence)` → the `EZW2_*_20164301`
  datecode decodes as **Year 2016, Week 43, Seq 01** (late Oct 2016), not a broken calendar date.

## Wire format & internals (disassembly-level, `api::APIServer`/`applyFirmwareUpdate`)

**ZeroMQ broker** — one `api::APIServer` singleton runs a custom **ROUTER/DEALER broker** via
`zmq_proxy_steerable` (not Majordomo): `ROUTER` bound `tcp://*:6676` (frontend), `DEALER` bound
`inproc://backend`, `PAIR` control `inproc://brokerctrl`, `PUB` bound `tcp://*:6677` (async
notifications). A fixed pool of **4 `ReceiverServerWorker` threads** services the backend.

**Message encoding** — custom **binary TLV** (`api::APIMessage` = `Header` + per-field `FieldHeader`;
`addField`/`readField<T>`), **not** JSON/protobuf/msgpack. Async correlation via `api::cid_t`
(`awaitResponse`/`awaitACK`). `api::MessageKind = {Request=0, Response=1, Notification=2}`;
Notification message-IDs occupy a separate **≥4096** range.

**Firmware transfer wire format** (`FirmwareUpdate::applyFirmwareUpdate`):
- streamed in **4064-byte (`0xFE0`) chunks** (4 KB − 32 B overhead);
- each package = **16-byte `Firmware_Package_MetaData_t`** {`fw_pkg_total_number`, `fw_pkg_number`,
  `fw_pkg_length`, `fw_pkg_checkSum`, `fw_pkg_reserve`} **+ payload**;
- integrity = **CRC32 only** (`crc32()`, `blocks::CheckSum`, `getFWFileChecksum`, `packageDataCRC`) —
  **no signature** → SECURITY.md #3.

**Firmware-update FSM** — enum `blocks::FW_UPD_PROCESSING_STATUS`, 23 states (from `getStatusText()`):
`None → Start → Ready-to-Receive → Parsing package → Update corehub → Update module → Reboot →
Success`; errors: `Check-Sum` / `Module Check-Sum` / `Bin Check-Sum`, `Same-Version`, `Old-Version`,
`Memory erase`, `Package sequence`, `Parsing package`, `Module busy`, `Have bootloader`,
`Firmware size`, `Module detach`, `Standard command`, `Abort`, `Fail`.

**Provenance:** `modulecom_daemon` self-IDs as `Blocks Module Communication Daemon v0.2.0.2`;
`bclient v0.7.0` / `libapi-v0.6.1` (build path `/build/blocks/code/client-utility`), GCC 4.9 + clang 3.8.

## What this enables
- **Write a companion / GadgetBridge integration** speaking `api::` over ZeroMQ, or over the BLE
  GATT bridge (`CRONO_SERVICE` 0xFE5A, see ROADMAP) — enumerate modules, subscribe to capability data.
- **Reflash / patch the module STM32 firmware** via the `DownloadFirmware`/`UpdateFirmware` path
  (blobs are plaintext STM32 images — openable in Ghidra as Cortex-M @ 0x08000000, vectors at +0x10).
- **`chutil`/`bclient` on-device** already drive the whole bus from a shell (scenarios: `led_stress`,
  `gps_nmea`, `error_on_attach`).
