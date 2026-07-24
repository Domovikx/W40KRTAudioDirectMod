#!/usr/bin/env python3
"""Tests for parse_blueprints.py — UnityFS bundle + GUID search.

Run:
    python tools/test_parse_blueprints.py
"""

from __future__ import annotations
import json, os, struct, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.lz4 import lz4_decompress

GAME = "C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40,000 Rogue Trader"
BUNDLE = GAME + "/Bundles/blueprint.assets"
CHEATDATA = GAME + "/Bundles/cheatdata.json"

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}: {detail}")


def load_bundle_header(path: str):
    """Parse and return UnityFS header fields."""
    with open(path, "rb") as f:
        d = f.read(200)

    pos = 8  # "UnityFS\0"
    ver = struct.unpack_from(">I", d, pos)[0]; pos += 4
    end = d.index(0, pos); pv = d[pos:end].decode("ascii"); pos = end + 1
    end = d.index(0, pos); ev = d[pos:end].decode("ascii"); pos = end + 1
    ts = struct.unpack_from(">Q", d, pos)[0]; pos += 8
    hc = struct.unpack_from(">I", d, pos)[0]; pos += 4
    hu = struct.unpack_from(">I", d, pos)[0]; pos += 4
    fl = struct.unpack_from(">I", d, pos)[0]
    return {"version": ver, "player": pv, "engine": ev,
            "total_size": ts, "header_comp": hc, "header_uncomp": hu, "flags": fl}


def test_header():
    print("\n--- UnityFS Header ---")
    h = load_bundle_header(BUNDLE)
    check("signature starts with UnityFS", open(BUNDLE, "rb").read(6) == b"UnityFS")
    check("version >= 7", h["version"] >= 7)
    check("engine version is 6000.x", h["engine"].startswith("6000"))
    check("total_size matches file", h["total_size"] == os.path.getsize(BUNDLE))
    check("header_comp > 0", h["header_comp"] > 0)
    check("header_uncomp > header_comp", h["header_uncomp"] > h["header_comp"])
    check("compression flag is LZ4", h["flags"] & 0x3F == 3)
    check("has blocks+directory combined", bool(h["flags"] & 0x40))
    return h


def test_lz4_vs_official():
    """Compare our LZ4 with the official lz4.block library."""
    print("\n--- LZ4 Decompression ---")
    try:
        import lz4.block
        HAS_OFFICIAL = True
    except ImportError:
        print("  (skipped — lz4 library not installed)")
        return

    h = load_bundle_header(BUNDLE)
    with open(BUNDLE, "rb") as f:
        d = f.read()

    # Find header body (after align)
    pos = 8 + 4  # sig + version
    end = d.index(0, pos); pos = end + 1  # player ver
    end = d.index(0, pos); pos = end + 1  # engine ver
    pos += 8 + 4 + 4 + 4  # total + hc + hu + flags
    if h["version"] >= 7:
        pad = (16 - pos % 16) % 16
        pos += pad
    raw = d[pos:pos + h["header_comp"]]

    official = lz4.block.decompress(raw, h["header_uncomp"])
    ours = lz4_decompress(raw, h["header_uncomp"])

    check("both decompress to same size", len(official) == len(ours) == h["header_uncomp"])
    check("decompressed data matches", official == ours)
    return official, ours


def test_blocks_nodes(data: bytes, h: dict):
    """Parse block info and node list from decompressed header."""
    print("\n--- Block / Node Info ---")
    off = 16  # skip hash
    block_count = struct.unpack_from(">i", data, off)[0]; off += 4
    check("block count > 0", block_count > 0, str(block_count))
    check("block count < 10000", block_count < 10000, str(block_count))

    total_block_uncomp = 0
    for i in range(block_count):
        u = struct.unpack_from(">I", data, off)[0]
        c = struct.unpack_from(">I", data, off + 4)[0]
        fl = struct.unpack_from(">H", data, off + 8)[0]
        total_block_uncomp += u
        off += 10
        if i == 0:
            check("first block flags LZ4", fl & 0x3F in (2, 3), f"flags=0x{fl:04x}")
            check("first block uncomp size ~128KB", 100000 < u < 200000, str(u))

    check("total uncomp blocks ~335 MB",
          300_000_000 < total_block_uncomp < 400_000_000,
          f"{total_block_uncomp:,}")

    node_count = struct.unpack_from(">i", data, off)[0]; off += 4
    check("node count >= 1", node_count >= 1, str(node_count))

    cab_found = False
    res_found = False
    for _ in range(node_count):
        no = struct.unpack_from(">q", data, off)[0]
        ns = struct.unpack_from(">q", data, off + 8)[0]
        nf = struct.unpack_from(">I", data, off + 16)[0]
        end = data.index(0, off + 20)
        np = data[off + 20:end].decode("ascii")
        off = end + 1
        check(f"node '{np[:50]}' offset+size valid", 0 <= no < total_block_uncomp,
              f"offset={no} size={ns}")
        if "CAB-" in np and not np.endswith("resS") and not np.endswith("resource"):
            cab_found = True
            check(f"CAB file size matches expected",
                  20_000_000 < ns < 100_000_000, f"{ns:,}")
        if np.endswith("resource"):
            res_found = True
            check(f"resource file size ~195 MB",
                  150_000_000 < ns < 250_000_000, f"{ns:,}")

    check("found CAB data file", cab_found)
    check("found CAB resource file", res_found)


