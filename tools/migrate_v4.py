"""Migrate a populated storage-v3 RetroBoxDB (NES) to storage v4 family-ordered solid groups.

python3 -B tools/migrate_v4.py OLD.sqlite NEW.sqlite --group-mib N [--workers N]

OLD is opened read-only and copied to NEW (refuses to replace NEW). On NEW:
  1. the compression_groups CHECK is relaxed to admit 'lzma2-solid' groups up to N MiB; user_version becomes 4;
  2. storage-v4 schema objects missing from the v3 schema are created (empty extension tables, views, indexes);
  3. every ROM payload object (NES body objects and headerless ROM objects) gets a family (newest DAT parent/clone,
     DB Export parent archive, older DAT, then title) and an RA hash (MD5 of the body, as rcheevos hashes NES);
  4. all blocks of those objects are decoded in block-ID order (cache-friendly for v3 groups), re-packed in family
     order into solid groups, round-trip checked, and switched to the 'group' codec; v3 groups left without blocks
     are removed. Block IDs, SHA256, sizes, object extents, 16-byte header recipes and all metadata are unchanged.
The whole step runs in one transaction; afterwards NEW is vacuumed. Validate with: engine.py NEW audit-all.
"""
import argparse, collections, concurrent.futures as cf, hashlib, importlib, json, pathlib, re, sqlite3, sys, time

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))


def log(*a): print(time.strftime('%H:%M:%S'), *a, flush=True)


def upgrade_schema(c, cap):
    sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='compression_groups'").fetchone()[0]
    new = sql.replace("CHECK(size>0 AND size<=2097152)", f"CHECK(size>0 AND size<={cap} AND (codec='lzma2-solid' OR size<=2097152))")
    new = new.replace("CHECK(codec='lzma2-4m')", "CHECK(codec IN ('lzma2-4m','lzma2-solid'))")
    if new == sql or "lzma2-solid" not in new: raise SystemExit('Unexpected v3 compression_groups definition')
    version = c.execute('PRAGMA schema_version').fetchone()[0]
    c.execute('PRAGMA writable_schema=ON')
    c.execute("UPDATE sqlite_master SET sql=? WHERE type='table' AND name='compression_groups'", (new,))
    c.execute(f'PRAGMA schema_version={version + 1}'); c.execute('PRAGMA writable_schema=OFF')
    if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise SystemExit('Integrity check failed after schema edit')
    fin = importlib.import_module('finalize_db')
    existing = {r[0] for r in c.execute('SELECT name FROM sqlite_master')}; added = []
    c.execute('BEGIN')
    for st in fin.statements((TOOLS / 'schema_v4.sql').read_text()):
        m = re.match(r'CREATE\s+(INDEX|VIEW|TRIGGER|TABLE)\s+(\w+)', st)
        if m and m[2] not in existing: c.execute(st); added.append(m[2])
    c.execute('COMMIT')
    c.execute('PRAGMA user_version=4')
    return added


