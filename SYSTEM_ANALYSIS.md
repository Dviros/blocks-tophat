# BLOCKS "tophat" Firmware — System Analysis

**Device:** BLOCKS modular smartwatch prototype, codename `tophat`
**ODM:** Compal | **SoC:** Qualcomm Snapdragon Wear 2100 (MSM8909w)
**OS:** Android 6.0.1 (MMB29M), build `eng.tincho5588.20171123.001812`, test-keys, user build
**Underlying platform vendor:** Cronologics Corp. (identified from `com.cronologics.*` package names baked into the Crono* APKs). Cronologics was acquired by **Google in December 2016** (for the Android Wear team); BLOCKS then had to take over OS development itself, and this build — a self-maintained fork of the Cronologics stack — carries a Nov 23, 2017 date. *(Correction: an earlier draft misattributed the acquisition to Fossil; the acquirer was Google, Dec 2016.)*
**Analysis scope:** `extracted/system/` (full /system ext4 rdump) and `extracted/boot/ramdisk_ro/` (boot ramdisk)
**Method:** static analysis only (`strings`, `unzip -l`, `grep -r`, `file`) — no device touched, no `aapt`/manifest decoding tool used; package names inferred from `classes.dex` string tables inside each APK.

---

## 1. build.prop — Full Summary

File: `extracted/system/build.prop` (303 lines, read in full)

### Identity / build
| Property | Value |
|---|---|
| `ro.build.id` | `MMB29M` |
| `ro.build.version.release` | `6.0.1` (SDK 23) |
| `ro.build.version.security_patch` | `2016-05-01` — **unpatched for ~18 months at ship, now ~8.5 years stale** |
| `ro.build.type` / `ro.build.tags` | `user` / `test-keys` |
| `ro.build.flavor` | `blocks_tophat-user` |
| `ro.product.model` | `BLOCKS modular smartwatch` |
| `ro.product.brand` | `BLOCKS` |
| `ro.product.name` / `.device` / `.board` | `blocks_tophat` / `tophat` / `msm8909` |
| `ro.product.manufacturer` | `Compal` (ODM) |
| `ro.product.cpu.abilist` | `armeabi-v7a,armeabi` (32-bit only, no arm64) |
| `ro.build.fingerprint` | `BLOCKS/blocks_tophat/tophat:6.0.1/MMB29M/tincho558811230021:user/test-keys` |
| `ro.build.characteristics` | `nosdcard,watch` |
| `ro.build.expect.bootloader` | `TOPHAT.00034.16370` |
| `ro.expect.recovery_id` | `0x9fdba1112ad3d0...` (a recovery partition hash is pinned) |

