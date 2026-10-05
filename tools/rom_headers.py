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


# ---------------------------------------------------------------- Game Boy / Game Boy Color

GB_CART_TYPES = {0x00: 'ROM ONLY', 0x01: 'MBC1', 0x02: 'MBC1+RAM', 0x03: 'MBC1+RAM+BATTERY', 0x05: 'MBC2', 0x06: 'MBC2+BATTERY',
                 0x08: 'ROM+RAM', 0x09: 'ROM+RAM+BATTERY', 0x0B: 'MMM01', 0x0C: 'MMM01+RAM', 0x0D: 'MMM01+RAM+BATTERY',
                 0x0F: 'MBC3+TIMER+BATTERY', 0x10: 'MBC3+TIMER+RAM+BATTERY', 0x11: 'MBC3', 0x12: 'MBC3+RAM', 0x13: 'MBC3+RAM+BATTERY',
                 0x19: 'MBC5', 0x1A: 'MBC5+RAM', 0x1B: 'MBC5+RAM+BATTERY', 0x1C: 'MBC5+RUMBLE', 0x1D: 'MBC5+RUMBLE+RAM',
                 0x1E: 'MBC5+RUMBLE+RAM+BATTERY', 0x20: 'MBC6', 0x22: 'MBC7+SENSOR+RUMBLE+RAM+BATTERY', 0xFC: 'POCKET CAMERA',
                 0xFD: 'BANDAI TAMA5', 0xFE: 'HuC3', 0xFF: 'HuC1+RAM+BATTERY'}
GB_RAM_SIZES = {0: 0, 1: 2048, 2: 8192, 3: 32768, 4: 131072, 5: 65536}


def gb_header_checksum(data):
    x = 0
    for b in data[0x134:0x14D]: x = (x - b - 1) & 0xFF
    return x


def parse_gb(data):
    """Cartridge header at 0x100-0x14F (Pan Docs). The Nintendo logo is identified by SHA1 only."""
    out = dict(format='gb', parse_status='unclassified', components=[], hardware=None, warnings=[])
    if len(data) < 0x150:
        out['warnings'].append('file shorter than the 0x150-byte cartridge header')
        if data: out['components'].append(('file', 0, len(data)))
        return out
    out['components'] += [('vectors', 0, 0x100), ('header', 0x100, 0x50), ('program', 0x150, len(data) - 0x150)]
    h = data
    cgb = h[0x143]
    out['format'] = 'gbc' if cgb & 0x80 else 'gb'
    title_end = 0x143 if cgb & 0x80 else 0x144
    manufacturer = h[0x13F:0x143]
    mfr = manufacturer.decode('ascii') if cgb & 0x80 and all(0x30 <= b <= 0x39 or 0x41 <= b <= 0x5A for b in manufacturer) else None
    if mfr: title_end = 0x13F
    declared_hdr = h[0x14D]; actual_hdr = gb_header_checksum(h)
    declared_glob = int.from_bytes(h[0x14E:0x150], 'big'); actual_glob = (sum(h) - h[0x14E] - h[0x14F]) & 0xFFFF
    rs = h[0x148]; rom_size = (32768 << rs) if rs <= 8 else {0x52: 1179648, 0x53: 1310720, 0x54: 1572864}.get(rs)
    ctype = GB_CART_TYPES.get(h[0x147])
    hw = dict(title=_text(h[0x134:title_end]), title_hex=h[0x134:0x144].hex(), manufacturer_code=mfr, cgb_flag=cgb,
              cgb_mode='cgb_only' if cgb == 0xC0 else 'cgb_enhanced' if cgb & 0x80 else 'dmg', sgb_flag=h[0x146],
              licensee_old=h[0x14B], licensee_new=_text(h[0x144:0x146]) if h[0x14B] == 0x33 else None,
              cartridge_type=h[0x147], cartridge_type_name=ctype, battery=int(bool(ctype and 'BATTERY' in ctype)),
              rtc=int(bool(ctype and 'TIMER' in ctype)), rumble=int(bool(ctype and 'RUMBLE' in ctype)),
              rom_size_code=rs, rom_size_declared=rom_size, ram_size_code=h[0x149], ram_size_declared=GB_RAM_SIZES.get(h[0x149]),
              destination=h[0x14A], version=h[0x14C], header_checksum_declared=declared_hdr, header_checksum_computed=actual_hdr,
              header_checksum_valid=int(declared_hdr == actual_hdr), global_checksum_declared=declared_glob,
              global_checksum_computed=actual_glob, global_checksum_valid=int(declared_glob == actual_glob),
              logo_sha1=hashlib.sha1(h[0x104:0x134]).hexdigest(),
              raw_json=_js({'entry_hex': h[0x100:0x104].hex(), 'header_hex_excluding_logo': h[0x134:0x150].hex(), 'parser': PARSER_VERSION,
                            'interpretation': 'cartridge header declaration; mapper hardware and save chips require external evidence'}))
    out['hardware'] = hw; out['parse_status'] = 'valid'
    if declared_hdr != actual_hdr: out['warnings'].append('header checksum invalid; fields may not describe this dump')
    if declared_glob != actual_glob: out['warnings'].append('global checksum differs')
    if rom_size and rom_size != len(data): out['warnings'].append('declared ROM size differs from file size')
    if ctype is None: out['warnings'].append(f'unknown cartridge type {h[0x147]:#04x}')
    if out['warnings']: out['parse_status'] = 'warning'
    return out


