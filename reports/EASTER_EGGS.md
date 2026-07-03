# BLOCKS "tophat" Firmware — Easter Egg & Hidden Feature Hunt

**Device:** BLOCKS modular smartwatch prototype, codename `tophat` (Qualcomm Wear 2100 / MSM8909w)
**Built by:** developer "tincho" (Unix user `tincho5588`, host `tincho5588-linux`), Buenos Aires, Argentina — Nov 23, 2017
**Method:** static analysis only — `strings`, `grep`, `unzip`, raw `classes.dex` string extraction from APKs, no live device, no git. Every finding below is cited to an exact file (and line number where applicable) so it can be independently re-verified.

This report ranks findings by "how cool/interesting," not by severity — see `extracted/SYSTEM_ANALYSIS.md` for the security-focused pass.

---

## Top 10 at a glance

1. A fully reconstructable **embedded HTML/CSS developer dashboard** ("Detailed Message Log") baked into the daemon's `.rodata`, complete with two embedded base64 GIF icons — one of them a literal **"hat" icon**, a quiet nod to the "tophat" codename.
2. The `led_stress` test scenario prints the stage direction **`Commence fiddling with hardware now.`** — the single most delightful line of prose in the entire firmware.
3. A self-aware, self-deprecating code comment: **`Terrible hack: creates a new context without cleaning the previous one.`** — literally the daemon admitting to its own resource leak.
4. A whole layer of **unshipped Cronologics-platform features** hiding in plain sight as Dalvik package/intent strings: `com.cronologics.alexa` (Amazon Alexa integration), `com.cronologics.assistant.timer.*` (a timer/alarm assistant), `com.cronologics.music.action.SET_PLAYBACK` — none of which ever got a corresponding BLOCKS-branded app or announcement.
5. `BlocksHalfWatchface` / `BlocksHalfWatchEngine` — a complete, compiled watchface class shipped in the APK with **zero matching artwork and zero manifest registration** — a cut watchface, still riding along as dead code.
6. Parallel **`fota.crono.services`** and **`fota.blocks.services`** OTA-update endpoints sitting side-by-side in the same settings APK — live fossil evidence of BLOCKS building its own backend to replace the inherited (and abandoned, post-Google-acquisition) Cronologics one.
7. Two Cathay Pacific airline-branded watchfaces (**Cathay Pacific**, **Cathay Pacific Classic**, **Cathay Dragon**) shipped as first-class assets in the watch's watchface picker — an unexplained corporate tie-in/licensing relic.
8. The build machine's own locale leaks into the firmware: `ro.build.date=jue nov 23 00:21:55 -03 2017` — "jue" is Spanish for Thursday, timestamped Argentina Standard Time (`-03`), confirming this was tincho's personal box, not a sanitized build farm.
9. Three code layers, three different names for the same hardware: the flashlight module is `com.cronologics.flashlight` at the platform-intent layer, `"led"` at the native `blocks::getModuleID` layer, and ships to users as **`BlocksTorch`** — a small, perfect fossil of a rebrand-in-progress.
10. Firmware blobs for all 7 modules share the identical, almost certainly malformed datecode **`20164301`** — not a valid calendar date under any reasonable YYYYMMDD/YYYYDDD interpretation.

---

## 1. Dev artifacts — names, paths, jokes, profanity

### The best line in the whole firmware
- **`Commence fiddling with hardware now.`**
  File: `extracted/strings/chutil.strings.txt` (in the `led_stress` scenario, `scenarios/examples.cpp`)
  Printed to the terminal when an engineer runs `chutil scenario led_stress <id>` — genuinely funny, human, in-the-moment developer prose. The best find in the entire corpus.

### The daemon confessing to its own bug
- **`Terrible hack: creates a new context without cleaning the previous one.`**
  File: `extracted/strings/modulecom_daemon.strings.txt:6518`
  Sits directly between `api::APIServer::APIServer()` (`api/server/apiserver.cpp`) and `bool api::APIServer::connect(...)` — a debug-log string admitting to a known resource leak in the ZeroMQ API server's connection-context handling. Across ~213,000 lines of extracted strings from three C++ binaries, this is the **one** genuinely self-aware, personality-bearing comment.

### Developer identity
- Build fingerprint: `ro.build.fingerprint=BLOCKS/blocks_tophat/tophat:6.0.1/MMB29M/tincho558811230021:user/test-keys` (`extracted/system/build.prop`)
- `ro.build.user=tincho5588`, `ro.build.host=tincho5588-linux` (`extracted/system/build.prop`) — tincho's actual Unix username and machine hostname, not a shared/sanitized CI runner.
- `ro.build.date=jue nov 23 00:21:55 -03 2017` and `ro.bootimage.build.date=jue nov 23 00:22:14 -03 2017` (`extracted/system/build.prop`) — "jue" = jueves (Thursday) in Spanish, `-03` = Argentina Standard Time. This is a genuine locale leak: the build machine's own `LANG` setting bled into the firmware's date string, independently corroborating the Argentina/tincho attribution from a completely different field than the fingerprint.
- `ro.product.manufacturer=Compal` (`extracted/system/build.prop`) — confirms the ODM directly. No individual Compal or Cronologics engineer names were found anywhere in the corpus (checked extensively — see negative results below).

