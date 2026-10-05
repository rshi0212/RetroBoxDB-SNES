"""Incremental update of a populated storage-v4 RetroBoxDB.

python3 -B tools/update_db.py FULL.sqlite [--dat P ...] [--nointro DB.zip DUMPLOG.zip] [--roms PATH ...]
        [--ra] [--names CSV] [--discover] [--no-compact] [--audit] [--catalog CATALOG.sqlite]

--discover  scan ~/Sync/Datfiles and /mnt/MyShare/No-Intro for this platform's DATs, DB/Dumplog
            pairs and ROM ZIPs that are not in the database yet (by content hash and path).
Every step is idempotent: a DAT, DB/Dumplog pair or ZIP already stored is skipped.

Order: schema additions -> DATs (scan, diff against the previous newest, extend releases) ->
No-Intro DB/Dumplog -> ROM ZIPs (ordinary blocks, family recorded) -> compact-solid (repack the
family's group when it has room, else new family-ordered groups) -> rescan, ROM/release links,
TorrentZip packages -> RetroAchievements -> names -> VACUUM [-> audit] [-> finalize + Catalog].
"""
import argparse, collections, hashlib, importlib, json, pathlib, sqlite3, sys, time, zipfile
import xml.etree.ElementTree as ET

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import build_db as B  # noqa: E402


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def ensure_schema(db):
    """Create schema_v4.sql objects added after this database was built (new tables are empty)."""
    import re
    fin = importlib.import_module('finalize_db')
    existing = {r[0] for r in db.c.execute('SELECT name FROM sqlite_master')}; added = []
    for st in fin.statements((TOOLS / 'schema_v4.sql').read_text()):
        m = re.match(r'CREATE\s+(INDEX|VIEW|TRIGGER|TABLE)\s+(\w+)', st)
        if m and m[2] not in existing: db.c.execute(st); added.append(m[2])
    return added


def backfill_families(db, eng):
    """Assign a family to every ROM payload object lacking one (DAT/DB metadata, else filename title).

    The payload object is the ROM object itself or, for NES header recipes, its body object; a body is matched by its
    own CRC/size (headerless DAT) and then by the headered file's CRC/size.
    """
    index = db.family_index(); n = collections.Counter()
    for r in db.c.execute('''SELECT coalesce(r.body_object_id,r.object_id) AS pid,o.crc32,o.size,b.crc32 AS bcrc,b.size AS bsize,
            (SELECT original_name FROM files f WHERE f.object_id=r.object_id AND f.kind='rom' ORDER BY f.id LIMIT 1) AS name
            FROM roms r JOIN objects o ON o.id=r.object_id JOIN objects b ON b.id=coalesce(r.body_object_id,r.object_id)
            WHERE b.storage_kind='chunks' AND NOT EXISTS(SELECT 1 FROM object_families f WHERE f.object_id=coalesce(r.body_object_id,r.object_id))''').fetchall():
        hit = index.get((r['bcrc'], r['bsize'])) or index.get((r['crc32'], r['size']))
        key, basis = hit if hit else (eng.base_title(r['name'] or str(r['pid'])), 'title')
        db.set_family(r['pid'], key, basis); n[basis] += 1
    return dict(n)


def backfill_ra_hashes(db):
    """RA hash for ROMs imported through the NES path: MD5 of the body (rcheevos ignores the 16-byte header)."""
    n = 0
    for r in db.c.execute('''SELECT r.id,r.object_id,r.body_object_id FROM roms r WHERE r.format!='auxiliary'
                             AND NOT EXISTS(SELECT 1 FROM rom_ra_hashes h WHERE h.rom_id=r.id)''').fetchall():
        body = r['body_object_id'] or r['object_id']
        md5 = db.c.execute('SELECT md5 FROM objects WHERE id=?', (body,)).fetchone()[0]
        method = 'md5 after the 16-byte NES header (rcheevos nes)' if body != r['object_id'] else 'md5 of complete file (rcheevos buffer)'
        db.c.execute('INSERT INTO rom_ra_hashes VALUES (?,?,?)', (r['id'], md5, method)); n += 1
    return n


