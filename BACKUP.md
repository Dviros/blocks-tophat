# BLOCKS Smartwatch (prototype `tophat`) — Backup & Enhance

## Device (read off the unit, not assumed)
- **Model:** BLOCKS modular smartwatch — **prototype**, codename `tophat`, ODM **Compal**
- **SoC:** Qualcomm **Snapdragon Wear 2100** (APQ8009w / **MSM8909w**), quad Cortex-A7
- **OS:** Android **6.0.1** (MMB29M), `user`/**test-keys**, security patch 2016-05-01
  - build: `BLOCKS/blocks_tophat/tophat:6.0.1/MMB29M/tincho558811230021` — built 2017-11-23 (AR timezone)
- **eMMC:** 3.64 GB (7,634,944 × 512-byte sectors) · **RAM:** 512 MB
- **Bootloader:** **UNLOCKED** (`verifiedbootstate=orange`)
- **Secure boot:** **OFF** — Sahara reports "unfused device" → unsigned images accepted
- **Root:** none (`ro.secure=1`, `ro.debuggable=0`, no `su`) — get it via Magisk-patched boot (see Enhance)

## Toolchain (all local, macOS-native — no Windows needed)
- `./venv/bin/edl` — Qualcomm EDL 9008 backup/restore (bkerler/edl)
- `fastboot` (`/opt/homebrew/bin/fastboot`) — flashing, since bootloader is unlocked
- `adb` — runtime access
- (mtkclient is also in the venv but UNUSED — this unit is Qualcomm, not MediaTek)

## Backup — DONE & VERIFIED ✅
- `edl_backup/` — **32 partition images** + `gpt_main0.bin`/`gpt_backup0.bin` + `rawprogram0.xml` (1.4 GB)
- `MANIFEST.sha256` — SHA-256 of every file
- All 32 firmware partitions verified byte-exact vs the GPT. `userdata` skipped (2.15 GB, ~91 MB used, non-firmware).
- Command used:
  ```bash
  ./venv/bin/edl rl edl_backup --genxml --skip=userdata
  ```
- To also grab userdata later (device in EDL):
  ```bash
  ./venv/bin/edl r userdata edl_backup/userdata.bin
  ```
- **Copy `edl_backup/` + `MANIFEST.sha256` to a second disk.** That is the restore point.

## EDL mode (for backup/restore)
- **Enter:** `adb reboot edl`  → screen goes black (normal), enumerates as Qualcomm QDLoader **9008**
- **Exit:** `./venv/bin/edl reset`  (a USB I/O error on reset is normal — it means the device rebooted) — or hold power ~10-15 s

## Restore
Per-partition, device in EDL:
```bash
./venv/bin/edl w boot   edl_backup/boot.bin
./venv/bin/edl w system edl_backup/system.bin
```
Or, for the fastboot-flashable set, from `fastboot` (bootloader unlocked):
```bash
adb reboot bootloader
fastboot flash boot     edl_backup/boot.bin
fastboot flash system   edl_backup/system.bin
fastboot flash recovery edl_backup/recovery.bin
fastboot reboot
```

## Enhance (only after the backup is copied off-machine)
No custom ROM exists for this Qualcomm prototype (the OpenWatchProject `harmony` TWRP/LineageOS is
MediaTek — wrong SoC, do not use). Realistic, reversible mods:
1. **Root** — Magisk-patch `boot.bin`:
   - copy `boot.bin` to a phone with Magisk → "Install → Patch a file" → get `magisk_patched.img`
   - `adb reboot bootloader && fastboot flash boot magisk_patched.img && fastboot reboot`
2. **System edits** — mount `system.bin` (ext4) on the Mac, modify, `fastboot flash system system.bin`. No signature checks to defeat.
3. Revert anything by reflashing the original image from `edl_backup/`.

## Partition map (from GPT) — ⚠ DO NOT erase the radio/secure/bootchain ones
| Partition | Size | Notes |
|---|---|---|
| modem | 64 MB | radio firmware |
| sbl1 / sbl1bak | 512 KB | secondary bootloader — **do not touch** |
| aboot / abootbak | 1 MB | Android bootloader (fastboot) |
| rpm / tz / cmnlib / keymaster (+bak) | small | power mgr, TrustZone, keymaster — **do not touch** |
| modemst1 / modemst2 / fsg / fsc | 1.5 MB ea | **radio NV / calibration — never wipe** |
| persist | 32 MB | **sensor calibration, MACs — never wipe** |
| sec / ssd / devinfo / keystore | small | secure config / device info |
| misc | 1 MB | bootloader control (bcb) |
| splash | 10 MB | boot logo |
| DDR | 32 KB | DDR training |
| boot | 32 MB | kernel + ramdisk — root target |
| recovery | 32 MB | recovery |
| system | 800 MB | Android system |
| cache | 350 MB | cache |
| oem / config | 64 MB / 512 KB | OEM data |
| userdata | 2.15 GB | user data (skipped in backup) |

`device-info/` holds the full `getprop`, `/proc/partitions`, GPT dump and edl logs.
