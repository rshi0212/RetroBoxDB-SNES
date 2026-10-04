"""Export latest No-Intro DAT Parent games as TorrentZip, read-only against the DB.

NES: latest Headered DAT; RA hashes fetched online (console 7).
SNES / Mega Drive (storage v4 databases): latest Parent-Clone DAT; RA data comes from the
database's own RetroAchievements snapshot (ra_snapshots/ra_games/ra_hashes), refreshed with
tools/import_ra.py. RA hash = MD5 of the file (SNES: after a 512-byte copier header, if any).

--ra-only         keep only games whose ROM hash is linked to a RetroAchievements game with official
                  achievements (RA NES hash: MD5 after a 16-byte NES/FDS header, i.e. the Headerless DAT MD5).
--clone-fallback  with --ra-only: when a Parent's own ROM has no achievements, export one Clone per RA game
                  instead (preferring USA > World > Europe > Japan, then the latest revision).
--ra-folders      with --ra-only: put each zip in a subfolder named after its RA category
                  (Official, Homebrew, Unlicensed, Prototype, Hack, ...).
"""
import argparse, collections, datetime, hashlib, io, json, pathlib, re, sqlite3, types, urllib.request, zipfile, zlib

ap = argparse.ArgumentParser()
ap.add_argument('db'); ap.add_argument('out_dir'); ap.add_argument('report')
ap.add_argument('--ra-only', action='store_true', help='only games with RetroAchievements achievements')
ap.add_argument('--clone-fallback', action='store_true', help='export an RA-supported Clone when the Parent has none')
ap.add_argument('--ra-folders', action='store_true', help='group zips into RA category subfolders')
args = ap.parse_args()
if (args.clone_fallback or args.ra_folders) and not args.ra_only: ap.error('--clone-fallback/--ra-folders require --ra-only')
db_path, out_dir = args.db, pathlib.Path(args.out_dir)
src = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True).execute(
    "SELECT content FROM resources WHERE name='engine.py'").fetchone()[0]
eng = types.ModuleType('rbdb_engine'); eng.__dict__['__name__'] = 'rbdb_engine'
exec(compile(src, 'RetroBoxDB:engine.py', 'exec'), eng.__dict__)
_real = sqlite3.connect
eng.sqlite3 = types.SimpleNamespace(**{k: getattr(sqlite3, k) for k in dir(sqlite3) if not k.startswith('__')})
eng.sqlite3.connect = lambda p, timeout=60: _real(f'file:{p}?mode=ro', uri=True, timeout=timeout)
db = eng.DB(db_path)
c = db.c

platform = c.execute('SELECT code FROM platforms WHERE id=1').fetchone()[0]
CONSOLE = {'nes': 7, 'snes': 3, 'megadrive': 1}[platform]
ds = c.execute("SELECT id, version FROM dat_sets WHERE mode=? ORDER BY version DESC, id DESC LIMIT 1",
               ('headered' if platform == 'nes' else 'unspecified',)).fetchone()
games = c.execute("SELECT id, name, cloneof FROM dat_games WHERE dat_set_id=? ORDER BY ordinal", (ds['id'],)).fetchall()
parents = [g for g in games if g['cloneof'] is None]
clones = collections.defaultdict(list)
for g in games:
    if g['cloneof'] is not None: clones[g['cloneof']].append(g)
out_dir.mkdir(parents=True, exist_ok=True)
report = {'dat_set_id': ds['id'], 'dat_version': ds['version'], 'parents': len(parents),
          'exported': 0, 'skipped_existing': 0, 'missing': [], 'errors': []}

def hs(b):
    return {'size': len(b), 'crc32': f'{zlib.crc32(b):08x}', 'md5': hashlib.md5(b).hexdigest(),
            'sha1': hashlib.sha1(b).hexdigest(), 'sha256': hashlib.sha256(b).hexdigest()}

def ra_hash(b):
    if platform == 'nes': return hashlib.md5(b[16:] if b[:4] in (b'NES\x1a', b'FDS\x1a') else b).hexdigest()
    if platform == 'snes' and len(b) % 0x2000 == 512: return hashlib.md5(b[512:]).hexdigest()
    return hashlib.md5(b).hexdigest()

def ra_get(r):
    req = urllib.request.Request(f'https://retroachievements.org/dorequest.php?r={r}&c={CONSOLE}', headers={'User-Agent': 'RetroBoxDB'})
    with urllib.request.urlopen(req, timeout=60) as f: data = json.load(f)
    if not data.get('Success'): raise SystemExit(f'RetroAchievements {r} request failed')
    return data

def ra_category(title):
    m = re.match(r'~([^~]+)~', title)
    return m.group(1) if m else 'Official'

def package(g):
    return c.execute("SELECT p.file_id FROM packages p JOIN files f ON f.id=p.file_id "
                     "WHERE p.dat_game_id=? AND f.original_name=?", (g['id'], g['name'] + '.zip')).fetchone()

def ra_games(g):
    # Headerless DAT MD5 equals the RA hash, so this also works for games whose ROM is not in the DB.
    found = {}
    if platform != 'nes':
        for (m, size) in c.execute("SELECT lower(md5), size FROM dat_roms WHERE dat_game_id=?", (g['id'],)):
            if m and size % 0x2000 != 512 and m in ra: found[ra[m][0]] = ra[m][1]
        return found
    for (m,) in c.execute("SELECT lower(dr.md5) FROM dat_roms dr JOIN dat_games hg ON hg.id=dr.dat_game_id "
                          "JOIN dat_sets hs ON hs.id=hg.dat_set_id WHERE hs.mode='headerless' AND hs.version=? AND hg.name=?",
                          (ds['version'], g['name'])):
        if m in ra: found[ra[m][0]] = ra[m][1]
    return found