def extend_catalog(db, new_ds, prev_ds):
    """Releases for a newer DAT: diff-linked entries join their existing release; added entries get new releases."""
    c = db.c; ver = c.execute('SELECT version FROM dat_sets WHERE id=?', (new_ds,)).fetchone()[0]
    rel_of_game = {r[0]: r[1] for r in c.execute('SELECT dat_game_id,release_id FROM release_dat_games')}
    games = {r['id']: dict(r) for r in c.execute('SELECT * FROM dat_games WHERE dat_set_id=? ORDER BY ordinal', (new_ds,))}
    by_name = {g['name']: g for g in games.values()}
    links = {}
    for r in c.execute('''SELECT n.dat_game_id AS new_game,o.dat_game_id AS old_game FROM dat_changes ch JOIN dat_roms n ON n.id=ch.new_dat_rom_id
                          JOIN dat_roms o ON o.id=ch.old_dat_rom_id JOIN dat_games og ON og.id=o.dat_game_id
                          WHERE og.dat_set_id=? AND ch.classification!='removed' ''', (prev_ds,)):
        if r['old_game'] in rel_of_game: links.setdefault(r['new_game'], rel_of_game[r['old_game']])
    stats = collections.Counter()
    for gid, g in games.items():
        if gid in rel_of_game: continue
        if gid in links:
            c.execute('INSERT OR IGNORE INTO release_dat_games VALUES (?,?)', (links[gid], gid)); rel_of_game[gid] = links[gid]; stats['linked'] += 1
    for gid, g in games.items():
        if gid in rel_of_game: continue
        root = g; seen = set()
        while root['cloneof'] in by_name and root['cloneof'] not in seen: seen.add(root['name']); root = by_name[root['cloneof']]
        game_id = None
        if root['id'] in rel_of_game: game_id = c.execute('SELECT game_id FROM releases WHERE id=?', (rel_of_game[root['id']],)).fetchone()[0]
        if game_id is None:
            game_id = db.insert('games', platform_id=1, title=root['name'], metadata_json=B.js({'catalog_source': 'No-Intro parent/clone, not independent scraped identification', 'dat_game_id': root['id'], 'added_by': 'update'}))
            stats['games_added'] += 1
        rel = [{'name': e.get('name'), 'region': e.get('region')} for e in ET.fromstring(g['raw_xml']).findall('release')]
        rid = db.insert('releases', game_id=game_id, title=g['name'], metadata_json=B.js({'dat_game_id': gid, 'source': f'No-Intro DAT {ver}; release fields unguessed', 'dat_release_elements': rel, 'added_by': 'update'}))
        c.execute('INSERT INTO release_dat_games VALUES (?,?)', (rid, gid)); rel_of_game[gid] = rid; stats['releases_added'] += 1
    return dict(stats)


def link_roms(db):
    before = db.c.execute('SELECT count(*) FROM rom_releases').fetchone()[0]
    db.c.execute("""INSERT OR IGNORE INTO rom_releases(rom_id,release_id,source_id,notes) SELECT DISTINCT v.rom_id,rdg.release_id,NULL,'Verified matching bytes to linked DAT entry; no inferred PCB identity'
        FROM validations v JOIN dat_roms dr ON dr.id=v.dat_rom_id JOIN release_dat_games rdg ON rdg.dat_game_id=dr.dat_game_id WHERE v.status='match'""")
    return db.c.execute('SELECT count(*) FROM rom_releases').fetchone()[0] - before


