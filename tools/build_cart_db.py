"""Build a populated RetroBoxDB (storage v4) for SNES or Mega Drive, plus its payload-free Catalog.

python3 -B tools/build_cart_db.py {snes|megadrive} OUT.sqlite [--catalog OUT.Catalog.sqlite]
        [--limit-families N] [--workers N] [--skip-audit]

Inputs (read-only): No-Intro Parent-Clone DATs (all versions found), DB Export + Dump Log,
ROM ZIPs under /mnt/MyShare/No-Intro, and the English/Chinese name CSV.
Never modifies inputs; refuses to replace an existing output database.
"""
import argparse, collections, concurrent.futures as cf, hashlib, importlib, io, json, os, pathlib, re, sqlite3, sys, time, zipfile, zlib

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
DATFILES = pathlib.Path('~/Sync/Datfiles').expanduser()
NOINTRO = pathlib.Path('/mnt/MyShare/No-Intro')
PLATFORMS = {
    'snes': dict(label='SNES', name='Super Nintendo Entertainment System / Super Famicom',
                 nointro='Nintendo - Super Nintendo Entertainment System', batocera='snes',
                 names=ROOT / 'data' / 'Nintendo - Super Nintendo Entertainment System.csv'),
    'megadrive': dict(label='MegaDrive', name='Sega Mega Drive / Genesis',
                      nointro='Sega - Mega Drive - Genesis', batocera='megadrive',
                      names=ROOT / 'data' / 'Sega - Mega Drive - Genesis.csv'),
}
SOURCE_DOCS = [
    ('No-Intro DAT-o-MATIC', 'https://datomatic.no-intro.org/', 'Parent-Clone DATs, DB Export and Dump Log snapshots as supplied locally; each snapshot is retained.'),
    ('SNES ROM header', 'https://snes.nesdev.org/wiki/ROM_header', 'Internal header declarations parsed descriptively.'),
    ('Mega Drive ROM header', 'https://plutiedev.com/rom-header', 'Internal header declarations parsed descriptively.'),
    ('TorrentZip specification', 'https://wiki.romvault.com/doku.php?id=torrentzip', 'Classic ZIP profile; no ZIP64 writer.'),
]


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def latest(paths):
    """Sort No-Intro artifacts by their (YYYYMMDD-HHMMSS) version stamp."""
    def stamp(p): m = re.search(r'\((\d{8}-\d{6})\)', p.name); return m[1] if m else ''
    return sorted(paths, key=stamp)


def combined_engine():
    base = (TOOLS / 'base' / 'engine.py').read_text()
    guard = "\nif __name__=='__main__': main(sys.argv[1],sys.argv[2:])\n"
    if not base.endswith(guard): raise ValueError('Unexpected base engine ending')
    body = base[:-len(guard)] + '\n\n' + (TOOLS / 'cart_headers.py').read_text() + '\n\n' + (TOOLS / 'cart_engine.py').read_text()
    return body + guard, body


def cart_schema(platform):
    s = (TOOLS / 'base' / 'schema.sql').read_text()
    reps = [
        ('PRAGMA user_version=3;', 'PRAGMA user_version=4;'),
        (" size INTEGER NOT NULL CHECK(size>0 AND size<=2097152),\n codec TEXT NOT NULL CHECK(codec='lzma2-4m'),",
         " size INTEGER NOT NULL CHECK(size>0 AND size<=33554432 AND (codec='lzma2-solid' OR size<=2097152)),\n codec TEXT NOT NULL CHECK(codec IN ('lzma2-4m','lzma2-solid')),"),
        (" sha1 TEXT NOT NULL CHECK(length(sha1)=40),sha256 TEXT NOT NULL CHECK(length(sha256)=64),\n bad INTEGER",
         " sha1 TEXT NOT NULL CHECK(length(sha1)=40),sha256 TEXT CHECK(sha256 IS NULL OR length(sha256)=64),\n bad INTEGER"),
        ("INSERT INTO frontend_platforms VALUES ('batocera','nes','nes','screenscraper',NULL);",
         f"INSERT INTO frontend_platforms VALUES ('batocera','{platform}','{PLATFORMS[platform]['batocera']}','screenscraper',NULL);"),
    ]
    for old, new in reps:
        if s.count(old) != 1: raise ValueError('Schema transform anchor not found: ' + old[:50])
        s = s.replace(old, new)
    return s + '\n' + (TOOLS / 'cart_schema.sql').read_text()


