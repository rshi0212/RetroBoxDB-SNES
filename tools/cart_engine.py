# ---------------------------------------------------------------------------
# RetroBoxDB cartridge extension: storage v4 solid groups + SNES / Mega Drive.
# This text is appended to the v3 engine (after cart_headers.py) by
# tools/build_cart_db.py; it relies on the names defined above it.
# ---------------------------------------------------------------------------
VERSION = '4.0.0'
SOLID_LIMIT = 32 * CHUNK
SOLID_BLOCK = 65536
SOLID_CODEC = 'lzma2-solid'
SOLID_FILTERS = [{'id': lzma.FILTER_LZMA2, 'dict_size': SOLID_LIMIT, 'lc': 3, 'lp': 0, 'pb': 0,
                  'mode': lzma.MODE_NORMAL, 'nice_len': 273, 'mf': lzma.MF_BT4}]
SOLID_CACHE = 96 * CHUNK
def _snes_cuts(data):
    # Copier-headered dumps: cut after the 512-byte header so body blocks align with headerless dumps.
    return {512} if len(data) % 1024 == 512 else set()


def _md_cuts(data):
    return {512} if len(data) >= 512 and len(data) % 16384 == 512 and data[8:10] == b'\xAA\xBB' else set()


# Per-platform adapter. New cartridge platforms register a parser, hardware table, extensions and block cuts here;
# storage parameters (block size, solid group limit) come from the database meta so each platform can be tuned.
CART_PLATFORMS = {
    'snes': {'name': 'Super Nintendo Entertainment System / Super Famicom', 'parser': parse_snes, 'cuts': _snes_cuts,
             'table': 'snes_hardware', 'rom_ext': ('.sfc', '.smc', '.swc', '.fig', '.bin', '.rom')},
    'megadrive': {'name': 'Sega Mega Drive / Genesis', 'parser': parse_md, 'cuts': _md_cuts,
                  'table': 'md_hardware', 'rom_ext': ('.md', '.gen', '.smd', '.bin', '.rom')},
}


def encode_solid(raw):
    """Encode one family-ordered solid group; round-trip checked before it can be stored."""
    if not raw or len(raw) > SOLID_LIMIT: raise ValueError('Solid group must hold 1 byte..32 MiB')
    encoded = lzma.compress(raw, format=lzma.FORMAT_RAW, filters=SOLID_FILTERS)
    if lzma.decompress(encoded, format=lzma.FORMAT_RAW, filters=SOLID_FILTERS) != raw:
        raise ValueError('Solid group encoder round-trip failure')
    return encoded, hashlib.sha256(raw).digest(), hashlib.sha256(encoded).digest()


def torrentzip_hashes(entries):
    """Checksums of the canonical TorrentZip for in-memory (name, bytes) members."""
    return hashes(make_torrentzip(entries))


RA_CONSOLES = {'snes': 3, 'megadrive': 1}


def ra_hash(platform, data):
    """RetroAchievements content hash (rcheevos rc_hash_snes / plain buffer for Mega Drive)."""
    if platform == 'snes' and len(data) % 0x2000 == 512:
        return hashlib.md5(data[512:]).hexdigest(), 'md5 after 512-byte copier header (rcheevos snes)'
    return hashlib.md5(data).hexdigest(), 'md5 of complete file (rcheevos buffer)'


def split_blocks(data, size=SOLID_BLOCK, cuts=()):
    bounds = sorted({0, len(data)} | {x for x in cuts if 0 < x < len(data)})
    return [data[p:min(p + size, b)] for a, b in zip(bounds, bounds[1:]) for p in range(a, b, size)]


def base_title(name):
    return '~' + re.sub(r'\s*\(.*$', '', name).strip().casefold()