def zip_unchanged(db, path):
    """True when this path is already stored with the same ZIP size and the same member names and CRC32 values.

    Only the ZIP central directory is read; a changed archive (different size, names or member CRCs) is re-imported.
    """
    row = db.c.execute("SELECT f.id,o.size FROM files f JOIN objects o ON o.id=f.object_id WHERE f.kind='archive' AND f.source_path=? AND f.parent_file_id IS NULL ORDER BY f.id DESC LIMIT 1", (str(path),)).fetchone()
    if row is None or row['size'] != path.stat().st_size: return False
    stored = sorted((r['member_path'] or r['original_name'], json.loads(r['metadata_json']).get('zip_crc')) for r in db.c.execute('SELECT original_name,member_path,metadata_json FROM files WHERE parent_file_id=?', (row['id'],)))
    with zipfile.ZipFile(path) as z:
        current = sorted((i.filename, f'{i.CRC:08x}') for i in z.infolist() if not i.is_dir())
    return stored == current


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('db', type=pathlib.Path); ap.add_argument('--dat', type=pathlib.Path, nargs='*', default=[])
    ap.add_argument('--nointro', type=pathlib.Path, nargs=2, action='append', default=[]); ap.add_argument('--roms', type=pathlib.Path, nargs='*', default=[])
    ap.add_argument('--ra', action='store_true'); ap.add_argument('--names', type=pathlib.Path); ap.add_argument('--discover', action='store_true')
    ap.add_argument('--no-compact', action='store_true'); ap.add_argument('--audit', action='store_true'); ap.add_argument('--catalog', type=pathlib.Path)
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args(); t0 = time.time()
    work = args.db.resolve().parent / '.build-update'; work.mkdir(exist_ok=True)
    text, _ = B.combined_engine(); (work / 'engine.py').write_text(text); sys.path.insert(0, str(work))
    eng = importlib.import_module('engine'); db = eng.DB(args.db)
    plat = db.platform; cfg = B.PLATFORMS[plat]; report = {'platform': plat, 'started_at': B.datetime_now()}
    with db.c:
        report['schema_added'] = ensure_schema(db)
        report['families_backfilled'] = backfill_families(db, eng)
    if args.discover:
        for pattern in cfg.get('dat_globs', (cfg['nointro'] + ' (Parent-Clone) (*).zip',)): args.dat += B.latest(B.DATFILES.glob(pattern))
        dbx = B.by_stamp(B.DATFILES.glob(cfg['nointro'] + ' (DB Export) (*).zip'))
        logs = B.by_stamp(B.DATFILES.glob(cfg['nointro'] + ' * (Dump Log) (*).zip') if plat == 'nes' else B.DATFILES.glob(cfg['nointro'] + ' (Dump Log) (*).zip'))
        unpaired = sorted(p.name for k, p in {**dbx, **logs}.items() if not (k in dbx and k in logs))
        if unpaired: report['unpaired_nointro_files'] = unpaired; log('DB Export/Dump Log without a same-timestamp partner (skipped):', unpaired)
        args.nointro += [[dbx[k], logs[k]] for k in sorted(set(dbx) & set(logs))]
        args.roms += sorted(p for p in B.NOINTRO.iterdir() if p.is_dir() and (p.name == cfg['nointro'] or p.name.startswith(cfg['nointro'] + ' (')))

    # DATs
    before = {r[0] for r in db.c.execute('SELECT id FROM dat_sets')}
    newest_before = db.c.execute('SELECT id FROM dat_sets ORDER BY version DESC,id DESC LIMIT 1').fetchone()
    with db.c:
        for p in B.latest(args.dat): db.import_dat_path(p)
    new_sets = [r[0] for r in db.c.execute('SELECT id FROM dat_sets ORDER BY version,id') if r[0] not in before]
    report['new_dat_sets'] = new_sets
    with db.c:
        for ds in new_sets: report.setdefault('scan_new', {})[ds] = db.scan(ds)
        newest = db.c.execute('SELECT id FROM dat_sets ORDER BY version DESC,id DESC LIMIT 1').fetchone()[0]
        if newest_before and newest != newest_before[0]:
            report['dat_diff'] = eng.dat_diff(db, newest_before[0], newest)
            report['catalog'] = extend_catalog(db, newest, newest_before[0])
    log('DATs', json.dumps({k: report.get(k) for k in ('new_dat_sets', 'dat_diff', 'catalog')}))

    # No-Intro DB Export + Dumplog snapshots
    # NES DB Exports carry 16-byte headers and headered/headerless pairs: use the NES importer for them.
    if plat == 'nes': sys.path.insert(0, str(TOOLS / 'base')); sys.modules['engine'] = eng; nointro = importlib.import_module('nointro')
    else: nointro = importlib.import_module('nointro_db')
    for dbp, logp in args.nointro:
        with db.c: r = nointro.import_snapshot(db, dbp, logp)
        r.pop('checksums', None); report.setdefault('nointro', []).append(r)
    if args.nointro: log('nointro', json.dumps(report['nointro'])[:600])

    # ROM ZIPs: ordinary blocks first (safe, immediate), family recorded for compaction.
    index = db.family_index(); added = 0; skipped = 0; errors = []
    paths = []
    for p in args.roms: paths += sorted(p.rglob('*.zip')) if p.is_dir() else [p]
    for i, p in enumerate(paths):
        if zip_unchanged(db, p): skipped += 1; continue
        raw = p.read_bytes()
        with zipfile.ZipFile(p) as z: keys = [index.get((f'{x.CRC:08x}', x.file_size)) for x in z.infolist() if not x.is_dir()]
        fam = next((k for k in keys if k), None) or (eng.base_title(p.stem), 'title')
        with db.c:
            db.c.execute('SAVEPOINT onefile')
            try:
                if db.adapter: db.import_zip_bytes(p, raw, None, None, fam)
                else: db.import_rom_path(p, 'headerless' if '(Headerless)' in p.parent.name else 'headered')  # NES path
                added += 1
            except Exception as e: db.c.execute('ROLLBACK TO onefile'); errors.append({'path': str(p), 'error': repr(e)})
            finally: db.c.execute('RELEASE onefile')
        if added and added % 100 == 0: log('zips added', added)
    sidecars = [q for p in args.roms if p.is_dir() for q in sorted(p.iterdir()) if q.is_file() and q.suffix.lower() != '.zip']
    with db.c: n_side = B.store_sidecars(db, sidecars)
    with db.c:
        report['families_assigned'] = backfill_families(db, eng); report['ra_hashes_added'] = backfill_ra_hashes(db)
    report['roms'] = {'zips_added': added, 'zips_already_stored': skipped, 'sidecar_files_checked': n_side, 'errors': errors}
    log('roms', json.dumps(report['roms'])[:600])
    if not args.no_compact:
        with db.c: report['compact_solid'] = db.compact_solid(args.workers)
        log('compact_solid', json.dumps(report['compact_solid']))

    with db.c:
        sets = [r[0] for r in db.c.execute('SELECT id FROM dat_sets ORDER BY id')]
        if added or new_sets: report['scan'] = {ds: db.scan(ds) for ds in sets}
        report['rom_release_links_added'] = link_roms(db)
    report['packages'] = B.build_packages(db, sets) if (added or new_sets) else 'unchanged'
    if args.ra:
        ra = importlib.import_module('import_ra')
        with db.c: report['retroachievements'] = ra.import_snapshot(db.c, plat, ra.fetch(ra.CONSOLES[plat]), B.datetime_now())
    if args.names or new_sets:
        names = importlib.import_module('import_game_names'); csvp = args.names or cfg['names']
        if csvp.exists():
            data = csvp.read_bytes(); names.read_csv(data); db.c.execute('BEGIN IMMEDIATE')
            try: report['game_names'] = names.import_names(db.c, data, csvp.name, plat); db.c.commit()
            except BaseException: db.c.rollback(); raise
    report['finished_at'] = B.datetime_now(); report['seconds'] = round(time.time() - t0)
    with db.c: db.event('update_db', **{k: v for k, v in report.items() if k not in ('game_names',)})
    db.c.execute('VACUUM')
    if args.audit:
        a = db.audit(archives=True); report['audit'] = {k: v for k, v in a.items() if k != 'errors'}; report['audit']['errors'] = a['errors'][:20]
    db.c.close()
    out = work / f'update-report-{plat}-{time.strftime("%Y%m%d-%H%M%S")}.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if args.catalog: importlib.import_module('finalize_db').main(str(args.db), str(args.catalog))
    summary = {k: report[k] for k in report if k not in ('game_names', 'scan', 'nointro')}
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str)); print('full report:', out)


if __name__ == '__main__':
    main()