def create(path, platform, schema):
    if path.exists(): raise SystemExit(f'Refusing to replace existing {path}')
    c = sqlite3.connect(path)
    c.execute('PRAGMA page_size=16384'); c.execute('PRAGMA journal_mode=DELETE'); c.execute('PRAGMA synchronous=FULL')
    c.executescript(schema)
    stamp = datetime_now()
    with c:
        c.executemany('INSERT INTO meta VALUES (?,?)', [
            ('name', 'RetroBoxDB'), ('schema_version', '4'), ('created_at', stamp), ('platform', platform),
            ('scope', f"{PLATFORMS[platform]['name']}; no ROM or source archive deletions"),
            ('nes_block_size', '65536'), ('rom_block_size', '65536'),
            ('execution', 'Python standard-library engine stored in resources; SQLite alone does not execute Python'),
            ('archive_policy', 'All original archive checksums retained as historical identity; export re-packs and verifies separate canonical output checksums; no ZIP payloads retained'),
            ('journal_policy', 'DELETE + synchronous FULL; one persistent SQLite file'),
            ('storage', 'SHA256 64 KiB block dedup; family-ordered solid LZMA2 groups up to 32 MiB (32 MiB dictionary); export-only ZIP plans'),
            ('solid_group_max_bytes', str(32 << 20)), ('solid_group_dictionary_bytes', str(32 << 20)), ('solid_group_cache_bytes', str(96 << 20)),
            ('compression_group_max_bytes', '2097152'), ('compression_group_dictionary_bytes', '4194304'), ('compression_group_cache_bytes', '16777216'),
            ('frontend_extension_version', '1'), ('frontend_scraping_state', 'placeholders only; no fetched metadata, media or API credentials'),
        ])
        c.execute('INSERT INTO platforms(id,code,name) VALUES (1,?,?)', (platform, PLATFORMS[platform]['name']))
        c.execute('INSERT INTO archive_profiles VALUES (?,?,?,?,?)', json.loads((TOOLS / 'base' / 'seed.json').read_text()))
        for title, url, notes in SOURCE_DOCS: c.execute('INSERT INTO sources(title,url,retrieved_at,notes) VALUES (?,?,?,?)', (title, url, stamp, notes))
    c.close()


def datetime_now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def family_index(eng, platform, dat_paths, db_export):
    """Map (crc32,size) -> family key. Order: newest DAT parent/clone, DB Export parent archive, older DATs."""
    import xml.etree.ElementTree as ET
    index = {}
    for p in reversed(dat_paths):
        with zipfile.ZipFile(p) as z:
            root = ET.fromstring(z.read([n for n in z.namelist() if n.lower().endswith(('.dat', '.xml'))][0]))
        parent = {g.get('name'): g.get('cloneof') for g in root.findall('game')}
        def top(n):
            seen = set()
            while parent.get(n) and parent[n] in parent and n not in seen: seen.add(n); n = parent[n]
            return n
        for g in root.findall('game'):
            for r in g.findall('rom'):
                index.setdefault((r.get('crc').lower(), int(r.get('size'))), top(g.get('name')))
        if p == dat_paths[-1] and db_export:
            nointro = importlib.import_module('cart_nointro')
            _, raw, _ = nointro.read_input(db_export); parsed = nointro.parse_export(raw)
            arch = parsed['archives']
            for s in parsed['sources']:
                a = arch[s['archive']]['attrs']; cl = a.get('clone', 'P')
                key = arch[cl]['title'] if cl not in ('P', '') and cl in arch else arch[s['archive']]['title']
                for fid in s['files']:
                    f = parsed['files'][fid]; index.setdefault((f['crc32'].lower(), int(f['size'])), key)
    return index


def base_title(name): return '~' + re.sub(r'\s*\(.*$', '', name).strip().casefold()  # same rule as engine.base_title


