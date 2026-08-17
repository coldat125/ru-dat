#!/usr/bin/env python3
"""Оставляет в geosite.dat / geoip.dat только нужные категории.

    python trim_dat.py geosite.dat                                  # показать категории и их вес
    python trim_dat.py geosite.dat geosite-min.dat category-ru ru-blocked
    python trim_dat.py geoip.dat   geoip-min.dat   ru private

ponytail: разбор на уровне wire-формата, без protobuf-зависимости.
GeoSiteList и GeoIPList имеют одинаковую форму: repeated <entry> = 1,
у entry первым полем идёт string country_code = 1. Записи вырезаются
как есть, байт в байт, поэтому пересборка не нужна.
"""
import sys


def varint(b, i):
    n = s = 0
    while True:
        c = b[i]
        i += 1
        n |= (c & 0x7F) << s
        if not c & 0x80:
            return n, i
        s += 7


def entries(buf):
    """(raw_chunk_с_тегом, тело_записи) для каждой категории."""
    i = 0
    while i < len(buf):
        start = i
        tag, i = varint(buf, i)
        assert tag == 0x0A, "не похоже на geosite/geoip .dat"
        ln, i = varint(buf, i)
        yield buf[start:i + ln], buf[i:i + ln]
        i += ln


def code(msg):
    tag, i = varint(msg, 0)
    assert tag == 0x0A, "у записи нет country_code"
    ln, i = varint(msg, i)
    return msg[i:i + ln].decode()


def trim(data, keep):
    keep = {k.upper() for k in keep}
    return b"".join(raw for raw, msg in entries(data) if code(msg) in keep)


def demo():
    # минимальный GeoSiteList из двух записей: 'RU' и 'CN'
    def entry(cc):
        body = b"\x0a" + bytes([len(cc)]) + cc.encode()
        return b"\x0a" + bytes([len(body)]) + body
    data = entry("RU") + entry("CN")
    assert [code(m) for _, m in entries(data)] == ["RU", "CN"]
    assert trim(data, ["ru"]) == entry("RU")
    assert trim(data, ["xx"]) == b""
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        demo()
        sys.exit()

    args = sys.argv[1:]
    src, dst, keep = args[0], (args[1] if len(args) > 1 else None), args[2:]
    data = open(src, "rb").read()

    if not dst:
        for raw, msg in sorted(entries(data), key=lambda e: -len(e[0])):
            print(f"{len(raw)/1024:9.1f} KB  {code(msg)}")
        sys.exit()

    out = trim(data, keep)
    missing = {k.upper() for k in keep} - {code(m) for _, m in entries(out)}
    assert not missing, f"нет таких категорий: {sorted(missing)}"
    open(dst, "wb").write(out)
    print(f"{len(data)/1e6:.1f} MB -> {len(out)/1e6:.3f} MB")
