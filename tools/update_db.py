"""Incremental update of a populated storage-v4 RetroBoxDB.

python3 -B tools/update_db.py FULL.sqlite [--dat P ...] [--nointro DB.zip DUMPLOG.zip] [--roms PATH ...]
        [--ra] [--names CSV] [--discover] [--no-compact] [--audit] [--catalog CATALOG.sqlite]

--discover  scan ~/Sync/Datfiles, /mnt/MyShare/No-Intro and /mnt/MyShare/RetroAchievements for this platform's
            DATs, DB/Dumplog pairs and ROM ZIPs that are not in the database yet (by content hash and path).
Every ROM folder is registered in source_collections; ROMs outside every DAT get the family of the stored ROMs they
share the most blocks with (hacks, translations), else a title family.
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
RA_ROOT = pathlib.Path('/mnt/MyShare/RetroAchievements')
# RetroAchievements-curated ROM sets (hashes as RA lists them; includes hacks, translations and homebrew outside No-Intro).
RA_FOLDERS = {'nes': 'RA - Nintendo Entertainment System', 'snes': 'RA - Super Nintendo Entertainment System', 'megadrive': 'RA - Sega Genesis',
              'gb': 'RA - Nintendo Game Boy', 'gbc': 'RA - Nintendo Game Boy Color', 'gba': 'RA - Nintendo Game Boy Advance',
              'fds': 'RA - Nintendo Entertainment System'}  # the RA NES set also holds the FDS disk images
# Files of another platform found in a mixed folder are skipped and listed in the report: Famicom Disk System images
# belong to the FDS database, not NES; Satellaview (BS-X) .bs files are their own platform, not SNES.
OTHER_PLATFORM_EXT = {'nes': {'.fds', '.qd'}, 'fds': {'.nes', '.unf', '.unif', '.nsf'}, 'snes': {'.bs'}}


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def ensure_schema(db):
    """Bring the database up to tools/schema_v4.sql (see finalize_db.sync_schema)."""
    added, replaced = importlib.import_module('finalize_db').sync_schema(db.c)
    return {'added': added, 'replaced': replaced}


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
        hit = index.get((r['bcrc'], r['bsize'])) or index.get((r['crc32'], r['size'])) or shared_block_family(db, r['pid'])
        key, basis = hit if hit else (eng.base_title(r['name'] or str(r['pid'])), 'title')
        db.set_family(r['pid'], key, basis); n[basis] += 1
    return dict(n)


def shared_block_family(db, oid, max_refs=32, min_share=0.1):
    """Family of the stored objects that share the most blocks with `oid` (hacks, translations and revisions not in any
    DAT keep most banks of their original). Blocks referenced by more than `max_refs` objects (padding, fill) are ignored.
    Returns (family key, 'shared_blocks') when at least `min_share` of the object's blocks are shared, else None."""
    total = db.c.execute('SELECT count(DISTINCT chunk_id) FROM object_chunks WHERE object_id=?', (oid,)).fetchone()[0]
    if not total: return None
    row = db.c.execute('''SELECT f.family_key,count(DISTINCT oc.chunk_id) AS n FROM object_chunks oc
        JOIN object_chunks o2 ON o2.chunk_id=oc.chunk_id AND o2.object_id!=oc.object_id JOIN object_families f ON f.object_id=o2.object_id
        WHERE oc.object_id=? AND (SELECT count(DISTINCT object_id) FROM object_chunks x WHERE x.chunk_id=oc.chunk_id)<=?
        GROUP BY f.family_key ORDER BY n DESC,f.family_key LIMIT 1''', (oid, max_refs)).fetchone()
    return (row['family_key'], 'shared_blocks') if row and row['n'] >= max(1, min_share * total) else None


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


