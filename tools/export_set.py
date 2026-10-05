"""Export a reproducible game set from a populated RetroBoxDB (any platform, storage v3 or v4). Read-only.

Selection dimensions combine freely:
  --dat latest|VERSION      DAT snapshot (NES also needs --dat-mode headered|headerless)
  --set all|parents|1g1r    every DAT game, parents only, or one game per parent/clone family
  --region-priority LIST    1G1R region order (default USA,World,Europe,Japan)
  --ra any|achievements|none   RetroAchievements filter (needs the database's RA snapshot)
  --ra-category LIST        keep only these RA categories (e.g. Official,Homebrew)
  --include / --exclude RE  regular expressions on DAT game names
  --container torrentzip|rom
  --layout flat|parent|ra-category|region
  --report-only             list the selection and missing members without writing files

Every written member is re-hashed against all checksums of its DAT entry; TorrentZip output is generated
with the engine's canonical encoder and compared with the registered archive plan when one exists.
OUT/export-manifest.json records the criteria, database identity and every file's checksums.
"""
import argparse, collections, datetime, hashlib, io, json, pathlib, re, sqlite3, sys, types, zipfile, zlib

REV = re.compile(r'\((?:Rev|v)\s*([0-9A-Za-z.]+)\)')


def load_engine(db_path, engine_file=None):
    if engine_file: text = pathlib.Path(engine_file).read_text()
    else:
        c = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        text = c.execute("SELECT content FROM resources WHERE name IN ('engine.full.py','engine.py') ORDER BY name='engine.full.py' DESC").fetchone()[0]; c.close()
    m = types.ModuleType('retroboxdb_engine'); m.__dict__['__name__'] = 'retroboxdb_engine'
    exec(compile(text, 'RetroBoxDB:engine.py', 'exec'), m.__dict__)
    return m


def hashes(b):
    return {'size': len(b), 'crc32': f'{zlib.crc32(b):08x}', 'md5': hashlib.md5(b).hexdigest(), 'sha1': hashlib.sha1(b).hexdigest(), 'sha256': hashlib.sha256(b).hexdigest()}


def tags(name): return re.findall(r'\(([^)]*)\)', name)


