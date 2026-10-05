"""Import bilingual CSV names as traceable metadata, without changing ROM identities."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3

NORMALIZATION_VERSION = 'parentheses-whitespace-casefold-v1'
MATCHING_VERSION = 'game-qualified-title-v1'
SCHEMA_PATH = Path(__file__).with_name('game_names_schema.sql')
REGIONS = {'usa', 'europe', 'japan', 'taiwan', 'china', 'asia', 'world', 'brazil',
           'australia', 'russia', 'spain', 'france', 'germany', 'sweden', 'italy',
           'canada', 'hong kong', 'korea', 'netherlands', 'argentina', 'mexico',
           'finland', 'denmark', 'norway', 'poland', 'portugal', 'united kingdom'}
LANGUAGES = {'en','ja','zh','zh-hans','zh-hant','fr','de','es','it','pt','ru','ko',
             'ar','nl','sv','fi','da','no','pl','tr','he','el','uk','hu','cs','sk','la'}
# These are evidence fields, never discarded from the stored parse. Unknown tags
# remain identity qualifiers, including publisher names, cartridge IDs and volumes.
RELEASE_TAGS = {'unl', 'pirate', 'aftermarket', 'pal', 'ntsc', 'virtual console',
                'switch online', 'animal crossing', 'e-reader', 'evercade',
                'limited run games', 'the cowabunga collection', 'namcot collection',
                'capcom town', 'wii virtual console', 'wii u virtual console',
                'gamecube edition', 'zelda collection', 'alt'}
TAG_ALIASES = {'bullet-proof': 'bulletproof'}


def clean_name(name):
    # Remove balanced ASCII/full-width parentheses, including nested contents.
    previous = None
    while previous != name:
        previous = name
        name = re.sub(r'\([^()]*\)|（[^（）]*）', ' ', name)
    return ' '.join(name.split())


def match_key(name):
    return clean_name(name).casefold()


def full_key(name):
    return ' '.join(name.split()).casefold()


def parse_title(name):
    """Separate display text from identifying evidence; do not guess unknown tags."""
    # Capture balanced outer parentheses so nested unknown qualifiers stay intact.
    stack, tags, start = [], [], None
    for pos, char in enumerate(name):
        if char in '(（':
            if not stack:
                start = pos + 1
            stack.append(char)
        elif char in ')）' and stack and (stack[-1], char) in (('(', ')'), ('（', '）')):
            stack.pop()
            if not stack:
                tags.append(full_key(name[start:pos]))
    parsed = {'base': match_key(name), 'regions': [], 'languages': [],
              'identity': [], 'version': [], 'stage': [], 'tags': []}
    for tag in tags:
        tag = TAG_ALIASES.get(tag, tag)
        pieces = [x.strip() for x in tag.split(',')]
        if all(x in REGIONS for x in pieces):
            field = 'regions'
        elif all(x in LANGUAGES for x in pieces):
            field = 'languages'
        elif all(x in RELEASE_TAGS for x in pieces):
            field = 'version'
        elif re.fullmatch(r'(?:rev\s+\S+|v\d[\w. -]*|(?:beta|proto|demo|sample)(?:\s+\d+)?|\d{4}(?:-(?:\d{2}|xx)){0,2})', tag):
            field, pieces = 'version', [tag]
        elif tag in ('simplified', 'traditional'):
            field, pieces = 'languages', [tag]
        else:
            field, pieces = 'identity', [tag]
        parsed[field].extend(pieces)
        parsed['tags'].extend(pieces)
        if re.fullmatch(r'(?:beta|proto|demo|sample)(?:\s+\d+)?', tag):
            parsed['stage'].append(tag.split()[0])
    for field in ('regions', 'languages', 'identity', 'version', 'stage', 'tags'):
        parsed[field] = sorted(set(parsed[field]))
    return parsed


def resolve_title(original, candidates):
    """Return release evidence at the strongest successful tier, never across games.

    Candidates are (release_id, game_id, title, parsed_title) tuples. Multiple DAT
    aliases for one release are allowed. Broad matches remain review candidates.
    """
    source = parse_title(original)
    all_games = sorted({r[1] for r in candidates})
    if not candidates:
        return [], None, 'unmatched', 'normalized_title', 'no_base_title_candidate', source, all_games

    def finish(rows, method, reason):
        games = {r[1] for r in rows}
        if len(games) == 1:
            return sorted({r[0] for r in rows}), next(iter(games)), 'matched', method, reason, source, all_games
        return sorted({r[0] for r in rows}), None, 'ambiguous', method, 'multiple_game_candidates', source, all_games

    exact = [r for r in candidates if full_key(r[2]) == full_key(original)]
    if exact:
        return finish(exact, 'exact_title', 'full_title')
    structured = [r for r in candidates if r[3]['tags'] == source['tags']]
    if structured:
        return finish(structured, 'structured_title', 'equivalent_qualifiers')

    # Never erase a volume, publisher or unknown identity tag to force a match.
    compatible = [r for r in candidates if r[3]['identity'] == source['identity']]
    if compatible:
        # Region can distinguish unrelated games that share the same base title.
        regional = [r for r in compatible if source['regions'] and
                    set(source['regions']) & set(r[3]['regions'])]
        if regional:
            compatible = regional
        # Retain prototype/demo/etc. evidence when independent groups compete.
        if len({r[1] for r in compatible}) > 1:
            variants = [r for r in compatible if r[3]['version'] == source['version']]
            if variants:
                compatible = variants
            elif source['stage']:
                stages = [r for r in compatible if r[3]['stage'] == source['stage']]
                if stages:
                    compatible = stages
        return finish(compatible, 'qualified_title', 'compatible_identity_within_one_game')
    return (sorted({r[0] for r in candidates}), None, 'ambiguous', 'normalized_title',
            'identity_qualifiers_differ', source, all_games)


def refresh_matches(c):
    """Refresh every stored source, so previous imports cannot retain unsafe links."""
    indexes = defaultdict(list)
    for pid, rid, gid, title in c.execute('''
        SELECT g.platform_id,r.id,r.game_id,r.title FROM releases r JOIN games g ON g.id=r.game_id
        UNION SELECT g.platform_id,r.id,r.game_id,d.name FROM release_dat_games rd
        JOIN dat_games d ON d.id=rd.dat_game_id JOIN releases r ON r.id=rd.release_id
        JOIN games g ON g.id=r.game_id'''):
        parsed = parse_title(title)
        indexes[(pid, parsed['base'])].append((rid, gid, title, parsed))
    links, decisions = [], []
    for entry_id, pid, original, key in c.execute('''
        SELECT e.id,i.platform_id,e.name_en_original,e.match_key FROM game_name_entries e
        JOIN game_name_imports i ON i.id=e.import_id ORDER BY e.id'''):
        ids, game, status, method, reason, parsed, games = resolve_title(original, indexes[(pid, key)])
        links.extend((entry_id, rid, status, method) for rid in ids)
        decisions.append((entry_id, MATCHING_VERSION, status, game, method, reason,
                          json.dumps(parsed, ensure_ascii=False), json.dumps(games)))
    c.execute('DELETE FROM release_name_links')
    c.execute('DELETE FROM game_name_match_decisions')
    c.executemany('INSERT INTO release_name_links VALUES (?,?,?,?)', links)
    c.executemany('INSERT INTO game_name_match_decisions VALUES (?,?,?,?,?,?,?,?)', decisions)


def read_csv(data):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    if reader.fieldnames != ['Name EN', 'Name CN']:
        raise ValueError('CSV headers must be Name EN,Name CN')
    rows = []
    for number, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f'Invalid column count at record {number}')
        en, cn = row['Name EN'], row['Name CN']
        if not match_key(en):
            raise ValueError(f'Empty English match key at record {number}')
        rows.append((number, en, cn))
    if not rows:
        raise ValueError('CSV contains no game names')
    return rows


def resource(c, name, kind, content):
    c.execute('''INSERT INTO resources(name,kind,content,sha256) VALUES (?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET kind=excluded.kind,
        content=excluded.content,sha256=excluded.sha256''',
        (name, kind, content, hashlib.sha256(content.encode('utf-8')).hexdigest()))


def apply_schema(c, schema):
    # executescript would implicitly commit: execute statements within our transaction.
    statement = ''
    for line in schema.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            c.execute(statement)
            statement = ''
    if statement.strip():
        raise ValueError('Incomplete game name schema')


def migrate_v1(c):
    """Convert the earlier per-row translations to references, within the transaction."""
    columns = {r[1] for r in c.execute('PRAGMA table_info(game_name_entries)')}
    if 'name_cn' not in columns:
        return
    for view in ('v_rom_game_names', 'v_game_names', 'v_release_game_names',
                 'v_game_name_import_status', 'v_game_name_conflicts'):
        c.execute('DROP VIEW IF EXISTS ' + view)
    c.execute('''CREATE TABLE IF NOT EXISTS game_chinese_names (
        id INTEGER PRIMARY KEY,
        name_cn TEXT NOT NULL UNIQUE CHECK(length(trim(name_cn))>0)) STRICT''')
    c.execute('INSERT OR IGNORE INTO game_chinese_names(name_cn) '
              'SELECT DISTINCT name_cn FROM game_name_entries WHERE name_cn IS NOT NULL ORDER BY name_cn')
    c.execute('ALTER TABLE game_name_entries ADD COLUMN name_cn_id INTEGER REFERENCES game_chinese_names(id)')
    c.execute('UPDATE game_name_entries SET name_cn_id=(SELECT id FROM game_chinese_names '
              'WHERE game_chinese_names.name_cn=game_name_entries.name_cn)')
    c.execute('ALTER TABLE game_name_entries DROP COLUMN name_cn')
    c.execute('ALTER TABLE game_name_entries DROP COLUMN name_cn_original')


def import_names(c, data, source_name, platform='nes'):
    """Caller owns the transaction; importing identical bytes refreshes links, not rows."""
    rows = read_csv(data)
    platform_row = c.execute('SELECT id FROM platforms WHERE code=?', (platform,)).fetchone()
    if platform_row is None:
        raise ValueError(f'Unknown platform: {platform}')
    platform_id = platform_row[0]
    schema = SCHEMA_PATH.read_text(encoding='utf-8')
    migrate_v1(c)
    old_links = c.execute("SELECT sql FROM sqlite_master WHERE name='release_name_links'").fetchone()
    if old_links and 'structured_title' not in old_links[0]:
        # All links are re-derived below from immutable source rows in this transaction.
        for name in re.findall(r'CREATE VIEW IF NOT EXISTS (\w+)', schema):
            c.execute('DROP VIEW IF EXISTS ' + name)
        c.execute('DROP TABLE release_name_links')
    apply_schema(c, schema)
    sha256 = hashlib.sha256(data).hexdigest()
    source_resource = 'game-names/source/' + sha256 + '.csv'
    # Decode without stripping BOM/newlines: re-encoding reproduces the source bytes.
    resource(c, source_resource, 'csv', data.decode('utf-8'))
    c.execute('''INSERT INTO game_name_imports
        (platform_id,source_name,source_sha256,resource_name,normalization_version,imported_at)
        VALUES (?,?,?,?,?,?) ON CONFLICT(platform_id,source_sha256) DO NOTHING''',
        (platform_id, source_name, sha256, source_resource, NORMALIZATION_VERSION,
         datetime.now(timezone.utc).isoformat()))
    import_id = c.execute('SELECT id FROM game_name_imports WHERE platform_id=? AND source_sha256=?',
                          (platform_id, sha256)).fetchone()[0]
    c.executemany('INSERT INTO game_chinese_names(name_cn) VALUES (?) ON CONFLICT(name_cn) DO NOTHING',
                  [(cn,) for cn in sorted({cn.strip() for _, _, cn in rows if cn.strip()})])
    chinese_ids = dict(c.execute('SELECT name_cn,id FROM game_chinese_names'))
    c.executemany('''INSERT INTO game_name_entries
        (import_id,row_number,name_en_original,name_en,name_cn_id,match_key)
        VALUES (?,?,?,?,?,?) ON CONFLICT(import_id,row_number) DO NOTHING''',
        [(import_id, n, en, clean_name(en), chinese_ids.get(cn.strip()), match_key(en))
         for n, en, cn in rows])

    refresh_matches(c)
    report = summarize(c, import_id)
    resource(c, 'game-names/import-report', 'json', json.dumps(report, ensure_ascii=False, indent=2))
    resource(c, 'import_game_names.py', 'python', Path(__file__).read_text(encoding='utf-8'))
    resource(c, 'game_names_schema.sql', 'sql', schema)
    old_schema = c.execute("SELECT content FROM resources WHERE name='schema.sql'").fetchone()
    if old_schema:
        base_schema = old_schema[0].split('-- Game name extension v')[0].rstrip()
        resource(c, 'schema.sql', 'sql', base_schema + '\n\n' + schema)
    resource(c, 'game-names/group-report', 'json',
             json.dumps(summarize_groups(c, platform_id), ensure_ascii=False, indent=2))
    c.execute("INSERT INTO meta VALUES ('game_names_extension_version','4') "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value")
    return report


def summarize(c, import_id):
    result = dict(zip(('source_name', 'source_sha256', 'normalization_version'), c.execute(
        'SELECT source_name,source_sha256,normalization_version FROM game_name_imports WHERE id=?',
        (import_id,)).fetchone()))
    result['import_id'] = import_id
    result['matching_version'] = MATCHING_VERSION
    for name, sql in {
        'rows': 'SELECT count(*) FROM game_name_entries WHERE import_id=?',
        'rows_with_chinese': 'SELECT count(*) FROM game_name_entries WHERE import_id=? AND name_cn_id IS NOT NULL',
        'unique_chinese_names': 'SELECT count(DISTINCT name_cn_id) FROM game_name_entries WHERE import_id=?',
        'normalized_titles': 'SELECT count(DISTINCT match_key) FROM game_name_entries WHERE import_id=?',
        'matched_rows': "SELECT count(*) FROM v_game_name_import_status WHERE import_id=? AND status='matched'",
        'matched_rows_with_chinese': "SELECT count(*) FROM v_game_name_import_status WHERE import_id=? AND status='matched' AND name_cn IS NOT NULL",
        'matched_releases': 'SELECT count(DISTINCT release_id) FROM v_release_game_names WHERE import_id=?',
        'releases_with_chinese': 'SELECT count(DISTINCT release_id) FROM v_release_game_names WHERE import_id=? AND name_cn IS NOT NULL',
        'matched_games': 'SELECT count(DISTINCT game_id) FROM v_release_game_names WHERE import_id=?',
        'matched_roms': 'SELECT count(DISTINCT rom_id) FROM v_rom_game_names WHERE import_id=?',
        'matched_links': 'SELECT count(*) FROM v_release_game_names WHERE import_id=?',
        'ambiguous_links': "SELECT count(*) FROM release_name_links l JOIN game_name_entries e ON e.id=l.entry_id WHERE e.import_id=? AND l.status='ambiguous'",
        'ambiguous_rows': "SELECT count(*) FROM v_game_name_import_status WHERE import_id=? AND status='ambiguous'",
        'unmatched_rows': "SELECT count(*) FROM v_game_name_import_status WHERE import_id=? AND status='unmatched'",
    }.items():
        result[name] = c.execute(sql, (import_id,)).fetchone()[0]
    result['unresolved_rows'] = [dict(zip(('row_number','name_en','name_cn','status'), row))
        for row in c.execute('SELECT row_number,name_en_original,name_cn,status FROM v_game_name_import_status '
                             "WHERE import_id=? AND status!='matched' ORDER BY row_number", (import_id,))]
    result['multiple_translation_keys'] = [row[0] for row in c.execute(
        'SELECT match_key FROM v_game_name_alternatives WHERE import_id=? ORDER BY match_key', (import_id,))]
    result['matched_rows_by_method'] = dict(c.execute('''SELECT d.match_method,count(*)
        FROM game_name_match_decisions d JOIN game_name_entries e ON e.id=d.entry_id
        WHERE e.import_id=? AND d.status='matched' GROUP BY d.match_method''', (import_id,)))
    return result


def summarize_groups(c, platform_id):
    """Count direct evidence separately from names inherited through existing game IDs."""
    states = dict(c.execute('SELECT status,count(*) FROM v_game_chinese_name_status '
                            'WHERE platform_id=? GROUP BY status', (platform_id,)))
    result = {'platform_id': platform_id, 'policy': 'inherit only a unique group translation; retain all direct aliases',
              'game_status_counts': states}
    result['release_counts_by_basis'] = dict(c.execute('''
        SELECT n.name_basis,count(DISTINCT n.release_id) FROM v_release_effective_chinese_names n
        JOIN games g ON g.id=n.game_id WHERE g.platform_id=? GROUP BY n.name_basis''', (platform_id,)))
    result['effective_releases_with_chinese'] = sum(result['release_counts_by_basis'].values())
    result['effective_roms_with_chinese'] = c.execute('''
        SELECT count(DISTINCT n.rom_id) FROM v_rom_effective_chinese_names n
        JOIN games g ON g.id=n.game_id WHERE g.platform_id=?''', (platform_id,)).fetchone()[0]
    # The production release metadata identifies its authoritative DAT parent/clone row.
    if 'metadata_json' in {r[1] for r in c.execute('PRAGMA table_info(releases)')}:
        result['release_coverage_by_role'] = []
        for role,total,direct,inherited in c.execute('''
            WITH effective AS MATERIALIZED (
                SELECT DISTINCT release_id,name_basis FROM v_release_effective_chinese_names
            )
            SELECT CASE WHEN coalesce(d.cloneof,'')='' THEN 'parent' ELSE 'clone' END,
                count(*),sum(coalesce(e.name_basis='direct',0)),
                sum(coalesce(e.name_basis='group_inherited',0))
            FROM releases r JOIN games g ON g.id=r.game_id
            JOIN dat_games d ON d.id=json_extract(r.metadata_json,'$.dat_game_id')
            LEFT JOIN effective e ON e.release_id=r.id WHERE g.platform_id=? GROUP BY 1
        ''', (platform_id,)):
            result['release_coverage_by_role'].append({
                'role': role, 'total': total, 'direct': direct, 'inherited': inherited,
                'effective': direct + inherited,
                'direct_percent': round(100 * direct / total, 2),
                'effective_percent': round(100 * (direct + inherited) / total, 2)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('databases', type=Path, nargs='+')
    parser.add_argument('--platform', default='nes')
    parser.add_argument('--dry-run', action='store_true', help='Run in a transaction and roll back')
    args = parser.parse_args()
    data = args.csv.read_bytes()
    read_csv(data)
    # All databases are imported inside their own open transactions first; commits happen only after
    # every database succeeded, so a failure leaves none of them changed (e.g. full database + Catalog).
    connections = []
    try:
        reports = []
        for database in args.databases:
            # mode=rw prevents accidentally creating a new empty database on a typo.
            c = sqlite3.connect(database.resolve().as_uri() + '?mode=rw', uri=True)
            connections.append(c)
            c.execute('PRAGMA foreign_keys=ON')
            c.execute('PRAGMA synchronous=FULL')
            c.execute('BEGIN IMMEDIATE')
            report = import_names(c, data, args.csv.name, args.platform)
            errors = c.execute('PRAGMA foreign_key_check').fetchall()
            if errors:
                raise ValueError(f'{database}: foreign key errors: {errors[:10]}')
            reports.append((database, report))
        for c in connections:
            c.rollback() if args.dry_run else c.commit()
        for database, report in reports:
            print(json.dumps({'database': str(database), 'dry_run': args.dry_run, **report},
                             ensure_ascii=False, indent=2))
    except BaseException:
        for c in connections:
            if c.in_transaction:
                c.rollback()
        raise
    finally:
        for c in connections:
            c.close()

if __name__ == '__main__':
    main()