# ---------------------------------------------------------------- Game Boy Advance

GBA_SAVE_PREFIXES = (b'EEPROM_V', b'SRAM_F_V', b'SRAM_V', b'FLASH1M_V', b'FLASH512_V', b'FLASH_V')


def gba_save_ids(data):
    """Word-aligned save-library ID strings such as FLASH1M_V103 (bytes.find is far faster than a regex here)."""
    found = set()
    for prefix in GBA_SAVE_PREFIXES:
        pos = data.find(prefix)
        while pos != -1:
            tail = data[pos + len(prefix):pos + len(prefix) + 3]
            if pos % 4 == 0 and len(tail) == 3 and tail.isdigit(): found.add((prefix + tail).decode())
            pos = data.find(prefix, pos + 1)
    return sorted(found)


def gba_complement(data):
    return (-(sum(data[0xA0:0xBD]) + 0x19)) & 0xFF


def parse_gba(data):
    """Cartridge header at 0x00-0xBF (GBATEK). Save-type library IDs are found by a word-aligned string scan."""
    out = dict(format='gba', parse_status='unclassified', components=[], hardware=None, warnings=[])
    if len(data) < 0xC0:
        out['warnings'].append('file shorter than the 0xC0-byte cartridge header')
        if data: out['components'].append(('file', 0, len(data)))
        return out
    h = data
    pad_byte = h[-1]
    padding = min(len(h) - len(h.rstrip(bytes([pad_byte]))), len(h) - 0xC0) if pad_byte in (0x00, 0xFF) else 0
    out['components'] += [('header', 0, 0xC0), ('program', 0xC0, len(h) - 0xC0 - padding)]
    if padding: out['components'].append(('padding', len(h) - padding, padding))
    saves = gba_save_ids(h)
    declared = h[0xBD]; actual = gba_complement(h)
    hw = dict(title=_text(h[0xA0:0xAC]), game_code=_text(h[0xAC:0xB0]), maker_code=_text(h[0xB0:0xB2]), fixed_value=h[0xB2],
              unit_code=h[0xB3], device_type=h[0xB4], version=h[0xBC], complement_declared=declared, complement_computed=actual,
              complement_valid=int(declared == actual), entry_hex=h[0:4].hex(), logo_sha1=hashlib.sha1(h[0x04:0xA0]).hexdigest(),
              save_types=','.join(saves) or None, padding_byte=pad_byte if padding else None, padding_bytes=padding,
              raw_json=_js({'header_hex_excluding_logo': h[0xA0:0xC0].hex(), 'parser': PARSER_VERSION,
                            'interpretation': 'cartridge header declaration; save IDs are library strings, not proof of the physical save chip'}))
    out['hardware'] = hw
    if h[0xB2] != 0x96:
        out['warnings'].append('fixed header byte 0xB2 is not 0x96'); return out
    out['parse_status'] = 'valid'
    if declared != actual: out['warnings'].append('header complement check invalid')
    if len(set(s.split('_V')[0] for s in saves)) > 1: out['warnings'].append('several save library types referenced')
    if out['warnings']: out['parse_status'] = 'warning'
    return out


