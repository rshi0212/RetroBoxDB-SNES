"""Post-build refresh for a cartridge RetroBoxDB: schema additions, resources, reports and Catalog.

python3 -B tools/finalize_cart_db.py FULL.sqlite CATALOG.sqlite
- Adds cart_schema.sql objects missing from FULL (indexes/views only; tables must already exist).
- Re-embeds the current tools, tests and documentation as resources.
- Writes reports/<platform>-build-report.json, reports/ra-<platform>.json and reports/ra-<platform>-games.csv.
- Rebuilds CATALOG from FULL (an existing CATALOG produced by this tool is replaced).
Payload tables are never modified.
"""
import hashlib, importlib, json, pathlib, re, sqlite3, sys

TOOLS = pathlib.Path(__file__).resolve().parent; ROOT = TOOLS.parent
sys.path[:0] = [str(TOOLS), str(TOOLS / 'base')]
import build_cart_db as B  # noqa: E402

DOCS = {'README.zh-CN': ('markdown', ROOT / 'RetroBoxDB.Cartridge.zh-CN.md'),
        'README.en': ('markdown', ROOT / 'RetroBoxDB.Cartridge.en.md'),
        'TECHNICAL-DESIGN.en': ('markdown', ROOT / 'RetroBoxDB.Cartridge.Technical-Design.en.md'),
        'storage-experiment': ('json', ROOT / 'assessment' / 'data' / 'cart-storage-experiment.json')}
CODE = ['cart_schema.sql', 'cart_headers.py', 'cart_engine.py', 'cart_nointro.py', 'build_cart_db.py', 'finalize_cart_db.py',
        'import_ra.py', 'ra_report.py', 'update_cart_db.py', 'import_game_names.py', 'game_names_schema.sql', 'export_nointro_parents.py']


def statements(sql):
    buf = ''
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            yield '\n'.join(l for l in buf.strip().splitlines() if not l.lstrip().startswith('--')).strip(); buf = ''


def main(full, catalog):
    full = pathlib.Path(full); catalog = pathlib.Path(catalog)
    c = sqlite3.connect(full); c.execute('PRAGMA foreign_keys=ON')
    platform = c.execute('SELECT code FROM platforms WHERE id=1').fetchone()[0]
    existing = {r[0] for r in c.execute('SELECT name FROM sqlite_master')}
    added = []
    with c:
        for st in statements((TOOLS / 'cart_schema.sql').read_text()):
            m = re.match(r'CREATE\s+(INDEX|VIEW|TRIGGER|TABLE)\s+(\w+)', st)
            if m and m[2] not in existing:
                if m[1] == 'TABLE': raise SystemExit(f'Table {m[2]} missing: rebuild instead of finalizing')
                c.execute(st); added.append(m[2])
        engine_text, engine_body = B.combined_engine()
        res = {'engine.py': ('python', engine_text), 'schema.sql': ('sql', B.cart_schema(platform)), 'tests_cart.py': ('python', (ROOT / 'tests' / 'test_cart.py').read_text())}
        for name in CODE: res[name] = ('sql' if name.endswith('.sql') else 'python', (TOOLS / name).read_text())
        for name, (kind, p) in DOCS.items():
            if p.exists(): res[name] = (kind, p.read_text())
        for name, (kind, content) in res.items(): B.put_resource(c, name, kind, content)
        c.execute("INSERT INTO events(action,details_json,created_at) VALUES ('finalize_cart_db',?,?)", (json.dumps({'added_schema_objects': added, 'resources': sorted(res)}), B.datetime_now()))
    c.execute('VACUUM'); c.close()
    reports = ROOT / 'reports'; reports.mkdir(exist_ok=True)
    rr = importlib.import_module('ra_report'); rr.main(str(full), str(reports / f'ra-{platform}'))
    c = sqlite3.connect(full)
    build = json.loads(c.execute("SELECT content FROM resources WHERE name='build-report'").fetchone()[0])
    with c:
        for suffix, kind in (('.json', 'json'), ('-games.csv', 'csv')):
            B.put_resource(c, f'ra-report{suffix}', kind, (reports / f'ra-{platform}{suffix}').read_text())
    c.close()
    (reports / f'{platform}-build-report.json').write_text(json.dumps(build, ensure_ascii=False, indent=2))
    work = full.parent / ('.build-' + platform); work.mkdir(exist_ok=True)
    cat_engine = work / 'catalog_engine.py'; cat_engine.write_text(engine_body + '\n\n' + (TOOLS / 'base' / 'catalog_wrapper.py').read_text())
    if catalog.exists():
        meta = sqlite3.connect(f'file:{catalog}?mode=ro', uri=True)
        ok = meta.execute("SELECT value FROM meta WHERE key='edition'").fetchone() == ('catalog-only',) and meta.execute("SELECT value FROM meta WHERE key='platform'").fetchone() == (platform,)
        meta.close()
        if not ok: raise SystemExit(f'{catalog} is not this platform\'s catalog; refusing to replace')
        catalog.unlink()
    rep = importlib.import_module('build_catalog').build(full, catalog, cat_engine)
    print(json.dumps({'platform': platform, 'added_schema_objects': added, 'catalog_bytes': rep['size_bytes'], 'catalog_integrity': rep['integrity_check'],
                      'catalog_fk_errors': len(rep['foreign_key_errors']), 'full_bytes': full.stat().st_size}, indent=2))


if __name__ == '__main__':
    main(*sys.argv[1:3])