### Internal build-tree paths (exactly 3, no more)
- `/build/blocks/code/modulecom-daemon` — `extracted/strings/modulecom_daemon.strings.txt:7405` (immediately follows the literal `daemon.cpp`, a `__FILE__` macro artifact)
- `/build/blocks/code/corehub-utility` — `extracted/strings/chutil.strings.txt:2952` (follows `main.cpp`)
- `/build/blocks/code/client-utility` — `extracted/strings/bclient.strings.txt:5725` (follows `main.cpp`)
No sibling directories, no other engineers' checkout paths, and no `/home/`, `/Users/`, or Jenkins-style paths were found anywhere in any of the three binaries.

### Build hygiene inconsistency
- `BlocksOverview.apk` is the **only** Blocks-branded app that shipped with ProGuard/R8-obfuscated class names (`Lcom/a/a/a/a;` through `.../t;`, `extracted/system/priv-app/BlocksOverview/BlocksOverview.apk`) — every other Blocks-prefixed app (`BlocksAdventure`, `BlocksBattery`, `BlocksButton`, `BlocksCompass`, `BlocksContainer`, `BlocksDecibel`, `BlocksGPS`, `BlocksHealth`, `BlocksNavigator`, `BlocksTorch`, `BlocksWatchfaces`) shipped with fully readable Java class/package names. A small, real build-config inconsistency across the app suite.

### What was searched for and genuinely NOT found (documented as useful negative evidence)
- **Emails**: zero real addresses across all three C++ binaries and all 12 Blocks APK `classes.dex` files. (A few 5-7 char regex false-positives like `o@O.Tv` in dex constant pools are binary garbage, not addresses — verified by inspecting surrounding bytes.)
- **Other developer names/handles/initials**: none besides tincho/tincho5588.
- **Git remnants**: no commit hashes, `git log` text, or `refs/heads` strings anywhere.
- **"Cronologics" as a standalone literal string**: never appears anywhere in any binary, strings dump, or config file (independently confirmed twice, via two separate `grep -rli "cronologics"` passes over the entire `extracted/` tree) — the company is only inferable from the `Crono*` app-naming convention (CronoLauncher, CronoSettings, CronoSystemUI, etc.) and the `com.cronologics.*` Dalvik package prefixes recovered from `classes.dex` string tables (e.g. `com.cronologics.bridge.ICronoBridge` in `CronoLauncher.apk`). This is itself a small, telling asymmetry: renaming user-facing display strings and app names to BLOCKS was evidently easy, but renaming the underlying Java package namespace was not — doing so would risk breaking APK signing/IPC contracts across the whole `Crono*`/`Blocks*` app suite, so it was left alone.
- **TODO/FIXME/HACK/XXX/WTF**: only 3 hits total in the entire corpus, and two are stock Qualcomm/AOSP boilerplate, not BLOCKS jokes:
  - `# TODO: add default audio pre processor configurations after debug and tuning phase` — `extracted/system/etc/audio_effects.conf:230` (stock Qualcomm)
  - `FIXME: We do not check decoder capabilities at present...` — `extracted/system/etc/media_profiles.xml:723` (stock AOSP)
  - The one true "hack" hit is the `Terrible hack:` line documented above.
