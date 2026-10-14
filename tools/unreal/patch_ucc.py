"""Ajusta o UCC.exe do UT2004 3369 ao layout de objeto do LandMass (UObject +8 bytes).

UStruct::SuperField: +0x2c -> +0x34; UCommandlet flags (bitfield): +0x1dc -> +0x1e4.
Vtable: UCommandlet::Main em +0x74 (UT2004 +0x70).
Aplicar sobre o UCC.exe original do patch 3369.
Fonte: LandMass Core.dll UStruct::IsChildOf (0x10110ca0) e UCommandlet::UCommandlet (0x101146f0).
"""

import struct
import sys
from pathlib import Path

# VA da instrução -> (bytes de deslocamento antigos, novos)
PATCHES = {
    0x4093C4: (b"\xdc\x01\x00\x00", b"\xe4\x01\x00\x00"),
    0x409409: (b"\xdc\x01\x00\x00", b"\xe4\x01\x00\x00"),
    0x40947D: (b"\xdc\x01\x00\x00", b"\xe4\x01\x00\x00"),
    0x409490: (b"\xdc\x01\x00\x00", b"\xe4\x01\x00\x00"),
    0x4094A3: (b"\xdc\x01\x00\x00", b"\xe4\x01\x00\x00"),
    0x4094B7: (b"\xdc\x01\x00\x00", b"\xe4\x01\x00\x00"),
    0x409554: (b"\xdc\x01\x00\x00", b"\xe4\x01\x00\x00"),
    0x4095AA: (b"\xdc\x01\x00\x00", b"\xe4\x01\x00\x00"),
    0x4094E8: (b"\x2c", b"\x34"),
    # call [edx+0x70] -> +0x74: o LandMass inseriu UObject::DBResult no slot 0x70 (Main em 0x74)
    0x409550: (b"\xff\x52\x70", b"\xff\x52\x74"),
}


def va_to_off(data: bytes, va: int) -> int:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    sec = pe + 24 + opt
    for i in range(nsec):
        vaddr, vsize, raw = (
            struct.unpack_from("<III", data, sec + i * 40 + 12)[:1]
            + struct.unpack_from("<I", data, sec + i * 40 + 8)
            + struct.unpack_from("<I", data, sec + i * 40 + 20)
        )
        if base + vaddr <= va < base + vaddr + vsize:
            return va - base - vaddr + raw
    raise ValueError(hex(va))


path = Path(sys.argv[1])
data = bytearray(path.read_bytes())
for va, (old, new) in PATCHES.items():
    off = va_to_off(data, va)
    window = bytes(data[off : off + 12])
    i = window.find(old)
    assert i > 0, (hex(va), window.hex())
    data[off + i : off + i + len(old)] = new
    print(hex(va), window.hex(), "->", bytes(data[off : off + 12]).hex())
path.write_bytes(data)
