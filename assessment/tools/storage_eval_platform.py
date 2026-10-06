"""Storage evaluation of a whole local platform collection (No-Intro folders plus the platform's files in RA folders).

python3 storage_eval_platform.py OUT.json --prefix "Sega - Master System - Mark III" --ext .sms
        [--extra "/mnt/MyShare/RetroAchievements/RA - Sega Master System" ...] [--blocks 8,16,32,64] [--caps 32,64,128,256]

Families: newest Parent-Clone DAT of the prefix (fallback: title). Groups: family-ordered LZMA2 (lc3 lp0 pb0, BT4,
nice_len 273, dictionary = group cap), as storage v4 stores them. total_MiB = compressed groups + block metadata
estimate (90 bytes per block, 40 per reference). A cap larger than the platform's unique data is measured once.
"""
import argparse, collections, hashlib, json, lzma, multiprocessing as mp, pathlib, re, time, zipfile, xml.etree.ElementTree as ET

DATS = pathlib.Path('~/Sync/Datfiles').expanduser(); NOINTRO = pathlib.Path('/mnt/MyShare/No-Intro')


def stamp(p): m = re.search(r'\((\d{8}-\d{6})\)', p.name); return m[1] if m else ''


def lz(data, d):
    f = [{'id': lzma.FILTER_LZMA2, 'dict_size': d, 'lc': 3, 'lp': 0, 'pb': 0, 'mode': lzma.MODE_NORMAL, 'nice_len': 273, 'mf': lzma.MF_BT4}]
    return len(lzma.compress(data, format=lzma.FORMAT_RAW, filters=f))


def collect(prefix, exts, extra, route=None):
    dat = sorted(DATS.glob(f'{prefix} (Parent-Clone) (*).zip'), key=stamp)[-1]
    z = zipfile.ZipFile(dat); root = ET.fromstring(z.read(z.namelist()[0]))
    parent = {g.get('name'): (g.get('cloneof') or g.get('name')) for g in root.findall('game')}
    fam = collections.defaultdict(list); zipbytes = 0; srcs = collections.Counter()
    dirs = [d for d in sorted(NOINTRO.iterdir()) if d.is_dir() and (d.name == prefix or d.name.startswith(prefix + ' ('))] + extra
    for d in dirs:
        for p in sorted(d.glob('*.zip')):
            with zipfile.ZipFile(p) as zz:
                members = [(i.filename, zz.read(i)) for i in zz.infolist() if not i.is_dir()]
            if d in extra:
                if route:  # shared folder split by platform (tools/msx_route.py), not by extension
                    if msx_route.route(p.name, members)[0] != route: continue
                else: members = [m for m in members if pathlib.PurePosixPath(m[0]).suffix.lower() in exts]  # this platform's files only
            if not members: continue
            zipbytes += p.stat().st_size; srcs[d.name] += 1
            fam[parent.get(p.stem) or '~' + re.sub(r'\s*\(.*$', '', p.stem).lower()] += members
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
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--prefix', required=True); ap.add_argument('--ext', nargs='+', required=True)
    ap.add_argument('--extra', nargs='*', default=[]); ap.add_argument('--blocks', default='8,16,32,64'); ap.add_argument('--caps', default='32,64,128,256')
    ap.add_argument('--memory-gib', type=int, default=6); ap.add_argument('--route', help='platform code: keep only extra-folder ZIPs routed to it (MSX)')
    a = ap.parse_args(); t0 = time.time()
    if a.route:
        import sys; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'tools')); import msx_route; msx_route.prime_blocks(); globals()['msx_route'] = msx_route
    fam, zipbytes, srcs, dat = collect(a.prefix, {e.lower() for e in a.ext}, [pathlib.Path(x) for x in a.extra], a.route)
    files = [d for v in fam.values() for _, d in v]; uniq = list({hashlib.sha256(d).digest(): d for d in files}.values())
    out = {'prefix': a.prefix, 'sources': srcs, 'dat': dat, 'families': len(fam), 'files': len(files), 'zip_MiB': round(zipbytes / 2**20, 2),
           'raw_MiB': round(sum(map(len, files)) / 2**20, 2), 'unique_files_MiB': round(sum(map(len, uniq)) / 2**20, 2), 'rows': [],
           'method': 'Whole local collection (no sample); families from the newest Parent-Clone DAT; storage-v4 group encoder settings'}
    with mp.Pool(4) as pool: out['per_file_lzma_MiB'] = round(sum(pool.starmap(lz, [(d, 1 << 20) for d in uniq])) / 2**20, 2)
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}), flush=True)
    for B in map(int, a.blocks.split(',')):
        single = False
        for C in map(int, a.caps.split(',')):
            if single: continue
            t = time.time(); groups, nb, refs = plan(fam, B << 10, C << 20)
            procs = max(1, min(4, len(groups), (a.memory_gib << 30) // (12 * (C << 20))))
            with mp.Pool(procs) as pool: sizes = pool.starmap(lz, [(g, C << 20) for g in groups])
            row = {'config': f'B{B}K_C{C}M', 'MiB': round(sum(sizes) / 2**20, 3), 'unique_MiB': round(sum(map(len, groups)) / 2**20, 2), 'groups': len(groups),
                   'blocks': nb, 'block_refs': refs, 'meta_MiB_est': round((nb * 90 + refs * 40) / 2**20, 3), 's': round(time.time() - t, 1)}
            row['total_MiB'] = round(row['MiB'] + row['meta_MiB_est'], 3); out['rows'].append(row); print(json.dumps(row), flush=True)
            single = len(groups) == 1  # larger caps give the same single group
    best = min(out['rows'], key=lambda r: r['total_MiB']); out['best'] = best['config']; out['seconds'] = round(time.time() - t0)
    json.dump(out, open(a.out, 'w'), indent=1)
