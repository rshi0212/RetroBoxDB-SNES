"""Re-tune the solid groups of a populated storage-v4 RetroBoxDB to a new group cap / dictionary.

python3 -B tools/retune_db.py FULL.sqlite --group-mib N [--workers N] [--dry-run]

Consecutive solid groups (already in No-Intro family order) are merged up to the new cap and re-encoded with a
dictionary equal to the cap. With the current cap, only adjacent groups that fit together are merged (consolidation). Block IDs, block SHA256 values and object extents never change: only the group a block
lives in and its offset are rewritten. Every new group is round-trip checked before insertion, the whole operation is
one transaction, and every block of every new group is re-verified before commit. If the existing table definition
caps group size below the new value, that CHECK constraint is relaxed (never tightened) through writable_schema and the
schema is integrity-checked afterwards. Use only on a database nothing else is writing to; run VACUUM afterwards.
"""
import argparse, collections, concurrent.futures as cf, importlib, json, pathlib, re, sqlite3, sys, time

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def relax_group_cap(c, new_cap):
    sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='compression_groups'").fetchone()[0]
    m = re.search(r"size<=(\d+) AND \(codec='lzma2-solid'", sql)
    if not m: raise SystemExit('Unexpected compression_groups definition; refusing to edit the schema')
    if int(m.group(1)) >= new_cap: return False
    new_sql = sql.replace(m.group(0), f"size<={new_cap} AND (codec='lzma2-solid'")
    version = c.execute('PRAGMA schema_version').fetchone()[0]
    c.execute('PRAGMA writable_schema=ON')
    c.execute("UPDATE sqlite_master SET sql=? WHERE type='table' AND name='compression_groups'", (new_sql,))
    c.execute(f'PRAGMA schema_version={version + 1}')
    c.execute('PRAGMA writable_schema=OFF')
    if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise SystemExit('Integrity check failed after relaxing the group cap')
    return True


