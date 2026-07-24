#!/usr/bin/env python3
"""Parse UnityFS blueprint.assets → extract BlueprintCue → speaker mapping.

Zero external dependencies — pure Python + stdlib (struct, json).

Reads the SerializedFile type tree to find BlueprintCue.Speaker field.
Outputs {guid: speaker_name} JSON.

Usage:
    python tools/parse_blueprints.py
"""

from __future__ import annotations
import argparse, json, os, struct, sys, time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.lz4 import lz4_decompress

GAME = "C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40,000 Rogue Trader"
BUNDLE = Path(GAME) / "Bundles" / "blueprint.assets"
CHEATDATA = Path(GAME) / "Bundles" / "cheatdata.json"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "Localization" / "ruRU" / "speakers.json"


# ---------------------------------------------------------------------------
# Stream reader helper
# ---------------------------------------------------------------------------

class Reader:
    def __init__(self, data: bytes, big_endian: bool = False):
        self.data = data
        self.pos = 0
        self.fmt = ">" if big_endian else "<"

    def _r(self, f: str, size: int):
        val = struct.unpack_from(self.fmt + f, self.data, self.pos)[0]
        self.pos += size
        return val

    def u8(self): return self._r("B", 1)
    def i16(self): return self._r("h", 2)
    def u16(self): return self._r("H", 2)
    def i32(self): return self._r("i", 4)
    def u32(self): return self._r("I", 4)
    def i64(self): return self._r("q", 8)
    def u64(self): return self._r("Q", 8)
    def f32(self): return self._r("f", 4)
    def bool(self): return self.u8() != 0

    def str(self):
        end = self.data.index(0, self.pos)
        s = self.data[self.pos:end].decode("utf-8", errors="replace")
        self.pos = end + 1
        return s

    def bytes(self, n: int):
        d = self.data[self.pos:self.pos + n]
        self.pos += n
        return d

    def skip(self, n: int):
        self.pos += n

    def align(self, n: int):
        pad = (n - self.pos % n) % n
        self.pos += pad

    def tell(self): return self.pos
    def seek(self, p): self.pos = p

    def arr_i32(self, n): return [self.i32() for _ in range(n)]


# ---------------------------------------------------------------------------
# UnityFS Bundle
# ---------------------------------------------------------------------------

class UnityFSBundle:
    def __init__(self, path: str):
        t0 = time.time()
        with open(path, "rb") as f:
            self.data = f.read()
        r = Reader(self.data)
        sig = r.bytes(7)
        if sig != b"UnityFS":
            raise ValueError(f"Not UnityFS: {sig!r}")
        r.skip(1)  # null
        self.version = r.u32()
        r.fmt = ">"  # UnityFS fields are big-endian
        self.player_ver = r.str()
        self.engine_ver = r.str()
        self.total_size = r.u64()
        self.header_comp = r.u32()
        self.header_uncomp = r.u32()
        self.flags = r.u32()

        # Align to 16 for version >= 7
        if self.version >= 7:
            r.align(16)

        raw = r.bytes(self.header_comp)
        decomp = lz4_decompress(raw, self.header_uncomp)

        # Parse block info
        dr = Reader(decomp)
        dr.fmt = ">"  # block info is big-endian
        dr.skip(16)  # hash
        block_count = dr.i32()
        self.blocks = []
        for _ in range(block_count):
            u = dr.u32()
            c = dr.u32()
            fl = dr.u16()
            self.blocks.append((u, c, fl))

        node_count = dr.i32()
        self.nodes = []
        self.cab_name = None
        self.cab_offset = 0
        self.cab_size = 0
        for _ in range(node_count):
            no = dr.i64()
            ns = dr.i64()
            nf = dr.u32()
            np = dr.str()
            self.nodes.append((no, ns, nf, np))
            if "CAB-" in np and not np.endswith("resS") and not np.endswith("resource"):
                self.cab_name = np
                self.cab_offset = no
                self.cab_size = ns

        # Align for block data
        if self.flags & 0x200:
            r.align(16)
        self.block_start = r.tell()
        print(f"  Bundle: {block_count} blocks, {node_count} nodes ({time.time()-t0:.1f}s)")

    def get_cab_data(self) -> bytes | None:
        """Decompress all blocks, return the main CAB file's data."""
        t0 = time.time()
        chunks = []
        offset = self.block_start
        for idx, (u, c, fl) in enumerate(self.blocks):
            block_raw = self.data[offset:offset + c]
            offset += c
            comp_type = fl & 0x3F
            if comp_type == 0:
                chunks.append(block_raw[:u])
            elif comp_type in (2, 3):
                chunks.append(lz4_decompress(block_raw, u))
            elif comp_type == 1:
                import lzma
                chunks.append(lzma.decompress(block_raw))
            else:
                raise ValueError(f"Block {idx}: unknown compression {comp_type}")
        uncompressed = b"".join(chunks)
        print(f"  Decompressed {len(uncompressed)//1024//1024} MB ({time.time()-t0:.1f}s)")
        if self.cab_name:
            return uncompressed[self.cab_offset:self.cab_offset + self.cab_size]
        return uncompressed