def register_collections(db, paths=()):
    """Record every folder ROM ZIPs come from as a source collection (No-Intro set, RetroAchievements set, other)."""
    roots = {str(pathlib.Path(r[0]).parent) for r in db.c.execute("""SELECT DISTINCT a.source_path FROM files a WHERE a.kind='archive' AND a.parent_file_id IS NULL
             AND a.source_path IS NOT NULL AND EXISTS(SELECT 1 FROM files m WHERE m.parent_file_id=a.id AND m.kind='rom')""")}
    roots |= {str(p.resolve()) for p in paths if p.is_dir()}
    n = 0
    for root in sorted(roots):
        kind = 'nointro' if root.startswith(str(B.NOINTRO)) else 'retroachievements' if root.startswith(str(RA_ROOT)) else 'other'
        n += db.c.execute('INSERT OR IGNORE INTO source_collections(kind,name,root_path,registered_at) VALUES (?,?,?,?)',
                          (kind, pathlib.Path(root).name, root, B.datetime_now())).rowcount
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
        for pattern in B.dat_globs(cfg): args.dat += B.latest(B.DATFILES.glob(pattern))
        dbx = B.by_stamp(B.DATFILES.glob(cfg['nointro'] + ' (DB Export) (*).zip'))
        logs = B.by_stamp(B.DATFILES.glob(cfg['nointro'] + ' * (Dump Log) (*).zip') if plat == 'nes' else B.DATFILES.glob(cfg.get('dumplog_glob', cfg['nointro'] + ' (Dump Log) (*).zip')))
        unpaired = sorted(p.name for k, p in {**dbx, **logs}.items() if not (k in dbx and k in logs))
        if unpaired: report['unpaired_nointro_files'] = unpaired; log('DB Export/Dump Log without a same-timestamp partner (skipped):', unpaired)
        args.nointro += [[dbx[k], logs[k]] for k in sorted(set(dbx) & set(logs))]
        args.roms += sorted(p for p in B.NOINTRO.iterdir() if p.is_dir() and (p.name == cfg['nointro'] or p.name.startswith(cfg['nointro'] + ' (')))
        if (RA_ROOT / RA_FOLDERS[plat]).is_dir(): args.roms.append(RA_ROOT / RA_FOLDERS[plat])

    # DATs
    # Each DAT format (NES headered/headerless, FDS/QD, or the single Parent-Clone DAT) is diffed against its own previous
    # newest version; the primary format extends games/releases, other formats join releases by name (B.link_format).
    def newest_by_format():
        out = {}
        for r in db.c.execute('SELECT id,name FROM dat_sets ORDER BY version,id'): out[B.dat_format(cfg, r['name'])] = r['id']
        return out
    before = {r[0] for r in db.c.execute('SELECT id FROM dat_sets')}; prev = newest_by_format()
    with db.c:
        for p in B.latest(args.dat): db.import_dat_path(p)
    new_sets = [r[0] for r in db.c.execute('SELECT id FROM dat_sets ORDER BY version,id') if r[0] not in before]
    report['new_dat_sets'] = new_sets
    with db.c:
        for ds in new_sets: report.setdefault('scan_new', {})[ds] = db.scan(ds)
        now = newest_by_format()
        for fmt in sorted(now):
            new, old = now[fmt], prev.get(fmt)
            if new == old: continue
            if old is not None: report.setdefault('dat_diff', {})[f'{old}->{new}'] = eng.dat_diff(db, old, new)
            if fmt == 0 and old is not None: report.setdefault('catalog', {})[new] = extend_catalog(db, new, old)
            elif fmt != 0 and 0 in now: report.setdefault('catalog', {})[new] = B.link_format(db, new, [old] if old else [], now[0])
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
    index = db.family_index(); added = 0; skipped = 0; errors = []; other_platform = []
    paths = []
    for p in args.roms: paths += sorted(p.rglob('*.zip')) if p.is_dir() else [p]
    for i, p in enumerate(paths):
        if zip_unchanged(db, p): skipped += 1; continue
        with zipfile.ZipFile(p) as z: infos = [x for x in z.infolist() if not x.is_dir()]
        foreign = sorted({pathlib.PurePosixPath(x.filename).suffix.lower() for x in infos} & OTHER_PLATFORM_EXT.get(plat, set()))
        if foreign: other_platform.append({'path': str(p), 'extensions': foreign}); continue
        raw = p.read_bytes(); keys = [index.get((f'{x.CRC:08x}', x.file_size)) for x in infos]
        fam = next((k for k in keys if k), None)  # otherwise assigned after import (shared blocks, then title)
        with db.c:
            db.c.execute('SAVEPOINT onefile')
            try:
                if db.adapter: db.import_zip_bytes(p, raw, None, None, fam)
                else:  # NES path: No-Intro folders declare headered/headerless; other collections are detected per file
                    mode = 'headerless' if '(Headerless)' in p.parent.name else 'headered' if p.parent.name.startswith(cfg['nointro']) else 'auto'
                    db.import_rom_path(p, mode)
                added += 1
            except Exception as e: db.c.execute('ROLLBACK TO onefile'); errors.append({'path': str(p), 'error': repr(e)})
            finally: db.c.execute('RELEASE onefile')
        if added and added % 100 == 0: log('zips added', added)
    sidecars = [q for p in args.roms if p.is_dir() for q in sorted(p.iterdir()) if q.is_file() and q.suffix.lower() != '.zip']
    with db.c: n_side = B.store_sidecars(db, sidecars)
    with db.c:
        report['families_assigned'] = backfill_families(db, eng); report['ra_hashes_added'] = backfill_ra_hashes(db)
        report['collections_registered'] = register_collections(db, args.roms)
    report['roms'] = {'zips_added': added, 'zips_already_stored': skipped, 'sidecar_files_checked': n_side, 'errors': errors,
                      'skipped_other_platform': other_platform}
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
