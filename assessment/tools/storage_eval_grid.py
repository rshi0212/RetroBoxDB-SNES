"""Per-platform storage grid: dedup block size B x family-ordered solid group cap C (LZMA2, dict = cap).

python3 grid.py sample_<plat>.pkl "B:C,B:C,..." [baseline]
Prints one JSON line per configuration: stored MiB, block metadata estimate, groups, seconds.
"""
import hashlib, json, lzma, multiprocessing as mp, pickle, sys, time


def lz(data, dict_size):
    f = [{'id': lzma.FILTER_LZMA2, 'dict_size': dict_size, 'lc': 3, 'lp': 0, 'pb': 0, 'mode': lzma.MODE_NORMAL, 'nice_len': 273, 'mf': lzma.MF_BT4}]
    return len(lzma.compress(data, format=lzma.FORMAT_RAW, filters=f))


def pow2(n, lo=1 << 20, hi=1 << 28):
    d = lo
    while d < n and d < hi: d <<= 1
    return d


def plan(S, B, C):
    seen = set(); groups = []; cur = []; size = 0; nblocks = 0; refs = 0
    for k, items in sorted(S['files'].items()):
        uniq = {}
        for p, n, d in sorted(items, key=lambda x: x[1]): uniq.setdefault(hashlib.sha256(d).digest(), d)
        fam = []
        for d in uniq.values():
            for i in range(0, len(d), B):
                b = d[i:i + B]; refs += 1; h = hashlib.sha256(b).digest()
                if h in seen: continue
                seen.add(h); fam.append(b); nblocks += 1
        fsize = sum(map(len, fam))
        if cur and size + fsize > C: groups.append(b''.join(cur)); cur = []; size = 0
        for b in fam:
            if size + len(b) > C: groups.append(b''.join(cur)); cur = []; size = 0
            cur.append(b); size += len(b)
    if cur: groups.append(b''.join(cur))
    return groups, nblocks, refs


if __name__ == '__main__':
    S = pickle.load(open(sys.argv[1], 'rb')); tag = sys.argv[1]
    if len(sys.argv) > 3:
        datas = list({hashlib.sha256(d).digest(): d for v in S['files'].values() for _, _, d in v}.values())
        t = time.time()
        with mp.Pool(4) as pool: sizes = pool.starmap(lz, [(d, pow2(len(d))) for d in datas], chunksize=1)
        print(tag, json.dumps({'config': 'per_file_lzma', 'MiB': round(sum(sizes) / 2**20, 1), 'zip_MiB': round(S['zipbytes'] / 2**20, 1),
                               'raw_MiB': round(sum(len(d) for v in S['files'].values() for _, _, d in v) / 2**20, 1),
                               'unique_files_MiB': round(sum(map(len, datas)) / 2**20, 1), 's': round(time.time() - t)}), flush=True)
    for cfg in sys.argv[2].split(','):
        B, C = (int(x) for x in cfg.split(':')); t = time.time()
        groups, nb, refs = plan(S, B << 10, C << 20); d = pow2(C << 20)
        workers = 8 if d <= 32 << 20 else 4 if d <= 64 << 20 else 2
        with mp.Pool(workers) as pool: sizes = pool.starmap(lz, [(g, d) for g in groups], chunksize=1)
        print(tag, json.dumps({'config': f'B{B}K_C{C}M', 'MiB': round(sum(sizes) / 2**20, 1), 'unique_MiB': round(sum(map(len, groups)) / 2**20, 1),
                               'groups': len(groups), 'blocks': nb, 'block_refs': refs, 'meta_MiB_est': round((nb * 90 + refs * 40) / 2**20, 2),
                               'max_group_MiB': round(max(map(len, groups)) / 2**20, 1), 's': round(time.time() - t)}), flush=True)