# ---------------------------------------------------------------------------
# SerializedFile (.assets) parser
# ---------------------------------------------------------------------------

class SerializedFileReader:
    """Parses Unity SerializedFile format to find BlueprintCue objects."""

    def __init__(self, data: bytes, cheat_entries: dict):
        self.data = data
        self.cheat = cheat_entries  # {hex_guid: {name, guid}}
        self.objects = []  # list of (path_id, type_index, byte_start, byte_size)
        self.types = []  # list of type info
        self.type_trees = {}  # type_idx -> list of type tree nodes
        self.cue_found = 0
        self.reader = Reader(data, False)
        self._parse_header()

    def _parse_header(self):
        r = self.reader
        r.fmt = ">"  # Unity serialized files are BE initially
        metadata_size = r.u32()
        file_size = r.u32()
        version = r.u32()
        data_offset = r.u32()

        if version >= 9:
            is_be = r.bool()  # True=BE, False=LE
            r.fmt = ">" if is_be else "<"
            r.skip(3)  # reserved
            if version >= 22:
                # v22 stores metadata_size/file_size/data_offset as BE even if flag says LE
                # Use BE for these re-read fields
                old_fmt = r.fmt
                r.fmt = ">"
                metadata_size = r.u32()
                file_size = r.i64()
                data_offset = r.i64()
                self.unknown = r.i64()
                r.fmt = old_fmt

        self.version = version
        self.data_offset = data_offset
        print(f"  SerializedFile v{version}, endian={r.fmt}, data_offset={data_offset}")

        if version >= 7:
            self.unity_version = r.str()
        if version >= 8:
            self.target_platform = r.i32()
        if version >= 13:
            self.enable_type_tree = r.bool()

        # Read types
        type_count = r.i32()
        self.types = []
        print(f"  Types: {type_count}")
        for i in range(type_count):
            self.types.append(self._read_serialized_type(r))
            if r.tell() + 4 > len(self.data):
                break

        if 7 <= version < 14:
            r.i32()  # big_id_enabled

        # Read objects
        t_obj = r.tell()
        obj_count = r.i32()
        print(f"  Object count: {obj_count} at position {t_obj}")
        self.objects = []
        for i in range(obj_count):
            if r.tell() + 20 > len(self.data):
                print(f"  Stopping at object {i}/{obj_count} — near end of data (pos {r.tell()})")
                break
            self.objects.append(self._read_object(r))

        # Skip scripts, externals, ref_types
        self._scan_objects()

    def _read_serialized_type(self, r: Reader):
        class_id = r.i32()
        script_id = None
        ttree = None

        if self.version >= 16:
            r.bool()  # is_stripped
        if self.version >= 17:
            r.i16()  # script_type_index
        if self.version >= 13:
            if class_id < 0 or class_id == 114:  # MonoBehaviour
                script_id = r.bytes(16)
            old_hash = r.bytes(16)

        if self.enable_type_tree:
            if self.version >= 12 or self.version == 10:
                self._read_typetree_blob(r)
                ttree = getattr(self, '_last_ttree', None)

        # v21+: type_dependencies (int32 count + array) for non-ref types
        if self.version >= 21:
            dep_count = r.i32()
            r.pos += dep_count * 4  # skip int32 array

        return {"class_id": class_id, "script_id": script_id, "ttree": ttree}

    def _read_typetree_blob(self, r: Reader):
        """Parse Unity type tree blob, return list of {name, type, offset, size, level}."""
        t_pos = r.tell()
        if t_pos + 8 > len(self.data):
            return

        endian = ">" if ">" in r.fmt else "<"
        node_count = struct.unpack_from(endian + "i", self.data, t_pos)[0]
        buf_size = struct.unpack_from(endian + "i", self.data, t_pos + 4)[0]

        if node_count <= 0 or node_count > 50000:
            r.pos += 8
            return

        has_refhash = self.version >= 19
        entry_size = 24 + (8 if has_refhash else 0)
        st = t_pos + 8
        blob_size = entry_size * node_count + buf_size
        if st + blob_size > len(self.data):
            r.pos += 8
            return

        # Parse node entries
        struct_fmt = endian + "hBBIIiii" + ("Q" if has_refhash else "")
        buf_start = st + entry_size * node_count

        # CommonString lookup for MSB-offset strings
        # Unity stores frequently used type/field names in a CommonString table
        # For now we handle absolute offsets only (MSB=0)
        def _s(offset):
            if offset & 0x80000000:
                return ""  # common string ID — skip for now
            p = buf_start + offset
            if p < 0 or p >= len(self.data):
                return ""
            e = self.data.find(0, p)
            if e < 0 or e > buf_start + buf_size:
                return ""
            return self.data[p:e].decode("utf-8", errors="replace")

        # Store the parsed type tree for this type
        ttree = []
        for i in range(node_count):
            off = st + i * entry_size
            vals = struct.unpack_from(struct_fmt, self.data, off)
            ver, level, type_flags, type_off, name_off, byte_size, idx, meta_flag = vals[:8]
            ttree.append({
                "level": level, "type": _s(type_off), "name": _s(name_off),
                "size": byte_size, "ver": ver, "idx": idx, "meta_flag": meta_flag,
            })

        r.pos = st + blob_size
        self._last_ttree = ttree

    def _read_object(self, r: Reader):
        if self.version < 14:
            path_id = r.i32()
        else:
            r.align(4)
            path_id = r.i64()
        byte_start = r.u32()
        byte_start_2 = 0
        if self.version >= 14:
            byte_start_2 = r.u32()
        byte_size = r.i32()
        type_index = r.i32()
        if type_index < 0:
            type_index = -type_index - 1
        byte_start_full = byte_start | (byte_start_2 << 32) if self.version >= 14 else byte_start
        return {
            "path_id": path_id,
            "byte_start": byte_start_full,
            "byte_size": byte_size,
            "type_index": type_index
        }

    def _scan_objects(self):
        """Scan objects and match their data against cheatdata GUIDs."""
        t0 = time.time()
        print(f"  Scanning {len(self.objects)} objects...")

        # Build BOTH raw and MS byte order maps
        guid_maps = {}
        for h, info in self.cheat.items():
            # Raw byte order (UUID.to_bytes format)
            raw_bytes = bytes.fromhex(h)
            guid_maps[raw_bytes] = info
            # Microsoft byte order
            hp = h[:8], h[8:12], h[12:16], h[16:20], h[20:32]
            ms_hex = (hp[0][6:8]+hp[0][4:6]+hp[0][2:4]+hp[0][0:2]+
                      hp[1][2:4]+hp[1][0:2]+
                      hp[2][2:4]+hp[2][0:2]+
                      hp[3]+hp[4])
            guid_maps[bytes.fromhex(ms_hex)] = info

        doff = self.data_offset
        found = 0
        self.results = []

        for obj in self.objects:
            abs_start = doff + obj["byte_start"]
            size = obj["byte_size"]
            obj_data = self.data[abs_start:abs_start + min(size, 1024)]
            if len(obj_data) < 16:
                continue
            # Try GUID at start, end, and various offsets
            for off in range(0, min(len(obj_data) - 16, 256), 1):
                chunk = obj_data[off:off + 16]
                if chunk in guid_maps:
                    self.results.append((obj, guid_maps[chunk], off))
                    found += 1
                    break

        print(f"  Found {found}/{len(self.cheat)} BlueprintCue objects by GUID match ({time.time()-t0:.1f}s)")
        self.cue_found = found

        if found == 0 and self.objects:
            print("  Trying alternative: search entire CAB for MS-order GUIDs...")
            # Pre-compute MS-order bytes for a sample
            sample_ms = set()
            for h in list(self.cheat.keys())[:1000]:
                hp = h[:8], h[8:12], h[12:16], h[16:20], h[20:32]
                ms_hex = (hp[0][6:8]+hp[0][4:6]+hp[0][2:4]+hp[0][0:2]+
                          hp[1][2:4]+hp[1][0:2]+
                          hp[2][2:4]+hp[2][0:2]+
                          hp[3]+hp[4])
                sample_ms.add(bytes.fromhex(ms_hex))
            cab_start = doff
            cab_end = min(doff + 100000, len(self.data))
            for pos in range(cab_start, cab_end - 16, 1):
                chunk = self.data[pos:pos + 16]
                if chunk in sample_ms:
                    print(f"  Found MS-order GUID at CAB offset {pos}!")
                    break
            # Try raw byte order too
            sample_raw = set(bytes.fromhex(h) for h in list(self.cheat.keys())[:1000])
            for pos in range(cab_start, cab_end - 16, 1):
                chunk = self.data[pos:pos + 16]
                if chunk in sample_raw:
                    print(f"  Found RAW-order GUID at CAB offset {pos}!")
                    break
            print("  (no GUIDs found in CAB data section)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_cheat_index(path: str) -> dict:
    """Build {hex_guid_no_hyphens: {name, guid}} for BlueprintCue."""
    with open(path, "r", encoding="utf-8") as f:
        cheat = json.load(f)
    result = {}
    for entry in cheat["Entries"]:
        if "BlueprintCue" in entry["TypeFullName"]:
            h = entry["Guid"].replace("-", "").lower()
            result[h] = {"name": entry["Name"], "guid": entry["Guid"]}
    return result


def main():
    parser = argparse.ArgumentParser(description="Extract BlueprintCue → speaker mapping")
    parser.add_argument("--output", help="Output JSON path", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    if not BUNDLE.exists() or not CHEATDATA.exists():
        print("ERROR: Bundle or cheatdata not found")
        sys.exit(1)

    t0 = time.time()

    # Build cheatdata index
    cheat_index = build_cheat_index(str(CHEATDATA))
    print(f"Cheatdata: {len(cheat_index)} BlueprintCue entries")

    # Parse bundle and extract CAB
    bundle = UnityFSBundle(str(BUNDLE))
    cab = bundle.get_cab_data()
    if not cab:
        print("ERROR: No CAB data")
        sys.exit(1)

    # Parse SerializedFile
    sf = SerializedFileReader(cab, cheat_index)
    print(f"  Objects in file: {len(sf.objects)}")
    print(f"  Cue objects matched: {sf.cue_found}")

    # Write results if found
    if sf.cue_found > 0:
        print(f"\nTotal time: {time.time() - t0:.1f}s")
        print(f"\nFound {sf.cue_found} BlueprintCue objects!")
        print("Next step would be parsing the Speaker field from type tree.")

    print(f"\nTotal time: {time.time() - t0:.1f}s")

    if sf.cue_found == 0:
        print("\nGUID search failed. Debug info:")
        print(f"  First 100 bytes of CAB: {cab[:100].hex()[:80]}...")
        print(f"  First object byte_start={sf.objects[0] if sf.objects else 'N/A'}")


if __name__ == "__main__":
    main()