# ---------------------------------------------------------------- Famicom Disk System

FDS_SIDE = {'fds': 65500, 'qd': 65536}  # No-Intro FDS sides hold blocks without CRCs or gaps; QD sides keep a CRC after each block
FDS_MAGIC = b'*NINTENDO-HVC*'


def fds_layout(data):
    """(image format, header length, side size) of a disk image: fwNES 'FDS\\x1a' header, then FDS or QD sides."""
    head = 16 if data[:4] == b'FDS\x1a' else 0
    body = len(data) - head
    if len(data) == 8192 and data[head + 1:head + 15] != FDS_MAGIC: return 'bios', 0, 0
    for fmt in ('qd', 'fds'):  # 131072 = 2 QD sides; 131000 = 2 FDS sides
        if body and body % FDS_SIDE[fmt] == 0: return fmt, head, FDS_SIDE[fmt]
    return ('fds' if data[head + 1:head + 15] == FDS_MAGIC else 'unknown'), head, FDS_SIDE['fds']


def _fds_date(b):
    """Declared BCD date (YY MM DD). The year is in the Japanese era counting used on these disks: values 50-64
    are read as Showa (1925 + YY), smaller values as Heisei (1988 + YY); the raw BCD is kept as well."""
    try:
        y, m, d = (int(f'{x:02x}') for x in b)
    except ValueError: return None
    if not (1 <= m <= 12 and 1 <= d <= 31): return None
    year = 1925 + y if 50 <= y <= 64 else 1988 + y if y < 50 else None
    return f'{year:04d}-{m:02d}-{d:02d}' if year else None


def parse_fds(data):
    """Disk information block (block 1) of every side; file-amount block (block 2). Descriptive only."""
    out = dict(format='unknown', parse_status='unclassified', components=[], hardware=None, warnings=[])
    fmt, head, side = fds_layout(data)
    if fmt == 'bios':
        out.update(format='bios', components=[('bios', 0, len(data))]); return out
    out['format'] = fmt
    if head: out['components'].append(('fwnes_header', 0, head))
    sides = []
    for n, off in enumerate(range(head, len(data), side)):
        chunk = data[off:off + side]; out['components'].append(('side', off, len(chunk)))
        if len(chunk) < 56 or chunk[0] != 1 or chunk[1:15] != FDS_MAGIC:
            sides.append({'side': n, 'disk_info': False}); continue
        b2 = 58 if fmt == 'qd' else 56
        sides.append({'side': n, 'disk_info': True, 'manufacturer_code': chunk[15], 'game_code': _text(chunk[16:19]), 'game_type': _text(chunk[19:20]) or None,
                      'revision': chunk[20], 'side_number': chunk[21], 'disk_number': chunk[22], 'disk_type': chunk[23], 'boot_file_code': chunk[25],
                      'manufacturing_date_bcd': chunk[31:34].hex(), 'manufacturing_date': _fds_date(chunk[31:34]), 'country_code': chunk[34],
                      'rewrite_date_bcd': chunk[44:47].hex(), 'file_amount': chunk[b2 + 1] if len(chunk) > b2 + 1 and chunk[b2] == 2 else None})
    first = next((x for x in sides if x['disk_info']), None)
    if first is None:
        out['warnings'].append('no disk information block found'); return out
    trailing = (len(data) - head) % side
    hw = dict(image_format=fmt, fwnes_header=int(bool(head)), fwnes_sides=data[4] if head else None, side_size=side, sides=len(sides),
              valid_sides=sum(x['disk_info'] for x in sides), manufacturer_code=first['manufacturer_code'], game_code=first['game_code'],
              game_type=first['game_type'], revision=first['revision'], disk_type=first['disk_type'],
              manufacturing_date=first['manufacturing_date'], manufacturing_date_bcd=first['manufacturing_date_bcd'], country_code=first['country_code'],
              trailing_bytes=trailing, sides_json=_js(sides),
              raw_json=_js({'parser': PARSER_VERSION, 'interpretation': 'disk information block declarations per side; physical disk and writer history require external evidence'}))
    out['hardware'] = hw; out['parse_status'] = 'valid'
    if hw['valid_sides'] != hw['sides']: out['warnings'].append('side without a disk information block')
    if head and data[4] != len(sides): out['warnings'].append('fwNES side count differs from the image')
    if trailing: out['warnings'].append('image length is not a whole number of sides')
    if len({(x['game_code'], x['revision']) for x in sides if x['disk_info']}) > 1: out['warnings'].append('sides declare different game codes or revisions')
    if out['warnings']: out['parse_status'] = 'warning'
    return out