def dat_diff(db, old_ds, new_ds):
    """Classify DAT ROM entries between two snapshots (same rule as the NES reconcile diff)."""
    def rows(ds): return [dict(r) for r in db.c.execute('SELECT dr.* FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id WHERE dg.dat_set_id=? ORDER BY dr.id', (ds,))]
    def signature(r): return tuple(r[k] for k in ('size', 'crc32', 'md5', 'sha1', 'sha256'))
    old = rows(old_ds); new = rows(new_ds)
    by_name = {r['name'].casefold(): r for r in old}; by_sig = {signature(r): r for r in old if r['sha1'] or r['sha256']}
    used = set(); counts = {}
    for t in new:
        prev = by_name.get(t['name'].casefold())
        if prev is None or prev['id'] in used: prev = by_sig.get(signature(t))
        if prev is not None and prev['id'] in used: prev = None
        if prev:
            used.add(prev['id'])
            kind = ('unchanged' if t['name'] == prev['name'] else 'case_changed' if t['name'].casefold() == prev['name'].casefold() else 'renamed') if signature(t) == signature(prev) else 'checksum_changed'
        else: kind = 'added'
        db.insert('dat_changes', old_dat_rom_id=prev['id'] if prev else None, new_dat_rom_id=t['id'], classification=kind,
                  evidence_json=js({'method': 'same casefold filename, then identical full signature', 'same_name_is_not_payload_equality': True}))
        counts[kind] = counts.get(kind, 0) + 1
    for r in old:
        if r['id'] not in used:
            db.insert('dat_changes', old_dat_rom_id=r['id'], classification='removed', evidence_json=js({}))
            counts['removed'] = counts.get('removed', 0) + 1
    db.event('dat_diff', old_dat_set=old_ds, new_dat_set=new_ds, counts=counts)
    return counts


_V3DB = DB


