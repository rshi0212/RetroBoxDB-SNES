"""SNES and Mega Drive internal-header parsers. Python >=3.10, stdlib only.

Parsing is descriptive: the stored file bytes are never modified, and a header
declaration is evidence about the dump, not proof of physical cartridge hardware.
"""
import hashlib, json

PARSER_VERSION = 'cart-headers-1'


def _js(x): return json.dumps(x, ensure_ascii=False, sort_keys=True)


def _text(raw):
    """Decode a fixed-width header text field without guessing beyond ASCII/Shift-JIS."""
    raw = raw.rstrip(b'\x00 ')
    for enc in ('ascii', 'shift_jis'):
        try: return raw.decode(enc).strip()
        except UnicodeDecodeError: pass
    return None


# ---------------------------------------------------------------- SNES

SNES_LAYOUTS = (('lorom', 0x7FC0), ('hirom', 0xFFC0), ('exlorom', 0x407FC0), ('exhirom', 0x40FFC0))
SNES_MAP_MODES = {0x20: 'lorom', 0x21: 'hirom', 0x22: 'sa1_or_exlorom', 0x23: 'sa1', 0x25: 'exhirom', 0x2A: 'spc7110_or_exhirom'}
SNES_REGIONS = {0: 'Japan', 1: 'USA', 2: 'Europe', 3: 'Sweden/Scandinavia', 4: 'Finland', 5: 'Denmark', 6: 'France',
                7: 'Netherlands', 8: 'Spain', 9: 'Germany', 10: 'Italy', 11: 'China', 12: 'Indonesia', 13: 'Korea',
                14: 'Global', 15: 'Canada', 16: 'Brazil', 17: 'Australia'}
SNES_COPROCESSORS = {0x0: 'DSP', 0x1: 'SuperFX', 0x2: 'OBC1', 0x3: 'SA-1', 0x4: 'S-DD1', 0x5: 'S-RTC',
                     0xE: 'other (Super Game Boy / Satellaview)'}
SNES_CUSTOM = {0x00: 'SPC7110', 0x01: 'ST010/ST011', 0x02: 'ST018', 0x10: 'CX4'}


