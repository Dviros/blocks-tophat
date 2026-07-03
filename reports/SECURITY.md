# BLOCKS "tophat" Firmware — Security & Bug Hunt

**Device:** BLOCKS modular smartwatch prototype, codename `tophat` | Compal ODM | Qualcomm MSM8909w | Android 6.0.1 (MMB29M) | `user`/`test-keys` | SELinux **permissive** (confirmed live via `device-info/getprop.txt`: `[ro.boot.selinux]: [permissive]`) | Kernel **Linux 3.18.24**, built 2016-09-13 (`device-info/kernel-cpu.txt`) | Bootloader unlocked.

**Method:** Static analysis only. No USB device touched, no git run. Sources: `extracted/system/`, `extracted/boot/ramdisk_ro/`, `extracted/strings/{modulecom_daemon,chutil,bclient}.strings.txt`, `device-info/*`, and `jadx`-decompiled APKs (24 of 26 priv-app packages fully decompiled and manifest-audited by two independent passes; `BlocksGPS`/`BlocksNavigator` — the two 17-18MB map-asset-bundled apps, both bundling Google Maps SDK code — could not be decompiled by either pass: jadx crashes with a `StackOverflowError` in `RootNode.deepResolveMethod` (infinite/cyclic type-resolution recursion), reproducible even with an increased thread stack size. No `aapt`/`aapt2` was available on the host as a manifest-only fallback. Their component/permission/secrets posture is an **acknowledged, unaudited coverage gap** — see "Coverage Gaps" at the end of this report.

**Important correction made during this audit:** the task brief's working hypothesis that `CronoBridgeService` is an exposed ZeroMQ bridge to `modulecom_daemon` was **investigated and disproven**. Full decompilation shows `CronoBridgeService`'s `BridgeService` (`com.cronologics.cronobridgeservice.BridgeService`) is a **Bluetooth LE bridge to a paired companion phone** (classes `BleCentralCronoBridge`/`BlePeripheralCronoBridge`, protobuf messages `GetTimeResponse`/`SetBrightnessRequest`/etc.) — no ZeroMQ symbol and no reference to `modulecom_daemon` exists anywhere across all 24 successfully decompiled source trees. Its AIDL Binder (`ICronoBridge.Stub`) is correctly gated by `cronologics.permission.BLUETOOTH_BRIDGE` at `protectionLevel="signatureOrSystem"` and is **not** exploitable by an arbitrary third-party app on its own (independent of the fleet-wide test-key caveat in Finding #3). This is called out explicitly so the correction isn't lost: the real "modulecom_daemon exposed to apps" surface is the TCP ZeroMQ API covered in Finding #1, not `CronoBridgeService`.

Every finding below cites an exact file path and string/symbol/line. Where a claim could not be fully verified from static artifacts alone (e.g. runtime reachability, disassembly-only confirmations), this is stated explicitly rather than asserted.

---

## Ranked Findings

### 1. CRITICAL — CoreHub API daemon binds a wildcard TCP socket, not a Unix socket — network-reachable root service, zero authentication strings anywhere
**Evidence:**
- `extracted/strings/modulecom_daemon.strings.txt:6135-6136`: literal strings `tcp://*:6676` and `tcp://*:6677`, sitting directly between the log lines `"CoreHub server started."` / `"Driver initialisation complete."` / `"Unable to start API server."` / `"API server started."` — i.e. these are the daemon's own ZeroMQ **bind** addresses for its `apiSocket`.
- Cross-confirmed via the client CLI: `extracted/strings/bclient.strings.txt:4785-4786` hardcodes `tcp://localhost:6676` / `tcp://localhost:6677` as its **connect** targets.
- `ipc://` (the Unix-socket ZeroMQ transport) has **zero hits** in any of the three binaries — TCP is the *only* external transport implemented. Internal broker-to-worker plumbing uses `inproc://brokerctrl` / `inproc://backend` (in-process only, not reachable externally) — confirming the `tcp://*` bind really is the external-facing surface, not a naming coincidence.
- `modulecom_daemon` runs as `user root / group root`, class `main` (`extracted/boot/ramdisk_ro/init.qcom.rc:6-9`).
- Device has a full WiFi radio stack confirmed present and wired up: `wpa_supplicant -iwlan0` (`extracted/boot/ramdisk_ro/init.qcom.base.rc:611-615`), Prima WLAN firmware (`extracted/system/etc/firmware/wlan/prima/`), and a dedicated `CronoSettingsWifi` app — this is not a Bluetooth-only device; `tcp://*:6676/6677` is reachable from any device on the same WiFi network/hotspot the watch joins.
- No `iptables`/netfilter rule restricting these ports was found anywhere in `extracted/boot/ramdisk_ro/*.rc|*.sh` (grepped for `iptables|6676|6677` — zero hits besides the bind/connect strings themselves). No config-file override of the bind address exists (grepped for `127.0.0.1|BIND_ADDR|.conf|.ini` near the daemon's ZMQ setup — no override found; the wildcard is hardcoded).
- Exhaustive credential/auth-string search across `apiserver.cpp`/message-parsing area found zero `password|token|Authorization|Bearer|session|auth` strings of any kind tied to the API layer.

**Severity: Critical.** Any device on the watch's WiFi network gets an unauthenticated ZeroMQ connection straight into a root-owned daemon that implements `DirectComDriver` raw SPI passthrough (#3 below), `FirmwareUpdate` (#2 below), and GPS/heart-rate/battery data access — with no login, no pairing token, no TLS.

**Exploit scenario:** Attacker joins the same WiFi network as the watch (e.g. a shared hotspot, café WiFi, or a spoofed AP the watch auto-joins), opens a raw ZMQ REQ socket to `tcp://<watch-ip>:6676`, and sends a crafted `APIMessage` invoking `BeginDirectCommunication` (raw SPI/CoreHub access) or the firmware-update flow — all as root, zero authentication.

---

### 2. CRITICAL — Module & CoreHub firmware integrity is CRC32-checksum-only; no cryptographic signature anywhere in the update path
**Evidence:**
- Full `E_FW_UPD_STATUS_*` enum recovered from `extracted/strings/chutil.strings.txt:13304-13326` (22 states): `NONE, SUCCESS, FAIL, START, READY_TO_RECEIVE, PARSING_PKG, TO_UPD_COREHUB, TO_UPD_MODULE, REBOOT, ABORT, CHECK_SUM_ERROR, SAME_VERSION_ERROR, OLD_VERSION_ERROR, MEM_ERASE_ERROR, PKG_SEQUENCE_ERROR, PARSING_PKG_ERROR, MODULE_BUSY_ERROR, MODULE_CHECK_SUM_ERROR, HAVE_BOOTLOADER_ERROR, FIRMWARE_SIZE_ERROR, MODULE_DETACH_ERROR, STANDARD_CMD_ERROR, BIN_CHECKSUM_ERROR`. Every error class is checksum/sequence/size/state-class — **zero signature-class states** (no `SIGNATURE_INVALID`, no `UNTRUSTED_SOURCE`, no `CERT_ERROR`).
- Concrete checksum implementation confirmed in `modulecom_daemon.strings.txt`: `blocksmsg::crc32` (`_ZN9blocksmsg5crc32EPKhj`), `blocks::CheckSum` class, `blocks::getFWFileChecksum`, `blocksmsg::CoreHubMessage::testChecksum`.
- Exhaustive search for `sha|SHA1|SHA256|RSA|pubkey|HMAC|sign|Signature|cert|X509` across `chutil.strings.txt` and `modulecom_daemon.strings.txt`: the only near-miss hits are C++ mangled-template noise (`__rebind_alloc<...RSA_...>` false-positive substring matches inside STL allocator symbol names) and one unrelated hit — `"Invalid message signature."` — which refers to the **API message envelope's magic-number/header validation**, not a firmware cryptographic signature. **Zero genuine crypto-signing primitives found anywhere in either binary.**
- Firmware blobs live at `extracted/system/etc/firmware/modules/EZW2_*_R.bin` (CoreHub, GPS, Flashlight, Button, Barometer, Extra-Battery, HRM) — all share the same `20164301` datecode, no per-file signature/manifest sidecar file exists in that directory.
- The OS-level FOTA (firmware-over-the-air) update path shows the **identical, and now fully confirmed via decompiled code, pattern**: `com.cronologics.settings.fota.FotaUpdateActivity` (`CronoSettings.apk`) fetches update manifests over **plain cleartext HTTP**:
  ```java
  API_URL = Build.PRODUCT.equalsIgnoreCase("blocks_tophat")
      ? "http://fota.blocks.services/api/v1/updates"
      : "http://fota.crono.services/api/v1/updates";
  ...
  DownloadManager.Request request = new DownloadManager.Request(Uri.parse(mUpdateJson.getString("url")));
  ...
  // VerifyUpdate.doInBackground():
  if (hexString.toString().equals(mUpdateJson.getString("sha256sum"))) { return true; }
  ...
  // flashAndReboot():
  os.writeBytes("echo '--update_package=" + file + "' >> /cache/recovery/command\n");
  ...reboot("recovery")
  ```
  This confirms and sharpens the checksum-only hypothesis: the download URL AND the `sha256sum` "verification" value both come from the **same single plaintext HTTP JSON response** — there is no HTTPS, no certificate pinning, and no independent trust root. An attacker who rewrites the JSON in transit trivially rewrites `sha256sum` to match their own malicious payload; the hash only detects accidental transit corruption, not tampering. After the check "passes," a short auto-accept timer fires `flashAndReboot()`, which writes `--update_package=<attacker file>` directly into `/cache/recovery/command` and reboots into recovery.

**Severity: Critical.** CRC32 (module/CoreHub firmware) and self-supplied-SHA256 (OS FOTA) are both trivially forgeable by any attacker who can reach the respective update path (via finding #1's TCP socket for the module side; via a network MITM position for the OS side). Neither path has a chain-of-trust root (no embedded pubkey/cert) anchoring firmware/updates to the vendor.

**Exploit scenario A (module/CoreHub firmware):** Attacker reaching the API socket (#1) or with local shell crafts a malicious CoreHub-MCU or module-MCU firmware image, computes a matching CRC32, and pushes it via the firmware-update message flow — potential persistent compromise of hardware below the Android OS.
**Exploit scenario B (OS FOTA):** A network-position attacker (rogue AP, ARP spoofing, or DNS spoofing of `fota.blocks.services`/`fota.crono.services`) serves a malicious update manifest with an attacker-controlled `url` and a matching self-computed `sha256sum`; the watch downloads and, after the short auto-accept window, writes `--update_package=<attacker-controlled file>` to `/cache/recovery/command` and reboots into recovery. Whether this becomes full code execution below Android depends on whether the recovery partition's own OTA-package signature enforcement is intact — that lives outside these APKs (in the recovery/boot partition) and was not independently verified in this pass — but at minimum this gives an attacker forced, unauthenticated control over what the watch attempts to flash, i.e. reliable bricking/DoS at will, and plausibly full compromise if recovery-side signature checking is weak (common on low-volume prototype OEM builds like this one).

---

### 3. CRITICAL — Confused-deputy chain: `normal`-level-permission-gated ContentProvider write → arbitrary attacker-supplied Intent → privileged `startActivity`/`startService`/`sendBroadcast`
**Evidence:** `extracted/system/priv-app/CronoContainerSdk/CronoContainerSdk.apk`, classes `com.cronologics.sdk.container.providers.ContainersProvider` and `com.cronologics.sdk.watchface.WatchfaceService` (both decompiled).
- `ContainersProvider` is `exported="true"`, `grantUriPermissions="true"`, gated only by the `READ_STATE`/`WRITE_STATE`/`READ_CONTAINERS`/`WRITE_CONTAINERS`/`READ_PACKAGE_CONTAINERS`/`WRITE_PACKAGE_CONTAINERS` permissions — which are declared `protectionLevel="normal"` in `CronoLauncher/AndroidManifest.xml` (see Finding #8) — i.e. any app can self-grant write access with zero signature check and zero runtime prompt.
- `insert()`/`update()` on this provider accept a caller-supplied `CLICK_INTENT` column, parsed via `ContainerDataUtils.getIntentFromUriString()` → `Intent.parseUri(uri, Intent.URI_INTENT_SCHEME)` — i.e. a raw, attacker-controlled `intent:` URI string is deserialized into a live `Intent` object with no target-component/action allowlist.
- `WatchfaceService` later fires that stored Intent **unconditionally** when the corresponding watch-tile is tapped:
  ```java
  List<ResolveInfo> receiverList = cqc.ws.getPackageManager().queryBroadcastReceivers(cqc.ci.clickIntent, ...);
  if (receiverList.size() > 0) { cqc.ws.sendBroadcast(cqc.ci.clickIntent); }
  List<ResolveInfo> serviceList = cqc.ws.getPackageManager().queryIntentServices(cqc.ci.clickIntent, ...);
  if (serviceList.size() > 0) { cqc.ws.startService(cqc.ci.clickIntent); }
  List<ResolveInfo> activityList = cqc.ws.getPackageManager().queryIntentActivities(cqc.ci.clickIntent, ...);
  if (activityList.size() > 0) { cqc.ws.startActivity(cqc.ci.clickIntent); }
  ```
  This fires from within the privileged watchface/container-hosting process, not the attacker's own process — a textbook confused-deputy / Intent-redirection pattern.

**Severity: Critical.** This chains a broken-access-control bug (Finding #8's `normal` permission) into a genuine privilege-escalation primitive: a fully unprivileged third-party app (zero dangerous permissions declared) can get a trusted, higher-privileged system-app process to launch an arbitrary activity/service/broadcast of the attacker's choosing.

**Exploit scenario:** A malicious app with zero declared "dangerous" permissions self-grants the `normal`-level container permissions, writes a crafted `intent:` URI as a watch tile's `CLICK_INTENT` via the open `ContainersProvider`, and waits for the user to tap that tile on the watchface. `WatchfaceService` (running with system-app identity) fires `startActivity`/`startService`/`sendBroadcast` on the attacker's fully-controlled Intent — letting the attacker reach otherwise-unreachable components, spoof a system-looking UI launched from a trusted process, or trigger a privileged broadcast the attacker's own app could never send directly.

---

### 4. HIGH — Systemic permission-theater: every custom `signatureOrSystem`/APK-signature-based protection is satisfied by the public, well-known AOSP `test-key`
**Evidence:**
- **Every APK checked is signed with the identical certificate** — verified via `openssl pkcs7 -inform DER -print_certs` on `META-INF/CERT.RSA` from `CronoBridgeService.apk`, `BlocksContainer.apk`, and the unrelated stock `system/app/Bluetooth/Bluetooth.apk`: `Subject/Issuer: C=US, ST=California, L=Mountain View, O=Android, OU=Android, CN=Android, emailAddress=android@android.com`, Serial `b3:99:80:86:d0:56:cf:fa`, Validity `Apr 15 2008 – Sep 1 2035`, `md5WithRSAEncryption`. These exact fields (serial, validity window, MD5 signing algo) identify this as **the publicly-committed AOSP `testkey`** (`build/target/product/security/testkey.{pk8,x509.pem}` in AOSP source since 2008, mirrored on countless public repos) — matching `ro.build.tags=test-keys` in `build.prop`.
- `CronoBridgeService/AndroidManifest.xml` (decompiled): `BridgeService` runs in the **`:system` process** (`android:process=":system"` — i.e. inside `system_server`), holds `INSTALL_PACKAGES`, `WRITE_SECURE_SETTINGS`, `BLUETOOTH_PRIVILEGED`, is gated by `cronologics.permission.BLUETOOTH_BRIDGE` at `protectionLevel="signatureOrSystem"`. Because ANY attacker-built APK can be signed with the publicly-downloadable AOSP testkey and will then match this device's platform signature, `signatureOrSystem` provides **no real protection here** — a self-signed-with-the-public-testkey malicious app can bind to a `:system`-process service holding install/secure-settings/Bluetooth-privileged permissions.
- Same weakness applies to `CronoSettingsProvider`'s `READ_SETTINGS`/`WRITE_SETTINGS` permissions (`protectionLevel="signatureOrSystem"`, `extracted from CronoSettingsProvider/AndroidManifest.xml`) and any other `signature`/`signatureOrSystem`-gated component in the 26-app set — the guarantee these declarations are meant to provide is broken fleet-wide by the shared public test-key, not per-component.
- This is distinct from (and independent of) findings #5/#12 below, which cover components with **no signature gate at all**.

**Severity: High.** This doesn't grant unauthenticated *network* access like #1, but it means the entire "signature-protected" tier of the app security model collapses to "any developer who knows to sign with the public AOSP testkey" — a very low bar, well-documented in every Android security teardown methodology.

**Exploit scenario:** Attacker builds a malicious APK, signs it with the publicly available AOSP `testkey.pk8`/`testkey.x509.pem`, sideloads it (bootloader unlocked, `ro.debuggable=0` but ADB is enabled by default per prior analysis §7) — the app now satisfies `signatureOrSystem` for `cronologics.permission.BLUETOOTH_BRIDGE`, `com.cronologics.provider.settings.permission.{READ,WRITE}_SETTINGS`, and any other custom signature permission on the device.

---

### 4. MEDIUM-HIGH — `CronoResponses`' quick-reply AIDL binder is fully exported with no permission — any app can read or silently overwrite the user's canned reply texts
**Evidence:** `extracted/system/priv-app/CronoResponses/CronoResponses.apk`, decompiled `AndroidManifest.xml` and `com.cronologics.responses.ResponseService`:
```xml
<service android:name="com.cronologics.responses.ResponseService" android:enabled="true" android:exported="true"/>
```
```java
public String[] getQuickResponses() throws RemoteException { return ResponseService.getSavedResponses(ResponseService.this); }
public void storeQuickResponses(String[] responses) throws RemoteException { ResponseService.saveResponses(responses, ResponseService.this); }
```
`onBind()` returns the full service Binder unconditionally to any caller — no permission attribute anywhere in the manifest. The same APK also exports, with no permission: `ResponseActivity`, `HoundifyAssistantActivity` (third-party voice-assistant integration), `EmojiPickerActivity`, and `EmojiPickerDrawerActivity`.

**Severity: Medium-High.** Any third-party app can bind to this AIDL service and call `storeQuickResponses()` to silently overwrite the user's canned quick-reply texts (used to auto-respond to incoming notifications) — a believable social-engineering/tampering vector (e.g. silently replacing a "running late" quick-reply with something embarrassing or malicious-looking) — or call `getQuickResponses()` to read them (mild privacy exposure). The exported `HoundifyAssistantActivity` also lets an untrusted app trigger the voice-assistant flow without any permission check.

**Exploit scenario:** A malicious app binds to `com.cronologics.responses.ResponseService` with zero declared permissions and calls `storeQuickResponses(["attacker-controlled text", ...])`, silently corrupting the user's quick-reply presets the next time they auto-respond to a notification from their watch.

---

### 5. HIGH — `HealthContentProvider` fully exported with ZERO permission — any app reads/writes raw heart-rate and step-count data; `sortOrder`/`selection` passed unsanitized into raw SQL
**Evidence:** `extracted/system/priv-app/CronoHealthProvider/CronoHealthProvider.apk`, decompiled `AndroidManifest.xml`:
```xml
<provider
    android:name="com.cronologics.health.provider.HealthContentProvider"
    android:exported="true"
    android:authorities="com.cronologics.health.provider"
    android:syncable="false"/>
```
No `android:permission`, `android:readPermission`, or `android:writePermission` attribute at all. Same file also exports `com.cronologics.health.HealthTestActivity` with `exported="true"` and no permission — a leftover test/debug activity.

Implementation, `HealthContentProvider.java` (full class, 90 lines):
```java
public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
    String table = getTableName(uri);
    return this.mDb.getReadableDatabase().query(table, projection, selection, selectionArgs, null, null, sortOrder);
}
public Uri insert(Uri uri, ContentValues values) {
    String table = getTableName(uri);
    long newRowId = this.mDb.getWritableDatabase().insert(table, null, values);
    return ContentUris.withAppendedId(uri, newRowId);
}
```
URIs `content://com.cronologics.health.provider/health_steps` and `/health_heartrate` map directly to SQLite tables `health_steps`/`health_heartrate`. `selection` and `sortOrder` are passed straight into `SQLiteDatabase.query()` with no validation — `sortOrder` in particular is never parameterized by the Android `ContentProvider`/`SQLiteDatabase` API, making it a classic SQL-injection vector via a malicious ORDER BY clause.

**Severity: High.** Full unauthenticated read AND write access to sensitive biometric data (heart rate, steps) from any co-installed app — no permission declared anywhere in the manifest, confirmed twice (manifest + implementation). Layered SQL-injection risk via `sortOrder` on top of the base exposure.

**Exploit scenario:** Any third-party app installed on the watch queries `content://com.cronologics.health.provider/health_heartrate` with zero permissions declared and exfiltrates the user's full heart-rate/step history; the same app can `insert()` fabricated readings to corrupt health tracking, or attempt a `sortOrder`-based SQL injection to read data outside the intended table.

---

### 6. HIGH — World-writable SPI control node to the CoreHub MCU (`chmod 666`), no SELinux domain/group restriction visible in the init script, plus two additional undifferentiated local access paths
**Evidence:**
- `extracted/boot/ramdisk_ro/init.rc:469-470`:
  ```
  /* Corehub permission for IPC server */
  chmod 666 /sys/bus/spi/devices/spi5.0/st-manager
  ```
  Bare `chmod 666` (world read+write), no `chown` to a dedicated group in this block, no wrapping SELinux-only restriction visible in the plaintext init script.
- `extracted/boot/ramdisk_ro/file_contexts` has **no entry at all** for this sysfs path — it is not among the 46 `sysfs_*`-labeled entries checked (grepped full file), meaning it inherits the generic default `sysfs` label rather than a dedicated BLOCKS-authored domain.
- `extracted/boot/ramdisk_ro/service_contexts`: **zero** `modulecom` entries (confirmed via `grep -c`) — the daemon is not a Binder service.
- `seapp_contexts`: **zero** `modulecom`/`corehub` entries.
- `sepolicy` (binary) `strings` dump shows exactly 3 BLOCKS-authored labels exist at all: `modulecom_daemon`, `modulecom_daemon_exec`, `modulecom_daemon_tmpfs` — an exec-domain label for the daemon itself, but no policy artifact restricting who can `open()`/`write()` the sysfs node was found (would require CIL/binary policy decompilation to fully rule out — not performed, flagged as a residual unknown).
- With SELinux **permissive** confirmed live (`device-info/getprop.txt: [ro.boot.selinux]: [permissive]`), even if such a restrictive rule existed in the compiled policy, it would not be enforced today regardless.
- **Two additional, distinct local access paths to CoreHub were identified, expanding the surface beyond what prior analysis covered:**
  1. `chutil` (`extracted/system/vendor/bin/chutil`, mode `0755`) talks directly to `/dev/corehub/`, bypassing the TCP API entirely — confirmed via zero `tcp://`/`6676`/`6677` hits in `chutil.strings.txt` (unlike `bclient`). A previously-undocumented custom Linux **netlink family `NETLINK_COREHUB`** was found in `modulecom_daemon.strings.txt` (`sockaddr_nl`, `nlmsghdr`, `nlmsg_type/flags/seq/pid`, `MAX_PAYLOAD`, adjacent to `corehub::CoreHubClient::connect()`) — implying a custom kernel driver registers this netlink family; its permission model is unknown from userspace strings alone (kernel image/module analysis was out of scope here).
  2. `bclient`/`chutil`/`modulecom_daemon` all get **zero `file_contexts` entries of their own** (only the daemon's *exec* domain is labeled) — confirmed via `grep -n "bclient\|chutil" file_contexts` returning 0 matches — and all three binaries are mode `0755` (world-executable), so any process capable of `exec()`ing a binary (any app with native-code/`Runtime.exec()` capability, or an `adb shell` session — enabled by default per prior analysis §7) can directly invoke `bclient`/`chutil` against CoreHub with the caller's own ambient privilege, with no additional MAC confinement.

**Severity: High.** Three independent, non-overlapping local paths into the same root-adjacent CoreHub subsystem (raw sysfs write, `/dev/corehub/` via `chutil`, TCP API via `bclient`/finding #1), all effectively ungated under permissive SELinux.

**Exploit scenario:** A malicious or compromised co-located app opens and writes directly to `/sys/bus/spi/devices/spi5.0/st-manager`, bypassing `modulecom_daemon`'s own message-framing/checksum logic (see #13's positive finding on that framing layer) entirely — potential bus-level desync, MCU state corruption, or module spoofing at a lower layer than any of the daemon's own defenses can see.

---

### 7. HIGH — `DirectComDriver` raw SPI/CoreHub passthrough has no visible authorization gate and is trivially reachable via the `bclient` CLI
**Evidence:**
- `modulecom_daemon.strings.txt`: `virtual bool blocks::DirectComDriver::handleRequest(const api::APIMessage &)` sits immediately adjacent to literal strings `directcom`, `"Handling request."`, `"Invalid request message."` (source: `drivers/directcom.cpp`) — no interleaved permission/session/capability-check string.
- Exhaustive search across the entire 103,571-line `modulecom_daemon.strings.txt` for `permission|capability check|not authoriz|access denied|unauthorized`: **zero hits anywhere in the binary**, not just near DirectCom.
- `bclient.strings.txt:5043-5044` / `:6095-6096` confirm `BeginDirectCommunication`/`EndDirectCommunication` are first-class message types the general-purpose `bclient` CLI can invoke, backed by a real `api::IDirectComListener` C++ interface wired into a container (lines ~8346-8371).

**Severity: High** (would be Critical if proven remotely reachable with no additional step; scoped to High since it requires first reaching the API socket — which per finding #1 may be network-wide on the same WiFi segment, or trivially local via `bclient` per finding #6).

**Caveat:** Strings analysis cannot prove the complete absence of an authorization check with code-level certainty — only that no distinguishing log/error string for one exists anywhere in the binary, which is a strong negative signal but not a disassembly-confirmed one.

**Exploit scenario:** Any caller that reaches the API socket (WiFi per #1, or local `bclient` per #5) sends `BeginDirectCommunication` and obtains a raw pass-through channel to the CoreHub SPI bus, issuing arbitrary low-level commands to any attached module (GPS, heart-rate PPG sensor, Extra Battery Module) — bypassing every higher-level driver class's validation logic entirely.

---

### 8. MEDIUM — `com.cronologics.container.BIND_CONTAINER` and related container permissions declared with `protectionLevel="normal"` — any app can self-grant them with zero user prompt
**Evidence:** `extracted/system/priv-app/CronoLauncher/` decompiled manifest declares:
```xml
<permission android:name="com.cronologics.container.BIND_CONTAINER" android:protectionLevel="normal"/>
<permission android:name="com.cronologics.containers.provider.READ_STATE" android:protectionLevel="normal"/>
<permission android:name="com.cronologics.containers.provider.WRITE_STATE" android:protectionLevel="normal"/>
<permission android:name="com.cronologics.containers.provider.READ_PACKAGE_CONTAINERS" android:protectionLevel="normal"/>
<permission android:name="com.cronologics.containers.provider.WRITE_PACKAGE_CONTAINERS" android:protectionLevel="normal"/>
<permission android:name="com.cronologics.containers.provider.READ_CONTAINERS" android:protectionLevel="normal"/>
<permission android:name="com.cronologics.containers.provider.WRITE_CONTAINERS" android:protectionLevel="normal"/>
```
These gate at least 13 exported `*ContainerService` components across `BlocksContainer.apk` (8 services: Adventure/Battery/Button/Compass/Gps/Health/Torch, each `android:exported="true"` with `android:permission="com.cronologics.container.BIND_CONTAINER"`) and `CronoLauncher.apk` (StepCounter/Weather/Music-controller×3/LightSwitch/SpeedDial container services). Under Android's permission model, `protectionLevel="normal"` means **any app is auto-granted the permission simply by declaring `<uses-permission>` for it in its own manifest — no signature check, no runtime user dialog**. This functions almost identically to declaring no permission at all, and (per Finding #3) enables a genuine confused-deputy privilege-escalation chain, not just a data-exposure issue.

Compounding this, at least seven of `CronoLauncher`'s container services (`WeatherContainerService`, `MusicControllerContainerService`, `MusicControllerSkipContainerService`, `MusicControllerPlayContainerService`, `LightSwitchContainerService`, `SpeedDialContainerService`, `StepCounterContainerService`) share one identical hardcoded third-party API key in source: `private static final String API_KEY = "c1da8a236418133e30e1dcce2104aef910479576";` — reused verbatim across unrelated services, now permanently exposed by this firmware extraction.

Separately in the same manifest: `com.cronologics.settings.MUTE_PERMISSION` and `com.cronologics.settings.AIRPLANE_PERMISSION` (`CronoSettings/AndroidManifest.xml`) are declared with **no `protectionLevel` attribute at all**, which defaults to `normal` — gating mute/airplane-mode broadcast receivers (`SilentModeReceiver`, `AirplaneModeReceiver`) with the same weak, self-grantable protection; any app can self-grant these two permissions and send `com.cronologics.mute.action.UPDATE_MUTE` / `com.cronologics.airplane.action.UPDATE_AIRPLANE` to silently force the watch to mute or enter airplane mode.

Also `exported="true"` with **no permission attribute whatsoever** (not even the weak `normal` tier): `BlocksContainer.apk`'s `com.blocks.app.container.BlocksContainerService` (accepts an unauthenticated `com.blocks.app.container.TOGGLE_LED` action to remotely toggle the torch) and `com.blocks.app.container.BlocksContainerReceiver`, plus the near-identical pattern repeated in `BlocksOverview.apk` (`AmbientService`/`OverviewService` and their receivers, all `exported="true"`, no permission). Both receivers listen for `com.cronologics.ambient.{ENTERING,EXIT,UPDATE,FORCE_EXIT}_AMBIENT` — any app can broadcast these to manipulate the watch's ambient/always-on-display state, or flip the torch/LED on and off, with zero permission declared at all.

**Severity: Medium** (scoped below the fully-unauthenticated findings above because the actual container-service payload observed, e.g. `BlocksHealthContainerService`, only renders a themed watchface-widget bitmap — not a raw biometric data feed — reducing real-world data-exposure impact versus #4; still a genuine broken-access-control pattern worth fixing).

**Exploit scenario:** A malicious app adds `<uses-permission android:name="com.cronologics.container.BIND_CONTAINER"/>` to its own manifest (no user-visible runtime prompt results, since it's a `normal`-level permission) and can now bind to any of the 8 container services, or directly broadcast ambient-mode control intents with no permission declared at all.

---

### 9. MEDIUM — Hardcoded third-party analytics credentials in source, including a live Treasure Data write key
**Evidence:** `extracted/system/priv-app/CronoAnalyticsProvider/CronoAnalyticsProvider.apk`, decompiled `TDProvider.java`:
```java
private static final String ENCRYPTION_KEY = "cronologics cronologics cronologics";
private static final String WRITE_KEY = "8435/12d4d72f1fd6eccae3e77a79f7f2d5730803e26b";
...
this.mTreasureData = TreasureData.initializeSharedInstance(getContext(), WRITE_KEY);
this.mTreasureData.setDefaultDatabase("cronologics_watch_events");
```
`TDProvider` (authority `com.cronologics.analytics.provider`) and `TDUploadService` are both `android:exported="true"` with no permission (manifest confirmed). `TDProvider.insert()` has no permission check and forwards caller-supplied event data straight to Treasure Data using this embedded write key. Separately, `BlocksContainer.apk`'s manifest embeds a Fabric/Crashlytics key: `<meta-data android:name="io.fabric.ApiKey" android:value="a5fb2a8d91e6e29b0b1d554abb09206641ea9c69"/>`. And all 7 of `BlocksContainer`'s per-module container services share one identical hardcoded "container API key" string, `0cee03db5fabe5419846d202793669e1a1b8ab27` (e.g. `BlocksHealthContainerService.configureContainerApiKey()`), consumed by an SDK class not present in this APK — exact purpose not fully traceable from this app alone.

**Severity: Medium.** The `ENCRYPTION_KEY` is a trivially weak, human-readable placeholder-looking value defeating its own purpose. The Treasure Data `WRITE_KEY` is a real external-service credential embedded in cleartext — anyone extracting it (as done here) can write arbitrary events into BLOCKS'/Cronologics' analytics account/database, or exhaust write quota. The Fabric/container keys are lower-impact (app-identifying, not typically full-account-takeover credentials) but still should not be hardcoded plainly in shipped, unobfuscated bytecode/manifest.

**Exploit scenario:** Extract `WRITE_KEY` (as done in this audit, via simple `unzip`+decompile, no special tooling) and use it directly against the Treasure Data ingestion API to inject fabricated/spam analytics events into the vendor's real analytics pipeline, or exploit `TDProvider`'s unauthenticated `insert()` from any co-installed app to the same effect without even needing to extract the key.

---

### 10. MEDIUM — Cleartext HTTP for the OS update (FOTA) endpoints and multiple third-party map/geocoding APIs
**Evidence:** Full inventory of `http://` (non-TLS) URLs found across all 26 priv-app `classes.dex` files:
- `CronoSettings.apk`: `http://fota.blocks.services/api/v1/updates`, `http://fota.crono.services/api/v1/updates` (see #2 for the full FOTA analysis).
- `CronoNotificationService.apk`: `http://api.crono.services/icons/v1/` — notification icon fetch over cleartext HTTP (icon spoofing/tracking-beacon risk, lower impact than the update path).
- `BlocksNavigator.apk`: ~35 distinct cleartext `http://` map-tile/geocoding endpoints (`tile.openstreetmap.org`, `tile.cloudmade.com`, `tiles.wmflabs.org`, `api.geonames.org`, `nominatim.openstreetmap.org`, `open.mapquestapi.com`, `overpass-api.de`, `dev.virtualearth.net`, `maps.googleapis.com/.../directions/xml`, etc.) — largely inherited from the bundled OSMDroid/mapping library defaults rather than BLOCKS-authored, but still cleartext traffic that discloses the user's approximate location/route queries to network observers.

**Severity: Medium.** The FOTA endpoints are the most consequential (tie to #2's critical finding); the map-tile/notification-icon endpoints are a privacy/MITM-content-injection concern (a network attacker can substitute map tiles or notification icons) rather than a code-execution path on their own.

---

### 11. MEDIUM (partially mitigating, newly surfaced) — Custom `NETLINK_COREHUB` protocol is a previously-undocumented kernel-level attack surface
**Evidence:** `modulecom_daemon.strings.txt` contains a complete netlink-socket implementation block: `NETLINK_COREHUB`, `MAX_PAYLOAD`, `sockaddr_nl`, `nl_family`/`nl_pid`/`nl_groups`, `nlmsghdr` with `nlmsg_type`/`nlmsg_flags`/`nlmsg_seq`/`nlmsg_pid`, full `msghdr`/`iovec` boilerplate, adjacent to `corehub::CoreHubClient::instance()`/`connect()`. This was **not identified in the prior architecture analysis**, which only covered the SPI sysfs node and ZeroMQ.
**Assessment:** Netlink sockets are kernel/userspace IPC; a custom netlink family implies a BLOCKS-authored (or vendored) kernel driver registers `NETLINK_COREHUB`, likely backing `chutil`'s `/dev/corehub/` access. Netlink-based kernel drivers are a well-known Android/Linux privilege-escalation bug class historically (improper input validation in netlink message handlers, missing capability checks on multicast group subscription, etc.). **No kernel image/module analysis was performed** — this is flagged as a new, real attack-surface component surfaced by this audit that needs the kernel binary/source to assess further, not a confirmed vulnerability.

---

### 12. MEDIUM — `mmi` factory-test binary imports `system()`, `fork`/`execv`, and opens sockets; runs as root:root; gated only by FFBM boot mode, which an unlocked bootloader lets an attacker set at will
**Evidence:**
- `extracted/system/bin/mmi` (stripped ELF32, 82.4KB) imports (via dynamic symbol table, confirmed with `strings`): `system`, `fork`, `execv`, `create_socket`, `listen`, `accept`, `recvfrom` — i.e., this factory test tool can execute arbitrary shell commands via libc `system()` and also opens a local socket server.
- `extracted/boot/ramdisk_ro/init.qcom.factory.rc:30-33`: `service fastmmi /system/bin/mmi` — `user root`, `group root`, `disabled` (only starts when explicitly triggered).
- Trigger path: `init.qcom.factory.rc:280-292`, `on ffbm` block runs `start srvmag_ffbm` (a **second, factory-mode ServiceManager**) and `start fastmmi`. `ro.bootmode`/`androidboot.mode=ffbm` is read from the kernel boot cmdline (`init.qcom.sh:235`, standard AOSP `getprop ro.bootmode` pattern) — on a device with an **unlocked bootloader**, an attacker with physical access controls the boot cmdline via `fastboot boot`/`fastboot oem`, and can set this flag directly to force FFBM/factory mode on next boot.
- `/system` is dm-verity-`wait,verify`-flagged in `extracted/boot/ramdisk_ro/fstab.qcom:11` against `verity_key` (524 bytes, present) — but this is moot on a `test-keys`/unlocked-bootloader device, where an attacker can re-sign a modified system image against a self-supplied key, or simply disable verity outright via the unlocked bootloader, or boot a patched `boot.img` directly without touching `/system` at all.

**Severity: Medium** (requires physical access + a reboot, so not remotely exploitable, but represents a root-level command-execution primitive left in a production `user` build, reachable via a boot-mode flag fully controllable given the unlocked bootloader).

**Exploit scenario:** Attacker with brief physical possession of the watch reboots it into FFBM factory mode via the unlocked bootloader, `fastmmi`/`mmi` starts as root with `system()`-call capability, giving the attacker a root command-execution primitive without ever needing an OS-level exploit.

---

### 13. LOW-MEDIUM — Dangerous libc symbols imported in `modulecom_daemon` (`strcpy`/`sprintf`/`vsprintf`); stack canaries present (partial mitigation)
**Evidence:** Exact-line grep against `modulecom_daemon.strings.txt` (isolated symbol-table-style lines in the unstripped binary): `strcpy` (3 hits, lines 213/16375/101170), `strcat` (1, line 16377), `sprintf` (3, lines 16410/72681/100097), `vsprintf` (3, lines 16417/72682/100098). `alloca`/`gets`/`popen`/`execve` family: **zero hits** (absent, good). The `strcpy` at line 101170 sits directly adjacent to demangled GPS response-parser symbols (`corehub::GPSGetGLLResponse::parse`, `GPSGetGNSResponse::parse`, `GPSGetGSAResponse::parse`) — consistent with, but not proof of, an unbounded copy inside NMEA-sentence parsing of data sourced from the CoreHub MCU/module. `__stack_chk_fail`/`__stack_chk_guard` are both present (stack canaries enabled by the NDK toolchain), which mitigates clean return-address-overwrite exploitation of any stack-based overflow at these sites but does not eliminate the underlying memory-corruption risk (crash/DoS still very plausible).

**Positive/mitigating counter-finding:** The message-framing layer (`api/message.cpp` area) has genuine, specific bounds-checking strings — `"Buffer size smaller than header.length value."`, `"Invalid 'length' field: larger than data length."`, `"Buffer too small."`, `"Data length less than size of message fields."`, etc. — indicating the higher-level `APIMessage`/`CoreHubMessage` wire format is length-validated before dispatch, which reduces (but does not eliminate, given the GPS-parser proximity above) the likelihood the strcpy/sprintf sites sit on a totally unguarded path.

**Severity: Low-Medium**, honestly caveated: this is import-table evidence only (confirms these functions are linked/callable, not that a specific call site is reachable with attacker-controlled unbounded data). No disassembly was performed to confirm exploitability either way.

---

### 14. LOW — Extensive factory/sample/debug cruft left in the production `user` build, expanding attack surface with zero end-user value
**Evidence (all present in `extracted/system/bin/` or `vendor/bin/` or `app/`/`priv-app/`):**
- `mmi`, `mmi_agent32`, `mmi_debug`, `mmi_diag` (factory MMI test suite, see #11), plus `init.qcom.factory.rc` (14KB) defining the `fastmmi`/`srvmag_ffbm` services.
- `oemwvtest` — Widevine DRM test tool; strings directly reference `OEMCrypto_EncryptAndStoreKeyBox`, `OEMCrypto_GetKeyboxData` (device-ID/device-key/keybox-data test routines) — a factory tool that exercises the device's Widevine keybox provisioning, left in a shipped build.
- `SampleAuthenticatorService` (`app/`), `SecureSampleAuthService` (`priv-app/`), `sampleauthdaemon` (`vendor/bin/`), `libSampleAuthJNI.so`/`libSecureSampleAuthClient.so`/`libSecureSampleAuthJNI.so` — Qualcomm QTI's own **sample** secure-authentication demo code, not meant for production.
- `qmi_simple_ril_test`, `PktRspTest`, `schedtest`, `test_diag`, `diag_dci_sample`, `diag_klog`, `diag_mdlog`, `diag_socket_log`, `diag_uart_log`, `ssr_diag` — Qualcomm diagnostic/test tooling.
- `CronoKeyboard.apk` package name is literally `com.example.android.softkeyboard` — **the unmodified AOSP "SoftKeyboard" sample IME** shipped verbatim as the production keyboard app (confirmed via decompiled manifest `package="com.example.android.softkeyboard"`). It does correctly declare `android.permission.BIND_INPUT_METHOD` on its service (proper IME protection), so this is a "should not ship, low-quality signal" finding rather than an exploitable one on its own.

**Severity: Low individually**, but collectively these represent meaningful unnecessary attack surface (every one of these binaries is `0755`/reachable by any local shell) and signal a build process that did not strip staging/demo artifacts before this `user`-tagged image shipped.

---

### 15. LOW — `/data/modulecom_daemon.html` is a static debug status file, not a live HTTP server (mitigating finding, confirms task hypothesis)
**Evidence:** Raw byte-context extraction around the string in `extracted/system/vendor/bin/modulecom_daemon` (offset 847415) shows it sitting among CLI-argument-parsing strings (`--advlog`, `--logmin`, `--logfile`, `"Usage: ..."`) rather than any HTTP-server boilerplate. Full-file search for `Content-Type|HTTP/1.1|Host:|GET |POST |bind(|listen(|accept(` non-mangled-symbol hits: none beyond the already-accounted-for `socket()` libc symbol entries (used by the netlink/ZMQ work above). The embedded HTML template itself (found elsewhere in the string dump) is plain static CSS/HTML with two inline base64 icons and a `<h1>Detailed Message Log</h1>` header — no `<script>` tags, no server-side templating markers.
**Assessment:** This is a locally-written debug/log-viewer file (likely written to `/data/` on `--advlog` trigger, meant for `adb pull`), **not** a bound TCP HTTP listener. No auth strings, no shell-metacharacter/command-injection-shaped strings found near it. Residual risk is limited to whatever the runtime file permissions on `/data/modulecom_daemon.html` turn out to be (not verifiable from a static image, since it's generated at runtime) — if world-readable, it could leak message-log contents (GPS coordinates, heart-rate data, module IDs) to any co-installed app.

---

### 16. INFORMATIONAL — Clean results (checked, not found)
- **No hardcoded credentials in the 3 core native binaries**: exhaustive grep across `modulecom_daemon.strings.txt`/`chutil.strings.txt`/`bclient.strings.txt` for `password|passwd|secret|apikey|api_key|Bearer |-----BEGIN|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}` — zero matches in all three.
- **No world-writable files or setuid/setgid binaries baked into the on-disk `/system` ext4 image**: `find system -perm -0002` and `find system -perm -4000 -o -perm -2000` both return empty (the `chmod 666` on the SPI node is a runtime `init.rc` action, not a static file permission).
- **No `android:debuggable="true"`** found in any of the 24 fully-decompiled manifests, and `default.prop` confirms `ro.debuggable=0` / `ro.secure=1` / `ro.adb.secure=1` device-wide.
- **`BlocksWatchfaces.apk`'s 23 exported components are correctly protected** — all watchface services use the standard AOSP-platform `android.permission.BIND_WALLPAPER` (a true `signature`-level OS permission, not satisfiable by the shared test-key trick in finding #3 the same way, since the platform itself — not a co-installed app — is the party enforcing it).
- **No `%n` format-string specifier** anywhere in `modulecom_daemon.strings.txt`; all `%s` usage found is templated logging strings, not evidence of a raw format-string bug (though this cannot fully rule one out from strings alone).
- **FOTA/analytics keys aside, no cloud/API keys were found directly embedded in any of the 3 native binaries** — all URL/key findings in this report came from the Java/APK layer, not the C++ daemon layer.

---

## Stale-CVE Exposure (kernel/platform vintage)

**Confirmed facts:** Kernel `Linux 3.18.24`, built `2016-09-13` (`device-info/kernel-cpu.txt: "Linux localhost 3.18.24-g6578b69 #1 SMP PREEMPT Tue Sep 13 19:26:51 CST 2016 armv7l"`). Android security patch level `2016-05-01` (`build.prop`). SDK 23 (Android 6.0.1). Being honest about verifiability: **no attempt was made to diff this exact kernel build's patch level against upstream CVE fix commits** (that would require the kernel source tree, not present in this static-image analysis) — the following is a list of *plausible, well-known CVE classes* for this vintage, not confirmed-present vulnerabilities:

- **CVE-2015-3636 / CVE-2016-0728** (keyring/ping-socket refcount UAF class, Linux <3.18/<4.4-era) — widely-cited Android root-exploit-chain building blocks from this exact kernel generation; plausible given 3.18.24 predates most such fixes, but not diffed against this specific build.
- **CVE-2016-2504 / CVE-2016-2469** and the broader **Qualcomm MSM8909-family "QuadRooter"-era (2016) driver CVEs** (kgsl/Adreno GPU, ashmem, msm_camera driver privilege-escalation bugs disclosed by Check Point in Aug 2016) — MSM8909 shares driver lineage with the affected Snapdragon SoCs; this build's kernel predates the fix window (built Sept 2016, patch level frozen at May 2016), so exposure is plausible but not independently confirmed against this exact source tree.
- **CVE-2016-5340-class Qualcomm Wi-Fi/WLAN driver bugs** given the bundled Prima WCNSS WLAN stack of this vintage.
- **Dirty COW (CVE-2016-5195)** — a kernel <4.8 UAF affecting essentially all contemporary Android devices of this era; 3.18.24 (Sept 2016 build) is very likely pre-fix, making this one of the more confidently-applicable entries on this list (the bug and its patch dates are extremely well-documented publicly), though again not independently verified against this exact kernel binary's compiled-in state.
- Being explicit about the honesty bar here: **all of the above are "plausible given the vintage" statements grounded in publicly known CVE disclosure timelines vs. this device's confirmed kernel/patch-level dates — not verified via source diffing, binary patch-level checking, or exploit testing against this specific image.** A real verification pass would require pulling the kernel source/config this device was built from and diffing against the relevant upstream security fix commits.

---

## Coverage Gaps (honest accounting)
- `BlocksGPS.apk` and `BlocksNavigator.apk` (the two largest, most map/asset-heavy APKs, both bundling Google Maps SDK code) were **not** fully Java-decompiled — this was attempted **independently by two separate analysis passes**, and both hit the identical `StackOverflowError` in jadx's method-resolution pass (`jadx.core.dex.nodes.RootNode.deepResolveMethod`), including a retry with an increased thread stack size — this is a genuine, reproducible jadx limitation on these two APKs specifically, not a one-off fluke. No `aapt`/`aapt2` was available on the host as a manifest-only fallback. Their manifests/permissions/secrets were **not independently re-verified** in this report beyond what the prior `SYSTEM_ANALYSIS.md` pass already noted (that both are large, GPS/maps-focused module apps). This is a real gap, not a "checked and clean" result — treat both as unaudited for exported-component and hardcoded-secret findings.
- `sepolicy`'s actual compiled CIL/binary allow-rules (as opposed to the plaintext label list recoverable via `strings`) were not decompiled — meaning finding #6's claim that SELinux offers no additional restriction on the SPI node is based on the *absence* of a `service_contexts`/`seapp_contexts` entry and the permissive runtime mode, not a confirmed absence of a compiled domain-transition rule.
- No disassembly (only `strings`/symbol-table-adjacency analysis) was performed on any native binary — all "dangerous function present" findings (#13) are import-table evidence, not confirmed-reachable vulnerabilities.
- Kernel/boot image (`extracted/boot/kernel`) was only checked for its version banner, not analyzed for the `NETLINK_COREHUB` driver implementation (#11) or diffed against upstream CVE fixes (see Stale-CVE section).
- The OS FOTA finding (#2) confirms the client-side update-verification logic is spoofable, but whether the recovery partition itself enforces an independent OTA-package signature check (which could still block a malicious `--update_package` at flash time even if the Android-side check is bypassed) was **not verified** — that lives in the recovery/boot partition, outside the `/system` + ramdisk scope of this analysis.

---
*Report generated via static analysis only. No USB device accessed, no git commands run. All findings sourced from files already on disk under `/Users/dviros/Downloads/blocks-watch/`.*
