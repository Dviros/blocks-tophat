#!/usr/bin/env python3
"""Surgically edit key=value props inside default.prop in a gzipped newc cpio ramdisk,
preserving every other entry byte-for-byte (modes, uids, device nodes). No root needed.

Usage: patch_ramdisk_prop.py in_ramdisk.gz out_ramdisk.gz KEY=VAL [KEY=VAL ...]
"""
import sys, gzip, io, struct

def read_cpio(data):
    """Yield (header_fields, name, filedata, raw_end_offset). newc format."""
    off = 0
    entries = []
    while True:
        magic = data[off:off+6]
        if magic not in (b"070701", b"070702"):
            raise ValueError(f"bad cpio magic at {off}: {magic!r}")
        fields = [int(data[off+6+i*8:off+6+(i+1)*8], 16) for i in range(13)]
        namesize = fields[11]
        name_off = off + 110
        name = data[name_off:name_off+namesize-1]  # strip trailing NUL
        # name padded so (110+namesize) rounds to 4
        data_off = name_off + namesize
        data_off = (data_off + 3) & ~3
        filesize = fields[6]
        fdata = data[data_off:data_off+filesize]
        next_off = data_off + filesize
        next_off = (next_off + 3) & ~3
        entries.append([fields, name, fdata])
        off = next_off
        if name == b"TRAILER!!!":
            break
    return entries

def write_cpio(entries):
    out = bytearray()
    for fields, name, fdata in entries:
        fields = list(fields)
        fields[6] = len(fdata)          # filesize
        fields[11] = len(name) + 1      # namesize incl NUL
        out += b"070701"
        for f in fields:
            out += b"%08x" % (f & 0xffffffff)
        out += name + b"\x00"
        while len(out) % 4: out += b"\x00"
        out += fdata
        while len(out) % 4: out += b"\x00"
    return bytes(out)

def patch_prop(text, overrides):
    lines = text.decode().splitlines()
    seen = set()
    for i, ln in enumerate(lines):
        if "=" in ln and not ln.strip().startswith("#"):
            k = ln.split("=", 1)[0].strip()
            if k in overrides:
                lines[i] = f"{k}={overrides[k]}"; seen.add(k)
    for k, v in overrides.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    return ("\n".join(lines) + "\n").encode()

def main():
    inp, outp, *kvs = sys.argv[1:]
    overrides = dict(kv.split("=", 1) for kv in kvs)
    raw = gzip.decompress(open(inp, "rb").read())
    entries = read_cpio(raw)
    n_before = len(entries)
    hit = False
    for e in entries:
        if e[1] == b"default.prop":
            e[2] = patch_prop(e[2], overrides); hit = True
    if not hit:
        raise SystemExit("default.prop not found in ramdisk")
    rebuilt = write_cpio(entries)
    # self-check: reparse, confirm same entry count + overrides applied
    check = read_cpio(rebuilt)
    assert len(check) == n_before, f"entry count changed {n_before}->{len(check)}"
    dp = next(e[2].decode() for e in check if e[1] == b"default.prop")
    for k, v in overrides.items():
        assert f"{k}={v}" in dp, f"override {k}={v} missing after rebuild"
    with open(outp, "wb") as f:
        f.write(gzip.compress(rebuilt, 6))
    print(f"OK: {n_before} entries preserved, {len(overrides)} props set -> {outp}")
    for k, v in overrides.items():
        print(f"   {k}={v}")

if __name__ == "__main__":
    main()