class DB(_V3DB):
    def __init__(self, path):
        BaseDB.__init__(self, path)
        self.storage_version = self.c.execute('PRAGMA user_version').fetchone()[0]
        if self.storage_version not in (2, 3, 4):
            self.c.close(); raise ValueError('This engine requires RetroBoxDB schema 2, 3 or 4')
        self._decoded = collections.OrderedDict(); self._cache_bytes = 0; self._band_index = None
        self._groups = collections.OrderedDict(); self._group_cache_bytes = 0
        self._solid = collections.OrderedDict(); self._solid_bytes = 0
        setting = self.c.execute("SELECT value FROM meta WHERE key='nes_block_size'").fetchone()
        self._rom_block = int(setting[0]) if setting else ROM_BLOCK
        if self._rom_block not in (4096, 8192, 16384, 65536): raise ValueError('Unsupported ROM block size')
        lim = self.c.execute("SELECT value FROM meta WHERE key='solid_group_max_bytes'").fetchone()
        self.solid_limit = min(int(lim[0]), SOLID_LIMIT) if lim else SOLID_LIMIT
        row = self.c.execute('SELECT code FROM platforms WHERE id=1').fetchone()
        self.platform = row[0] if row else None
        self.cart = CART_PLATFORMS.get(self.platform)

    def clear_caches(self):
        super().clear_caches(); self._solid.clear(); self._solid_bytes = 0

    def group(self, gid):
        r = self.c.execute('SELECT sha256,encoded_sha256,size,codec FROM compression_groups WHERE id=?', (gid,)).fetchone()
        if r is None: raise ValueError('Missing compression group')
        if r['codec'] != SOLID_CODEC: return super().group(gid)
        if self.storage_version < 4: raise ValueError('Solid groups require storage schema 4')
        if r['size'] <= 0 or r['size'] > SOLID_LIMIT: raise ValueError('Invalid solid group size')
        key = (r['sha256'], r['encoded_sha256'], r['size'])
        cached = self._solid.get(gid)
        if cached and cached[0] == key: self._solid.move_to_end(gid); return cached[1]
        data = self.c.execute('SELECT data FROM compression_groups WHERE id=?', (gid,)).fetchone()[0]
        if hashlib.sha256(data).digest() != r['encoded_sha256']: raise ValueError('Compressed group checksum mismatch')
        d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=SOLID_FILTERS)
        raw = d.decompress(data, max_length=r['size'] + 1)
        if len(raw) != r['size'] or not d.eof or d.unused_data or hashlib.sha256(raw).digest() != r['sha256']:
            raise ValueError('Solid group integrity failure')
        self._solid[gid] = (key, raw); self._solid_bytes += len(raw)
        while self._solid_bytes > SOLID_CACHE and len(self._solid) > 1:
            _, old = self._solid.popitem(last=False); self._solid_bytes -= len(old[1])
        return raw

    def _seed_bands(self):
        # Similarity bases come from ordinary blocks only; never decode every solid group.
        if self._band_index is not None: return
        self._band_index = {}
        for r in self.c.execute("SELECT id,depth FROM chunks WHERE depth<2 AND codec!='group' AND size BETWEEN 1024 AND 65536").fetchall():
            self._add_bands(r['id'], self.chunk(r['id']), r['depth'])

    def store_chunk(self, raw, encoded=None):
        # Cartridge payload is later packed into solid groups; XOR deltas would only add dependency chains.
        if not self.cart: return super().store_chunk(raw, encoded)
        sha = hashlib.sha256(raw).digest(); old = self.c.execute('SELECT id FROM chunks WHERE sha256=?', (sha,)).fetchone()
        if old:
            if self.chunk(old[0]) != raw: raise ValueError('Hash collision or corrupt block')
            return old[0]
        codec, data = encoded or plain_encoding(raw)
        cid = self.insert('chunks', sha256=sha, size=len(raw), codec=codec, base_id=None, depth=0, data=data)
        self._remember(cid, raw); return cid

    def set_family(self, object_id, key, basis):
        self.c.execute('INSERT OR IGNORE INTO object_families VALUES (?,?,?)', (object_id, key, basis))

    def family_index(self):
        """(crc32,size) -> (family key, basis) from data already in this database (newest DAT first)."""
        index = {}
        sets = self.c.execute('SELECT id,version FROM dat_sets ORDER BY version DESC,id DESC').fetchall()
        for n, ds in enumerate(sets):
            games = {r['name']: r['cloneof'] for r in self.c.execute('SELECT name,cloneof FROM dat_games WHERE dat_set_id=?', (ds['id'],))}
            def top(name):
                seen = set()
                while games.get(name) and games[name] in games and name not in seen: seen.add(name); name = games[name]
                return name
            for r in self.c.execute('SELECT dg.name,dr.crc32,dr.size FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id WHERE dg.dat_set_id=?', (ds['id'],)):
                if r['crc32']: index.setdefault((r['crc32'], r['size']), (top(r['name']), 'dat' if n else 'newest_dat'))
            if n == 0 and self.c.execute("SELECT 1 FROM sqlite_master WHERE name='ni_archives'").fetchone():
                snap = self.c.execute('SELECT max(id) FROM ni_snapshots').fetchone()[0]
                if snap:
                    arch = {r['archive_id']: (r['title'], json.loads(r['attrs_json']).get('clone', 'P')) for r in self.c.execute('SELECT * FROM ni_archives WHERE snapshot_id=?', (snap,))}
                    for r in self.c.execute('SELECT f.crc32,f.size,s.archive_id FROM ni_files f JOIN ni_source_files sf USING(snapshot_id,file_id) JOIN ni_sources s ON s.snapshot_id=sf.snapshot_id AND s.kind=sf.kind AND s.external_id=sf.external_id WHERE f.snapshot_id=?', (snap,)):
                        title, clone = arch[r['archive_id']]
                        index.setdefault((r['crc32'], r['size']), (arch[clone][0] if clone in arch else title, 'nointro_db'))
        return index

    def compact_solid(self, workers=4, progress=None):
        """Pack loose ROM blocks into solid groups by family; repack a family's newest group when it has room.

        Block IDs, SHA256, sizes and object extents never change. Runs in one savepoint; callers VACUUM after commit.
        """
        if self.storage_version < 4: raise ValueError('Solid compaction requires storage schema 4')
        edition = self.c.execute("SELECT value FROM meta WHERE key='payload_available'").fetchone()
        if edition and edition[0] == 'false': raise ValueError('Catalog-only database cannot compact payloads')
        rows = self.c.execute('''SELECT oc.chunk_id,coalesce(f.family_key,'~unassigned') AS family FROM object_chunks oc
            JOIN roms r ON r.object_id=oc.object_id JOIN chunks c ON c.id=oc.chunk_id LEFT JOIN object_families f ON f.object_id=oc.object_id
            WHERE c.codec IN ('raw','zlib','lzma','xor-zlib','xor-lzma') ORDER BY family,oc.object_id,oc.ordinal''').fetchall()
        result = {'loose_blocks': 0, 'groups_created': 0, 'groups_repacked': 0, 'families': 0, 'raw_bytes': 0}
        families = collections.OrderedDict(); seen = set()
        for r in rows:
            if r['chunk_id'] in seen: continue
            seen.add(r['chunk_id']); families.setdefault(r['family'], []).append(r['chunk_id'])
        if not families: return result
        result['loose_blocks'] = len(seen); result['families'] = len(families)
        limit = self.solid_limit
        plans = []; pending = []; pend_fams = []; size = 0
        for fam, cids in families.items():
            sizes = {cid: self.c.execute('SELECT size FROM chunks WHERE id=?', (cid,)).fetchone()[0] for cid in cids}
            new = sum(sizes.values())
            target = self.c.execute('''SELECT g.id,g.size FROM solid_group_families f JOIN compression_groups g ON g.id=f.group_id
                WHERE f.family_key=? AND g.codec=? ORDER BY g.id DESC LIMIT 1''', (fam, SOLID_CODEC)).fetchone()
            if target and target['size'] + new <= limit:
                plans.append(('repack', target['id'], cids, [fam])); continue
            for cid in cids:
                if size + sizes[cid] > limit and pending:
                    plans.append(('new', None, pending, pend_fams)); pending = []; pend_fams = []; size = 0
                if fam not in pend_fams: pend_fams.append(fam)
                pending.append(cid); size += sizes[cid]
        if pending: plans.append(('new', None, pending, pend_fams))
        merged = collections.OrderedDict()  # several families may repack into the same group
        for kind, gid, cids, fams in plans:
            key = (kind, gid) if kind == 'repack' else (kind, id(cids))
            if key in merged: merged[key][2].extend(cids); merged[key][3].extend(f for f in fams if f not in merged[key][3])
            else: merged[key] = [kind, gid, list(cids), list(fams)]
        triggers = {n: self.c.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (n,)).fetchone()
                    for n in ('immutable_chunks_update', 'immutable_compression_groups_delete')}
        if any(v is None for v in triggers.values()): raise ValueError('Missing immutability guards')
        self.c.execute('SAVEPOINT compact_solid')
        try:
            for n in triggers: self.c.execute('DROP TRIGGER ' + n)
            jobs = []; touched = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                for kind, gid, cids, fams in merged.values():
                    base = self.group(gid) if kind == 'repack' else b''
                    if kind == 'repack' and len(base) + sum(len(self.chunk(c)) for c in cids) > limit:
                        kind, gid, base = 'new', None, b''
                    raw = base + b''.join(self.chunk(c) for c in cids)
                    jobs.append((kind, gid, cids, fams, len(base), pool.submit(encode_solid, raw)))
                for kind, gid, cids, fams, base_len, fut in jobs:
                    encoded, digest, edigest = fut.result()
                    size = base_len + sum(self.c.execute('SELECT size FROM chunks WHERE id=?', (c,)).fetchone()[0] for c in cids)
                    ng = self.insert('compression_groups', sha256=digest, encoded_sha256=edigest, size=size, codec=SOLID_CODEC, data=encoded)
                    order = []; touched.append(ng)
                    if kind == 'repack':
                        self.c.execute('UPDATE chunks SET group_id=? WHERE group_id=?', (ng, gid))
                        order = [r[0] for r in self.c.execute('SELECT family_key FROM solid_group_families WHERE group_id=? ORDER BY ordinal', (gid,))]
                        self.c.execute('DELETE FROM solid_group_families WHERE group_id=?', (gid,))
                        self.c.execute('DELETE FROM compression_groups WHERE id=?', (gid,)); result['groups_repacked'] += 1
                    else: result['groups_created'] += 1
                    offset = base_len
                    for c in cids:
                        n = self.c.execute('SELECT size FROM chunks WHERE id=?', (c,)).fetchone()[0]
                        self.c.execute("UPDATE chunks SET codec='group',data=X'',base_id=NULL,depth=0,group_id=?,group_offset=? WHERE id=?", (ng, offset, c))
                        offset += n
                    for i, fam in enumerate(order + [f for f in fams if f not in order]):
                        self.c.execute('INSERT INTO solid_group_families VALUES (?,?,?)', (ng, i, fam))
                    result['raw_bytes'] += size
                    if progress: progress(dict(result))
            for sql in triggers.values(): self.c.execute(sql[0])
            # Independent verification of every block now served by a solid group touched here.
            self.clear_caches()
            for g in touched:
                for (c,) in self.c.execute('SELECT id FROM chunks WHERE group_id=? ORDER BY group_offset', (g,)).fetchall(): self.chunk(c)
            self.event('compact_solid', details=result)
            self.c.execute('RELEASE compact_solid')
        except BaseException:
            self.c.execute('ROLLBACK TO compact_solid'); self.c.execute('RELEASE compact_solid')
            self.clear_caches(); raise
        self.clear_caches()
        return result

    # ---------------------------------------------------------------- solid import
    def missing_blocks(self, data, pending):
        """New 64 KiB blocks of data, in order, skipping stored and already-pending blocks."""
        out = []
        for raw in split_blocks(data, self._rom_block, self.cart['cuts'](data) if self.cart else ()):
            sha = hashlib.sha256(raw).digest()
            if sha in pending: continue
            if self.c.execute('SELECT 1 FROM chunks WHERE sha256=?', (sha,)).fetchone(): continue
            pending.add(sha); out.append((sha, raw))
        return out

    def store_solid_group(self, encoded, digest, encoded_digest, blocks, families):
        """Insert one encoded solid group and its block rows; plaintext identities stay per block."""
        raw_size = sum(len(raw) for _, raw in blocks)
        if raw_size > self.solid_limit: raise ValueError('Solid group exceeds limit')
        gid = self.insert('compression_groups', sha256=digest, encoded_sha256=encoded_digest, size=raw_size, codec=SOLID_CODEC, data=encoded)
        offset = 0
        for sha, raw in blocks:
            if hashlib.sha256(raw).digest() != sha: raise ValueError('Block identity mismatch')
            self.insert('chunks', sha256=sha, size=len(raw), codec='group', base_id=None, depth=0, data=b'', group_id=gid, group_offset=offset)
            offset += len(raw)
        for i, key in enumerate(families):
            self.c.execute('INSERT INTO solid_group_families VALUES (?,?,?)', (gid, i, key))
        return gid

    # ---------------------------------------------------------------- cartridge ROMs
    def rom(self, data, mode='auto'):
        if not self.cart: return super().rom(data, mode)
        if mode == 'auxiliary':
            p = dict(format='auxiliary', parse_status='unclassified', components=[('file', 0, len(data))] if data else [], hardware=None, warnings=[])
        else: p = self.cart['parser'](data)
        oid = self.put_body(data, self.cart['cuts'](data))
        old = self.c.execute('SELECT id FROM roms WHERE object_id=? AND platform_id=1', (oid,)).fetchone()
        if old: return old[0], oid
        rid = self.insert('roms', object_id=oid, platform_id=1, format=p['format'], parse_status=p['parse_status'], header=None,
                          body_object_id=oid, prg_chr_sha256=None, prg_chr_size=None, parser_version=VERSION + '/' + PARSER_VERSION,
                          warnings_json=js(p['warnings']))
        for i, (kind, off, size) in enumerate(p['components']):
            self.insert('rom_components', rom_id=rid, ordinal=i, kind=kind, offset=off, size=size, sha256=hashlib.sha256(data[off:off + size]).hexdigest())
        if p['hardware']: self.insert(self.cart['table'], rom_id=rid, **p['hardware'])
        if mode != 'auxiliary':
            md5, method = ra_hash(self.platform, data)
            self.insert('rom_ra_hashes', rom_id=rid, ra_md5=md5, method=method)
        return rid, oid

    def import_zip_bytes(self, path, original, tz_expected=None, members=None, family=None):
        """Import one source ZIP already read into memory; ZIP bytes are a historical identity only."""
        path = pathlib.Path(path)
        oid, _ = self.object_record(hashes(original), 'archive_manifest')
        fid = self.file(oid, path.name, 'archive', str(path)); result = []; entries = []
        with zipfile.ZipFile(io.BytesIO(original)) as z:
            total = 0
            for i, info in enumerate(z.infolist()):
                if info.is_dir(): entries.append((info.filename, None)); continue
                total += info.file_size
                if info.file_size > MAX_ROM or total > 2 * 1024 ** 3: raise ValueError('ZIP import size limit')
                data = members[i] if members is not None else z.read(info)
                if zlib.crc32(data) != info.CRC: raise ValueError('ZIP member CRC mismatch')
                ext = pathlib.PurePosixPath(info.filename).suffix.lower()
                if ext in self.cart['rom_ext'] or ext == '.sav':
                    rid, obj = self.rom(data, 'auxiliary' if ext == '.sav' else 'auto'); result.append(rid); kind = 'other' if ext == '.sav' else 'rom'
                    if family: self.set_family(obj, *family)
                else: obj = self.put(data); kind = 'other'
                self.file(obj, info.filename, kind, str(path), fid, i, dict(zip_crc=f'{info.CRC:08x}', compression=info.compress_type, flags=info.flag_bits))
                entries.append((info.filename, obj))
        pid = self.plan(entries, tz_expected)
        self.c.execute('INSERT OR IGNORE INTO file_archives VALUES (?,?)', (fid, pid))
        return result

    def import_rom_path(self, path, mode='auto'):
        if not self.cart: return super().import_rom_path(path, mode)
        path = pathlib.Path(path).expanduser().resolve()
        if path.suffix.lower() == '.zip': return self.import_zip_bytes(path, path.read_bytes())
        if path.stat().st_size > MAX_ROM: raise ValueError('ROM too large')
        rid, oid = self.rom(path.read_bytes(), mode); self.file(oid, path.name, path=str(path)); return [rid]

    def audit(self, archives=False, workers=4):
        """v3 audit semantics, visiting objects and archive plans in solid-group order so each group is decoded ~once."""
        if self.storage_version < 4: return super().audit(archives)
        self.clear_caches()
        result = {'integrity_check': [r[0] for r in self.c.execute('PRAGMA integrity_check')], 'foreign_key_errors': [tuple(r) for r in self.c.execute('PRAGMA foreign_key_check')],
                  'objects_checked': 0, 'archive_plans_checked': 0, 'compression_groups_checked': 0,
                  'historical_zip_objects': self.c.execute("SELECT count(*) FROM objects WHERE storage_kind='archive_manifest'").fetchone()[0], 'errors': []}
        for gid, in self.c.execute('SELECT id FROM compression_groups ORDER BY id').fetchall():
            try: self.group(gid)
            except Exception as e: result['errors'].append({'compression_group_id': gid, 'error': str(e)})
            result['compression_groups_checked'] += 1
        locality = '(SELECT min(c.group_id) FROM object_chunks oc JOIN chunks c ON c.id=oc.chunk_id WHERE oc.object_id={})'
        for o in self.c.execute(f"SELECT o.* FROM objects o WHERE storage_kind!='archive_manifest' ORDER BY {locality.format('o.id')},o.id").fetchall():
            try:
                hs = {k: hashlib.new(k) for k in ('sha256', 'sha1', 'md5')}; crc = 0; size = 0
                for b in self.stream(o['id']):
                    size += len(b); crc = zlib.crc32(b, crc)
                    for h in hs.values(): h.update(b)
                actual = {k: h.hexdigest() for k, h in hs.items()}; actual.update(size=size, crc32=f'{crc:08x}')
                if any(actual[k] != o[k] for k in actual): raise ValueError('Object checksum mismatch')
            except Exception as e: result['errors'].append({'object_id': o['id'], 'error': str(e)})
            result['objects_checked'] += 1
        if archives:
            plans = self.c.execute(f'''SELECT p.* FROM archive_plans p ORDER BY (SELECT min({locality.format('ae.object_id')}) FROM archive_entries ae WHERE ae.plan_id=p.id),p.id''').fetchall()
            def check(plan, entries):
                actual = hashes(make_torrentzip(entries))
                return plan['id'], [k for k in actual if actual[k] != plan[k]]
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                pending = collections.deque()
                def drain(n):
                    while len(pending) > n:
                        pid, bad = pending.popleft().result(); result['archive_plans_checked'] += 1
                        if bad: result['errors'].append({'archive_plan_id': pid, 'error': 'regenerated ZIP differs: ' + ','.join(bad)})
                for plan in plans:
                    try:
                        entries = [(r['name'], b'' if r['is_directory'] else self.get(r['object_id'])) for r in self.c.execute('SELECT * FROM archive_entries WHERE plan_id=? ORDER BY ordinal', (plan['id'],)).fetchall()]
                    except Exception as e: result['errors'].append({'archive_plan_id': plan['id'], 'error': str(e)}); continue
                    pending.append(pool.submit(check, plan, entries)); drain(workers * 2)
                drain(0)
        missing = self.c.execute("SELECT count(*) FROM files f LEFT JOIN file_archives fa ON fa.file_id=f.id WHERE f.kind='archive' AND fa.file_id IS NULL").fetchone()[0]
        if missing: result['errors'].append({'missing_archive_plans': missing})
        result['ok'] = result['integrity_check'] == ['ok'] and not result['foreign_key_errors'] and not result['errors']
        return result

    def stats(self):
        out = super().stats(); out['platform'] = self.platform
        if self.storage_version >= 4:
            out['solid_groups'] = dict(self.c.execute("SELECT count(*) AS groups,coalesce(sum(size),0) AS raw_bytes,coalesce(sum(length(data)),0) AS stored_bytes FROM compression_groups WHERE codec=?", (SOLID_CODEC,)).fetchone())
        return out