def import_roms(db, eng, platform, index, workers, limit_families=None):
    dirs = sorted(p for p in NOINTRO.iterdir() if p.is_dir() and (p.name == PLATFORMS[platform]['nointro'] or p.name.startswith(PLATFORMS[platform]['nointro'] + ' (')))
    families = collections.defaultdict(list); stats = collections.Counter()
    for d in dirs:
        for p in sorted(d.iterdir()):
            if p.suffix.lower() != '.zip': stats['non_zip_skipped'] += 1; continue
            with zipfile.ZipFile(p) as z:
                keys = [index.get((f'{i.CRC:08x}', i.file_size)) for i in z.infolist() if not i.is_dir()]
            key = next((k for k in keys if k), None)
            stats['family_from_dat_or_db' if key else 'family_from_title'] += 1
            families[key or base_title(p.stem)].append(p)
    keys = sorted(families, key=lambda k: (k.lstrip('~').casefold(), k))
    if limit_families: keys = keys[:limit_families]
    log('ROM directories', [d.name for d in dirs], 'families', len(keys), dict(stats))
    errors = []; pending_shas = set(); counters = collections.Counter()
    pool = cf.ProcessPoolExecutor(max_workers=workers)
    limit = eng.SOLID_LIMIT

    # A batch is a run of whole families whose new blocks fill <=1 group (large families: several groups).
    def batches():
        cur = []; cur_blocks = []; size = 0
        for key in keys:
            fam = []
            for p in families[key]:
                raw = p.read_bytes(); members = {}
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    for i, info in enumerate(z.infolist()):
                        if not info.is_dir(): members[i] = z.read(info)
                    names = [(info.filename, members.get(i)) for i, info in enumerate(z.infolist())]
                fam.append((p, raw, members, names))
            new = []
            for p, raw, members, names in fam:
                for data in members.values(): new += db.missing_blocks(data, pending_shas)
            fsize = sum(len(b) for _, b in new)
            if cur and size + fsize > limit:
                yield cur, cur_blocks; cur = []; cur_blocks = []; size = 0
            cur.append((key, fam)); cur_blocks.append((key, new)); size += fsize
        if cur: yield cur, cur_blocks

    def groups_of(cur_blocks):
        out = []; blocks = []; fams = []; size = 0
        for key, new in cur_blocks:
            if key not in fams: fams.append(key)
            for sha, b in new:
                if size + len(b) > limit and blocks:
                    out.append((blocks, fams)); blocks = []; fams = [key]; size = 0
                blocks.append((sha, b)); size += len(b)
        if blocks: out.append((blocks, fams))
        return out

    inflight = collections.deque(); start = time.time()

    def finish(item):
        fams, group_jobs, zip_jobs = item
        with db.c:
            for (blocks, gfams), fut in group_jobs:
                encoded, digest, edigest = fut.result()
                db.store_solid_group(encoded, digest, edigest, blocks, gfams); counters['groups'] += 1
                counters['raw_group_bytes'] += sum(len(b) for _, b in blocks); counters['stored_group_bytes'] += len(encoded)
                for sha, _ in blocks: pending_shas.discard(sha)
            for (key, p, raw, members), fut in zip_jobs:
                db.c.execute('SAVEPOINT onefile')
                try:
                    db.import_zip_bytes(p, raw, fut.result(), members, (key, 'title' if key.startswith('~') else 'dat')); counters['zips'] += 1
                except Exception as e:
                    db.c.execute('ROLLBACK TO onefile'); errors.append({'path': str(p), 'error': repr(e)}); db.event('import_error', path=str(p), error=repr(e))
                finally: db.c.execute('RELEASE onefile')
        db.clear_caches()

    for cur, cur_blocks in batches():
        group_jobs = [((blocks, gfams), pool.submit(eng.encode_solid, b''.join(b for _, b in blocks))) for blocks, gfams in groups_of(cur_blocks)]
        zip_jobs = []
        for key, fam in cur:
            for p, raw, members, names in fam:
                zip_jobs.append(((key, p, raw, members), pool.submit(eng.torrentzip_hashes, [(n, b'' if d is None else d) for n, d in names])))
        inflight.append(([k for k, _ in cur], group_jobs, zip_jobs))
        while len(inflight) > workers: finish(inflight.popleft())
        if counters['groups'] and counters['groups'] % 20 == 0:
            log('progress zips', counters['zips'], 'groups', counters['groups'], 'raw MiB', counters['raw_group_bytes'] >> 20, 'stored MiB', counters['stored_group_bytes'] >> 20, 'elapsed', round(time.time() - start))
    while inflight: finish(inflight.popleft())
    pool.shutdown()
    result = {'directories': [str(d) for d in dirs], 'families': len(keys), 'family_assignment': dict(stats), 'errors': errors, **counters, 'seconds': round(time.time() - start)}
    with db.c: db.event('initial_collection_import', **result)
    log('ROM import done', json.dumps({k: v for k, v in result.items() if k != 'errors'}), 'errors', len(errors))
    return result


