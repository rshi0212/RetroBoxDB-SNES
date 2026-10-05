import sqlite3, lzma, sys, time, json, multiprocessing as mp
D = 128 << 20
def run(args):
    gid, name, chain = args
    c = sqlite3.connect('file:/mnt/MyShare/RetroBoxDB/RetroBoxDB.GBA.sqlite?mode=ro', uri=True)
    data = c.execute('SELECT data FROM compression_groups WHERE id=?', (gid,)).fetchone()[0]
    base = [{'id': lzma.FILTER_LZMA2, 'dict_size': D, 'lc': 3, 'lp': 0, 'pb': 0, 'mode': lzma.MODE_NORMAL, 'nice_len': 273, 'mf': lzma.MF_BT4}]
    raw = lzma.decompress(data, format=lzma.FORMAT_RAW, filters=base)
    t = time.time(); enc = lzma.compress(raw, format=lzma.FORMAT_RAW, filters=chain + base)
    return gid, name, len(raw), len(enc), round(time.time() - t)
if __name__ == '__main__':
    gids = [int(x) for x in sys.argv[1].split(',')]
    chains = [('lzma2', []), ('armthumb+lzma2', [{'id': lzma.FILTER_ARMTHUMB}]), ('arm+lzma2', [{'id': lzma.FILTER_ARM}])]
    with mp.Pool(3) as p:
        for r in p.imap(run, [(g, n, ch) for g in gids for n, ch in chains]): print(json.dumps(r), flush=True)
