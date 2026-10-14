"""Troca uma textura de um pacote UE2 do LandMass pela mesma textura gerada em outro pacote.

Uso: uv run python unreal/transplant_texture.py <pacote.lm> <fonte.u> <Grupo.Nome> <saída.lm>

O `ucc make` do LandMass gera a textura nova num pacote próprio (o `OBJ SAVEPACKAGE` desta
build não grava). Aqui os bytes dessa export vão para o fim do pacote do jogo e a export antiga
passa a apontar para eles. Tabelas, GUID, malhas e animações não mudam. Remapeia os nomes das tags
de propriedade e os `SavedPos` (posição absoluta) dos `TLazyArray` dos mipmaps; nome que falta no
destino é acrescentado, com a tabela de nomes regravada também no fim do arquivo.
"""

import struct
import sys
from dataclasses import dataclass
from pathlib import Path

TAG = 0x9E2A83C1


def read_index(b: bytes, p: int) -> tuple[int, int]:
    """Índice compacto do UE2: (valor, nova posição)."""
    b0 = b[p]
    p += 1
    v = b0 & 0x3F
    if b0 & 0x40:
        shift = 6
        while True:
            bx = b[p]
            p += 1
            v |= (bx & 0x7F) << shift
            shift += 7
            if not bx & 0x80:
                break
    return (-v if b0 & 0x80 else v), p


def write_index(v: int) -> bytes:
    neg, v = v < 0, abs(v)
    out = bytearray([(0x80 if neg else 0) | (v & 0x3F) | (0x40 if v >= 0x40 else 0)])
    v >>= 6
    while v:
        out.append((v & 0x7F) | (0x80 if v >= 0x80 else 0))
        v >>= 7
    return bytes(out)


@dataclass
class Export:
    pos: int  # início da entrada na tabela
    class_index: int
    package: int
    name: int
    size: int
    offset: int
    end: int  # fim da entrada na tabela


class Package:
    def __init__(self, data: bytes) -> None:
        self.data = data
        tag, self.ver, self.lic, _flags = struct.unpack_from("<IHHI", data, 0)
        assert tag == TAG, "não é pacote UE2"
        (
            self.name_count,
            self.name_offset,
            self.export_count,
            self.export_offset,
            self.import_count,
            self.import_offset,
        ) = struct.unpack_from("<6i", data, 12)
        self.names = self._names()
        self.imports = self._imports()
        self.exports = self._exports()

    def _names(self) -> list[str]:
        p, out = self.name_offset, []
        for _ in range(self.name_count):
            n, p = read_index(self.data, p)
            out.append(self.data[p : p + n - 1].decode("latin-1"))
            p += n + 4
        self.names_end = p
        return out

    def _imports(self) -> list[tuple[int, int, int, int]]:
        p, out = self.import_offset, []
        for _ in range(self.import_count):
            cp, p = read_index(self.data, p)
            cn, p = read_index(self.data, p)
            (pk,) = struct.unpack_from("<i", self.data, p)
            p += 4
            on, p = read_index(self.data, p)
            out.append((cp, cn, pk, on))
        return out

    def _exports(self) -> list[Export]:
        p, out = self.export_offset, []
        for _ in range(self.export_count):
            start = p
            ci, p = read_index(self.data, p)
            _super, p = read_index(self.data, p)
            (pk,) = struct.unpack_from("<i", self.data, p)
            p += 4
            nm, p = read_index(self.data, p)
            p += 4  # flags
            size, p = read_index(self.data, p)
            off = 0
            if size > 0:
                off, p = read_index(self.data, p)
            out.append(Export(start, ci, pk, nm, size, off, p))
        return out

    def object_name(self, ref: int) -> str:
        if ref > 0:
            return self.names[self.exports[ref - 1].name]
        if ref < 0:
            return self.names[self.imports[-ref - 1][3]]
        return "None"

    def path(self, i: int) -> str:
        parts, e = [], self.exports[i]
        while True:
            parts.append(self.names[e.name])
            if e.package <= 0:
                break
            e = self.exports[e.package - 1]
        return ".".join(reversed(parts))

    def find(self, path: str) -> int:
        for i, e in enumerate(self.exports):
            if (
                self.object_name(e.class_index) == "Texture"
                and self.path(i).lower() == path.lower()
            ):
                return i
        raise SystemExit(f"textura {path} não achada")


TYPE_SIZES = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}
STRUCT, OBJECT, NAME, BOOL = 10, 5, 4, 3