def build_catalog_records(db, new_ds, old_sets):
    """Games/releases from the newest DAT's explicit parent/clone relations (as the NES catalog did)."""
    c = db.c
    new_ver = c.execute('SELECT version FROM dat_sets WHERE id=?', (new_ds,)).fetchone()[0]
    datgames = [dict(r) for r in c.execute('SELECT * FROM dat_games WHERE dat_set_id=? ORDER BY ordinal', (new_ds,))]
    by_name = {g['name']: g for g in datgames}; game_ids = {}; release_of = {}
    for g in datgames:
        root = g; visited = set()
        while root['cloneof'] in by_name and root['cloneof'] not in visited: visited.add(root['name']); root = by_name[root['cloneof']]
        if root['name'] not in game_ids:
            game_ids[root['name']] = db.insert('games', platform_id=1, title=root['name'], metadata_json=js({'catalog_source': 'No-Intro parent/clone, not independent scraped identification', 'dat_game_id': root['id']}))
        rel = [{'name': e.get('name'), 'region': e.get('region')} for e in __import__('xml.etree.ElementTree', fromlist=['x']).fromstring(g['raw_xml']).findall('release')]
        release_of[g['id']] = db.insert('releases', game_id=game_ids[root['name']], title=g['name'], metadata_json=js({'dat_game_id': g['id'], 'source': f'No-Intro DAT {new_ver}; release fields unguessed', 'dat_release_elements': rel}))
        db.insert('release_dat_games', release_id=release_of[g['id']], dat_game_id=g['id'])
    # Older DAT games join the release whose newer DAT entry is the same ROM (diff: unchanged/renamed/case_changed/checksum_changed).
    linked = 0
    for ds in old_sets:
        for r in c.execute('''SELECT DISTINCT og.id AS old_game,ng.id AS new_game FROM dat_changes ch JOIN dat_roms o ON o.id=ch.old_dat_rom_id
            JOIN dat_games og ON og.id=o.dat_game_id JOIN dat_roms n ON n.id=ch.new_dat_rom_id JOIN dat_games ng ON ng.id=n.dat_game_id
            WHERE og.dat_set_id=? AND ng.dat_set_id=? AND ch.classification!='removed' ''', (ds, new_ds)).fetchall():
            c.execute('INSERT OR IGNORE INTO release_dat_games VALUES (?,?)', (release_of[r['new_game']], r['old_game'])); linked += 1
    c.execute("""INSERT OR IGNORE INTO rom_releases(rom_id,release_id,source_id,notes) SELECT DISTINCT v.rom_id,rdg.release_id,NULL,'Verified matching bytes to linked DAT entry; no inferred PCB identity'
        FROM validations v JOIN dat_roms dr ON dr.id=v.dat_rom_id JOIN release_dat_games rdg ON rdg.dat_game_id=dr.dat_game_id WHERE v.status='match'""")
    return {'games': len(game_ids), 'releases': len(release_of), 'old_dat_games_linked': linked,
            'rom_release_links': c.execute('SELECT count(*) FROM rom_releases').fetchone()[0]}


