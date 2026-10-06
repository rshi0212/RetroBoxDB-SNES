"""Platform routing for the shared RetroAchievements MSX folder: platform first (MSX1 or MSX2), medium second.

RA lists MSX and MSX2 games under one console and one folder; each ZIP goes to exactly one database, decided in order:
  1. dat       - a member's SHA1 is in the MSX2 (or MSX) Parent-Clone DATs;
  2. tag       - the file name says '(MSX2' or a member has the .mx2 extension;
  3. curated   - data/msx-routing.csv: reviewed decisions (reference title lists, public references such as MSX
                 software databases and contest pages, manual knowledge); its basis column is recorded. Reviewed decisions override the heuristics below;
  4. title     - the base title (qualifiers removed) names games of only one platform's DATs;
  5. blocks    - a member shares at least 10% of its 8 KiB blocks with DAT ROMs of only one platform (hacks, translations);
  6. default   - MSX1 (the base platform; MSX2 machines run MSX1 software), flagged 'platform_unconfirmed' for review.
Disk, tape and playlist members follow their ZIP. Pure standard library; used by update_db.py and the reports.
"""
import hashlib, html, os, pathlib, re, zipfile, xml.etree.ElementTree as ET

DATFILES = pathlib.Path('~/Sync/Datfiles').expanduser()
CURATED = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'msx-routing.csv'
PREFIX = {'msx1': 'Microsoft - MSX', 'msx2': 'Microsoft - MSX2'}
BLOCK = 8192
_cache = {}


def _base(name):
    return re.sub(r'\s*\(.*$', '', re.sub(r'\.[A-Za-z0-9]{2,4}$', '', name)).strip().casefold()


def _index(datfiles=DATFILES):
    key = str(datfiles)
    if key in _cache: return _cache[key]
    idx = {}
    for code, pfx in PREFIX.items():
        sha1, titles, blocks = set(), set(), set()
        for f in sorted(datfiles.glob('*.zip')):
            if not html.unescape(f.name).startswith(pfx + ' (Parent-Clone)'): continue
            with zipfile.ZipFile(f) as z:
                root = ET.fromstring(z.read(z.namelist()[0]))
            for g in root.findall('game'):
                titles.add(_base(g.get('name')))
                for r in g.findall('rom'): sha1.add((r.get('sha1') or '').lower())
        idx[code] = {'sha1': sha1, 'titles': titles, 'blocks': blocks}
    _cache[key] = idx
    return idx


def add_dat_rom_blocks(code, data, datfiles=DATFILES):
    """Register the 8 KiB block hashes of a DAT ROM (called with local DAT ROMs before routing hacks)."""
    _index(datfiles)[code]['blocks'].update(hashlib.sha1(data[i:i + BLOCK]).digest() for i in range(0, len(data), BLOCK))


def route(zip_name, members, datfiles=DATFILES, curated_path=CURATED):
    """members: [(member name, bytes)]. Returns (platform code, basis)."""
    idx = _index(datfiles)
    hits = {c for name, data in members for c in PREFIX if hashlib.sha1(data).hexdigest() in idx[c]['sha1']}
    if len(hits) == 1: return hits.pop(), 'dat'
    if 'msx2' in hits: return 'msx2', 'dat'
    if re.search(r'\(MSX2', zip_name) or any(n.lower().endswith('.mx2') for n, _ in members): return 'msx2', 'tag'
    cur = curated(curated_path).get(zip_name)
    if cur and cur[0] in PREFIX: return cur[0], 'curated:' + cur[1]
    t = _base(zip_name); in1, in2 = t in idx['msx1']['titles'], t in idx['msx2']['titles']
    if in1 != in2: return ('msx2' if in2 else 'msx1'), 'title'
    best = {}
    for name, data in members:
        bl = [hashlib.sha1(data[i:i + BLOCK]).digest() for i in range(0, len(data), BLOCK)]
        if not bl: continue
        for c in PREFIX:
            share = sum(b in idx[c]['blocks'] for b in bl) / len(bl)
            best[c] = max(best.get(c, 0), share)
    s1, s2 = best.get('msx1', 0), best.get('msx2', 0)
    if max(s1, s2) >= 0.10 and s1 != s2: return ('msx2' if s2 > s1 else 'msx1'), 'blocks'
    return 'msx1', 'default'


def curated(path=CURATED):
    """{zip name: (platform code, basis)} from data/msx-routing.csv (columns zip_name, platform, basis, note)."""
    key = ('curated', str(path))
    if key not in _cache:
        import csv
        _cache[key] = {r['zip_name']: (r['platform'], r['basis']) for r in csv.DictReader(open(path, encoding='utf-8'))} if path.exists() else {}
    return _cache[key]


def prime_blocks(nointro_root='/mnt/MyShare/No-Intro', dbs=None, datfiles=DATFILES):
    """Load the block hashes of every local DAT ROM: from the No-Intro folders when present, else from the populated
    databases (source ZIPs may have been deleted; the databases export the same bytes)."""
    idx = _index(datfiles)
    for code, pfx in PREFIX.items():
        if idx[code]['blocks']: continue
        root = pathlib.Path(nointro_root) / pfx
        if root.is_dir() and any(root.glob('*.zip')):
            for p in root.glob('*.zip'):
                with zipfile.ZipFile(p) as z:
                    for i in z.infolist():
                        if not i.is_dir(): add_dat_rom_blocks(code, z.read(i), datfiles)
        elif dbs and code in dbs:
            for data in dbs[code](): add_dat_rom_blocks(code, data, datfiles)