def remap_body(src: Package, idx: int, name_of: callable[[str], int], base: int) -> bytes:
    """Regrava a export `idx` de `src` para começar em `base` no destino."""
    e = src.exports[idx]
    b = src.data
    p, end = e.offset, e.offset + e.size
    out = bytearray()
    while True:  # propriedades com tag, até "None"
        n, p = read_index(b, p)
        out += write_index(name_of(src.names[n]))
        if src.names[n] == "None":
            break
        info = b[p]
        p += 1
        out.append(info)
        typ, code, is_array = info & 0x0F, (info >> 4) & 0x07, info & 0x80
        if typ == STRUCT:
            sn, p = read_index(b, p)
            out += write_index(name_of(src.names[sn]))
        if code < 5:
            size = TYPE_SIZES[code]
        else:
            fmt = {5: "<B", 6: "<H", 7: "<i"}[code]
            (size,) = struct.unpack_from(fmt, b, p)
            out += b[p : p + struct.calcsize(fmt)]
            p += struct.calcsize(fmt)
        if is_array and typ != BOOL:
            a = b[p]
            n_extra = 0 if a < 0x80 else (1 if a < 0xC0 else 3)
            out += b[p : p + 1 + n_extra]
            p += 1 + n_extra
        value = b[p : p + size]
        if typ in (OBJECT, NAME) and size:
            raise SystemExit(f"propriedade de objeto/nome não suportada: {src.names[n]}")
        out += value
        p += size
    # Mips: TArray<FMipmap>, cada um com TLazyArray<BYTE> (SavedPos absoluto + dados) e tamanhos.
    count, p = read_index(b, p)
    out += write_index(count)
    for _ in range(count):
        (saved,) = struct.unpack_from("<i", b, p)
        p += 4
        n, q = read_index(b, p)
        data_end = q + n
        assert saved == data_end, f"SavedPos {saved} != fim {data_end}"
        header = write_index(n)
        new_saved = base + len(out) + 4 + len(header) + n
        out += struct.pack("<i", new_saved) + header + b[q:data_end]
        p = data_end
        out += b[p : p + 10]  # USize, VSize (i32) e UBits, VBits (u8)
        p += 10
    out += b[p:end]  # resto da serialização da textura (sem posições absolutas)
    return bytes(out)


def check_roundtrip(pkg: Package, idx: int) -> None:
    """O parser tem de reproduzir a export original byte a byte no mesmo lugar."""
    e = pkg.exports[idx]
    same = remap_body(pkg, idx, lambda s: pkg.names.index(s), e.offset)
    assert same == pkg.data[e.offset : e.offset + e.size], "parser não reproduz a export original"


def main() -> None:
    dst_p, src_p, path, out_p = sys.argv[1:5]
    dst, src = Package(Path(dst_p).read_bytes()), Package(Path(src_p).read_bytes())
    di = dst.find(path)
    si = src.find(path)
    check_roundtrip(dst, di)
    check_roundtrip(src, si)

    names = list(dst.names)
    lower = {s.lower(): i for i, s in enumerate(names)}

    def name_of(s: str) -> int:
        if s.lower() not in lower:
            lower[s.lower()] = len(names)
            names.append(s)
        return lower[s.lower()]

    data = bytearray(dst.data)
    base = len(data)
    body = remap_body(src, si, name_of, base)
    data += body

    if len(names) != len(dst.names):  # tabela de nomes nova no fim
        flags = []
        p = dst.name_offset
        for _ in range(dst.name_count):
            n, p = read_index(dst.data, p)
            p += n
            flags.append(dst.data[p : p + 4])
            p += 4
        new_off = len(data)
        for i, s in enumerate(names):
            raw = s.encode("latin-1") + b"\0"
            data += (
                write_index(len(raw)) + raw + (flags[i] if i < len(flags) else b"\x10\x00\x07\x00")
            )
        struct.pack_into("<ii", data, 12, len(names), new_off)
        print("nomes acrescentados:", names[len(dst.names) :])

    # Entrada da export: SerialSize e SerialOffset novos. Se o tamanho da entrada mudar, a tabela de
    # exports inteira é regravada no fim.
    e = dst.exports[di]
    entry = bytearray(dst.data[e.pos : e.end])
    head_len = len(entry) - len(write_index(e.size)) - (len(write_index(e.offset)) if e.size else 0)
    new_entry = entry[:head_len] + write_index(len(body)) + write_index(base)
    if len(new_entry) == len(entry):
        data[e.pos : e.end] = new_entry
    else:
        table = bytearray(dst.data[dst.export_offset : e.pos]) + new_entry
        table += dst.data[e.end : dst.exports[-1].end]
        struct.pack_into("<i", data, 24, len(data))
        data += table
    Path(out_p).write_bytes(data)

    chk = Package(bytes(data))
    ci = chk.find(path)
    check_roundtrip(chk, ci)
    print(f"ok: {path} {e.size} -> {len(body)} bytes, {out_p}")


if __name__ == "__main__":
    main()
