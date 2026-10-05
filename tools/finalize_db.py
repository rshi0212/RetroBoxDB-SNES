"""Post-build refresh for a storage-v4 RetroBoxDB: schema additions, resources, reports and Catalog.

python3 -B tools/finalize_db.py FULL.sqlite CATALOG.sqlite
- Adds schema_v4.sql objects missing from FULL (indexes/views only; tables must already exist).
- Re-embeds the current tools, tests and documentation as resources.
- Writes reports/<platform>-build-report.json, reports/ra-<platform>.json and reports/ra-<platform>-games.csv.
- Rebuilds CATALOG from FULL (an existing CATALOG produced by this tool is replaced).
Payload tables are never modified.
"""
import hashlib, importlib, json, pathlib, re, sqlite3, sys

TOOLS = pathlib.Path(__file__).resolve().parent; ROOT = TOOLS.parent
sys.path[:0] = [str(TOOLS), str(TOOLS / 'base')]
import build_db as B  # noqa: E402

DOCS = {'README.zh-CN': ('markdown', 'RetroBoxDB.Storage-v4.zh-CN.md'),
        'README.en': ('markdown', 'RetroBoxDB.Storage-v4.en.md'),
        'TECHNICAL-DESIGN.en': ('markdown', 'RetroBoxDB.Storage-v4.Technical-Design.en.md'),
        'storage-experiment-snes-md': ('json', 'assessment/data/storage-experiment-snes-md.json'),
        'storage-experiment-gb-gbc-gba': ('json', 'assessment/data/storage-experiment-gb-gbc-gba.json'),
        'storage-curves': ('json', 'assessment/data/storage-curves.json'),
        'audit-resolution': ('markdown', 'reports/audit-resolution-20261004.md')}
# NES keeps its own README, its v3 design as history, and its `schema.sql` resource (the v3 fixture schema its embedded
# test suite builds); the current storage design is the shared storage-v4 document.
NES_DOCS = {'README.en': ('markdown', 'README.md'), 'README.zh-CN': ('markdown', 'README.zh-CN.md'),
            'TECHNICAL-DESIGN.en': ('markdown', 'RetroBoxDB.Storage-v4.Technical-Design.en.md'),
            'TECHNICAL-DESIGN.v3.en': ('markdown', 'RetroBoxDB.NES.Technical-Design.en.md'),
            'STORAGE-V4.en': ('markdown', 'RetroBoxDB.Storage-v4.en.md'), 'STORAGE-V4.zh-CN': ('markdown', 'RetroBoxDB.Storage-v4.zh-CN.md'),
            'documentation-index': ('json', 'release/documentation-index.json'),
            'storage-experiment-nes': ('json', 'assessment/data/storage-experiment-nes.json')}
CODE = ['schema_v4.sql', 'rom_headers.py', 'engine_v4.py', 'nointro_db.py', 'build_db.py', 'finalize_db.py',
        'import_ra.py', 'ra_report.py', 'update_db.py', 'retune_db.py', 'migrate_v4.py', 'export_set.py', 'build_catalog_release.py', 'import_game_names.py', 'game_names_schema.sql', 'export_nointro_parents.py']
# Resource names used before the 2026-10-05 rename; the same code now lives under the names above.
OBSOLETE = ('cart_schema.sql', 'cart_headers.py', 'cart_engine.py', 'cart_nointro.py', 'build_cart_db.py', 'update_cart_db.py',
            'finalize_cart_db.py', 'tests_cart.py', 'storage-experiment')