REGION_RANK = ('USA', 'World', 'Europe', 'Japan')
def clone_preference(g):
    tags = re.findall(r'\(([^)]*)\)', g['name'])
    regions = tags[0].split(', ') if tags else []
    region = min((REGION_RANK.index(r) for r in regions if r in REGION_RANK), default=len(REGION_RANK))
    rev = next((t[4:] for t in tags if t.startswith('Rev ')), '')
    return (package(g) is None, region, -len(rev), [-ord(ch) for ch in rev], g['name'])

def selections():
    """Yield (game, role, {ra_id: title}) in DAT order."""
    for g in parents:
        if ra is None:
            yield g, 'parent', {}; continue
        own = ra_games(g)
        if own:
            yield g, 'parent', own; continue
        if not args.clone_fallback:
            report['skipped_no_ra'] += 1; continue
        by_ra = collections.defaultdict(list)
        for cl in clones[g['name']]:
            for gid, t in ra_games(cl).items(): by_ra[gid].append((cl, t))
        if not by_ra:
            report['skipped_no_ra'] += 1; continue
        chosen = {}
        for gid, cands in by_ra.items():
            cl, t = min(cands, key=lambda x: clone_preference(x[0]))
            chosen.setdefault(cl['name'], (cl, {}))[1][gid] = t
        for cl, ids in chosen.values(): yield cl, 'clone', ids

ra = None
if args.ra_only and platform != 'nes':
    snap = c.execute('SELECT * FROM ra_snapshots ORDER BY id DESC LIMIT 1').fetchone()
    if snap is None: raise SystemExit('No RetroAchievements snapshot in this database; run tools/import_ra.py first')
    ra = {r['md5']: (r['ra_game_id'], r['title']) for r in c.execute(
        'SELECT h.md5, g.ra_game_id, g.title FROM ra_hashes h JOIN ra_games g USING(snapshot_id, ra_game_id) '
        'WHERE h.snapshot_id=? AND g.num_achievements>0', (snap['id'],))}
    report.update(ra_source={'snapshot_id': snap['id'], 'fetched_at': snap['fetched_at'], 'console_id': CONSOLE,
                             'official_games': len({v[0] for v in ra.values()}), 'official_hashes': len(ra)},
                  ra_matches=[], skipped_no_ra=0, folders=collections.Counter())
elif args.ra_only:
    official = ra_get('officialgameslist')['Response']  # RA game id -> title, games with official achievements
    ra = {md5.lower(): (gid, official[str(gid)]) for md5, gid in ra_get('hashlibrary')['MD5List'].items() if str(gid) in official}
    report.update(ra_source={'fetched_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'console_id': CONSOLE,
                             'official_games': len(official), 'official_hashes': len(ra)},
                  ra_matches=[], skipped_no_ra=0, folders=collections.Counter())

for i, (g, role, ids) in enumerate(selections(), 1):
    pkg = package(g)
    if pkg is None:
        missing = [r[0] for r in c.execute(
            "SELECT dr.name FROM dat_roms dr WHERE dr.dat_game_id=? AND NOT EXISTS "
            "(SELECT 1 FROM validations v WHERE v.dat_rom_id=dr.id AND v.status='match') ORDER BY dr.ordinal", (g['id'],))]
        report['missing'].append({'game': g['name'], 'role': role, 'missing_roms': missing,
                                  'ra': [{'ra_game_id': k, 'ra_title': t} for k, t in ids.items()]}); continue
    folder = ra_category(next(iter(ids.values()))) if args.ra_folders else None
    target = (out_dir / folder if folder else out_dir) / (eng.safe_name(g['name']) + '.zip')
    if target.exists():
        report['skipped_existing'] += 1; continue
    target.parent.mkdir(exist_ok=True)
    try:
        db.export(pkg['file_id'], target)  # exclusive create; verifies registered ZIP checksums
        # Independent check: members named exactly as DAT roms, every DAT hash matches, TorrentZip comment present.
        dat_roms = {r['name']: r for r in c.execute("SELECT * FROM dat_roms WHERE dat_game_id=?", (g['id'],))}
        raw = target.read_bytes()
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if set(z.namelist()) != set(dat_roms) or not z.comment.startswith(b'TORRENTZIPPED-'):
                raise ValueError('ZIP structure/name mismatch')
            for n, t in dat_roms.items():
                a = hs(z.read(n))
                bad = [k for k in a if t[k] is not None and str(t[k]).lower() != str(a[k]).lower()]
                if bad: raise ValueError(f'{n}: DAT mismatch on {bad}')
            if ra is not None:
                got = {ra[h][0] for h in (ra_hash(z.read(n)) for n in dat_roms) if h in ra}
                if not set(ids) <= got: raise ValueError('RA hash mismatch after export')
        if ra is not None:
            report['ra_matches'] += [{'game': g['name'], 'role': role, 'parent': g['cloneof'] or g['name'],
                                      'folder': folder, 'ra_game_id': k, 'ra_title': t} for k, t in ids.items()]
            if folder: report['folders'][folder] += 1
        report['exported'] += 1
    except Exception as e:
        target.unlink(missing_ok=True)
        report['errors'].append({'game': g['name'], 'error': str(e)})
    if i % 250 == 0: print(f'{i} selected', flush=True)

db.c.close()
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}, ensure_ascii=False))
pathlib.Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2))
