"""Satellaview storage evaluation on the whole local collection (No-Intro folders + .bs files of the RA SNES folder).

python3 storage_eval_satellaview.py OUT.json
Families: newest Satellaview Parent-Clone DAT (fallback: title). Groups: family-ordered LZMA2 (lc3 lp0 pb0, BT4,
nice_len 273, dictionary = group cap). total_MiB = compressed groups + block metadata estimate (90 bytes per block,
40 per reference).
"""
import collections, hashlib, json, lzma, multiprocessing as mp, pathlib, re, sys, time, zipfile, xml.etree.ElementTree as ET

DATS = pathlib.Path('~/Sync/Datfiles').expanduser(); NOINTRO = pathlib.Path('/mnt/MyShare/No-Intro'); PRE = 'Nintendo - Satellaview'
EXTRA = [pathlib.Path('/mnt/MyShare/RetroAchievements/RA - Super Nintendo Entertainment System')]
EXT = {'.bs', '.sfc', '.bin'}


def stamp(p): m = re.search(r'\((\d{8}-\d{6})\)', p.name); return m[1] if m else ''


def lz(data, d):
    f = [{'id': lzma.FILTER_LZMA2, 'dict_size': d, 'lc': 3, 'lp': 0, 'pb': 0, 'mode': lzma.MODE_NORMAL, 'nice_len': 273, 'mf': lzma.MF_BT4}]
    return len(lzma.compress(data, format=lzma.FORMAT_RAW, filters=f))


def collect():
    dat = sorted(DATS.glob(f'{PRE} (Parent-Clone) (*).zip'), key=stamp)[-1]
    z = zipfile.ZipFile(dat); root = ET.fromstring(z.read(z.namelist()[0]))
    parent = {g.get('name'): (g.get('cloneof') or g.get('name')) for g in root.findall('game')}
    fam = collections.defaultdict(list); zipbytes = 0; srcs = collections.Counter()
    dirs = [d for d in sorted(NOINTRO.iterdir()) if d.is_dir() and d.name.startswith(PRE)] + EXTRA
    for d in dirs:
        for p in sorted(d.glob('*.zip')):
            with zipfile.ZipFile(p) as zz:
                members = [(i.filename, zz.read(i)) for i in zz.infolist() if not i.is_dir() and pathlib.PurePosixPath(i.filename).suffix.lower() in EXT]
            if d in EXTRA: members = [m for m in members if m[0].lower().endswith('.bs')]
            if not members: continue
            zipbytes += p.stat().st_size; srcs[d.name] += 1
            key = parent.get(p.stem) or '~' + re.sub(r'\s*\(.*$', '', p.stem).lower()
            fam[key] += members
    return fam, zipbytes, dict(srcs), dat.name


def plan(fam, B, C):
    seen = set(); groups = []; cur = []; size = 0; nb = refs = 0
    for k in sorted(fam):
        new = []
        for n, data in sorted(fam[k]):
            for i in range(0, len(data), B):
                b = data[i:i + B]; refs += 1; h = hashlib.sha256(b).digest()
                if h not in seen: seen.add(h); new.append(b); nb += 1
        for b in new:
            if cur and size + len(b) > C: groups.append(b''.join(cur)); cur = []; size = 0
            cur.append(b); size += len(b)
    if cur: groups.append(b''.join(cur))
    return groups, nb, refs


if __name__ == '__main__':
    t0 = time.time(); fam, zipbytes, srcs, dat = collect()
    files = [d for v in fam.values() for _, d in v]; uniq = list({hashlib.sha256(d).digest(): d for d in files}.values())
    out = {'sources': srcs, 'dat': dat, 'families': len(fam), 'files': len(files), 'zip_MiB': round(zipbytes / 2**20, 2),
           'raw_MiB': round(sum(map(len, files)) / 2**20, 2), 'unique_files_MiB': round(sum(map(len, uniq)) / 2**20, 2), 'rows': []}
    with mp.Pool(4) as pool: out['per_file_lzma_MiB'] = round(sum(pool.starmap(lz, [(d, 1 << 20) for d in uniq])) / 2**20, 2)
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}), flush=True)
    for B in (16, 64):
        for C in (32, 64, 128, 256):
            t = time.time(); groups, nb, refs = plan(fam, B << 10, C << 20)
            with mp.Pool(max(1, min(4, len(groups), (8 << 30) // (12 * (C << 20))))) as pool: sizes = pool.starmap(lz, [(g, C << 20) for g in groups])
            row = {'config': f'B{B}K_C{C}M', 'MiB': round(sum(sizes) / 2**20, 3), 'unique_MiB': round(sum(map(len, groups)) / 2**20, 2), 'groups': len(groups),
                   'blocks': nb, 'block_refs': refs, 'meta_MiB_est': round((nb * 90 + refs * 40) / 2**20, 3), 's': round(time.time() - t, 1)}
            row['total_MiB'] = round(row['MiB'] + row['meta_MiB_est'], 3); out['rows'].append(row); print(json.dumps(row), flush=True)
    out['seconds'] = round(time.time() - t0)
    json.dump(out, open(sys.argv[1], 'w'), indent=1)
