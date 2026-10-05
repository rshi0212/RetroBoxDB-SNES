"""Import a RetroAchievements game/hash snapshot (public Web API) into a storage-v4 RetroBoxDB.

python3 -B tools/import_ra.py FULL.sqlite [--response saved.json]
The API key is read from $RETROACHIEVEMENTS_API_KEY or ~/Sync/API_TOKEN/retroachievements.md
and is never written to the database, reports or logs. The stored resource is the API response only.
"""
import argparse, datetime, hashlib, json, os, pathlib, re, sqlite3, sys, urllib.parse, urllib.request

ENDPOINT = 'https://retroachievements.org/API/API_GetGameList.php'
CONSOLES = {'snes': 3, 'megadrive': 1, 'nes': 7, 'gb': 4, 'gbc': 6, 'gba': 5}
TOKEN_FILE = pathlib.Path('~/Sync/API_TOKEN/retroachievements.md').expanduser()


def api_key():
    key = os.environ.get('RETROACHIEVEMENTS_API_KEY')
    if not key and TOKEN_FILE.exists():
        m = re.search(r"RETROACHIEVEMENTS_API_KEY\s*[:=]\s*['\"]?([^'\"\s]+)", TOKEN_FILE.read_text())
        key = m and m[1]
    if not key: raise SystemExit('RetroAchievements API key not found (env RETROACHIEVEMENTS_API_KEY or token file)')
    return key


def fetch(console_id):
    query = urllib.parse.urlencode({'i': console_id, 'h': 1, 'f': 0, 'y': api_key()})
    req = urllib.request.Request(ENDPOINT + '?' + query, headers={'User-Agent': 'RetroBoxDB'})
    try:
        with urllib.request.urlopen(req, timeout=120) as f: raw = f.read()
    except Exception as e:  # never echo the URL (it carries the key)
        raise SystemExit(f'RetroAchievements request failed: {type(e).__name__}') from None
    data = json.loads(raw)
    if not isinstance(data, list): raise SystemExit('Unexpected RetroAchievements response: ' + str(data)[:200])
    return raw


def category(title):
    tags = re.findall(r'~([^~]+)~', title)
    return '/'.join(tags) if tags else 'Official'


def import_snapshot(c, platform, raw, fetched_at):
    console = CONSOLES[platform]; data = json.loads(raw)
    if any(g.get('ConsoleID') != console for g in data): raise ValueError('Response contains another console')
    digest = hashlib.sha256(raw).hexdigest()
    old = c.execute('SELECT id FROM ra_snapshots WHERE console_id=? AND response_sha256=?', (console, digest)).fetchone()
    if old: return {'snapshot_id': old[0], 'already_imported': True}
    resource = f'ra/API_GetGameList-c{console}-{digest[:12]}.json'
    text = raw.decode('utf-8')
    c.execute('INSERT INTO resources VALUES (?,?,?,?)', (resource, 'json', text, hashlib.sha256(text.encode()).hexdigest()))
    hashes = sum(len(g.get('Hashes') or []) for g in data)
    sid = c.execute('INSERT INTO ra_snapshots(console_id,endpoint,fetched_at,response_sha256,resource_name,games,hashes) VALUES (?,?,?,?,?,?,?)',
                    (console, ENDPOINT + '?i=%d&h=1&f=0' % console, fetched_at, digest, resource, len(data), hashes)).lastrowid
    for g in data:
        c.execute('INSERT INTO ra_games VALUES (?,?,?,?,?,?,?,?)', (sid, g['ID'], g['Title'], category(g['Title']), g.get('NumAchievements') or 0,
                                                                   g.get('NumLeaderboards'), g.get('Points'), g.get('DateModified')))
        for h in g.get('Hashes') or []:
            c.execute('INSERT OR IGNORE INTO ra_hashes VALUES (?,?,?)', (sid, h.lower(), g['ID']))
    q = lambda sql: c.execute(sql).fetchone()[0]
    report = {'snapshot_id': sid, 'console_id': console, 'fetched_at': fetched_at, 'games': len(data), 'hashes': hashes,
              'games_with_achievements': q(f'SELECT count(*) FROM ra_games WHERE snapshot_id={sid} AND num_achievements>0'),
              'hashes_of_games_with_achievements': q(f'SELECT count(*) FROM ra_hashes h JOIN ra_games g USING(snapshot_id,ra_game_id) WHERE h.snapshot_id={sid} AND g.num_achievements>0'),
              'local_roms_matched': q('SELECT count(DISTINCT rom_id) FROM v_rom_ra_matches WHERE has_achievements'),
              'ra_games_with_local_rom': q('SELECT count(DISTINCT ra_game_id) FROM v_rom_ra_matches WHERE has_achievements'),
              'dat_entries_matched': q('SELECT count(DISTINCT dat_rom_id) FROM v_dat_ra_matches WHERE has_achievements'),
              'ra_games_in_any_dat': q('SELECT count(DISTINCT ra_game_id) FROM v_dat_ra_matches WHERE has_achievements'),
              'hashes_with_achievements_unexplained': q('SELECT count(*) FROM v_ra_unmatched_hashes WHERE num_achievements>0'),
              'by_category_local': dict(c.execute('SELECT ra_category,count(DISTINCT ra_game_id) FROM v_rom_ra_matches WHERE has_achievements GROUP BY 1').fetchall())}
    c.execute('INSERT INTO events(action,entity,entity_id,details_json,created_at) VALUES (?,?,?,?,?)',
              ('import_ra_snapshot', 'ra_snapshots', sid, json.dumps(report, ensure_ascii=False, sort_keys=True), fetched_at))
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('db'); ap.add_argument('--response', type=pathlib.Path)
    args = ap.parse_args()
    c = sqlite3.connect(pathlib.Path(args.db).resolve().as_uri() + '?mode=rw', uri=True); c.execute('PRAGMA foreign_keys=ON')
    platform = c.execute('SELECT code FROM platforms WHERE id=1').fetchone()[0]
    raw = args.response.read_bytes() if args.response else fetch(CONSOLES[platform])
    with c: report = import_snapshot(c, platform, raw, datetime.datetime.now(datetime.timezone.utc).isoformat())
    c.close(); print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