def build_packages(db, dat_sets):
    c = db.c; counts = {}; errors = []
    for ds in dat_sets:
        rows = c.execute('''SELECT dg.id FROM dat_games dg WHERE dg.dat_set_id=? AND EXISTS(SELECT 1 FROM dat_roms dr WHERE dr.dat_game_id=dg.id)
            AND NOT EXISTS(SELECT 1 FROM dat_roms dr WHERE dr.dat_game_id=dg.id AND NOT EXISTS(SELECT 1 FROM validations v WHERE v.dat_rom_id=dr.id AND v.status='match'))
            ORDER BY (SELECT min(c2.group_id) FROM dat_roms dr JOIN validations v ON v.dat_rom_id=dr.id AND v.status='match'
                      JOIN object_chunks oc ON oc.object_id=v.checked_object_id JOIN chunks c2 ON c2.id=oc.chunk_id WHERE dr.dat_game_id=dg.id),dg.id''', (ds,)).fetchall()
        n = 0
        for i in range(0, len(rows), 200):
            with c:
                for r in rows[i:i + 200]:
                    c.execute('SAVEPOINT package')
                    try: db.package(r[0]); n += 1
                    except Exception as e:
                        c.execute('ROLLBACK TO package'); errors.append({'dat_game_id': r[0], 'error': repr(e)})
                    finally: c.execute('RELEASE package')
        counts[ds] = n; log('packages', ds, n, '/', len(rows))
    return {'packages_by_dat_set': counts, 'errors': errors}


def put_resource(c, name, kind, content):
    c.execute('INSERT INTO resources VALUES (?,?,?,?) ON CONFLICT(name) DO UPDATE SET kind=excluded.kind,content=excluded.content,sha256=excluded.sha256',
              (name, kind, content, hashlib.sha256(content.encode()).hexdigest()))