def migrate(old, new, group_mib, workers=None):
    a = argparse.Namespace(old=pathlib.Path(old), new=pathlib.Path(new), group_mib=group_mib, workers=workers); t0 = time.time(); cap = a.group_mib << 20
    if a.new.exists(): raise SystemExit(f'Refusing to replace {a.new}')
    src = sqlite3.connect(f'file:{a.old.resolve()}?mode=ro', uri=True)
    if src.execute('PRAGMA user_version').fetchone()[0] != 3: raise SystemExit('Source must be storage v3')
    dst = sqlite3.connect(a.new, isolation_level=None); src.backup(dst); src.close()
    log('copied', a.old.name, '->', a.new.name)
    added = upgrade_schema(dst, cap)
    block = int(dst.execute("SELECT value FROM meta WHERE key='nes_block_size'").fetchone()[0])
    dst.execute('BEGIN')
    for k, v in (('schema_version', '4'), ('rom_block_size', str(block)), ('solid_group_max_bytes', str(cap)), ('solid_group_dictionary_bytes', str(cap)),
                 ('solid_group_cache_bytes', str(max(96 << 20, 2 * cap))),
                 ('storage', f'SHA256 {block // 1024} KiB block dedup aligned to NES header/PRG/CHR boundaries; 16-byte headers stored separately; '
                             f'family-ordered solid LZMA2 groups up to {a.group_mib} MiB ({a.group_mib} MiB dictionary); export-only ZIP plans')):
        dst.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (k, v))
    dst.execute('COMMIT'); dst.close()
    log('schema upgraded to v4; added', len(added), 'objects')

    B = importlib.import_module('build_db'); text, _ = B.combined_engine()
    work = a.new.resolve().parent / '.build-migrate'; work.mkdir(exist_ok=True); (work / 'engine.py').write_text(text); sys.path.insert(0, str(work))
    eng = importlib.import_module('engine'); db = eng.DB(a.new); c = db.c
    report = {'source': a.old.name, 'group_cap': cap, 'schema_objects_added': added}
    payload = [r[0] for r in c.execute('''SELECT body_object_id FROM roms WHERE body_object_id IS NOT NULL
        UNION SELECT r.object_id FROM roms r JOIN objects o ON o.id=r.object_id WHERE o.storage_kind='chunks' ''')]
    payload_set = set(payload)
    c.execute('BEGIN IMMEDIATE')
    try:
        # Families and RA hashes for payload objects.
        index = db.family_index(); fam = {}; basis = collections.Counter()
        for oid in payload:
            o = c.execute('SELECT crc32,size FROM objects WHERE id=?', (oid,)).fetchone()
            hit = index.get((o['crc32'], o['size']))
            if hit is None:
                for r in c.execute('SELECT o2.crc32,o2.size FROM roms r JOIN objects o2 ON o2.id=r.object_id WHERE r.body_object_id=?', (oid,)):
                    hit = index.get((r['crc32'], r['size']))
                    if hit: break
            if hit is None:
                name = c.execute('''SELECT f.original_name FROM roms r JOIN files f ON f.object_id=r.object_id
                                    WHERE (r.body_object_id=? OR r.object_id=?) AND f.kind='rom' ORDER BY f.id LIMIT 1''', (oid, oid)).fetchone()
                hit = (eng.base_title(name[0] if name else str(oid)), 'title')
            fam[oid] = hit; db.set_family(oid, *hit); basis[hit[1]] += 1
        report['family_basis'] = dict(basis)
        n_ra = 0
        for r in c.execute("SELECT r.id,r.object_id,r.body_object_id,r.format FROM roms r WHERE r.format!='auxiliary'").fetchall():
            body = r['body_object_id'] or r['object_id']
            md5 = c.execute('SELECT md5 FROM objects WHERE id=?', (body,)).fetchone()[0]
            method = 'md5 after the 16-byte NES header (rcheevos nes)' if r['body_object_id'] and r['body_object_id'] != r['object_id'] else 'md5 of complete file (rcheevos buffer)'
            c.execute('INSERT OR IGNORE INTO rom_ra_hashes VALUES (?,?,?)', (r['id'], md5, method)); n_ra += 1
        report['rom_ra_hashes'] = n_ra

        # Decode every payload block once, in block-ID order.
        refs = collections.defaultdict(list)
        for oid, cid, ordn in c.execute('SELECT object_id,chunk_id,ordinal FROM object_chunks').fetchall():
            if oid in payload_set: refs[oid].append((ordn, cid))
        blocks = sorted({cid for v in refs.values() for _, cid in v})
        codec = dict(c.execute('SELECT id,codec FROM chunks').fetchall())
        blocks = [b for b in blocks if codec[b] != 'fill']
        raw = {}
        for i, cid in enumerate(blocks):
            raw[cid] = db.chunk(cid)
            if i % 20000 == 0: log(f'decoded {i}/{len(blocks)} blocks')
        db.clear_caches()
        log('decoded', len(raw), 'blocks,', sum(map(len, raw.values())) >> 20, 'MiB')

        # Family-ordered packing.
        order = []; seen = set()
        for oid in sorted(payload, key=lambda o: (fam[o][0].lstrip('~').casefold(), fam[o][0], o)):
            for _, cid in sorted(refs.get(oid, [])):
                if cid in raw and cid not in seen: seen.add(cid); order.append((fam[oid][0], cid))
        groups = []; cur = []; size = 0; cur_fams = []
        by_fam = collections.OrderedDict()
        for key, cid in order: by_fam.setdefault(key, []).append(cid)
        for key, cids in by_fam.items():
            fsize = sum(len(raw[x]) for x in cids)
            if cur and size + fsize > cap: groups.append((cur, cur_fams)); cur = []; size = 0; cur_fams = []
            for cid in cids:
                if cur and size + len(raw[cid]) > cap: groups.append((cur, cur_fams)); cur = []; size = 0; cur_fams = []
                if key not in cur_fams: cur_fams.append(key)
                cur.append(cid); size += len(raw[cid])
        if cur: groups.append((cur, cur_fams))
        log(len(groups), 'solid groups planned')
        triggers = {n: c.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (n,)).fetchone()[0]
                    for n in ('immutable_chunks_update', 'immutable_compression_groups_delete')}
        for n in triggers: c.execute('DROP TRIGGER ' + n)
        old_groups = {r[0] for r in c.execute('SELECT DISTINCT group_id FROM chunks WHERE group_id IS NOT NULL')}
        workers = a.workers or max(1, min(4, (8 << 30) // (12 * cap)))
        stored = 0; pending = collections.deque()

        def commit(item):
            nonlocal stored
            (cids, fams), fut = item
            encoded, digest, edigest = fut.result()
            ng = db.insert('compression_groups', sha256=digest, encoded_sha256=edigest, size=sum(len(raw[x]) for x in cids), codec=eng.SOLID_CODEC, data=encoded)
            off = 0
            for cid in cids:
                c.execute("UPDATE chunks SET codec='group',data=X'',base_id=NULL,depth=0,group_id=?,group_offset=? WHERE id=?", (ng, off, cid)); off += len(raw[cid])
            for i, f in enumerate(fams): c.execute('INSERT INTO solid_group_families VALUES (?,?,?)', (ng, i, f))
            stored += len(encoded)
        with B.engine_pool(workers, eng) as pool:
            for g in groups:
                pending.append((g, pool.submit(eng.encode_solid, b''.join(raw[x] for x in g[0]), cap)))
                while len(pending) > workers: commit(pending.popleft())
            while pending: commit(pending.popleft())
        orphan = [g for g in old_groups if not c.execute('SELECT 1 FROM chunks WHERE group_id=? LIMIT 1', (g,)).fetchone()]
        c.executemany('DELETE FROM compression_groups WHERE id=?', [(g,) for g in orphan])
        for sql in triggers.values(): c.execute(sql)
        db.clear_caches()
        for (gid,) in c.execute("SELECT id FROM compression_groups WHERE codec='lzma2-solid' ORDER BY id").fetchall():
            db.group(gid)
            for cid, sha in c.execute('SELECT id,sha256 FROM chunks WHERE group_id=?', (gid,)).fetchall():
                if db.chunk(cid) != raw[cid]: raise ValueError(f'block {cid} differs after migration')
            db.clear_caches()
        report.update(blocks_moved=len(raw), solid_groups=len(groups), solid_stored_bytes=stored, v3_groups_removed=len(orphan),
                      v3_groups_kept=len(old_groups) - len(orphan))
        db.event('migrate_v4', details=report)
        c.execute('COMMIT')
    except BaseException:
        c.execute('ROLLBACK'); db.c.close(); a.new.unlink(missing_ok=True); raise
    log('committed; VACUUM'); c.execute('VACUUM'); db.c.close()
    report['seconds'] = round(time.time() - t0); report['new_bytes'] = a.new.stat().st_size
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('old', type=pathlib.Path); ap.add_argument('new', type=pathlib.Path)
    ap.add_argument('--group-mib', type=int, required=True); ap.add_argument('--workers', type=int)
    a = ap.parse_args()
    print(json.dumps(migrate(a.old, a.new, a.group_mib, a.workers), indent=2))


if __name__ == '__main__':
    main()
