"""Bigger-group test on real data: merge k consecutive (family-ordered) solid groups and recompress with a k-times dictionary.

python3 merge.py DB.sqlite START COUNT K [filters]   -> stored bytes now vs merged
"""
import json, lzma, sqlite3, sys, time
import multiprocessing as mp
db, start, count, k = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
pre = [{'id': lzma.FILTER_ARMTHUMB}] if len(sys.argv) > 5 and sys.argv[5] == 'armthumb' else []


def filt(d): return [{'id': lzma.FILTER_LZMA2, 'dict_size': d, 'lc': 3, 'lp': 0, 'pb': 0, 'mode': lzma.MODE_NORMAL, 'nice_len': 273, 'mf': lzma.MF_BT4}]


def comp(args):
    raw, d = args
    return len(lzma.compress(raw, format=lzma.FORMAT_RAW, filters=pre + filt(d)))


if __name__ == '__main__':
    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    dict_now = int(c.execute("SELECT value FROM meta WHERE key='solid_group_dictionary_bytes'").fetchone()[0])
    rows = c.execute("SELECT id,size,data FROM compression_groups WHERE codec='lzma2-solid' ORDER BY id LIMIT ? OFFSET ?", (count, start)).fetchall()
    raws = [lzma.decompress(d, format=lzma.FORMAT_RAW, filters=filt(dict_now)) for _, _, d in rows]
    now = sum(len(d) for _, _, d in rows)
    merged = [b''.join(raws[i:i + k]) for i in range(0, len(raws), k)]
    d = 1 << (max(len(m) for m in merged) - 1).bit_length()
    t = time.time()
    with mp.Pool(max(1, min(4, 8 * 2**30 // (12 * d)))) as p: sizes = p.map(comp, [(m, d) for m in merged])
    print(json.dumps({'db': db.split('/')[-1], 'groups': len(rows), 'raw_MiB': round(sum(map(len, raws)) / 2**20, 1), 'stored_now_MiB': round(now / 2**20, 2),
                      'merged_k': k, 'dict_MiB': d >> 20, 'filters': 'armthumb+lzma2' if pre else 'lzma2', 'merged_MiB': round(sum(sizes) / 2**20, 2),
                      'change_pct': round(100 * (sum(sizes) - now) / now, 2), 's': round(time.time() - t)}), flush=True)