def js(x): return json.dumps(x, ensure_ascii=False, sort_keys=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('platform', choices=sorted(PLATFORMS)); ap.add_argument('out', type=pathlib.Path)
    ap.add_argument('--catalog', type=pathlib.Path); ap.add_argument('--limit-families', type=int)
    ap.add_argument('--workers', type=int, default=6); ap.add_argument('--skip-audit', action='store_true')
    ap.add_argument('--work', type=pathlib.Path, help='directory for the generated engine.py (default: next to OUT)')
    args = ap.parse_args(); t0 = time.time(); plat = args.platform; cfg = PLATFORMS[plat]
    work = (args.work or args.out.parent / ('.build-' + plat)).resolve(); work.mkdir(parents=True, exist_ok=True)
    engine_text, engine_body = combined_engine()
    (work / 'engine.py').write_text(engine_text)
    catalog_engine = work / 'catalog_engine.py'
    catalog_engine.write_text(engine_body + '\n\n' + (TOOLS / 'base' / 'catalog_wrapper.py').read_text())
    sys.path[:0] = [str(work), str(TOOLS)]
    eng = importlib.import_module('engine')
    for m in ('cart_nointro', 'import_game_names'): sys.modules.pop(m, None)
    schema = cart_schema(plat)
    create(args.out, plat, schema)
    db = eng.DB(args.out)
    report = {'platform': plat, 'started_at': datetime_now(), 'engine_version': eng.VERSION}

    dats = latest(DATFILES.glob(cfg['nointro'] + ' (Parent-Clone) (*).zip'))
    dbx = latest(DATFILES.glob(cfg['nointro'] + ' (DB Export) (*).zip'))
    dlog = latest(DATFILES.glob(cfg['nointro'] + ' (Dump Log) (*).zip'))
    log('DATs', [p.name for p in dats], 'DB', [p.name for p in dbx], 'Dumplog', [p.name for p in dlog])
    with db.c:
        dat_sets = [db.import_dat_path(p)[0] for p in dats]
    report['dat_sets'] = [dict(r) for r in db.c.execute('SELECT id,name,version FROM dat_sets ORDER BY id')]

    index = family_index(eng, plat, dats, dbx[-1] if dbx else None)
    report['rom_import'] = import_roms(db, eng, plat, index, args.workers, args.limit_families)

    with db.c:
        report['scan'] = {ds: db.scan(ds) for ds in dat_sets}
        report['dat_diff'] = {f'{a}->{dat_sets[-1]}': eng.dat_diff(db, a, dat_sets[-1]) for a in dat_sets[:-1]}
        report['catalog'] = build_catalog_records(db, dat_sets[-1], dat_sets[:-1])
    log('scan/diff/catalog', json.dumps({k: report[k] for k in ('scan', 'dat_diff', 'catalog')}))

    if dbx and dlog:
        nointro = importlib.import_module('cart_nointro')
        with db.c: report['nointro'] = nointro.import_snapshot(db, dbx[-1], dlog[-1], lambda s: log(s))
        report['nointro'].pop('checksums', None); log('nointro', json.dumps(report['nointro']))

    report['packages'] = build_packages(db, dat_sets)

    ra = importlib.import_module('import_ra')
    try:
        raw = ra.fetch(ra.CONSOLES[plat])
        with db.c: report['retroachievements'] = ra.import_snapshot(db.c, plat, raw, datetime_now())
        log('retroachievements', json.dumps(report['retroachievements'], ensure_ascii=False))
    except SystemExit as e:
        report['retroachievements'] = {'error': str(e)}; log('retroachievements FAILED', e)

    if cfg['names'].exists():
        names = importlib.import_module('import_game_names')
        data = cfg['names'].read_bytes(); names.read_csv(data)
        db.c.execute('BEGIN IMMEDIATE')
        try: report['game_names'] = names.import_names(db.c, data, cfg['names'].name, plat); db.c.commit()
        except BaseException: db.c.rollback(); raise
        log('names', json.dumps(report['game_names'], ensure_ascii=False)[:600])

    with db.c:
        db.c.execute("INSERT OR REPLACE INTO meta VALUES ('nointro_extension_version','1-cart')")
        res = {'engine.py': ('python', engine_text), 'schema.sql': ('sql', schema),
               'cart_schema.sql': ('sql', (TOOLS / 'cart_schema.sql').read_text()),
               'cart_headers.py': ('python', (TOOLS / 'cart_headers.py').read_text()),
               'cart_engine.py': ('python', (TOOLS / 'cart_engine.py').read_text()),
               'cart_nointro.py': ('python', (TOOLS / 'cart_nointro.py').read_text()),
               'import_ra.py': ('python', (TOOLS / 'import_ra.py').read_text()),
               'import_game_names.py': ('python', (TOOLS / 'import_game_names.py').read_text()),
               'game_names_schema.sql': ('sql', (TOOLS / 'game_names_schema.sql').read_text()),
               'build_cart_db.py': ('python', (TOOLS / 'build_cart_db.py').read_text()),
               'build_catalog.py': ('python', (TOOLS / 'base' / 'build_catalog.py').read_text()),
               'catalog_wrapper.py': ('python', (TOOLS / 'base' / 'catalog_wrapper.py').read_text()),
               'seed.json': ('json', (TOOLS / 'base' / 'seed.json').read_text())}
        for p in (ROOT / 'tests' / 'test_cart.py', ROOT / 'RetroBoxDB.Cartridge.Technical-Design.en.md', ROOT / 'RetroBoxDB.Cartridge.zh-CN.md'):
            if p.exists(): res[{'.py': 'tests_cart.py', '.md': 'TECHNICAL-DESIGN.en' if '.en.' in p.name else 'README.zh-CN'}[p.suffix]] = ('python' if p.suffix == '.py' else 'markdown', p.read_text())
        for name, (kind, content) in res.items(): put_resource(db.c, name, kind, content)
    db.c.execute('VACUUM')
    if not args.skip_audit:
        log('audit-all start'); audit = db.audit(archives=True)
        report['audit'] = {k: v for k, v in audit.items() if k != 'errors'}; report['audit']['errors'] = audit['errors'][:50]
        log('audit', json.dumps(report['audit'])[:800])
    report['stats'] = db.stats(); report['finished_at'] = datetime_now(); report['seconds'] = round(time.time() - t0)
    report['database_bytes'] = args.out.stat().st_size
    with db.c: put_resource(db.c, 'build-report', 'json', json.dumps(report, ensure_ascii=False, indent=2, default=str))
    db.c.close()
    (work / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if args.catalog:
        sys.path.insert(0, str(TOOLS / 'base')); bc = importlib.import_module('build_catalog')
        rep = bc.build(args.out, args.catalog, catalog_engine)
        log('catalog', args.catalog, rep['size_bytes'], rep['integrity_check'])
    log('DONE', args.out, args.out.stat().st_size, 'seconds', round(time.time() - t0))


if __name__ == '__main__':
    main()