def retune(db_path, group_mib, workers=None, dry_run=False, eng=None):
    a = argparse.Namespace(db=pathlib.Path(db_path), group_mib=group_mib, workers=workers, dry_run=dry_run); t0 = time.time()
    B = importlib.import_module('build_db')
    if eng is None:
        text, _ = B.combined_engine()
        work = a.db.resolve().parent / '.build-retune'; work.mkdir(exist_ok=True); (work / 'engine.py').write_text(text); sys.path.insert(0, str(work))
        eng = importlib.import_module('engine')
    cap = a.group_mib << 20
    if cap > eng.SOLID_MAX: raise SystemExit(f'Group cap above the engine ceiling ({eng.SOLID_MAX >> 20} MiB)')
    c0 = sqlite3.connect(a.db, isolation_level=None)
    old_cap = int(c0.execute("SELECT value FROM meta WHERE key='solid_group_max_bytes'").fetchone()[0])
    if cap < old_cap: raise SystemExit('Retune only merges groups: the new cap must not be below the current one')
    if not a.dry_run:
        relaxed = relax_group_cap(c0, cap)
        log('schema cap relaxed' if relaxed else 'schema cap already sufficient')
    c0.close()
    db = eng.DB(a.db)
    old_dict = db.solid_dict
    groups = [dict(r) for r in db.c.execute("SELECT id,size FROM compression_groups WHERE codec='lzma2-solid' ORDER BY id")]
    plan = []; cur = []; size = 0
    for g in groups:
        if cur and size + g['size'] > cap: plan.append(cur); cur = []; size = 0
        cur.append(g); size += g['size']
    if cur: plan.append(cur)
    # Same cap: consolidate only (adjacent groups that fit together are merged; groups left alone are not re-encoded).
    if cap == old_cap: plan = [m for m in plan if len(m) > 1]
    if not plan: log('nothing to merge'); return {'groups_before': len(groups), 'groups_after': len(groups)}
    before = db.c.execute("SELECT count(*),sum(length(data)) FROM compression_groups WHERE codec='lzma2-solid'").fetchone()
    log(f'{len(groups)} groups -> {len(groups) - sum(len(m) - 1 for m in plan)} groups of <= {a.group_mib} MiB ({len(plan)} merged groups to encode)')
    if a.dry_run: return {'groups_before': len(groups), 'groups_after': len(plan)}
    workers = a.workers or max(1, min(4, (8 << 30) // (12 * cap)))
    report = {'old_group_cap': old_cap, 'new_group_cap': cap, 'old_dictionary': old_dict, 'new_dictionary': cap,
              'groups_before': before[0], 'stored_before': before[1]}
    triggers = {n: db.c.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (n,)).fetchone()[0]
                for n in ('immutable_chunks_update', 'immutable_compression_groups_delete')}
    c = db.c; c.execute('BEGIN IMMEDIATE')
    try:
        for n in triggers: c.execute('DROP TRIGGER ' + n)
        for k, v in (('solid_group_max_bytes', cap), ('solid_group_dictionary_bytes', cap), ('solid_group_cache_bytes', max(96 << 20, 2 * cap))):
            c.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (k, str(v)))
        block = int(c.execute("SELECT value FROM meta WHERE key='rom_block_size'").fetchone()[0])
        c.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('storage', B.storage_text(db.platform, block, cap, cap)))  # keep the description in step
        new_db_filters = eng.solid_filters(cap)
        pending = collections.deque(); done = 0

        def decode_old(members):
            raws = []
            for g in members:
                data = c.execute('SELECT data FROM compression_groups WHERE id=?', (g['id'],)).fetchone()[0]
                raw = eng.lzma.decompress(data, format=eng.lzma.FORMAT_RAW, filters=eng.solid_filters(old_dict))
                row = c.execute('SELECT sha256,size FROM compression_groups WHERE id=?', (g['id'],)).fetchone()
                if len(raw) != row['size'] or eng.hashlib.sha256(raw).digest() != row['sha256']: raise ValueError(f'group {g["id"]} integrity failure')
                raws.append(raw)
            return raws

        def commit(item):
            nonlocal done
            members, fut = item
            encoded, digest, edigest = fut.result()
            total = sum(g['size'] for g in members)
            ng = db.insert('compression_groups', sha256=digest, encoded_sha256=edigest, size=total, codec=eng.SOLID_CODEC, data=encoded)
            offset = 0; fams = []
            for g in members:
                c.execute('UPDATE chunks SET group_id=?,group_offset=group_offset+? WHERE group_id=?', (ng, offset, g['id']))
                fams += [r[0] for r in c.execute('SELECT family_key FROM solid_group_families WHERE group_id=? ORDER BY ordinal', (g['id'],))]
                c.execute('DELETE FROM solid_group_families WHERE group_id=?', (g['id'],))
                c.execute('DELETE FROM compression_groups WHERE id=?', (g['id'],))
                offset += g['size']
            for i, f in enumerate(dict.fromkeys(fams)): c.execute('INSERT INTO solid_group_families VALUES (?,?,?)', (ng, i, f))
            done += 1
            if done % 5 == 0: log(f'{done}/{len(plan)} new groups')
        with B.engine_pool(workers, eng) as pool:
            for members in plan:
                raw = b''.join(decode_old(members))
                pending.append((members, pool.submit(eng.encode_solid, raw, cap)))
                while len(pending) > workers: commit(pending.popleft())
            while pending: commit(pending.popleft())
        for sql in triggers.values(): c.execute(sql)
        db.solid_limit = cap; db.solid_dict = cap; db._solid_filters = new_db_filters; db._solid_cache = max(96 << 20, 2 * cap); db.clear_caches()
        for (gid,) in c.execute("SELECT id FROM compression_groups WHERE codec='lzma2-solid' ORDER BY id").fetchall():
            db.group(gid)
            for (cid,) in c.execute('SELECT id FROM chunks WHERE group_id=? ORDER BY group_offset', (gid,)).fetchall(): db.chunk(cid)
            db.clear_caches()
        after = c.execute("SELECT count(*),sum(length(data)) FROM compression_groups WHERE codec='lzma2-solid'").fetchone()
        report.update(groups_after=after[0], stored_after=after[1], change_pct=round(100 * (after[1] - before[1]) / before[1], 2), seconds=round(time.time() - t0))
        db.event('retune_solid', details=report)
        c.execute('COMMIT')
    except BaseException:
        c.execute('ROLLBACK'); raise
    log('verified; VACUUM'); c.execute('VACUUM'); db.c.close()
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('db', type=pathlib.Path); ap.add_argument('--group-mib', type=int, required=True)
    ap.add_argument('--workers', type=int); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    print(json.dumps(retune(a.db, a.group_mib, a.workers, a.dry_run), indent=2))


if __name__ == '__main__':
    main()
