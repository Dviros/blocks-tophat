# BLOCKS Modular Smartwatch — Prototype `tophat` — Teardown, Backup & Docs

Reverse-engineering, firmware backup, and documentation of a **prototype** BLOCKS modular
smartwatch — the crowdfunded (Kickstarter 2015) "world's first modular smartwatch" by the
now-defunct **BLOCKS Wearables Ltd**. This particular unit is an **engineering prototype**
(codename `tophat`, ODM Compal), not a retail unit.

> ⚠️ **Preservation project, not a ROM release.** This repo documents the device and the
> *method*. It deliberately **excludes** the firmware binaries themselves (proprietary
> BLOCKS/Compal/Qualcomm IP) and **all device-unique secrets** (serials, radio calibration
> in `persist`/`modemst`/`fsg`, keys in `keystore`/`keymaster`). Nothing here lets you clone
> an identity or bypass anyone's security. If you own one of these, follow the process on
> *your own* hardware.

## What it actually is (determined by reading the silicon, not marketing)

| | |
|---|---|
| Model | BLOCKS modular smartwatch — **prototype** |
| Codename / ODM | `tophat` / **Compal** |
| SoC | **Qualcomm Snapdragon Wear 2100** (APQ8009w / MSM8909w), quad Cortex-A7 |
| RAM / Storage | 512 MB / 3.64 GB eMMC |
| OS | Android **6.0.1** (MMB29M), `user` / **test-keys** |
| Build stamp | `tincho558811230021`, built **2017-11-23** (AR timezone) |
| Security patch | 2016-05-01 |
| Bootloader | **UNLOCKED** (`verifiedbootstate=orange`) |
| Secure boot | **OFF** — Qualcomm Sahara reports "unfused device" |
| SELinux | **permissive** (per kernel cmdline) |
| Root (stock) | none — `user` build, `adbd` compiled `ALLOW_ADBD_ROOT=0` |

Note the retail units that shipped to backers in 2018 were a **different** platform
(MediaTek MT6580, OpenWatchProject codename `harmony`). This prototype predates that switch
and is **Qualcomm** — so MediaTek tooling and the community `harmony` TWRP/LineageOS do **not**
apply here.

### How the SoC was identified
1. `adb shell getprop` → `ro.board.platform=msm8909`, `ro.hardware=qcom` (not MediaTek).
2. `adb reboot edl` → Qualcomm EDL 9008. Sahara handshake reported
   `HWID 0x000520e1`, `TargetName=MSM8909w`, and **"Possibly unfused device"** →
   [edl.py](https://github.com/bkerler/edl) auto-selected a `wear3100` firehose loader.
3. GPT read back cleanly → the partition table below.

## Partition map (34 partitions, from GPT)

Bootchain/secure/radio (**never erase**): `sbl1(bak)`, `rpm(bak)`, `tz(bak)`, `aboot(bak)`,
`cmnlib(bak)`, `keymaster(bak)`, `sec`, `ssd`, `devinfo`, `modem`, `modemst1/2`, `fsg`, `fsc`,
`persist` (sensor calibration + MACs), `keystore`.
Flashable/interesting: `boot` (32 MB), `recovery` (32 MB), `system` (800 MB), `cache`,
`splash` (boot logo), `oem`, `config`, `misc` (bcb), `userdata`.

Full details + sizes in [`BACKUP.md`](BACKUP.md).

## Key findings (full detail in [SYSTEM_ANALYSIS.md](SYSTEM_ANALYSIS.md))

- **OS lineage:** BlocksOS is a fork of **Cronologics Corp's** wearable OS (`com.cronologics.*` packages). Google acquired Cronologics in Dec 2016, forcing BLOCKS to self-maintain the stack — hence the in-house Nov 2017 build.
- **The module bus is SPI, not I²C/UART.** A root userspace daemon `modulecom_daemon` (`/system/vendor/bin`, ZeroMQ to apps, *no* Android HAL, *no* Binder) drives a **"CoreHub" MCU** — an ST part at `/sys/bus/spi/devices/spi5.0/st-manager` (SPI bus 5). CoreHub fans out to the swappable hardware modules.
- **Per-module MCU firmware** ships in `/system/etc/firmware/modules/` (`EZW2_{CoreHub,GPS,FLASHLIGHT,BUTTON,BAROMETER,EXTRA_BATT,HRM}_*.bin`); the daemon can OTA-flash them over CoreHub. "EZW2" is an internal pre-BLOCKS codename.
- **Clean capability abstraction:** apps query `blocks::Capability` (Temperature/Pressure/HeartRate/BatteryLevel…) without knowing which physical module answers.
- **Engineering CLIs left in the shipping build:** `chutil` (CoreHub test tool, scenarios like `led_stress`) and `bclient` (API client) — unstripped, full debug symbols.
- **Security reality:** `test-keys`, permissive SELinux, ADB in the default USB composition, factory/MMI test suite + QTI sample-auth demo code left in, and a world-writable (`chmod 666`) SPI node — `modulecom_daemon` runs as root parsing untrusted data from physically-swappable modules with no MAC confinement. Classic un-hardened prototype.

**Top improvement targets:** lock down + strip the CoreHub daemon and its SPI node · debloat factory/sample cruft · drop the unused CDMA/LTE RIL stack · promote CoreHub to a real HIDL/AIDL HAL · backport kernel CVE fixes (patch level 2016-05-01).

## Repo layout
```
README.md              this file
BACKUP.md              full backup/restore/EDL/fastboot procedure
SYSTEM_ANALYSIS.md     reverse-engineering findings (apps, module bus, init, improvements)
tools/
  patch_ramdisk_prop.py   surgical default.prop editor for the boot ramdisk (root prep)
  mkbootimg/              AOSP boot image pack/unpack (vendored, git-ignored)
```
(`edl_backup/`, `device-info/`, `venv/` are git-ignored — binaries & secrets stay local.)

## Procedures (summary — see BACKUP.md)
- **Full backup (read-only, no root):** `adb reboot edl` → `edl rl edl_backup --genxml`.
  All 34 partitions verified byte-exact vs GPT, SHA-256 in `MANIFEST.sha256`.
- **Restore:** `edl w <part> <file>` (EDL) or `fastboot flash <part> <file>` (bootloader unlocked).
- **Boot repack / root prep:** unpack `boot` with `tools/mkbootimg/unpack_bootimg.py`, edit the
  ramdisk with `tools/patch_ramdisk_prop.py`, repack with `mkbootimg.py`, **test with
  `fastboot boot` (RAM, no flash)** before ever flashing.
- **Root:** property-flip alone does **not** work (user-build `adbd`). Requires Magisk
  (patch `boot` with the Magisk app) or a ramdisk-level injection. Every step reversible from
  the backup.

## Reversibility guarantee
Every partition is backed up and checksummed before anything is written. `fastboot boot` is
used to *test* modified images from RAM without flashing. Any change is undone by reflashing
the original image from the local backup.

## Tools & credits
- [edl.py](https://github.com/bkerler/edl) (bkerler) — Qualcomm Sahara/Firehose backup/restore
- [AOSP mkbootimg](https://android.googlesource.com/platform/system/tools/mkbootimg) — boot image pack/unpack
- `e2fsprogs` `debugfs` — read-only ext4 extraction of `system` on macOS (no mount needed)

*Not affiliated with BLOCKS Wearables Ltd (defunct), Compal, or Qualcomm. All trademarks
belong to their owners. Documented for preservation, research, and repair of a rare device.*