def resource_files(platform):
    """Resource name -> (kind, path relative to the repository) for every file-backed resource; shared with the release manifest."""
    out = {name: ('sql' if name.endswith('.sql') else 'python', f'tools/{name}') for name in CODE}
    out['tests_v4.py'] = ('python', 'tests/test_v4.py')
    out.update(DOCS)
    if platform == 'nes':
        out.update(NES_DOCS)
        for k in ('README.zh-CN', 'README.en'): out[k] = NES_DOCS[k]
    out['ra-report.json'] = ('json', f'reports/ra-{platform}.json'); out['ra-report-games.csv'] = ('csv', f'reports/ra-{platform}-games.csv')
    return out


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
        for st in statements((TOOLS / 'schema_v4.sql').read_text()):
            m = re.match(r'CREATE\s+(INDEX|VIEW|TRIGGER|TABLE)\s+(\w+)', st)
            if m and m[2] not in existing:
                # New extension tables start empty; existing tables are never altered here.
                c.execute(st); added.append(m[2])
        engine_text, engine_body = B.combined_engine()
        res = {'engine.py': ('python', engine_text)}
        if platform != 'nes': res['schema.sql'] = ('sql', B.schema_v4(platform))
        for name, (kind, rel) in resource_files(platform).items():
            if name.startswith('ra-report'): continue  # written after the report below
            if (ROOT / rel).exists(): res[name] = (kind, (ROOT / rel).read_text())
        for name, (kind, content) in res.items(): B.put_resource(c, name, kind, content)
        for old in OBSOLETE: c.execute('DELETE FROM resources WHERE name=?', (old,))
        c.execute("INSERT INTO events(action,details_json,created_at) VALUES ('finalize_db',?,?)", (json.dumps({'added_schema_objects': added, 'resources': sorted(res)}), B.datetime_now()))
    pages, free = c.execute('PRAGMA page_count').fetchone()[0], c.execute('PRAGMA freelist_count').fetchone()[0]
    if free > max(64, pages // 100): c.execute('VACUUM')  # resource refreshes free few pages; skip rewriting a multi-GiB file for them
    c.close()
    reports = ROOT / 'reports'; reports.mkdir(exist_ok=True)
    rr = importlib.import_module('ra_report'); rr.main(str(full), str(reports / f'ra-{platform}'))
    c = sqlite3.connect(full)
    row = c.execute("SELECT content FROM resources WHERE name='build-report'").fetchone()
    if row: build = json.loads(row[0])
    else:  # NES: not built by build_db.py; report the v4 migration and later maintenance events instead
        build = {'platform': platform, 'events': [json.loads(r[0]) | {'action': r[1], 'at': r[2]} for r in c.execute(
            "SELECT details_json,action,created_at FROM events WHERE action IN ('migrate_v4','retune_solid','import_ra_snapshot','compact_solid','finalize_db') ORDER BY id")]}
    with c:
        for suffix, kind in (('.json', 'json'), ('-games.csv', 'csv')):
            B.put_resource(c, f'ra-report{suffix}', kind, (reports / f'ra-{platform}{suffix}').read_text())
    c.close()
    (reports / (f'{platform}-migration-report.json' if platform == 'nes' else f'{platform}-build-report.json')).write_text(json.dumps(build, ensure_ascii=False, indent=2))
    work = full.parent / ('.build-' + platform); work.mkdir(exist_ok=True)
    cat_engine = work / 'catalog_engine.py'; cat_engine.write_text(engine_body + '\n\n' + (TOOLS / 'base' / 'catalog_wrapper.py').read_text())
    if catalog.exists():
        meta = sqlite3.connect(f'file:{catalog}?mode=ro', uri=True)
        ok = meta.execute("SELECT value FROM meta WHERE key='edition'").fetchone() == ('catalog-only',) and meta.execute("SELECT code FROM platforms WHERE id=1").fetchone() == (platform,)
        meta.close()
        if not ok: raise SystemExit(f'{catalog} is not this platform\'s catalog; refusing to replace')
        catalog.unlink()
    rep = importlib.import_module('build_catalog').build(full, catalog, cat_engine)
    print(json.dumps({'platform': platform, 'added_schema_objects': added, 'catalog_bytes': rep['size_bytes'], 'catalog_integrity': rep['integrity_check'],
                      'catalog_fk_errors': len(rep['foreign_key_errors']), 'full_bytes': full.stat().st_size}, indent=2))


if __name__ == '__main__':
    main(*sys.argv[1:3])