def snes_checksum(data):
    """Console checksum convention: mirror a non-power-of-two tail up to the next power of two."""
    size = len(data)
    if not size: return None
    base = 1 << (size.bit_length() - 1)
    if base == size: return sum(data) & 0xFFFF
    tail = size - base
    if base % tail: return None
    return (sum(data[:base]) + sum(data[base:]) * (base // tail)) & 0xFFFF


def _snes_score(rom, off):
    if off + 0x40 > len(rom): return None
    h = rom[off:off + 0x40]
    score = 0
    cks, comp = h[0x1E] | h[0x1F] << 8, h[0x1C] | h[0x1D] << 8
    if cks ^ comp == 0xFFFF: score += 8 if cks not in (0, 0xFFFF) else 3
    mode = h[0x15]
    expected = {0x7FC0: (0x20, 0x22, 0x23, 0x30, 0x32, 0x33), 0xFFC0: (0x21, 0x31, 0x2A, 0x3A, 0x25, 0x35),
                0x407FC0: (0x22, 0x32), 0x40FFC0: (0x25, 0x35)}[off]
    if mode in expected: score += 4
    elif mode & 0xE0 == 0x20: score += 1
    title = h[:21]
    if all(0x20 <= b < 0x7F or b >= 0xA0 or b == 0 for b in title): score += 2
    if h[0x17] and 0x07 <= h[0x17] <= 0x0D: score += 2
    reset = h[0x3C] | h[0x3D] << 8
    if reset >= 0x8000: score += 2
    if h[0x1A] == 0x33 or h[0x1A] in (0x01, 0x08, 0xC3): score += 1
    if off >= 0x400000 and len(rom) <= 0x400000: return None
    return score


def parse_snes(data):
    out = dict(format='snes', parse_status='unclassified', components=[], hardware=None, warnings=[])
    copier = 512 if len(data) % 1024 == 512 else 0
    if copier:
        out['format'] = 'snes_copier'
        out['components'].append(('copier_header', 0, 512))
        out['warnings'].append('512-byte copier header detected; DAT identity covers the stored file bytes')
    rom = data[copier:]
    if rom: out['components'].append(('rom', copier, len(rom)))
    scored = [(s, name, off) for name, off in SNES_LAYOUTS if (s := _snes_score(rom, off)) is not None]
    if not scored:
        out['warnings'].append('no internal header location fits the file size'); return out
    score, layout, off = max(scored, key=lambda x: (x[0], -x[2]))
    if score < 8:
        out['warnings'].append(f'no plausible internal header (best score {score} at {layout})'); return out
    h = rom[off:off + 0x40]
    ext = h[0x1A] == 0x33 and off >= 0x10
    e = rom[off - 0x10:off] if ext else None
    chipset = h[0x16]; low, high = chipset & 0x0F, chipset >> 4
    # Low nibble: 0 ROM, 1 +RAM, 2 +RAM+battery, 3 +coprocessor, 4 +coproc+RAM, 5 +coproc+RAM+battery, 6 +coproc+battery.
    coprocessor = None
    if low >= 3:
        if high == 0xF: coprocessor = SNES_CUSTOM.get(e[0x0F], f'custom subtype {e[0x0F]:#04x}') if e is not None else 'custom (no extended header)'
        else: coprocessor = SNES_COPROCESSORS.get(high, f'unknown {high:#x}')
    declared_cks, declared_comp = h[0x1E] | h[0x1F] << 8, h[0x1C] | h[0x1D] << 8
    actual = snes_checksum(rom)
    rom_kib = (1 << h[0x17]) if 0 < h[0x17] < 16 else None
    ram_kib = (1 << h[0x18]) if 0 < h[0x18] < 16 else 0
    hw = dict(header_offset=copier + off, layout=layout, map_mode=h[0x15], map_mode_name=SNES_MAP_MODES.get(h[0x15] & 0xEF),
              fast_rom=(h[0x15] >> 4) & 1, chipset=chipset, coprocessor=coprocessor, battery=int(low in (2, 5, 6, 9, 10)),
              title=_text(h[:21]), title_hex=h[:21].hex(), rom_size_declared=rom_kib * 1024 if rom_kib else None,
              ram_size_declared=ram_kib * 1024, region_code=h[0x19], region=SNES_REGIONS.get(h[0x19]),
              developer_id=h[0x1A], maker_code=_text(e[0:2]) if e else None, game_code=_text(e[2:6]) if e else None,
              expansion_ram_size=(1 << e[0x0D]) * 1024 if e and 0 < e[0x0D] < 16 else None,
              version=h[0x1B], checksum_declared=declared_cks, checksum_complement=declared_comp,
              checksum_computed=actual, checksum_valid=None if actual is None else int(actual == declared_cks),
              raw_json=_js({'internal_header_hex': (e + h).hex() if e else h.hex(), 'extended_header': bool(ext),
                            'layout_scores': {n: s for s, n, o in scored}, 'parser': PARSER_VERSION,
                            'interpretation': 'internal header declaration; enhancement chips and PCB require external evidence'}))
    out['hardware'] = hw
    out['parse_status'] = 'valid'
    if declared_cks ^ declared_comp != 0xFFFF: out['warnings'].append('checksum and complement disagree')
    if actual is None: out['warnings'].append('checksum not computed for irregular ROM size')
    elif actual != declared_cks: out['warnings'].append('declared checksum differs from computed checksum')
    if rom_kib and rom_kib * 1024 < len(rom): out['warnings'].append('file larger than declared ROM size')
    if out['warnings'] and not (copier and len(out['warnings']) == 1): out['parse_status'] = 'warning'
    return out


# ---------------------------------------------------------------- Mega Drive

def md_checksum(data):
    """Sum of big-endian 16-bit words after the 0x200-byte vector/header area."""
    body = data[0x200:]
    if len(body) % 2: body += b'\x00'
    return sum(int.from_bytes(body[i:i + 2], 'big') for i in range(0, len(body), 2)) & 0xFFFF


def _md_checksum_fast(data):
    import array, sys
    body = data[0x200:]
    if len(body) % 2: body += b'\x00'
    a = array.array('H', body)
    if sys.byteorder == 'little': a.byteswap()
    return sum(a) & 0xFFFF


def parse_md(data):
    out = dict(format='md', parse_status='unclassified', components=[], hardware=None, warnings=[])
    if len(data) >= 0x200 and len(data) % 16384 == 512 and data[8:10] == b'\xAA\xBB':
        out['format'] = 'smd_interleaved'
        out['warnings'].append('SMD copier interleaving detected; bytes stored unchanged, no automatic de-interleave')
        out['components'].append(('file', 0, len(data))); return out
    if len(data) < 0x200:
        out['warnings'].append('file shorter than vector table and header')
        if data: out['components'].append(('file', 0, len(data)))
        return out
    out['components'] += [('vectors', 0, 0x100), ('header', 0x100, 0x100), ('program', 0x200, len(data) - 0x200)]
    h = data[0x100:0x200]
    system = _text(h[0x00:0x10])
    if not system or not system.upper().lstrip().startswith(('SEGA', ' SEGA')):
        out['warnings'].append('no SEGA system string at 0x100'); signature = False
    else: signature = True
    u32 = lambda b: int.from_bytes(b, 'big')
    declared = u32(h[0x8E:0x90]); actual = _md_checksum_fast(data)
    extra = h[0xB0:0xBC]
    has_ram = extra[:2] == b'RA'
    hw = dict(system_type=system, copyright=_text(h[0x10:0x20]), title_domestic=_text(h[0x20:0x50]),
              title_overseas=_text(h[0x50:0x80]), serial=_text(h[0x80:0x8E]),
              checksum_declared=declared, checksum_computed=actual, checksum_valid=int(declared == actual),
              devices=_text(h[0x90:0xA0]), rom_start=u32(h[0xA0:0xA4]), rom_end=u32(h[0xA4:0xA8]),
              ram_start=u32(h[0xA8:0xAC]), ram_end=u32(h[0xAC:0xB0]),
              sram_type=extra[2] if has_ram else None, sram_start=u32(extra[4:8]) if has_ram else None,
              sram_end=u32(extra[8:12]) if has_ram else None, modem=_text(h[0xBC:0xC8]),
              notes=_text(h[0xC8:0xF0]), regions=_text(h[0xF0:0xF3]),
              raw_json=_js({'internal_header_hex': h.hex(), 'parser': PARSER_VERSION,
                            'interpretation': 'internal header declaration; mapper, SRAM and lock-on hardware require external evidence'}))
    out['hardware'] = hw
    if signature:
        out['parse_status'] = 'valid'
        if declared != actual: out['warnings'].append('declared checksum differs from computed checksum')
        if hw['rom_end'] and hw['rom_end'] + 1 != len(data): out['warnings'].append('declared ROM end differs from file size')
        if out['warnings']: out['parse_status'] = 'warning'
    return out


PARSERS = {'snes': parse_snes, 'megadrive': parse_md}
