"""RetroAchievements coverage report for a storage-v4 RetroBoxDB (read-only).

python3 -B tools/ra_report.py FULL_OR_CATALOG.sqlite OUT_PREFIX
Writes OUT_PREFIX.json (summary), OUT_PREFIX-games.csv (one row per RA game with achievements, with the source
collections that hold its local ROMs) and OUT_PREFIX-collection-unknown.csv (files of RetroAchievements collections
whose RA hash is not in the latest snapshot) and OUT_PREFIX-missing.csv (RA games with achievements and no local ROM). Games are
classified as local (a local ROM's RA hash matches), dat_only (a DAT entry matches but no local ROM),
or unmatched (no DAT entry or local ROM has any of its hashes: usually hacks, translations or
dumps that No-Intro does not list).
"""
import collections, csv, json, pathlib, sqlite3, sys

# rcheevos hashing per RA console ID; matching is exact hash equality.
RULES = {7: 'MD5 of the ROM body without the 16-byte iNES/NES 2.0 header (headered and headerless dumps hash the same)',
         3: 'MD5 of the file after a 512-byte copier header when size % 8192 == 512, otherwise of the whole file'}


def main(db, prefix, siblings=None, shared_console=False):
    """siblings: {name: path} of databases holding another platform's ROMs (NES<->FDS, SNES<->Satellaview); an RA game
    whose hash matches a ROM there is 'local_other_platform'. shared_console: the RA console also covers another
    platform, so only games tied to this database (local ROM, DAT entry or DB Export file) are reported."""
    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True); c.row_factory = sqlite3.Row
    snap = c.execute('SELECT * FROM ra_snapshots ORDER BY id DESC LIMIT 1').fetchone()
    games = c.execute('SELECT * FROM ra_games WHERE snapshot_id=? AND num_achievements>0 ORDER BY ra_game_id', (snap['id'],)).fetchall()
    local = {}
    for r in c.execute('SELECT ra_game_id,group_concat(DISTINCT release_title) AS t,count(DISTINCT rom_id) AS n FROM v_rom_ra_matches GROUP BY ra_game_id'):
        local[r['ra_game_id']] = (r['n'], r['t'])
    dat = {}
    for r in c.execute('SELECT ra_game_id,group_concat(DISTINCT game_name) AS t,count(DISTINCT dat_rom_id) AS n FROM v_dat_ra_matches GROUP BY ra_game_id'):
        dat[r['ra_game_id']] = (r['n'], r['t'])
    nidb = {}
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='v_nointro_ra_matches'").fetchone():
        for r in c.execute('SELECT ra_game_id,group_concat(DISTINCT nointro_title) AS t,count(DISTINCT file_id) AS n FROM v_nointro_ra_matches WHERE NOT in_dat GROUP BY ra_game_id'):
            nidb[r['ra_game_id']] = (r['n'], r['t'])
    has_coll = c.execute("SELECT 1 FROM sqlite_master WHERE name='v_collection_files'").fetchone() is not None
    sources = {}
    if has_coll:  # source collections holding a local ROM of each RA game
        for r in c.execute('''SELECT m.ra_game_id,group_concat(DISTINCT cf.kind) AS kinds FROM v_rom_ra_matches m JOIN roms ro ON ro.id=m.rom_id
                              JOIN v_collection_files cf ON cf.object_id=ro.object_id GROUP BY m.ra_game_id'''):
            sources[r['ra_game_id']] = ','.join(sorted(r['kinds'].split(',')))
    sib = {n: sqlite3.connect(f'file:{pth}?mode=ro', uri=True) for n, pth in (siblings or {}).items() if pathlib.Path(pth).exists()}
    game_hashes = collections.defaultdict(list)
    for h, g in c.execute('SELECT md5,ra_game_id FROM ra_hashes WHERE snapshot_id=?', (snap['id'],)): game_hashes[g].append(h.lower())
    rows = []; summary = {}
    for g in games:
        gid = g['ra_game_id']; hashes = c.execute('SELECT count(*) FROM ra_hashes WHERE snapshot_id=? AND ra_game_id=?', (snap['id'], gid)).fetchone()[0]
        status = 'local' if gid in local else 'dat_only' if gid in dat else 'nointro_db_only' if gid in nidb else 'unmatched'
        other = [n for n, sc in sib.items() if status != 'local' and sc.execute(f"SELECT 1 FROM rom_ra_hashes WHERE ra_md5 IN ({','.join('?' * len(game_hashes[gid]))}) LIMIT 1", game_hashes[gid]).fetchone()] if game_hashes.get(gid) else []
        if other and status in ('unmatched', 'dat_only', 'nointro_db_only'): status = 'local_other_platform'
        if shared_console and status in ('unmatched', 'local_other_platform'): continue
        summary.setdefault(g['category'], {}).setdefault(status, 0); summary[g['category']][status] += 1
        rows.append({'ra_game_id': gid, 'title': g['title'], 'category': g['category'], 'achievements': g['num_achievements'], 'ra_hashes': hashes,
                     'status': status, 'local_roms': local.get(gid, (0, ''))[0], 'local_releases': local.get(gid, (0, ''))[1] or '',
                     'dat_entries': dat.get(gid, (0, ''))[0], 'dat_games': dat.get(gid, (0, ''))[1] or '',
                     'nointro_db_files': nidb.get(gid, (0, ''))[0], 'nointro_db_titles': nidb.get(gid, (0, ''))[1] or '',
                     'local_sources': sources.get(gid, ''), 'other_platform_db': ','.join(other)})
    totals = {s: sum(1 for r in rows if r['status'] == s) for s in ('local', 'local_other_platform', 'dat_only', 'nointro_db_only', 'unmatched')}
    out = {'snapshot_id': snap['id'], 'console_id': snap['console_id'], 'fetched_at': snap['fetched_at'],
           'ra_games_with_achievements': len(rows), 'status_totals': totals, 'by_category': summary, 'sibling_databases': sorted(sib), 'shared_console_scope': bool(shared_console),
           'local_roms_with_achievements': c.execute('SELECT count(DISTINCT rom_id) FROM v_rom_ra_matches WHERE has_achievements').fetchone()[0],
           'rule': 'RA hash = ' + RULES.get(snap['console_id'], 'MD5 of the complete file') + '; exact hash equality only'}
    if has_coll:
        out['local_games_by_source'] = {k: sum(1 for r in rows if r['local_sources'] == k) for k in sorted({r['local_sources'] for r in rows if r['local_sources']})}
        coll = {}
        for r in c.execute('SELECT collection,status,count(*) AS n,sum(num_achievements>0) AS ach FROM v_ra_collection GROUP BY 1,2'):
            coll.setdefault(r['collection'], {})[r['status']] = r['n']
        out['retroachievements_collections'] = coll
        unknown = [dict(r) for r in c.execute("SELECT collection,zip_name,original_name,ra_md5 FROM v_ra_collection WHERE status='ra_hash_unknown' ORDER BY 1,2,3")]
        with open(prefix + '-collection-unknown.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['collection', 'zip_name', 'original_name', 'ra_md5']); w.writeheader(); w.writerows(unknown)
        out['collection_files_with_unknown_ra_hash'] = len(unknown)
    missing = [r for r in rows if r['status'] not in ('local', 'local_other_platform')]
    with open(prefix + '-missing.csv', 'w', newline='', encoding='utf-8') as f:  # gaps: RA games with achievements and no local ROM
        w = csv.DictWriter(f, fieldnames=['ra_game_id', 'title', 'category', 'achievements', 'status', 'dat_games', 'nointro_db_titles']); w.writeheader()
        w.writerows({k: r[k] for k in w.fieldnames} for r in sorted(missing, key=lambda r: (r['status'], r['category'] or '', r['title'])))
    out['missing_by_category'] = {}
    for r in missing: out['missing_by_category'][r['category'] or ''] = out['missing_by_category'].get(r['category'] or '', 0) + 1
    with open(prefix + '-games.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(prefix + '.json', 'w', encoding='utf-8') as f: json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2)); return out


if __name__ == '__main__':
    main(*sys.argv[1:3])
