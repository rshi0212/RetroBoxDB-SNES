import pickle, sqlite3, time, json, sys, pathlib
sys.path.insert(0, '.'); from build_v3 import create; import engine
out = pathlib.Path('v3.sqlite'); out.unlink(missing_ok=True); create(out)
c = sqlite3.connect(out); c.execute("INSERT OR REPLACE INTO meta VALUES('nes_block_size','8192')"); c.commit(); c.close()
db = engine.DB(out); raw = pickle.load(open('sample_nes_raw.pkl', 'rb')); t = time.time()
with db.c:
    for p, n, d in sorted(raw, key=lambda x: x[0]):
        db.rom(d, 'headerless' if '(Headerless)' in p else 'headered')
t1 = time.time()
with db.c: g = db.compact_groups()
db.c.execute('VACUUM')
st = db.c.execute("SELECT (SELECT sum(length(data)) FROM chunks)+(SELECT coalesce(sum(length(data)),0) FROM compression_groups)").fetchone()[0]
print(json.dumps({'config': 'nes_v3_engine_as_is', 'stored_MiB': round(st / 2**20, 1), 'sqlite_file_MiB': round(out.stat().st_size / 2**20, 1), 'import_s': round(t1 - t), 'compact_s': round(time.time() - t1)}), flush=True)