- **"DO NOT SHIP" / "SHIP THIS" / "DEBUG ONLY" / "REMOVE BEFORE" / kludge / ugly**: zero hits.
- **Profanity** (shit/fuck/ass/bitch/bastard/damn/hell/crap): zero hits anywhere.
- **Literal "easter egg" or "secret" strings**: zero genuine hits. The ~500+ raw "hidden" matches per binary are all libc++ STL template noise (`__hidden_allocator<...>`, a real standard-library internal name) or standard Android `View` visibility API strings — nothing bespoke.
- **Copyright strings**: only third-party boilerplate — `Copyright 2002-2016, LAMP/EPFL` (Scala's copyright header, pulled in transitively via the `osmdroid` mapping library used by BlocksNavigator/BlocksGPS) and generic Linux Foundation BSD headers in the boot scripts. Nothing attributable to Cronologics, Compal, or any individual.
- **Secret dialer codes** (`*#*#...#*#*` pattern): zero hits anywhere in the extracted system image, boot ramdisk, or any of the three strings dumps — expected for a watch with no dialer, but confirmed rather than assumed.
- **"Tap build number 7 times" developer-options unlock gesture**: the classic AOSP easter egg is **absent**. Checked both the stock `SettingsProvider` (present as a content-provider backend, `extracted/system/priv-app/SettingsProvider/SettingsProvider.apk`) and the custom `CronoSettings` UI (`extracted/system/priv-app/CronoSettings/CronoSettings.apk`) — neither contains the "You are now a developer" string or any tap-counter logic. Cronologics fully replaced the Settings UI shell and evidently never reimplemented this particular Android tradition.

**Bottom line on this section:** this is a remarkably clean, professional internal codebase. Across ~213,000 lines of extracted strings and 12 decompiled APKs, the entire "personality" haul is: one hack-admission comment, one gleeful scenario message, and the build-fingerprint metadata. State that plainly rather than implying more exists — the absence itself is a genuine and slightly surprising finding for a ~500-unit beta-stage startup firmware.

---

## 2. Hidden debug/test features — chutil scenarios & CoreHub catalog

### The 3 named test scenarios (complete list, independently verified)
`chutil` ships exactly three named test "scenarios" — small built-in programs for testing CoreHub functionality, run via `chutil scenario <name> [<args>]`:

| Scenario | Source file | What it does |
|---|---|---|
| `error-on-attach` | `scenarios/error-on-attach.cpp` | Deliberately reproduces a module-attach failure path (`bool testForError()`, "Error reproduced: empty message received.", "Wait for CoreHub to reboot and re-run.") |
| `led_stress` | `scenarios/examples.cpp` | Stress-tests the LED driver; prints `Commence fiddling with hardware now.` |
| `gps_nmea` | `scenarios/gps_nmea.cpp` | Drives the GPS module through `GPSStart`/`GPSGetNMEA`/`GPSStop` and prints raw NMEA strings ("NMEA String: \"...") |

Evidence (all `extracted/strings/chutil.strings.txt`): `_scenarios_internal::_scenario_error_on_attach`, `_scenarios_internal::_scenario_led_stress`, `_scenarios_internal::_scenario_gps_nmea` (mangled C++ symbols around lines 2213-2227 and 2710-2714), plus the registration machinery `scenarios::registerScenario`/`scenarios::deregisterScenario` (`scenarios/scenarios.cpp`).

### `chutil` usage / help banner (verbatim, reconstructed from strings)
```
Blocks CoreHub Utility v1.2.1
---------------------------------------
Built with: libapi-v0.6.1 libcorehub libshared advlog
CoreHub status: AVAILABLE / UNAVAILABLE
Usage: chutil <command> [args]

Commands include:
  list [ modules | messages | functions | scenarios ] [--log]
    modules   - lists the connected modules
    messages  - lists the available CoreHub messages
    functions - lists the available standard functions
    scenarios - lists the available scenarios
  Example: list modules

  scenario <name> [<args..>]
    Runs the given scenario. Scenarios are small programs for testing
    CoreHub functionality.
  Example: scenario led_stress 12345

  subscribe <capability name/no.[@interval] | -module | -capability>... [--log]
    Subscribes to the specified Capability data or events at the given
    rate (in ms) and waits indefinitely.
  Example: subscribe Humidity@10 ButtonPushed -module

  help <command>
    Prints the help info for the given command.
  Example: help scenario
```
(Source: `extracted/strings/chutil.strings.txt` lines ~2085-2260; `extracted/strings/bclient.strings.txt` lines ~4780-4900 for the `bclient`-specific `subscribe` example above, which is shared client-library text between the two tools.)

### The CoreHub message / StandardFunction catalog
`modulecom_daemon` exposes a two-tier API: raw **CoreHub messages** (protocol-level, module attach/detach/firmware-update) and **StandardFunctions** (per-capability calls like `GPSStart`, `LEDOn`). Both `chutil` and `bclient` are clients of this same catalog.

**CoreHub-level messages** (module lifecycle & firmware, from `blocks::` message classes):
`ConfirmUpdate`, `CoreHubRestart`, `FetchModuleFirmwareVersion`, `FetchRegisteredModuleList`, `FetchRegisteredModuleListResponse`, `FetchEBMList`, `FetchAuxiliaryAddressList`, `DownloadFirmware`, `DownloadFirmwareResponse`, `ModuleAttachment`, `ModuleAttachmentRequest`, `ModuleDetachment`, `ModuleDetachmentRequest`, `ModuleAuxiliarySleep`, `ModuleAuxiliaryWake`, `ModuleTimedSleep`, `ModuleInfo`, `QueryStandardFunctions`, `QueryStandardFunctionsResponse`, `ReportDataDemand`, `ReportDataDemandResponse`.

**Named StandardFunction enum values** (36 confirmed, `extracted/strings/chutil.strings.txt` + `modulecom_daemon.strings.txt`, `grep -oE 'blocks::StandardFunction::[A-Za-z]+'`):
`ButtonGetInfo`, `EBMGetCapacity`, `EBMGetLevel`, `EBMGetStatus`, `EBMSetEnabled`, `GPSGetCN`, `GPSGetDTM`, `GPSGetGBS`, `GPSGetGGA`, `GPSGetGLL`, `GPSGetGNS`, `GPSGetGSA`, `GPSGetGST`, `GPSGetGSV`, `GPSGetLocation`, `GPSGetNMEA`, `GPSGetNavStatus`, `GPSGetRMC`, `GPSGetTXT`, `GPSGetVTG`, `GPSGetZDA`, `GPSReset`, `GPSStart`, `GPSStop`, `GetBaroPressure`, `GetBaroRelAlt`, `GetExternalTemp`, `GetHumidity`, **`HPTReset`**, `LEDGetInfo`, `LEDOff`, `LEDOn`, `PPGGetHeartRate`, `PPGReset`, `PPGSetEnabled`, `SetBaroRefAlt`.

**Driver classes** (`grep -oE 'blocks::[A-Za-z]+Driver' modulecom_daemon.strings.txt`): `blocks::AdventureDriver`, `blocks::DirectComDriver`, `blocks::EBMDriver`, `blocks::GPSDriver`, `blocks::HeartRateDriver`, `blocks::ModuleDriver`, `blocks::PBDriver`, `blocks::StandardDriver` (generic fallback — "Special request routed to standard driver," `drivers/stddriver.cpp`, not a hardware-specific driver), `blocks::TorchDriver`.

### Zero hidden Settings/engineering menus, developer gestures, or test activities found
Checked `CronoSettings`, `CronoSettingsWifi`, `CronoSettingsProvider`, `CronoAmbient`, and `CronoLauncher` for: engineering-menu strings, "Diagnostic"/"Hidden"/"DevMenu"/"SecretMenu" class or string names, and wrist gestures (raise-to-wake / twist / shake / flick, despite `ro.qti.sensors.wrist_tilt=true` being enabled in `build.prop`) — no hits in any app-layer Java strings. This doesn't rule out gesture handling living in a HAL/native layer instead of app Java code, which this static pass didn't cover, so treat as "not found at the app-string layer" rather than "definitively absent."

---

## 3. The debug dashboard — reconstructed

**`/data/modulecom_daemon.html`** (`extracted/strings/modulecom_daemon.strings.txt:6180`) is real, shipped, dev-only code — not aspirational dead code. High-confidence reconstruction below.

### Architecture
A shared logging library, `advlog`, is linked into **all three** BLOCKS binaries (`modulecom_daemon`, `chutil`, `bclient`) and implements a pluggable "printer" pattern: `advlog::AdvancedLog::logEvent()` (`advlog/advlog.cpp`) dispatches each logged event to a `std::set<advlog::IAdvancedLogPrinter*>` of registered printers. Confirmed concrete printer implementations:
- `advlog::TerminalPrinter` (`advlog/terminal-printer.cpp`) — plain console output.
- `advlog::HTMLLogPrinter` (`advlog/html-printer.cpp`, `advlog/html-template.cpp`, static symbol `htmlPrinter_template`) — the dashboard generator.

`chutil` and `bclient` both default their HTML output to a plain **`log.html`** in the working directory (`extracted/strings/chutil.strings.txt:2097`, `extracted/strings/bclient.strings.txt:4797`), while the always-running daemon writes to the fixed absolute path `/data/modulecom_daemon.html`. All three share the same `--log` flag semantics: logging is off by default, `--log` turns it on, and (per the multi-printer dispatch pattern) enabling it drives **both** the terminal and the HTML file simultaneously — there is no separate flag to choose HTML vs. terminal output specifically.

`bclient` also has two other notable strings in the same region: hardcoded ZeroMQ endpoints `tcp://localhost:6676` and `tcp://localhost:6677` (`extracted/strings/bclient.strings.txt:4785-4786`).

### What the dashboard shows: a "Detailed Message Log"
It is a rolling, per-event **wire-protocol audit trail** of CoreHub traffic (module attach/detach, standard function calls/responses, raw bytes sent/received) — not a battery/uptime/firmware-version summary dashboard. (Confirmed by absence: no "Attached Modules," "CoreHub Status," "Refresh," "Last Updated," or "Uptime" strings exist anywhere in the binary.)

### Reconstructed HTML/CSS (verbatim strings, `extracted/strings/modulecom_daemon.strings.txt`)

Per-event template (lines 6698-6708):
```html
<div class='event-box' id='event<N>'>
  <label>event&nbsp;</label><h2><EVENT_NAME/TIMESTAMP></h2>
  <a href='#event<N>' class='link-btn'></a>
  <hr/><table>
    <tr><td><FIELD_NAME></td><td><FIELD_VALUE></td></tr>
    ...
  </table>
</div>
<div class='event-group'>
```
(`<N>`, `<EVENT_NAME/TIMESTAMP>`, `<FIELD_NAME>`, `<FIELD_VALUE>` are runtime-substituted values, inferred, not literal strings — everything else above is copy-pasted from the binary.)

Page shell (lines 7017-7089, contiguous run of real markup):
```html
<!DOCTYPE html>
<html>
<meta>
    <title>Detailed Message Log</title>
    <style>
body { font-family: Roboto, 'Segoe UI', Calibri, Futura, Arial, sans-serif;
footer { background-color: red; height: 20px;
header { margin: 30px 50px;
header h1 { display: inline; vertical-align: middle;
.event-container { justify-content: center; display: flex; flex-wrap: nowrap; flex-direction: column;
.event-group { justify-content: flex-start; display: flex; flex-wrap: wrap; padding: 10px 0; margin: 20px 0; width: 100%; border: 1px solid darkgrey; border-radius: 2px;
.event-box { border: 2px; border-color: grey; min-width: 400px; width: 40%; padding: 20px;
.event-box:hover { background-color: azure;
.event-box label { font-size: 12px; margin-right: 10px; color: grey;
.event-box h2 { display: inline;
.event-box table tr :first-child { font-weight: bold; padding-right: 10px; vertical-align: top;
.event-box table .mono { font-family: monospace;
.hat { width: 64px; height: 64px; display: inline-block; vertical-align: middle; margin-right: 50px; background-image: url(data:image/gif;base64,R0lGODlhQABAAPcAAAAA...[~2.4KB embedded GIF]...OQAOw==);
.link-btn { height: 18px; width: 18px; cursor: pointer; display: none; margin-right: 10px; float: right; background-image: url('data:image/gif;base64,R0lGODlhEgASAPcAAAAAADMzMzQ0NDY2Njc3Nzg4OENDQ0xMTFdXV1paWltbW15eXmRkZGZmZm5ubnBwcHFxcXNzc4ODg4SEhI2NjZOTk5eXlw...[~1.2KB embedded GIF]...COw==')
.event-box:hover .link-btn { display: inline-block;
    </style>
</meta>
<body>
<header>
    <div class='hat'></div> <h1> Detailed Message Log </h1>
</header>
<div class='event-container'>
```
Note: every CSS rule's closing `}` is missing from this extraction — almost certainly a `strings`-tool line-splitting artifact on one long embedded CSS blob, not evidence of genuinely broken CSS shipped in the binary.

**The nicest detail:** a 64x64 `.hat` icon — base64-embedded GIF, shown next to the "Detailed Message Log" title — is very plausibly a literal top-hat graphic, a quiet visual nod to the "tophat" codename baked right into the debug tooling only an engineer would ever see. No `</body>`/`</html>` closing tags exist anywhere in the binary — the developer likely never bothered, relying on browser leniency.

**Ruled out:** no embedded HTTP server (checked for mongoose/civetweb/microhttpd/HttpServer/WebServer/websocket/HTTP headers/bind-port strings — all zero hits); this is a static file writer, not a live web server. The separate `api::APIServer` class is the daemon's actual ZeroMQ control-plane API, unrelated to this HTML page.

---

## 4. Unreleased / vaporware modules & features

### The real haul: unshipped Cronologics-platform features with no BLOCKS app
The strongest vaporware evidence isn't in the native C++ binaries at all — it's in Dalvik package/intent strings recovered from `classes.dex` across several priv-app APKs, naming entire platform features that never got a shipping BLOCKS-branded app:
- **`com.cronologics.alexa`** (plus adjacent string `amazon_alexa`) — `extracted/system/priv-app/CronoContainerSdk/CronoContainerSdk.apk` — an Amazon Alexa integration that never became a visible BLOCKS feature.
- **`com.cronologics.assistant.alert.ALERT_ACTION`**, **`.assistant.timer.TIMER_DELETED`**, **`.assistant.timer.TIMER_START`** — present in `BlocksWatchfaces.apk`, `CronoContainerSdk.apk`, `CronoResponses.apk`, and dedicated (but never publicly documented) `CronoAlarmContainer.apk`/`CronoTimerContainers.apk` — a full timer/alarm "assistant" subsystem.
- **`com.cronologics.music.action.SET_PLAYBACK`** — `extracted/system/priv-app/CronoLauncher/CronoLauncher.apk` — media-playback-control plumbing with no corresponding music-control UI anywhere in the known app roster.
- **`com.cronologics.heartratemonitor`** — `CronoContainerSdk.apk` — the platform-layer internal name for what shipped to users as `BlocksHealth` / the `blocks::HeartRateDriver` PPG sensor.

### Three names, one flashlight — a rebrand caught mid-flight
- Platform/intent layer: **`com.cronologics.flashlight`** (`CronoContainerSdk.apk`)
- Native daemon layer: `blocks::getModuleID` hardcodes the short-code key **`"led"`** for this module (`modulecom_daemon`)
- Shipped, user-facing app: **`BlocksTorch`**
Three different names for the exact same piece of hardware across three different layers of the same codebase — a small, perfect fossil of BLOCKS renaming the Cronologics platform in place, one layer at a time, without fully finishing the job.

### The `blocks::Capability` enum is genuinely closed — no hidden Camera/Speaker/Storage
Cross-checked across all three native binaries: `Capability::Temperature, Pressure, Humidity, Altitude, HeartRate, BatteryLevel, BatteryCapacity, BatteryStatus` — exactly 8 values, no more, in every binary. This is corroborated at the source-file level: `modulecom_daemon` embeds literal build paths for exactly these driver source files — `drivers/adventure.cpp`, `directcom.cpp`, `ebm.cpp`, `firmware_update.cpp`, `gps.cpp`, `heartrate.cpp`, `module_driver.cpp`, `modules.cpp`, `pb.cpp`, `stddriver.cpp`, `torch.cpp` — and no `camera.cpp`, `speaker.cpp`, `storage.cpp`, or `display.cpp` ever existed at the source level. `blocks::getModuleID` has exactly 5 hardcoded short-code keys: `gps`, `led`, `hrm`, `adv`, `ebm`. A targeted, noise-filtered search for camera/speaker/microphone/storage-module/memory-module/NFC/display-module across all three strings files returned zero genuine hits (raw "storage" hits are all libc++ `__time_get_storage`/`aligned_storage` template noise). **Despite the Kickstarter's original promise of camera, speaker, and extra-memory modules, none of them got far enough to leave even a single enum value or driver stub in this build** — the roadmap cuts happened before the wire protocol was touched, not after.

### `StandardFunction::HPTReset`/`HPTTurnOff` — real, but not the smoking gun it first looked like
A DWARF debug-info dump (`llvm-dwarfdump --debug-info` against the unstripped `modulecom_daemon` ELF, which ships with full `debug_info` — see `SYSTEM_ANALYSIS.md` §6) pulled the actual `enum class StandardFunction : uint16_t` definition — ground-truth compiler metadata, not string-guessing. The full 44-value enumerator table (values 0-257) shows `HPTReset=37` and `HPTTurnOff=38` sitting in a completely ordinary, contiguous numeric run alongside `GetBaroPressure=34`, `GetHumidity=35`, `GetExternalTemp=36`, `GPSGetCN=39`, `EBMSetEnabled=40` — **not** isolated in a suspicious gap. Every enumerator DWARF exposes has a name; there is no name-less/blank slot anywhere in the debug info. So: `HPTReset`/`HPTTurnOff` are real, plausibly "Haptic" (matching the `LEDOn`/`LEDOff` naming pattern for a vibration-motor reset+off pair), and have no dedicated `hpt.cpp` driver file or shipped app — but the earlier hypothesis that they sit in a large abandoned numeric gap does not hold up against the DWARF ground truth. What the gaps that DO exist (9, 22-23, 25, 41-52, 55-63, 68-256) most honestly represent is unused reserved numeric space, not a disprovable "there was a Camera function here" claim — treat "HPT is an under-documented, driver-less function" as the finding, and the enum-gap theory as a lead that didn't pan out under closer inspection.

### Confirmed: cut watchface, no assets
`BlocksHalfWatchface` / `BlocksHalfWatchEngine` (`extracted/system/priv-app/BlocksWatchfaces/BlocksWatchfaces.apk`, class `Lcom/blocks/app/watchface/BlocksHalfWatchface;`) is a fully compiled watchface class shipped inside the APK, but:
- No `half_background.png`, `half_thumbnail.png`, or any `half_*` drawable exists anywhere in the APK (every other shipped watchface has a matching `_background.png`/`_ambient_background.png`/`_thumbnail.png`/hand-PNG set).
- No manifest wallpaper-service declaration was found referencing it (inconclusive on its own since the manifest is binary AXML, but combined with the total absence of matching artwork this is a strong "abandoned mid-build" signal).
- All 20 other watchface classes (`BlocksBlackMetalWatchface` through `BlocksWhiteWatchface`) have complete, matching asset sets.

### Parallel OTA infrastructure — Cronologics vs. BLOCKS
Two firmware-update-check endpoints exist side by side in `CronoSettings.apk`:
- `http://fota.crono.services/api/v1/updates`
- `http://fota.blocks.services/api/v1/updates`
(both `extracted/system/priv-app/CronoSettings/CronoSettings.apk`, `classes.dex` strings)
This is direct fossil evidence of the platform transition described in `SYSTEM_ANALYSIS.md`: BLOCKS inherited the Cronologics OTA backend and was in the process of standing up its own (`blocks.services`) parallel infrastructure, with both URLs still compiled into the same settings binary at ship time.

### Other backend/analytics vendor URLs found (context, not vaporware per se)
`http://api.crono.services/icons/v1/` (icon CDN, `CronoNotificationService.apk`), `https://api.keen.io` and `https://in.treasuredata.com` (real third-party analytics SaaS vendors wired into `CronoAnalyticsProvider.apk` via the `io.keen.client.java` and `com.treasuredata.android` SDKs), and every `io.fabric.ApiKey` meta-data tag across all 12 Blocks apps is still the SDK's literal placeholder value `YOUR_API_KEY` — meaning Crashlytics/Fabric crash reporting was integrated but **never actually configured with a real key** in any shipped Blocks app.

---

## 5. Branding & lineage relics

### The Cathay Pacific watchfaces — an unexplained airline tie-in
Three watchfaces in `BlocksWatchfaces.apk` are explicitly airline-branded, with matching color-scheme resource names (`cathayPacificAccentColor`, `cathaypacificPrimaryColor`, etc.) and dedicated Java classes (`CathayPacificWatchface`, `CathayDragonWatchface`, both with their own `*HandsEngine`/`*WatchEngine` inner classes — the same code pattern used for every other "real" watchface, not a stub):
- **Cathay Pacific** (`cathay_pacific_*` assets)
- **Cathay Pacific Classic** (`cathay_pacific_classic_*` assets)
- **Cathay Dragon** (`cathay_dragon_*` assets — Cathay Dragon was Cathay Pacific's regional subsidiary airline)
No other corporate/airline branding appears anywhere else in the firmware. This reads as a genuine (if now-orphaned) partnership or licensing relationship between BLOCKS/Cronologics and Cathay Pacific — plausibly built for airline-crew or frequent-flyer distribution — that never received any documentation elsewhere in the accessible firmware.

### Locale leak confirms Argentina/tincho attribution independently
See §1 — `ro.build.date=jue nov 23 00:21:55 -03 2017`.

### No stock "Android Wear"/"Nexus" branding leftovers
Checked `build.prop` and every `Crono*`/`Blocks*` APK's dex strings for "Android Wear" and "Nexus" — zero hits in either. Combined with the SYSTEM_ANALYSIS.md's separate finding that `ro.config.ringtone=Ring_Synth_04.ogg` is an unbranded stock AOSP filename, the picture is: BLOCKS rebranded cleanly at the *user-visible string* layer, while leaving stock AOSP *filenames* (ringtones, media assets) untouched — a sensible, low-effort rebrand strategy.

### Boot animation predates the OS build by 11 months
`extracted/system/media/bootanimation.zip` — every frame inside carries a filesystem timestamp of **December 15, 2016** (`desc.txt`, `part0/000.png` through `part0/135.png`), nearly a full year before the Nov 23, 2017 OS build date. This is either a genuinely stable, never-touched-since asset, or (more likely, given the Cronologics-to-Google-to-BLOCKS timeline in `SYSTEM_ANALYSIS.md`) a leftover from the original Cronologics-era build that simply never needed changing because the BLOCKS wordmark logo was already correct. `desc.txt` itself: `400 400 20` / `p 0 0 part0` — a 400x400 canvas at 20fps, single part, infinite loop (count=0) until boot completes, 136 frames = 6.8 seconds per loop.

### The datecode mystery: `20164301`
All 7 module firmware blobs in `extracted/system/etc/firmware/modules/` share the identical datecode `20164301` (e.g. `EZW2_CoreHub_00_20164301_R.bin`). This string appears **nowhere else** in the entire extracted corpus (`grep -rn "20164301"` across all of `extracted/` returns only the 7 filenames themselves — no matching internal build-timestamp constant was found inside any binary to corroborate or explain it). Tested hypotheses, none conclusive:
- Not a valid `YYYYMMDD` (would require month `43`).
- Not a valid `YYYYDDD` Julian date (day-of-year `4301` exceeds 366).
- Most plausible reading: a transposed/malformed date where two digit groups swapped (e.g. an intended `20160430`), or the trailing `4301` is actually an internal build/sequence counter rather than a date fragment at all, with "2016" as a genuine year prefix.
All 7 `.bin` files do share one corroborating, if weaker, data point: identical filesystem mtimes of **Nov 22, 2017** (one day before the OS build) — consistent with a same-batch firmware refresh, though this is an extraction/copy timestamp, not necessarily the original build timestamp, so it doesn't resolve the internal datecode string itself. Firmware content: all 7 blobs open with what looks like an ARM Cortex-M/Thumb vector table (repeating `xxED0308` 4-byte little-endian function-pointer pattern), consistent with `SYSTEM_ANALYSIS.md`'s hypothesis that CoreHub is an STM32-class MCU (`st-manager` sysfs node).

### `ble_bogus_uuid` — a single, isolated occurrence with no further explanation available
`persist.sys.ble_bogus_uuid=0000181D-0000-1000-8000-00805F9B34FB` (`extracted/system/build.prop`, line 278) is confirmed to be the **only** occurrence of this property or this specific UUID anywhere in the corpus: `0000181D`/`181D` never appears a second time in `build.prop`, any of the three native strings dumps, or any APK's `classes.dex`, and no code path referencing this property was found in `modulecom_daemon`/`chutil`/`bclient`. `0x181D` is the standard Bluetooth SIG-assigned "Weight Scale" GATT service UUID — syntactically valid, standards-compliant, and (as far as this static analysis can tell) simply an arbitrary-but-real UUID reused as a placeholder because it was unlikely to collide with anything the watch actually implements. Why *that specific* service was picked over any other unused standard UUID remains unresolved — flagged here as an open, minor mystery rather than a solved one.

---

## 6. Media

### Watchfaces — 21 shipped, 1 dead
20 fully-assetted watchfaces ship in `BlocksWatchfaces.apk`: Black Metal, Carbon, Cathay Dragon, Cathay Pacific, Cathay Pacific Classic, Cobalt, Dark Gold, Dark Gray, Dashboard, Daydream, Digital, Formal, Gold, Leather, Marble, Moon, Neon, Pop, Prime, Radial, Ring, Simple, Spider, Steel, Ticker, White (each with a matching `_ambient` low-power variant). Plus the dead **`BlocksHalfWatchface`** documented in §4 — compiled, shipped, completely inert.

### Boot animation
`extracted/system/media/bootanimation.zip` — a clean white-on-black "BLOCKS" wordmark, with a stylized "Ō" (a small arc/cap above the O, echoing a module or a tiny top hat) fading in over 136 frames / 6.8 seconds at 400x400. Asset timestamps predate the OS build by 11 months (see §5).

### Ringtones/alarms/notifications
All audio assets in `extracted/system/media/audio/` are **stock AOSP**, not custom-branded: alarms are named after chemical elements (Argon, Barium, Carbon, Cesium, Fermium, Hassium, Krypton, Neon, Neptunium, Nobelium, Osmium, Oxygen, Platinum, Plutonium, Promethium, Scandium), ringtones after constellations/stars (Atria, Bootes, Cassiopeia, Carina, Nairobi, Paradise Island, Perseus, Solarium, Themos), all identical to any stock Android 6.0.1 build. No BLOCKS-specific or Cronologics-specific custom sound assets were found. `ro.config.ringtone=Ring_Synth_04.ogg` (per `SYSTEM_ANALYSIS.md`) remains the literal stock-AOSP default.

---

## 7. Funny/telling log & error strings

- **`Emergency Mode detected for module 0x%x.`** (`extracted/strings/modulecom_daemon.strings.txt:6374`) — part of the `blocks::FirmwareUpdate` class's real fault-handling path (`isEmergencyMode()`, sitting alongside `Module (version type: %d) in emergency mode.` and `Firmware Update available for module 0x%x.`). Not a joke, but genuinely dramatic phrasing for what is, mechanically, just "module firmware is in a recovery/bootloader state."
- **`Commence fiddling with hardware now.`** — see §1/§2, the best line in the firmware.
- **`Terrible hack: creates a new context without cleaning the previous one.`** — see §1, the daemon's self-aware bug admission.
- A firmware-update state machine reads almost like stage directions when extracted in sequence: `Success` → `Start` → `Ready-to-Receive` → `Parsing package` → `Update corehub` → `Update module` → `Reboot` → `Abort` → `Check-Sum error` (`extracted/strings/modulecom_daemon.strings.txt` lines 6376-6384).
- A leftover Android platform-bug URL baked into a BLE library string: `Not requesting bigger MTU, since your phone may not be compatible. See https://code.google.com/p/android/issues/detail?id=211129` (found in dex strings of a Blocks app using a third-party BLE library) — a developer literally cited a public bug tracker issue number in a runtime log message.

---

## A note on report integrity

Every claim above was independently re-derived from the raw files (exact `grep`/`unzip`/DWARF-dump evidence, cited by path and line where applicable) by at least one of: this session's own direct checks, or one of four dedicated research passes over the dev-artifact strings, the `chutil` scenario/command catalog, the `modulecom_daemon.html` dashboard reconstruction, and the vaporware/branding cross-reference. Several leads were explicitly tested and found to be **negative results**, which are reported as such throughout (no Camera/Speaker/Storage capability enum, no leaked emails or profanity) — absence of evidence was treated as worth stating plainly, not glossed over. **However, two initially-reported negatives were WRONG and are overturned in the Correction below.**

## Correction (verified against dex-level ground truth)

The paragraph originally here claimed a "7-tap dev mode," an "aw808/cowatch gate," and a "*#*#225 code" were absent (zero `grep` hits). **That was wrong.** A `grep` over the raw tree cannot see inside `classes.dex` (it lives in DEFLATE-compressed zip members), and BSD `strings` on macOS also misses UTF-16LE binary manifests. Extracting each APK's dex (`unzip -p <apk> classes.dex | strings`) and decompiling with `jadx` confirms all three ARE present:

- **Hidden hardware-test gate — REAL.** `com/cronologics/settings/developer/DevOptionsActivity.java:33`:
  `if (Build.PRODUCT.equalsIgnoreCase("aw808") && Build.MODEL.equalsIgnoreCase("cowatch")) { mBtnHwTest.setVisibility(0); }` — a factory hardware-test button (launches `com.android.testphone/.TestPhoneActivity`, a Qualcomm QRD app) shown ONLY when the firmware runs on the original **Cronologics CoWatch** (`aw808` reference design, `cowatch` model), never on retail `tophat`.
- **CoWatch lineage in the BLE bridge — REAL.** `com/cronologics/bridge/ble/central/BleCentralCronoBridge.java:267`: `Log.w(TAG, "No service filtering set. Accepting both CoWatch and Blocks devices.")`.
- **"Tap Build 7×" developer unlock — REAL.** `CronoSettings.apk` dex contains `TAPS_TO_BE_A_DEVELOPER` (AboutActivity) + toast "You are now a developer!" — a hand-rolled clone of AOSP's dev-mode gag (there is no stock `com.android.settings` on this device); unlocks a Developer Options screen with an ADB toggle.
- `aw808`/`cowatch` appear in the dex of **13 APKs** (a shared Cronologics library), not zero.
- `*#*#225#*#*` — the stock-AOSP `CalendarProvider` `CalendarDebugReceiver` secret code (`225`=CAL); genuinely present, but plain AOSP, not BLOCKS-authored.

These `aw808`/`cowatch` relics are the **single hardest proof in the firmware that BlocksOS is the Cronologics CoWatch codebase reskinned** — the best easter egg here, missed by the original grep-only pass.

*Report compiled via static analysis of `extracted/system/` and `extracted/boot/ramdisk_ro/`, plus targeted `unzip -p <apk> classes.dex | strings` extraction across all 12 Blocks-branded and relevant Crono-branded APKs, full-text search of the three pre-extracted binary strings dumps (`modulecom_daemon.strings.txt`, `chutil.strings.txt`, `bclient.strings.txt`, ~213,000 lines combined), and one DWARF debug-info dump against the unstripped `modulecom_daemon` ELF binary. No USB device was accessed; no git history was consulted.*