def regions(name):
    t = tags(name); return [r.strip() for r in t[0].split(',')] if t else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('db'); ap.add_argument('out', type=pathlib.Path)
    ap.add_argument('--dat', default='latest'); ap.add_argument('--dat-mode', choices=['headered', 'headerless', 'unspecified'])
    ap.add_argument('--set', choices=['all', 'parents', '1g1r'], default='all'); ap.add_argument('--region-priority', default='USA,World,Europe,Japan')
    ap.add_argument('--ra', choices=['any', 'achievements', 'none'], default='any'); ap.add_argument('--ra-category')
    ap.add_argument('--include'); ap.add_argument('--exclude')
    ap.add_argument('--container', choices=['torrentzip', 'rom'], default='torrentzip')
    ap.add_argument('--layout', choices=['flat', 'parent', 'ra-category', 'region'], default='flat')
    ap.add_argument('--report-only', action='store_true'); ap.add_argument('--engine-file')
    a = ap.parse_args()
    eng = load_engine(a.db, a.engine_file); db = eng.DB(a.db); c = db.c
    platform = c.execute('SELECT code FROM platforms WHERE id=1').fetchone()[0]
    sets = c.execute('SELECT id,version,mode,name FROM dat_sets ORDER BY version,id').fetchall()
    version = sets[-1]['version'] if a.dat == 'latest' else a.dat
    cand = [s for s in sets if s['version'] == version and (a.dat_mode is None or s['mode'] == a.dat_mode)]
    if len(cand) != 1: raise SystemExit(f'Choose one DAT set: {[(s["version"], s["mode"]) for s in sets if s["version"] == version]} (use --dat-mode)')
    ds = cand[0]
    games = [dict(g) for g in c.execute('SELECT id,name,cloneof FROM dat_games WHERE dat_set_id=? ORDER BY ordinal', (ds['id'],))]
    by_name = {g['name']: g for g in games}

    # RetroAchievements: a DAT game matches when one of its members' MD5 (or, for NES headered DATs, the
    # same-named headerless entry of the same version) is an RA hash of a game with achievements.
    ra_of = collections.defaultdict(dict)
    has_ra = c.execute("SELECT 1 FROM sqlite_master WHERE name='ra_snapshots'").fetchone() and c.execute('SELECT count(*) FROM ra_snapshots').fetchone()[0]
    if a.ra != 'any' or a.layout == 'ra-category' or a.ra_category:
        if not has_ra: raise SystemExit('This database has no RetroAchievements snapshot; import one with tools/import_ra.py')
        snap = c.execute('SELECT max(id) FROM ra_snapshots').fetchone()[0]
        ra = {r[0]: (r[1], r[2], r[3]) for r in c.execute('SELECT h.md5,g.ra_game_id,g.title,g.category FROM ra_hashes h JOIN ra_games g USING(snapshot_id,ra_game_id) WHERE h.snapshot_id=? AND g.num_achievements>0', (snap,))}
        md5s = collections.defaultdict(list)
        for r in c.execute('SELECT dg.name,dr.md5,dr.size FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id WHERE dg.dat_set_id=?', (ds['id'],)):
            md5s[r['name']].append(r['md5'])
        if platform == 'nes' and ds['mode'] == 'headered':
            for r in c.execute("SELECT dg.name,dr.md5 FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id JOIN dat_sets s ON s.id=dg.dat_set_id WHERE s.version=? AND s.mode='headerless'", (version,)):
                md5s[r['name']].append(r['md5'])
        for g in games:
            for m in md5s[g['name']]:
                if m and m in ra: ra_of[g['name']][ra[m][0]] = ra[m]

    def available(g):
        return all(c.execute("SELECT 1 FROM validations WHERE dat_rom_id=? AND status='match'", (r[0],)).fetchone() for r in c.execute('SELECT id FROM dat_roms WHERE dat_game_id=?', (g['id'],)))
    inc = re.compile(a.include) if a.include else None; exc = re.compile(a.exclude) if a.exclude else None
    cats = set(a.ra_category.split(',')) if a.ra_category else None

    def keep(g):
        if inc and not inc.search(g['name']): return False
        if exc and exc.search(g['name']): return False
        r = ra_of.get(g['name'], {})
        if a.ra == 'achievements' and not r: return False
        if a.ra == 'none' and r: return False
        if cats and not any(v[2] in cats for v in r.values()): return False
        return True
    pool = [g for g in games if keep(g)]
    if a.set == 'parents': pool = [g for g in pool if not g['cloneof']]
    elif a.set == '1g1r':
        prio = a.region_priority.split(',')
        def root(g):
            seen = set()
            while g['cloneof'] in by_name and g['name'] not in seen: seen.add(g['name']); g = by_name[g['cloneof']]
            return g['name']
        fam = collections.defaultdict(list)
        for g in pool: fam[root(g)].append(g)
        def score(g):
            reg = min((prio.index(r) for r in regions(g['name']) if r in prio), default=len(prio))
            rev = REV.search(g['name']); rv = rev.group(1) if rev else ''
            return (not available(g), a.ra != 'none' and not ra_of.get(g['name']), reg, -len(rv), [-ord(ch) for ch in rv], g['name'])
        pool = [min(v, key=score) for _, v in sorted(fam.items())]

    def folder(g):
        if a.layout == 'parent': return eng.safe_name(g['cloneof'] or g['name'])
        if a.layout == 'region': return eng.safe_name(regions(g['name'])[0] if regions(g['name']) else 'Unknown')
        if a.layout == 'ra-category':
            r = ra_of.get(g['name']); return eng.safe_name(sorted(v[2] for v in r.values())[0] if r else 'No achievements')
        return None
    report = {'database': pathlib.Path(a.db).name, 'platform': platform, 'dat': {'version': ds['version'], 'mode': ds['mode'], 'name': ds['name']},
              'criteria': {k: getattr(a, k) for k in ('set', 'region_priority', 'ra', 'ra_category', 'include', 'exclude', 'container', 'layout')},
              'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'selected': len(pool), 'exported': 0, 'missing': [], 'errors': [], 'files': []}
    if not a.report_only: a.out.mkdir(parents=True, exist_ok=True)
    selection = []
    for g in pool:
        members = []; missing = []
        for t in c.execute('SELECT * FROM dat_roms WHERE dat_game_id=? ORDER BY ordinal', (g['id'],)).fetchall():
            v = c.execute("SELECT checked_object_id FROM validations WHERE dat_rom_id=? AND status='match' ORDER BY CASE strength WHEN 'sha256' THEN 0 WHEN 'sha1' THEN 1 ELSE 2 END LIMIT 1", (t['id'],)).fetchone()
            if v is None: missing.append(t['name'])
            else: members.append((t, v[0]))
        if missing: report['missing'].append({'game': g['name'], 'members': missing}); continue
        selection.append((g, members))
    if a.report_only: selection = []
    # Export in storage order so each solid group is decoded once, front to back, instead of once per name-ordered jump.
    pos = db.storage_positions() if hasattr(db, 'storage_positions') else {}
    if hasattr(db, 'set_bulk_cache') and len(selection) > 1: db.set_bulk_cache()
    far = (float('inf'), 0)
    selection.sort(key=lambda gm: min((pos.get(oid, far) for _, oid in gm[1]), default=far))
    for g, members in selection:
        try:
            sub = folder(g); base = a.out / sub if sub else a.out; base.mkdir(parents=True, exist_ok=True)
            datas = []
            for t, oid in members:
                data = b''.join(db.stream(oid)); h = hashes(data)
                bad = [k for k in ('size', 'crc32', 'md5', 'sha1', 'sha256') if t[k] is not None and str(t[k]).lower() != str(h[k])]
                if bad: raise ValueError(f'{t["name"]}: differs from DAT in {bad}')
                datas.append((eng.safe_name(t['name']), data, h))
            if a.container == 'rom':
                for name, data, h in datas:
                    p = base / name; p.parent.mkdir(parents=True, exist_ok=True)
                    with p.open('xb') as f: f.write(data)
                    report['files'].append({'path': str(p.relative_to(a.out)), 'game': g['name'], **h})
            else:
                z = eng.make_torrentzip([(n, d) for n, d, _ in datas]); h = hashes(z)
                desc = [[n, hh['sha256']] for n, _, hh in sorted(datas, key=lambda x: x[0].lower())]
                fp = hashlib.sha256(eng.js({'profile': 'torrentzip-classic-v1', 'members': desc}).encode()).hexdigest()
                plan = c.execute('SELECT * FROM archive_plans WHERE fingerprint=?', (fp,)).fetchone()
                if plan and any(plan[k] != h[k] for k in h): raise ValueError('TorrentZip differs from the registered archive plan')
                with zipfile.ZipFile(io.BytesIO(z)) as zz:
                    if not zz.comment.startswith(b'TORRENTZIPPED-') or zz.testzip() is not None: raise ValueError('TorrentZip structure check failed')
                p = base / (eng.safe_name(g['name']) + '.zip')
                with p.open('xb') as f: f.write(z)
                report['files'].append({'path': str(p.relative_to(a.out)), 'game': g['name'], 'registered_plan': bool(plan), **h})
            report['exported'] += 1
        except Exception as e: report['errors'].append({'game': g['name'], 'error': repr(e)})
    db.c.close(); report['files'].sort(key=lambda r: r['path'])
    summary = {k: (len(v) if isinstance(v, list) else v) for k, v in report.items() if k != 'files'}
    if not a.report_only: (a.out / 'export-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report['errors']: raise SystemExit(2)


if __name__ == '__main__':
    main()