def fds_cuts(data):
    """Blocks restart at the fwNES header and at every side, so headered/headerless copies and shared sides deduplicate."""
    fmt, head, side = fds_layout(data)
    if fmt == 'bios': return set()
    return {head} | set(range(head, len(data), side)) if head else set(range(0, len(data), side))


# ---------------------------------------------------------------- Satellaview (BS-X)

BSX_BASES = (0x7FB0, 0xFFB0)  # LoROM / HiROM header area of a BS memory-pack file


def _bsx_score(data, base):
    h = data[base:base + 0x30]
    if len(h) < 0x30 or h[0x2A] != 0x33: return -1, h
    score = 2 + (h[0x28] in (0x20, 0x21, 0x30, 0x31)) * 2 + ((int.from_bytes(h[0x2C:0x2E], 'little') ^ int.from_bytes(h[0x2E:0x30], 'little')) == 0xFFFF)
    return score, h


def parse_bsx(data):
    """BS-X memory-pack header at 0x7FB0 / 0xFFB0 (Satellaview). A standard SNES header (the BS-X base cartridge) is
    parsed by parse_snes and stored in snes_hardware. Descriptive only."""
    out = dict(format='bs', parse_status='unclassified', components=[('file', 0, len(data))] if data else [], hardware=None, warnings=[])
    if len(data) >= 0x8000 and data[0x7FDA] == 0x33 and data[0x7FD5] in (0x20, 0x21, 0x23, 0x30, 0x31, 0x32, 0x35) and data[0x7FD8] not in (0x20, 0x21, 0x30, 0x31):
        p = parse_snes(data); p['format'] = 'snes_cartridge'; p['table'] = 'snes_hardware'; return p
    scored = [(*_bsx_score(data, b), b) for b in BSX_BASES]
    score, h, base = max(scored, key=lambda x: x[0])
    if score < 4:
        out['warnings'].append('no BS-X header found (data pack or unheadered file)'); return out
    month, day = h[0x26] >> 4, h[0x27] >> 3
    declared = int.from_bytes(h[0x2E:0x30], 'little'); complement = int.from_bytes(h[0x2C:0x2E], 'little')
    hw = dict(header_offset=base, mapping='lorom' if base == 0x7FB0 else 'hirom', maker_code=_text(h[0:2]), program_type=h[2:6].hex(), title=_text(h[0x10:0x20]),
              title_hex=h[0x10:0x20].hex(), block_allocation=h[0x20:0x24].hex(), limited_starts=int.from_bytes(h[0x24:0x26], 'little'),
              broadcast_month=month if 1 <= month <= 12 else None, broadcast_day=day if 1 <= day <= 31 else None, map_mode=h[0x28], execution_type=h[0x29],
              version=h[0x2B], checksum_declared=declared, checksum_complement=complement, checksum_pair_valid=int((declared ^ complement) == 0xFFFF),
              raw_json=_js({'parser': PARSER_VERSION, 'header_hex': h.hex(), 'interpretation': 'BS-X memory-pack header declaration; broadcast history and pack hardware require external evidence'}))
    out.update(hardware=hw, parse_status='valid')
    if not hw['checksum_pair_valid']: out['warnings'].append('checksum and complement do not pair')
    if hw['broadcast_month'] is None or hw['broadcast_day'] is None: out['warnings'].append('broadcast date field outside calendar range')
    if out['warnings']: out['parse_status'] = 'warning'
    return out


PARSERS = {'snes': parse_snes, 'megadrive': parse_md, 'gb': parse_gb, 'gbc': parse_gb, 'gba': parse_gba, 'fds': parse_fds, 'satellaview': parse_bsx}
