"""Normalize a populated storage-v4 RetroBoxDB to the naming and metadata conventions (idempotent).

python3 -B tools/normalize_db.py DB.sqlite [--code NEW_CODE] [--dry-run]

Conventions:
  * platform code = the Batocera system name (platforms.code, meta.platform, frontend_platforms.platform_code);
  * meta.scope and meta.storage are derived from the platform and the current storage parameters;
  * every database has meta.platform and meta.game_names_extension_version;
  * page size 16 KiB (a database with another page size is rebuilt by VACUUM);
  * file name RetroBoxDB.<label>.sqlite (renaming the file is left to the caller; the expected name is reported).
File formats (roms.format, e.g. 'sms', 'ws') are file-format values, not platform codes, and are not changed.
Each change is recorded as a 'normalize_db' event.
"""
import argparse, json, pathlib, sqlite3, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_db as B  # noqa: E402

PAGE_SIZE = 16384
GAME_NAMES_EXTENSION_VERSION = '4'


def normalize(path, new_code=None, dry_run=False):
    c = sqlite3.connect(pathlib.Path(path).resolve().as_uri() + '?mode=rw', uri=True); c.execute('PRAGMA foreign_keys=ON')
    old = c.execute('SELECT code FROM platforms WHERE id=1').fetchone()[0]
    code = new_code or old
    if code not in B.PLATFORMS: raise SystemExit(f'unknown platform code {code}')
    if B.PLATFORMS[code]['batocera'] != code: raise SystemExit(f'{code}: platform code must equal the Batocera system name {B.PLATFORMS[code]["batocera"]}')
    meta = dict(c.execute('SELECT key,value FROM meta'))
    changes = {}
    with c:
        if old != code:
            c.execute('UPDATE platforms SET code=? WHERE id=1', (code,))
            c.execute('UPDATE frontend_platforms SET platform_code=? WHERE platform_code=?', (code, old))
            changes['platform_code'] = [old, code]
        want = {'platform': code, 'scope': B.scope_text(code),
                'storage': B.storage_text(code, int(meta['rom_block_size']), int(meta['solid_group_max_bytes']), int(meta['solid_group_dictionary_bytes']))}
        if 'game_names_extension_version' not in meta: want['game_names_extension_version'] = GAME_NAMES_EXTENSION_VERSION
        for k, v in want.items():
            if meta.get(k) != v:
                changes[f'meta.{k}'] = [meta.get(k), v]; c.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (k, v))
        fe = c.execute('SELECT system_code FROM frontend_platforms WHERE platform_code=?', (code,)).fetchall()
        if [r[0] for r in fe] != [B.PLATFORMS[code]['batocera']]: raise SystemExit(f'frontend_platforms for {code}: {fe}')
        page = c.execute('PRAGMA page_size').fetchone()[0]
        if page != PAGE_SIZE: changes['page_size'] = [page, PAGE_SIZE]
        if changes and not dry_run:
            c.execute('INSERT INTO events(action,entity,entity_id,details_json,created_at) VALUES (?,?,?,?,?)',
                      ('normalize_db', 'platforms', 1, json.dumps(changes, ensure_ascii=False, sort_keys=True), B.datetime_now()))
        if dry_run: c.rollback()
    if 'page_size' in changes and not dry_run:
        c.execute(f'PRAGMA page_size={PAGE_SIZE}'); c.execute('VACUUM')
        if c.execute('PRAGMA page_size').fetchone()[0] != PAGE_SIZE: raise SystemExit('page size change failed (WAL mode?)')
    ok = c.execute('PRAGMA quick_check').fetchone()[0]; c.close()
    expected = B.db_path(code, pathlib.Path(path).resolve().parent)
    return {'db': str(path), 'code': code, 'changes': changes, 'quick_check': ok, 'expected_file': expected.name,
            'file_name_ok': pathlib.Path(path).resolve() == expected.resolve(), 'dry_run': dry_run}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('db'); ap.add_argument('--code'); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    print(json.dumps(normalize(a.db, a.code, a.dry_run), ensure_ascii=False))