### Hardware/feature flags of note
- **Density**: `ro.sf.lcd_density=240` (a commented-out `160` line for "8909 wearables" was left in — suggests density was tuned late for this specific watch's round display)
- **Ambient/AOD display**: `persist.sys.ambient_brightness=60`, `persist.sys.ambient_low_bit=true`, `persist.sys.ambient_burn_in=true` — always-on-display with burn-in protection and low-bit-color mode, standard Android Wear ambient-mode plumbing
- **Containers**: `persist.sys.containers_count=3` — BLOCKS-specific; ties to the "Container" apps (`BlocksContainer`, `CronoContainerSdk`) — likely governs how many module-driven "app containers" can be active/cached at once
- **BLE**: `persist.sys.ble_company_id=1077` (this is Qualcomm's assigned Bluetooth SIG company ID, not a custom BLOCKS one), `persist.sys.ble_bogus_uuid=0000181D-...` (0x181D = standard BLE Weight Scale service UUID, oddly reused as a "bogus" placeholder)
- **Sensors**: telephony/gesture/orientation/tilt/tap/proximity/heart-rate sensors are explicitly **disabled** (`ro.qti.sensors.*=false`) except `ro.qti.sensors.wrist_tilt=true` (for raise-to-wake) — consistent with sensing being delegated to external Blocks modules via CoreHub rather than onboard SoC sensors
- **WearQSTA**: `ro.sensors.wearqstp=1` — Qualcomm's Wear Sensor/Quick-start-type-app framework enabled
- **Battery**: `ro.cutoff_voltage_mv=3200` — hardware low-battery cutoff tuned for the watch's small cell
- **CPU**: `ro.core_ctl_min_cpu=2` / `ro.core_ctl_max_cpu=4` (quad-core core-control tuning for MSM8909's 4x Cortex-A7)
- **Heap**: Dalvik heap is small and wearable-tuned (`dalvik.vm.heapsize=256m`, `heapstartsize=8m`, `heapgrowthlimit=96m`)
- **USB default composition**: `persist.sys.usb.config=diag,serial_smd,rmnet_qti_bam,adb` — **ADB is enabled by default in the USB composition string** (see §7)
- **Telephony**: `rild.libpath=/system/vendor/lib/libril-qc-qmi-1.so`, `ril.subscription.types=NV,RUIM`, `telephony.lteOnCdmaDevice=1`, default network mode 9 (CDMA/LTE) — **full modem/RIL stack is present and wired up**, even though this is a fashion/module smartwatch; msm8909w is the same silicon used in some cellular-capable wearables, so the modem path was inherited from the reference platform rather than custom-built for tophat
- **FM transmitter**: explicitly disabled (`ro.fm.transmitter=false`)
- **WFD (Wireless Display)**: `persist.debug.wfd.enable=1`, `persist.hwc.enable_vds=1` — Google WFD/Miracast settings access enabled, unusual for a watch, likely inherited unmodified from the Qualcomm reference `system.prop`
- **GPU/graphics debug**: `debug.sf.hw=1`, `debug.egl.hw=1`, `debug.mdpcomp.logs=0`, dirty-rect/ABC composition enabled — standard perf tuning, not watch-specific
- **Ringtone/UI defaults**: `ro.config.ringtone=Ring_Synth_04.ogg` — Nexus/AOSP stock, not re-skinned for BLOCKS branding at the property level

### BLOCKS/Compal-specific properties
Only a handful of properties are truly BLOCKS-authored (the rest is stock Qualcomm `device/qcom/msm8909w/system.prop`):
- `ro.product.brand=BLOCKS`, `ro.product.name=blocks_tophat`, `ro.product.device=tophat`
- `ro.build.flavor=blocks_tophat-user`
- `ro.build.fingerprint` / `ro.build.description` (BLOCKS vendor string)
- `ro.build.expect.bootloader=TOPHAT.00034.16370`
- `persist.sys.containers_count=3`, `persist.sys.ambient_*` (product-tier, plausibly Cronologics-authored rather than raw Qualcomm)
- `ro.frp.pst=/dev/block/bootdevice/by-name/config` (Factory Reset Protection partition — present but see §7, FRP is effectively moot on an unlocked test-keys device)

**Nothing unusual/alarming found** beyond what's expected for a 2017 pre-production Snapdragon Wear reference build — no hardcoded credentials, no obvious backdoor properties, no leftover carrier-specific config beyond generic CDMA defaults.

---

## 2. App Inventory

`extracted/system/app/` — **27 packages** (AOSP + Qualcomm stock, no BLOCKS branding)
`extracted/system/priv-app/` — **50 packages** (mix of AOSP privileged apps, Qualcomm services, and the BLOCKS/Cronologics platform)

### BLOCKS-CUSTOM apps (in `priv-app/`, package names recovered from `classes.dex` string tables)

These form two layers: the **Cronologics platform layer** (OS shell: launcher, settings, systemUI, health/notification providers — likely largely unbranded/reusable Cronologics IP) and the **BLOCKS module-app layer** (per-hardware-module apps built on `com.blocks.api`/`com.blocks.ui`).

| Directory | Inferred package | Role |
|---|---|---|
| `CronoLauncher` | `com.cronologics.launcher` | Home-screen / watch launcher |
| `CronoSettings` | `com.cronologics.launcher` (+ `.ambient`, `.tutorial`) | Settings app |
| `CronoSettingsProvider` | (settings backing content provider) | Settings storage |
| `CronoSettingsWifi` | — | Wi-Fi settings sub-app |
| `CronoSystemUI` | — | Status bar / SystemUI replacement |
| `CronoOnboarding` | `com.cronologics.launcher`, `.tutorial`, `com.blocks.app.watchface` | First-boot setup flow (explicitly references BLOCKS watchface pkg) |
| `CronoTutorial` | `com.cronologics.launcher`, `.tutorial` | In-watch tutorial/help |
| `CronoAmbient` | `com.cronologics.ambient` | Always-on-display controller |
| `CronoAnalyticsProvider` | `com.cronologics.analytics` | Usage analytics content provider |
| `CronoBridgeService` | — (no plain-text pkg string found in dex; likely obfuscated/native) | **Bridges the Crono OS layer to hardware** — candidate glue between UI shell and `modulecom_daemon`/CoreHub, see §3 |
| `CronoContainerSdk` | — | SDK backing the "container" app model shared by Blocks module-apps |
| `CronoHealthProvider` | `com.cronologics.health.provider` | Health-data content provider (steps/HR aggregation) |
| `CronoNotificationService` | `com.cronologics.responses` | Notification handling / quick-responses |
| `CronoResponses` | (3.2 MB — largest Crono app, likely bundles response templates/ML) | Smart-reply / canned response engine |
| `CronoKeyboard` | — | IME |
| `BlocksContainer` | `com.blocks.api`, `com.blocks.app.{adventure,battery,button,compass,container,gps,health}`, `com.blocks.ui` | **Central "container" app** — hosts/dispatches to all per-module Blocks apps; references nearly every module package, strongly suggesting this is the module-manager/hub UI |
| `BlocksOverview` | (not confirmed via dex grep, name implies module dashboard) | Likely the "which modules are attached" overview screen |
| `BlocksAdventure` | `com.blocks.app.adventure` | Outdoor/adventure module app (barometer/humidity/temp — see EBM/Adventure driver in §3) |
| `BlocksBattery` | `com.blocks.api`, `com.blocks.ui` | Extra Battery Module (EBM) UI |
| `BlocksButton` | `com.blocks.api`, `.app.adventure`, `.app.battery`, `.app.gps`, `.app.health` | Programmable Button module app (cross-references many modules — it's an action launcher) |
| `BlocksCompass` | `com.blocks.app.compass` | Compass module app |
| `BlocksDecibel` | `com.blocks.ui` | Sound-level (decibel meter) module app |
| `BlocksGPS` | `com.blocks.api`, `.app.gps`, `.ui` (17.3 MB — bundles offline maps/GPS assets) | GPS module app |
| `BlocksHealth` | `com.blocks.api`, `.ui` | Health/heart-rate module app |
| `BlocksNavigator` | `com.blocks.api`, `.app.navigator`, `.ui` (18.1 MB, largest APK in the image) | Navigation module app (maps) |
| `BlocksTorch` | `com.blocks.api`, `.ui` | Flashlight/Torch module app |
| `BlocksWatchfaces` | `com.blocks.app.watchface` (5.0 MB) | Watchface picker/gallery |

**Bottom line:** BLOCKS-custom apps total **~26 packages** across the `Crono*` (OS shell, Cronologics-authored) and `Blocks*` (module-app, hardware-facing) families — over half of everything in `priv-app/`.

### Stock AOSP (in `app/` and `priv-app/`)
`app/`: `CaptivePortalLogin`, `CertInstaller`, `DocumentsUI`, `HTMLViewer`, `KeyChain`, `OpenWnn`, `PacProcessor`, `PicoTts`, `Stk`, `TimeService`, `UserDictionaryProvider`, `WAPPushManager`, `webview`, `remove-core-packages` (a placeholder/removal-marker package, common in AOSP builds).
`priv-app/`: `BackupRestoreConfirmation`, `CalendarProvider`, `CellBroadcastReceiver`, `ContactsProvider`, `DefaultContainerService`, `DownloadProvider`, `ExternalStorageProvider`, `InputDevices`, `MediaProvider`, `OneTimeInitializer`, `PackageInstaller`, `ProxyHandler`, `SettingsProvider`, `SharedStorageBackup`, `Shell`, `StatementService`, `WallpaperCropper`.
Note: `BluetoothMidiService`, `Bluetooth`, `BluetoothExt` in `app/` are stock AOSP Bluetooth stack (not custom).

### Qualcomm / QTI stock
`priv-app/CNEService`, `com.qualcomm.location`, `qcrilmsgtunnel` (radio-interface-layer message tunnel — telephony debug path), `contextualmodedozeservice` (QTI's Doze-mode power service). `AntHalService` in `app/` is the ANT+ wireless HAL (used for fitness sensor pairing — stock Qualcomm/ANT component, plausible fit for a wearable but not BLOCKS-authored).

### Test/sample components left in
`SampleAuthenticatorService` (app/), `SecureSampleAuthService` (priv-app/) — Qualcomm SDK sample code, should not ship in a production build (see §7/§8).

---

## 3. BLOCKS-Specific Components — The Crown Jewel

### The core daemon: `modulecom_daemon`
- **Path:** `extracted/system/vendor/bin/modulecom_daemon` (20.9 MB, ELF32 ARM, dynamically linked, **not stripped**, contains full `debug_info`)
- **Launched by:** `extracted/boot/ramdisk_ro/init.qcom.rc`:
  ```
  service modulecom_daemon /system/vendor/bin/modulecom_daemon
      class main
      user root
      group root
  ```
  This is the **only service defined in `init.qcom.rc`** (everything else in that file is `import init.qcom.base.rc`) — i.e. BLOCKS engineers repurposed the normally-stock `init.qcom.rc` file specifically to inject this one service. Runs as **root:root**, class `main` (starts at normal boot, not `late_start`/`core`).
- **SELinux domain:** `extracted/boot/ramdisk_ro/file_contexts` line 320-321:
  ```
  #line 1 "device/blocks/tophat/sepolicy/file_contexts"
  /system/vendor/bin/modulecom_daemon             u:object_r:modulecom_daemon_exec:s0
  ```
  This is the **only BLOCKS-authored sepolicy fragment found anywhere** in the compiled `sepolicy` binary (confirmed via `strings sepolicy | grep -i modulecom` → `modulecom_daemon`, `modulecom_daemon_exec`, `modulecom_daemon_tmpfs` — three domains total, no others). It does not appear in `service_contexts` at all, meaning it never registers a Binder/`ServiceManager` service — see IPC mechanism below.
- **Build provenance string embedded in binary:** `/build/blocks/code/modulecom-daemon` — confirms an internal BLOCKS build tree path `blocks/code/modulecom-daemon`.
- **Self-identifying string:** `"Blocks Module Communication Daemon v0.2.0.2"` — versioned independently from the OS, v0.2.x suggests early/prototype development stage.

### Architecture (recovered purely from symbol/string tables — see §4 for full evidence)
`modulecom_daemon` implements a hub called **"CoreHub"** — evidently a microcontroller (or dedicated coprocessor) that sits between the SoC and the physically-attached hardware modules ("straps"). The daemon:
1. Talks to the CoreHub MCU over **SPI** (device node `/sys/bus/spi/devices/spi5.0/st-manager` — the `st-` prefix strongly suggests an **STMicroelectronics** part, e.g. an STM32 acting as the CoreHub MCU).
2. Exposes a local API to Android apps via **ZeroMQ (libzmq)** IPC over named sockets (symbols: `apiSocket`, `controlSocket`, `incomingSocket`, `notifySocket`, `workerSocket`, `broker sockets` — a broker/worker pattern, not raw Binder). This explains why it never appears in `service_contexts`.
3. Implements **per-module-type driver classes** (recovered via C++ mangled symbols and DriverEntry templates):
   - `blocks::AdventureDriver` ("Blocks Adventure Driver" — barometer/humidity/external-temp: `GetBaroPressure`, `GetHumidity`, `GetExternalTemp`)
   - `blocks::EBMDriver` ("Blocks EBM Driver" = **Extra Battery Module**: `EBMGetCapacity`, `EBMGetLevel`, `EBMGetStatus`, `EBMSetEnabled`, charging enable/disable)
   - `blocks::GPSDriver` ("Blocks GPS Driver": NMEA-style sentence parsing — `GPSGetGGA`, `GPSGetGBS`, `GPSGetDTM`, `GPSGetCN`, location/altitude)
   - `blocks::HeartRateDriver` ("Blocks Heart Rate Driver": `PPGGetHeartRate` — photoplethysmography sensor)
   - `blocks::PBDriver` ("Blocks Programmable Button Driver")
   - `blocks::TorchDriver` ("Blocks Torch Driver")
   - `blocks::ModuleDriver` (generic module enumeration/capability driver — `handleRequestAvailableModulesWithCapability`)
   - `blocks::DirectComDriver` (raw passthrough channel: `BeginDirectCommunication`/`EndDirectCommunication` — a debug/bring-up bypass path straight to a module, bypassing higher-level parsing)
   - `blocks::FirmwareUpdate` (OTA update path for module MCU firmware — see below)
4. Exposes a **`blocks::Capability`** flag enum (bitmask, `EnumFlags<blocks::Capability>`) that abstracts sensor capability across driver types — e.g. `Capability::Temperature`, `::Pressure`, `::Humidity`, `::Altitude`, `::HeartRate`, `::BatteryLevel`, `::BatteryCapacity`, `::BatteryStatus` — a genuinely well-designed capability-query abstraction layer letting apps ask "which attached module can give me X" without knowing which physical module it is.
5. Implements **module firmware OTA**: strings `"Begin Downloading new CoreHub-FW..."`, `E_FW_UPD_STATUS_TO_UPD_COREHUB`, `E_FW_UPD_STATUS_TO_UPD_MODULE`, `E_FW_UPD_STATUS_MODULE_BUSY_ERROR`, `E_FW_UPD_STATUS_MODULE_DETACH_ERROR`, `E_FW_UPD_STATUS_MODULE_CHECK_SUM_ERROR`, reading firmware blobs from `/system/etc/firmware/modules/` (see §6 for the actual `.bin` files present).
6. Debug web UI: string `/data/modulecom_daemon.html` — the daemon appears to serve (or at least reference) a local HTML status page written to `/data`, i.e. a developer-only web dashboard left compiled into the shipped binary.
7. `"Emergency Mode detected for module 0x%x."` — modules have an "emergency mode" fault state the daemon detects and presumably surfaces to apps.

### Companion CLI tools (also in `extracted/system/vendor/bin/`)
- **`chutil`** — "Blocks CoreHub Utility v1.2.1", build path `/build/blocks/code/corehub-utility`. A debug CLI that talks to `/dev/corehub/` and can `list modules|messages|functions|scenarios`, run named test **scenarios** (e.g. `scenario led_stress 12345`), and send raw CoreHub messages (`ConfirmUpdate`, `CoreHubRestart`, `FetchModuleFirmwareVersion`, `FetchRegisteredModuleList`, `DownloadFirmware`). This is effectively the **factory/engineering test tool for the module bus** and ships in the production `user` build.
- **`bclient`** — "Blocks API Client Utility v0.7.0", build path `/build/blocks/code/client-utility`. A CLI over the same ZeroMQ API surface `modulecom_daemon` exposes to apps — lets an engineer query connected modules/capabilities from a shell instead of writing an app.

### What is CoreHub, physically?
Best-evidence conclusion: **CoreHub is a dedicated microcontroller (likely ST-brand, given `st-manager`) embedded in the watch's "core"/mainboard**, which itself talks over SPI to the Android SoC (via `spi5.0`) on one side and to the swappable hardware modules ("straps"/"bands") on its own separate module-facing bus on the other side (see §4 — no i2c/uart wiring for the module-facing side was found in the extracted files, meaning that link is either handled entirely inside CoreHub firmware, or those artifacts live in a CoreHub firmware SDK not present in this Android image). Android's role is reduced to: (a) SPI-transact with CoreHub via `modulecom_daemon`, (b) surface a clean `blocks::Capability`-based API to apps via ZeroMQ, (c) push firmware updates down to CoreHub and, transitively, to each attached module.

---

## 4. The Module Bus — Mechanism and Evidence

**Mechanism: SPI**, not I2C/UART/GPIO-bitbang as might be assumed for a modular connector system.

### Direct evidence
1. `extracted/boot/ramdisk_ro/init.rc` line ~469-471:
   ```
   /* Corehub permission for IPC server */
   chmod 666 /sys/bus/spi/devices/spi5.0/st-manager
   ```
   This is the **only place in the entire ramdisk** where module-bus device permissions are set — it is set inline in generic `init.rc` (not in a BLOCKS-specific `.rc` file), with a comment explicitly naming "Corehub" and "IPC server". World-writable (666) permission on an SPI device node is unusually permissive — normally SPI HAL access would be gated via SELinux + a dedicated group, but here it's opened wide, consistent with an early prototype/bring-up shortcut.
2. `modulecom_daemon` binary string: `/sys/bus/spi/devices/spi5.0/st-manager` (same path, confirming the daemon opens exactly this node).
3. `chutil` binary string: `/dev/corehub/` — a second, higher-level device-node namespace the CLI tool expects (likely a udev-created symlink or extra kernel driver's chardev; the raw node itself wasn't found as a file inside `extracted/system` since `/dev` is populated by the kernel/ueventd at runtime, not present in the static image).

### What was checked and NOT found (ruling out alternatives)
- **No I2C/UART/GPIO configuration specific to a "module" bus** was found in `ueventd.rc`, `ueventd.qcom.rc`, or `extracted/system/etc/` — all I2C/UART references in those files are stock Qualcomm (Bluetooth `hci_uart`, NFC, sensors), unrelated to Blocks modules.
- No `service_contexts` entry for `modulecom_daemon` — it is **not** a Binder service; IPC to apps is via ZeroMQ over Unix domain sockets (`apiSocket`/`controlSocket`/`notifySocket`/`workerSocket`, all `libzmq` symbols confirmed in the binary).
- No dedicated udev/ueventd rule creates or chmods `/dev/corehub` — permissions for the actual module-facing transport are set by the one `chmod 666` line above; everything else about `/dev/corehub/*` must be created by a kernel driver (SPI subsystem or a BLOCKS-authored kernel module, not present in `/system` since kernel modules would live in `/lib/modules` on the boot/vendor ramdisk or be built into the monolithic `kernel` image — out of scope for this static `/system` + ramdisk analysis).

### Conclusion
The mechanism is: **CoreHub MCU ↔ SPI bus 5, chip-select 0 ↔ Android SoC**, gated only by a world-writable sysfs node (`st-manager`) chmod'd from generic `init.rc`, consumed exclusively by the root-run `modulecom_daemon`, which re-exposes it to apps over a ZeroMQ broker pattern. This is a thin, pragmatic prototype-grade design: no dedicated HAL, no Binder service, no custom SELinux beyond exec-domain labeling of the daemon itself.

---

## 5. Init Customizations vs Stock

`extracted/boot/ramdisk_ro/` contains the standard Qualcomm MSM8909w `.rc` set (`init.rc`, `init.qcom.base.rc`, `init.qcom.usb.rc`, `init.target.rc`, `init.trace.rc`, `init.usb.rc`, `init.usb.configfs.rc`, `init.zygote32.rc`, `init.environ.rc`, `init.mdm.sh`, `init.qcom.*.sh`) plus a factory variant `init.qcom.factory.rc`. There is **no `extracted/system/etc/init/` directory at all** — this build predates (or simply doesn't use) the Android 7+ per-APK `init/*.rc` convention; all services are declared in the monolithic ramdisk `.rc` files, consistent with the MMB29M (6.0.1) vintage.

### Custom services added by BLOCKS
| Service | Exec path | Defined in | Notes |
|---|---|---|---|
| `modulecom_daemon` | `/system/vendor/bin/modulecom_daemon` | `init.qcom.rc` | The only service in this file; class `main`, user/group `root` |

That is the **only** custom Android `service` stanza attributable to BLOCKS found anywhere in the ramdisk. Everything else (mmi/fastmmi, srvmag_ffbm, qcom-usb-sh, etc.) is stock Qualcomm factory/bringup tooling (see §7).

### Notable non-service customization
- `init.rc`'s inline `chmod 666 /sys/bus/spi/devices/spi5.0/st-manager` (§4) — a one-line, unlabeled-as-such BLOCKS edit dropped into an otherwise-generic AOSP file, only discoverable by its comment ("Corehub").
- `init.qcom.rc` itself was **repurposed**: its header comment reads `"This will override init.qcom.rc which is renamed to init.qcom.base.rc and included here"` — i.e. BLOCKS engineers renamed the real Qualcomm file to `init.qcom.base.rc`, then wrote a new thin `init.qcom.rc` that just does `import init.qcom.base.rc` followed by the `modulecom_daemon` service block. This is a clean, minimal-diff way to inject one custom service without hand-editing Qualcomm's large base file — good practice, actually.

No other `.rc` file in the ramdisk shows BLOCKS/tophat-specific edits under the grep patterns tested (`blocks|tophat|compal|hwlink|module|modular|strap|band|hub` — see §3/§4 for what those hits actually were, all false positives from kernel `/sys/module/*` parameter paths or Qualcomm's own generic `insmod`/`.ko` module loading, unrelated to "module" in the BLOCKS hardware sense).

---

## 6. Interesting Binaries / Libraries

### BLOCKS-proprietary (all in `extracted/system/vendor/bin/`)
| Binary | Size | Notes |
|---|---|---|
| `modulecom_daemon` | 20.9 MB | Core daemon, see §3. Unstripped, full debug symbols shipped in production build (info leak / reverse-engineering gift, and a wasted ~20 MB of not-stripped symbol data). |
| `bclient` | 9.5 MB | Blocks API client CLI, unstripped. |
| `chutil` | 10.5 MB | CoreHub utility/test CLI, unstripped, includes named test "scenarios" (e.g. `led_stress`, `error-on-attach`) — factory/engineering tooling shipped in the user build. |

All three are linked against libc++ (`__ndk1` namespace symbols), so BLOCKS built this stack with the Android NDK's libc++, not a bespoke toolchain — reasonably modern C++ (templates, `shared_ptr`, `std::function`) for 2016-17 embedded Android work.

### Firmware blobs
`extracted/system/etc/firmware/modules/` — **per-module MCU firmware images**, naming scheme `EZW2_<MODULE>_<seq>_<datecode>_R.bin` (EZW2 is an internal codename, plausibly "EZ Watch 2" or a Cronologics-internal project name predating "BLOCKS"/"tophat"):
- `EZW2_CoreHub_00_20164301_R.bin` — **the CoreHub MCU's own firmware**, confirming CoreHub is a separately-flashed microcontroller and it's index `00` (loaded/updated first, logically the "hub" others depend on)
- `EZW2_GPS_03_20164301_R.bin`
- `EZW2_FLASHLIGHT_01_20164301_R.bin`
- `EZW2_BUTTON_05_20164301_R.bin`
- `EZW2_BAROMETER_02_20164301_R.bin`
- `EZW2_EXTRA_BATT_06_20164301_R.bin`
- `EZW2_HRM_04_20164301_R.bin` (heart rate monitor)

All share the datecode `20164301` (likely a malformed/internal date-encoding, not a real calendar date — worth noting as a firmware-versioning oddity) and revision suffix `_R`. These are the exact binaries `modulecom_daemon`'s `FirmwareUpdate` driver and `chutil`'s `DownloadFirmware`/`ConfirmUpdate` messages push down over the SPI/CoreHub link.

Other `etc/firmware/*` contents (`a2xx/a3xx/a4xx/leia_*` `.fw` files, `wlan/prima/`) are stock Adreno GPU microcode and Qualcomm Prima WLAN firmware — not BLOCKS-specific.

### system/vendor — other binaries
- `thermal-engine` (1.1 MB), `perfd` (60 KB), `qti` (100 KB) — stock Qualcomm QTI power/thermal daemons, unmodified.
- `sampleauthdaemon` (33.6 KB) — Qualcomm's `com.qualcomm.qti.auth.securesampleauthdaemon` **sample** secure-auth daemon; paired with the `SecureSampleAuthService`/`SampleAuthenticatorService` priv-apps (§2/§7) — this is QTI sample/demo code, should not be present in a shipping `user` build.
- `slim_daemon` (137.7 KB) — stock Qualcomm QMI-SLIM sensor-interconnect service daemon, unrelated to Blocks modules despite the superficial "sensor link" naming similarity.

### HALs (`extracted/system/lib/hw/`)
All present HALs are **stock Qualcomm/AOSP defaults** for MSM8909: `audio.primary.msm8909.so`, `gralloc.msm8909.so`, `hwcomposer.msm8909.so`, `copybit.msm8909.so`, `lights.msm8909.so`, `memtrack.msm8909.so`, `power.qcom.so`, `bluetooth.default.so`, `gps.default.so`, `vibrator.default.so`, `keystore.default.so`, `local_time.default.so`. **No BLOCKS-authored HAL exists** — the module bus is deliberately kept entirely in userspace (`modulecom_daemon` + raw sysfs SPI node), bypassing the HAL layer completely. This is a meaningful architectural finding: BLOCKS did not integrate CoreHub as a first-class Android hardware abstraction; it's a bolt-on userspace daemon.

### Notable non-BLOCKS oddity
`extracted/system/xbin/antradio_app` — ANT+ radio app, paired with `AntHalService` in `app/`. ANT+ is typically used for fitness-sensor pairing (heart-rate straps, cadence sensors); its presence alongside BLOCKS's own `HeartRateDriver`/PPG sensor suggests ANT+ may have been inherited from a Cronologics reference platform rather than actively used by BLOCKS' own module ecosystem.

---

## 7. Security Posture

| Item | Finding | Evidence |
|---|---|---|
| Build tags | `test-keys` | `build.prop`: `ro.build.tags=test-keys`; `ro.build.display.id=MMB29M test-keys` |
| `ro.secure` | **1** (secure, contradicts naive "wide open" assumption) | `default.prop` line 4 |
| `ro.debuggable` | **0** (not debuggable by default) | `default.prop` line 6 |
| `ro.adb.secure` | **1** | `default.prop` line 7 |
| USB default | `persist.sys.usb.config=none` in `default.prop`, **but** `build.prop`'s `persist.sys.usb.config=diag,serial_smd,rmnet_qti_bam,adb` is the higher-priority/later-loaded default that actually takes effect on most boots — **ADB is effectively enabled by default over USB** | `build.prop` line 195, `default.prop` line 21 |
| SELinux mode | Task brief states **permissive**; no explicit `enforcing`/`permissive` setprop found anywhere in ramdisk `.rc`/`.sh` scripts — mode is therefore set via kernel cmdline or compiled sepolicy default, not visible in this static analysis | grep across all `.rc`/`.sh` in `ramdisk_ro/`, zero hits |
| `verity_key` | Present (524 bytes) at `extracted/boot/ramdisk_ro/verity_key` | dm-verity is wired up in principle, but moot on a `test-keys`/unlocked prototype — anyone can re-sign or simply disable verity |
| FRP | `ro.frp.pst=/dev/block/bootdevice/by-name/config` configured | `build.prop` line 287 — again largely theatre on an unlocked test-keys device |
| Factory/debug tooling left in `system/bin` | `mmi`, `mmi_agent32`, `mmi_debug`, `mmi_diag` (MTK-style "MMI" factory test suite), `oemwvtest`, `debuggerd`, `diag_dci_sample`, `diag_klog`, `diag_mdlog`, `diag_socket_log`, `diag_uart_log`, `ssr_diag`, `test_diag`, `schedtest`, `qmi_simple_ril_test`, `PktRspTest` | `ls extracted/system/bin` |
| Factory init script | `init.qcom.factory.rc` (14 KB) present in ramdisk, defines `service fastmmi /system/bin/mmi` and `service srvmag_ffbm /system/bin/servicemanager` (a **second, factory-mode ServiceManager** — used in Qualcomm "FFBM" factory/field-test boot mode) | `extracted/boot/ramdisk_ro/init.qcom.factory.rc` |
| Sample/demo auth code shipped | `SampleAuthenticatorService` (app/), `SecureSampleAuthService` (priv-app/), `sampleauthdaemon` (vendor/bin/) — Qualcomm QTI **sample** secure-auth code, not meant for production | §2, §6 |
| `modulecom_daemon` | Runs as **root:root**, unstripped with full debug symbols, opens a **world-writable (666)** SPI device node, and — being a large C++ ZeroMQ-based service parsing binary messages from external, swappable, physically-attached hardware modules — represents the single largest untrusted-input attack surface on the device (a malicious or malfunctioning module could feed crafted CoreHub messages straight into a root process) | §3, §4 |
| Kernel/security patch level | `2016-05-01`, i.e. unpatched for well over a year even at original ship, and now ~8+ years stale relative to "today" | `build.prop` line 12 |

**Net assessment:** the device ships with textbook-correct default flags (`ro.secure=1`, `ro.debuggable=0`) but undermines them via (a) `test-keys` + no real anti-rollback/lock enforcement, (b) ADB baked into the default USB composition string, (c) an entire factory/MMI test-app suite and Qualcomm sample-auth demo code left in the `user` build, and (d) SELinux permissive (per task brief) with essentially zero BLOCKS-specific policy beyond one exec-domain label — meaning `modulecom_daemon`, running as root and parsing untrusted external module data, has no meaningful MAC confinement at all. This is squarely "prototype/engineering build that never got hardened for retail," which tracks with BLOCKS shipping only ~500 beta units and entering liquidation (2019) without a hardened retail release.

---

## 8. Improvement Opportunities

Concrete and scoped to what's realistic for a rootable, unlocked, unfused, unpatched Android 6.0.1 Snapdragon Wear 2100 prototype from 2017 being revived today:

1. **Strip and re-lock `modulecom_daemon`/`bclient`/`chutil`.** They're unstripped (carrying ~40 MB of combined debug symbols across the three binaries) and the SPI node they depend on is world-writable. At minimum: `strip` the binaries to reclaim space, and replace the blanket `chmod 666` on `st-manager` with a dedicated group (e.g. `corehub`) + SELinux domain transition so only `modulecom_daemon` can touch it — closing the "any app/process on a permissive-SELinux, world-writable-sysfs box can talk raw SPI to CoreHub" hole.

2. **Debloat the factory/sample cruft.** Safe, well-scoped removal candidates that provide zero end-user value and only add attack surface + storage/OTA bloat: `mmi*` (fastmmi factory test suite + `init.qcom.factory.rc`'s `fastmmi`/`srvmag_ffbm` services), `oemwvtest`, `SampleAuthenticatorService`, `SecureSampleAuthService`, `sampleauthdaemon`, `qmi_simple_ril_test`, `PktRspTest`, `schedtest`, `test_diag`. None of this touches the BLOCKS module system.

3. **Reconsider the modem/RIL stack.** Full CDMA/LTE RIL plumbing (`rild`, `qcrilmsgtunnel`, `CellBroadcastReceiver`, `Stk`) is wired up on a device that (per the module-app roster) has no telephony-focused Blocks module and was never sold with a SIM slot as far as the app inventory suggests. If genuinely unused, removing it shrinks the attack surface (RIL/QMI parsing of basebands is a classic exploit vector) and boot time. Worth confirming against `edl_backup`/hardware photos before removing, since msm8909w boards sometimes do have an unpopulated modem footprint.

4. **Modernize the module-bus transport from "bolt-on userspace daemon" to a real HAL.** Currently CoreHub bypasses Android's HAL layer entirely (raw sysfs SPI node + ZeroMQ to apps, no `service_contexts` entry, no Binder). For a revival project this is actually the single highest-leverage architectural change: wrapping CoreHub access in a proper `hardware/interfaces`-style HIDL/AIDL HAL would (a) let it survive future Android version jumps far better than a raw sysfs path will, (b) get it real SELinux-domain-to-domain mediation instead of `chmod 666`, and (c) make the existing, genuinely well-designed `blocks::Capability` abstraction (§3) available to more of the system (e.g. Health Connect / SensorManager bridging) instead of being locked behind a bespoke ZeroMQ client library.

5. **Security-patch and toolchain currency.** `2016-05-01` security patch level and MMB29M base mean this device is missing ~8+ years of Android/Linux CVE fixes. Given `ro.build.tags=test-keys` and no real verified-boot enforcement in practice, the realistic modernization path isn't "take an OTA" (none will ever come) but rather: (a) backport a current kernel if the msm8909w BSP allows it, or at minimum cherry-pick the highest-severity known MSM8909/Qualcomm CVEs from the same era into the shipped kernel, (b) given SDK 23 and 32-bit-only ABI, most modern Play Services / app compatibility is already a lost cause — treat this as a closed, offline hobbyist/dev device rather than aim for app-store parity.

Additional lower-priority ideas surfaced during analysis but not in the top 5: the `EZW2_*` module firmware datecode (`20164301`) looks like a broken/placeholder date encoding worth investigating if module firmware updates are ever re-enabled; the `/data/modulecom_daemon.html` debug dashboard referenced in the daemon's strings could be a fast way to get a live status view of attached modules without writing new tooling, if that code path still functions.

---

*Report generated via static analysis of `extracted/system/` (613 MB) and `extracted/boot/ramdisk_ro/` (13 MB). No USB device was accessed; all findings are derived from files already dumped to disk under `/Users/dviros/Downloads/blocks-watch/extracted/`.*
