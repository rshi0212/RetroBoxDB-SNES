"""Build a public Catalog release from a checksum-pinned, payload-free base Catalog (used by the release workflow).

python3 -B tools/build_catalog_release.py [--manifest release/catalog-release.json] [--output dist/<Catalog>.sqlite] [--base local.sqlite]

The base Catalog supplies all data; this repository commit supplies the engine (generated from tools/), documents
and reports listed in the manifest. The build fails unless:
  * the base matches its pinned SHA256, is the catalog-only edition and its payload tables are empty;
  * every data table (all tables except `resources`) has exactly the digest recorded in the manifest;
  * SQLite integrity and foreign keys pass, every resource checksum is valid and the Catalog engine audit passes;
  * the repository tests pass, plus any embedded test suite the manifest names (NES keeps its own);
  * the vacuumed output has no free pages.
Outputs: the Catalog, SHA256SUMS and release-notes.md next to it.
"""
import argparse, hashlib, json, pathlib, shutil, sqlite3, subprocess, sys, tempfile, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAYLOAD = ('compression_groups', 'chunks', 'object_chunks')
sys.path.insert(0, str(ROOT / 'tools'))


def digest_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def table_digest(c, table):
    """Order-independent, column-name-keyed digest of a table's rows (stable across column order and VACUUM)."""
    cols = sorted(r[1] for r in c.execute(f'PRAGMA table_info("{table}")'))
    sel = ','.join(f'"{x}"' for x in cols)
    h = hashlib.sha256(json.dumps(cols).encode()); n = 0
    for row in c.execute(f'SELECT {sel} FROM "{table}" ORDER BY {sel}'):
        h.update(repr(tuple(v.hex() if isinstance(v, bytes) else v for v in row)).encode()); n += 1
    return {'rows': n, 'sha256': h.hexdigest()}


def data_tables(c):
    return sorted(r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='resources'"))


def put(c, name, kind, content):
    c.execute('INSERT INTO resources VALUES (?,?,?,?) ON CONFLICT(name) DO UPDATE SET kind=excluded.kind,content=excluded.content,sha256=excluded.sha256',
              (name, kind, content, hashlib.sha256(content.encode()).hexdigest()))


def build(manifest_path, output, base=None):
    m = json.loads(pathlib.Path(manifest_path).read_text())
    output = pathlib.Path(output or ROOT / 'dist' / m['catalog_name'])
    if output.exists(): raise SystemExit('Refusing to replace an existing output')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='catalog-base-') as tmp:
        if base is None:
            base = pathlib.Path(tmp) / 'base.sqlite'
            req = urllib.request.Request(m['base_url'], headers={'User-Agent': 'RetroBoxDB-release'})
            with urllib.request.urlopen(req, timeout=300) as r, open(base, 'wb') as f: shutil.copyfileobj(r, f)
        if digest_file(base) != m['base_sha256']: raise SystemExit('Base Catalog SHA256 mismatch')
        src = sqlite3.connect(pathlib.Path(base).resolve().as_uri() + '?mode=ro', uri=True)
        c = sqlite3.connect(output); src.backup(c); src.close()
    meta = dict(c.execute('SELECT key,value FROM meta'))
    if meta.get('edition') != 'catalog-only' or meta.get('payload_available') != 'false': raise SystemExit('Base is not the catalog-only edition')
    if any(c.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in PAYLOAD): raise SystemExit('Base contains payload rows')
    B = __import__('build_db')
    engine_text, engine_body = B.combined_engine()
    catalog_engine = engine_body + '\n\n' + (ROOT / 'tools' / 'base' / 'catalog_wrapper.py').read_text()
    c.execute('BEGIN')
    put(c, 'engine.full.py', 'python', engine_text); put(c, 'engine.py', 'python', catalog_engine)
    for name, info in m['resources'].items(): put(c, name, info['kind'], (ROOT / info['path']).read_text())
    for old in m.get('remove_resources', []): c.execute('DELETE FROM resources WHERE name=?', (old,))
    tables = data_tables(c)
    if sorted(m['data_table_sha256']) != tables: raise SystemExit(f'Data table set differs from the manifest: {sorted(set(tables) ^ set(m["data_table_sha256"]))}')
    for t in tables:
        if table_digest(c, t) != m['data_table_sha256'][t]: raise SystemExit(f'Data table changed: {t}')
    if c.execute('PRAGMA foreign_key_check').fetchall(): raise SystemExit('Foreign key check failed')
    for name, content, sha in c.execute('SELECT name,content,sha256 FROM resources'):
        if hashlib.sha256(content.encode()).hexdigest() != sha: raise SystemExit(f'Resource checksum mismatch: {name}')
    put(c, 'release-manifest', 'json', json.dumps(m, ensure_ascii=False, indent=2))
    c.execute('COMMIT'); c.execute('VACUUM')
    if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or c.execute('PRAGMA freelist_count').fetchone()[0]: raise SystemExit('Integrity / free-page check failed')
    c.close()
    # Catalog engine audit (query-only, as a user would run it).
    probe = subprocess.run([sys.executable, '-B', '-c', 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); s=c.execute("SELECT content FROM resources WHERE name=?",("engine.py",)).fetchone()[0]; c.close(); exec(compile(s,"RetroBoxDB:engine.py","exec"))', str(output), 'audit'],
                           capture_output=True, text=True)
    if probe.returncode or not json.loads(probe.stdout)['ok']: raise SystemExit('Catalog engine audit failed: ' + probe.stdout[-500:] + probe.stderr[-500:])
    tests = subprocess.run([sys.executable, '-B', '-m', 'unittest'] + m.get('repo_tests', []), cwd=ROOT, capture_output=True, text=True)
    print(tests.stderr[-3000:], flush=True)
    if tests.returncode: raise SystemExit('Repository tests failed')
    if m.get('embedded_tests'):
        con = sqlite3.connect(f'file:{output}?mode=ro', uri=True)
        with tempfile.TemporaryDirectory(prefix='catalog-embedded-tests-') as tmp:
            for filename, resource in m['embedded_tests']['files'].items():
                pathlib.Path(tmp, filename).write_text(con.execute('SELECT content FROM resources WHERE name=?', (resource,)).fetchone()[0])
            r = subprocess.run([sys.executable, '-B', '-m', 'unittest'] + m['embedded_tests']['modules'], cwd=tmp, capture_output=True, text=True)
            print(r.stderr[-3000:], flush=True)
            if r.returncode: raise SystemExit('Embedded tests failed')
        con.close()
    checksum = digest_file(output)
    (output.parent / 'SHA256SUMS').write_text(f'{checksum}  {output.name}\n')
    notes = (ROOT / 'release' / 'notes.md').read_text() + f'\nCatalog size: **{output.stat().st_size:,} bytes**.\n\nSHA256: `{checksum}`\n'
    (output.parent / 'release-notes.md').write_text(notes)
    print(json.dumps({'catalog': str(output), 'sha256': checksum, 'size': output.stat().st_size, 'tag': m['tag']}, indent=2))


def manifest_digests(catalog):
    """Helper for maintainers: the data_table_sha256 block for a new base Catalog."""
    c = sqlite3.connect(f'file:{catalog}?mode=ro', uri=True)
    return {t: table_digest(c, t) for t in data_tables(c)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--manifest', default=ROOT / 'release' / 'catalog-release.json'); ap.add_argument('--output'); ap.add_argument('--base')
    ap.add_argument('--digests', help='print data_table_sha256 for this Catalog and exit')
    a = ap.parse_args()
    if a.digests: print(json.dumps(manifest_digests(a.digests), indent=1))
    else: build(a.manifest, a.output, a.base)
