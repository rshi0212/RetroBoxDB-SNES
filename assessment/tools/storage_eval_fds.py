"""Famicom Disk System storage evaluation on the whole local collection (FDS + QD + FDS images found in other folders).

python3 storage_eval_fds.py OUT.json
Families: newest FDS Parent-Clone DAT; QD entries join the FDS family of the same name, else their own QD parent.
Blocks restart at the 16-byte fwNES header and at every disk side (FDS 65500 bytes, QD 65536 bytes) so that
headered/headerless copies and revisions sharing a side deduplicate; the 'nocut' rows ignore side boundaries.
Groups: family-ordered LZMA2 (lc3 lp0 pb0, BT4, nice_len 273, dictionary = group cap).
"""
import collections, hashlib, json, lzma, multiprocessing as mp, pathlib, re, sys, time, zipfile, xml.etree.ElementTree as ET

DATS = pathlib.Path('~/Sync/Datfiles').expanduser()
NOINTRO = pathlib.Path('/mnt/MyShare/No-Intro'); PRE = 'Nintendo - Family Computer Disk System'
EXTRA = [pathlib.Path('/mnt/MyShare/RetroAchievements/RA - Nintendo Entertainment System')]  # FDS images mixed into NES folders
SIDE = {'.fds': 65500, '.qd': 65536}


def stamp(p): m = re.search(r'\((\d{8}-\d{6})\)', p.name); return m[1] if m else ''


def parents(kind):
    dat = sorted(DATS.glob(f'{PRE} ({kind}) (Parent-Clone) (*).zip'), key=stamp)[-1]
    z = zipfile.ZipFile(dat); root = ET.fromstring(z.read(z.namelist()[0]))
    return {g.get('name'): (g.get('cloneof') or g.get('name')) for g in root.findall('game')}, dat.name


def layout(data, ext):
    """Cut points: fwNES header, then each side."""
    off = 16 if data[:4] == b'FDS\x1a' else 0; side = SIDE[ext]; cuts = {off} if off else set()
    p = off
    while p < len(data): cuts.add(p); p += side
    return cuts


def blocks(data, B, cuts):
    bounds = sorted({0, len(data)} | {c for c in cuts if 0 < c < len(data)})
    return [data[p:min(p + B, b)] for a, b in zip(bounds, bounds[1:]) for p in range(a, b, B)]


def lz(data, d):
    f = [{'id': lzma.FILTER_LZMA2, 'dict_size': d, 'lc': 3, 'lp': 0, 'pb': 0, 'mode': lzma.MODE_NORMAL, 'nice_len': 273, 'mf': lzma.MF_BT4}]
    return len(lzma.compress(data, format=lzma.FORMAT_RAW, filters=f))


def collect():
    fds, fdsdat = parents('FDS'); qd, qddat = parents('QD'); fam = collections.defaultdict(list); zipbytes = 0; srcs = collections.Counter()
    dirs = [d for d in sorted(NOINTRO.iterdir()) if d.is_dir() and d.name.startswith(PRE)] + EXTRA
    for d in dirs:
        for p in sorted(d.glob('*.zip')):
            with zipfile.ZipFile(p) as z:
                members = [(i.filename, z.read(i)) for i in z.infolist() if not i.is_dir() and pathlib.PurePosixPath(i.filename).suffix.lower() in SIDE]
            if not members: continue
            zipbytes += p.stat().st_size; srcs[d.name] += 1
            name = p.stem; key = fds.get(name) or fds.get(qd.get(name, '')) or qd.get(name) or '~' + re.sub(r'\s*\(.*$', '', name).lower()
            for n, data in members: fam[key].append((n, data))
    return fam, zipbytes, dict(srcs), fdsdat, qddat


def plan(fam, B, C, cut=True):
    seen = set(); groups = []; cur = []; size = 0; nb = refs = 0
    for k in sorted(fam):
        new = []
        for n, data in sorted(fam[k]):
            for b in blocks(data, B, layout(data, pathlib.PurePosixPath(n).suffix.lower()) if cut else ()):
                refs += 1; h = hashlib.sha256(b).digest()
                if h not in seen: seen.add(h); new.append(b); nb += 1
        for b in new:
            if cur and size + len(b) > C: groups.append(b''.join(cur)); cur = []; size = 0
            cur.append(b); size += len(b)
    if cur: groups.append(b''.join(cur))
    return groups, nb, refs


if __name__ == '__main__':
    t0 = time.time(); fam, zipbytes, srcs, fdsdat, qddat = collect()
    files = [d for v in fam.values() for _, d in v]; uniq = list({hashlib.sha256(d).digest(): d for d in files}.values())
    out = {'sources': srcs, 'dats': [fdsdat, qddat], 'families': len(fam), 'files': len(files), 'zip_MiB': round(zipbytes / 2**20, 2),
           'raw_MiB': round(sum(map(len, files)) / 2**20, 2), 'unique_files_MiB': round(sum(map(len, uniq)) / 2**20, 2), 'rows': []}
    with mp.Pool(4) as pool: out['per_file_lzma_MiB'] = round(sum(pool.starmap(lz, [(d, 1 << 20) for d in uniq])) / 2**20, 2)
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}), flush=True)
    configs = [(B, C, True) for B in (4, 8, 16, 64) for C in (16, 32, 64, 128)] + [(64, 128, False), (8, 128, False)]
    for B, C, cut in configs:
        t = time.time(); groups, nb, refs = plan(fam, B << 10, C << 20, cut)
        with mp.Pool(min(4, len(groups))) as pool: sizes = pool.starmap(lz, [(g, C << 20) for g in groups])
        row = {'config': f'B{B}K_C{C}M' + ('' if cut else '_nocut'), 'MiB': round(sum(sizes) / 2**20, 3), 'unique_MiB': round(sum(map(len, groups)) / 2**20, 2),
               'groups': len(groups), 'blocks': nb, 'block_refs': refs, 'meta_MiB_est': round((nb * 90 + refs * 40) / 2**20, 3), 's': round(time.time() - t, 1)}
        row['total_MiB'] = round(row['MiB'] + row['meta_MiB_est'], 3); out['rows'].append(row); print(json.dumps(row), flush=True)
    out['seconds'] = round(time.time() - t0)
    json.dump(out, open(sys.argv[1], 'w'), indent=1)