def _guid_to_ms_bytes(hex_str: str) -> bytes:
    hp = hex_str[:8], hex_str[8:12], hex_str[12:16], hex_str[16:20], hex_str[20:32]
    ms_hex = (hp[0][6:8]+hp[0][4:6]+hp[0][2:4]+hp[0][0:2]+
              hp[1][2:4]+hp[1][0:2]+
              hp[2][2:4]+hp[2][0:2]+
              hp[3]+hp[4])
    return bytes.fromhex(ms_hex)


def test_guid_search():
    """Test finding dialog GUIDs from cheatdata in the SerializedFile."""
    print("\n--- GUID Search ---")

    with open(CHEATDATA, "r") as f:
        cheat = json.load(f)

    # Take a small sample to determine byte order
    cue_hex = []
    for entry in cheat["Entries"]:
        if "BlueprintCue" in entry["TypeFullName"]:
            cue_hex.append(entry["Guid"].replace("-", "").lower())
            if len(cue_hex) >= 200:
                break

    print(f"  {len(cue_hex)} sample BlueprintCue GUIDs")

    # Decompress bundle
    from tools.parse_blueprints import UnityFSBundle
    bundle = UnityFSBundle(BUNDLE)

    cab_data = None
    for no, ns, nf, np in bundle.nodes:
        if "CAB-" in np and not np.endswith("resS") and not np.endswith("resource"):
            cab_data = bundle.decompress_all()[no:no + ns]
            break

    if not cab_data:
        check("CAB extracted", False)
        return
    check("CAB extracted", len(cab_data) > 0, f"{len(cab_data)//1024//1024} MB")

    # Search with small sample — use C-level bytes.find() which is fast
    found_raw = 0
    found_ms = 0
    sample = cab_data

    for h in cue_hex:
        raw = bytes.fromhex(h)
        if sample.find(raw) >= 0:
            found_raw += 1
        ms = _guid_to_ms_bytes(h)
        if sample.find(ms) >= 0:
            found_ms += 1

    check("raw byte order GUIDs found", found_raw > 0, f"{found_raw}/{len(cue_hex)}")
    check("MS byte order GUIDs found", found_ms > 0, f"{found_ms}/{len(cue_hex)}")
    print(f"  Matches: raw={found_raw}, ms={found_ms}")

    if found_ms > found_raw:
        print("  → GUIDs use Microsoft byte order (likely)")
    elif found_raw > found_ms:
        print("  → GUIDs use standard UUID byte order")
    else:
        print("  → Both orders match equally")

    return found_raw, found_ms


if __name__ == "__main__":
    t0 = time.time()

    h = test_header()
    test_lz4_vs_official()

    if h["header_uncomp"] > 0:
        with open(BUNDLE, "rb") as f:
            d = f.read()
        pos = 8 + 4
        end = d.index(0, pos); pos = end + 1
        end = d.index(0, pos); pos = end + 1
        pos += 8 + 4 + 4 + 4
        if h["version"] >= 7:
            pad = (16 - pos % 16) % 16
            pos += pad
        raw = d[pos:pos + h["header_comp"]]
        data = lz4_decompress(raw, h["header_uncomp"])
        test_blocks_nodes(data, h)

    test_guid_search()

    print(f"\n{'='*40}")
    print(f"Results: {PASS} passed, {FAIL} failed ({time.time() - t0:.1f}s)")
    sys.exit(0 if FAIL == 0 else 1)
