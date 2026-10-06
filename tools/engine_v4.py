# ---------------------------------------------------------------------------
# RetroBoxDB storage v4: solid groups and platform adapters (SNES, Mega Drive, GB, GBC, GBA).
# This text is appended to the v3 engine (after rom_headers.py) by
# tools/build_db.py; it relies on the names defined above it.
# ---------------------------------------------------------------------------
VERSION = '4.0.0'
SOLID_LIMIT = 32 * CHUNK          # default group cap and dictionary (SNES / Mega Drive measurements)
SOLID_MAX = 256 * CHUNK           # hard ceiling for any platform; the per-database value lives in meta
SOLID_BLOCK = 65536
SOLID_CODEC = 'lzma2-solid'


def solid_filters(dict_size=SOLID_LIMIT):
    return [{'id': lzma.FILTER_LZMA2, 'dict_size': dict_size, 'lc': 3, 'lp': 0, 'pb': 0,
             'mode': lzma.MODE_NORMAL, 'nice_len': 273, 'mf': lzma.MF_BT4}]


SOLID_FILTERS = solid_filters()
SOLID_CACHE = 96 * CHUNK
REUSE_BYTES = 256 * CHUNK         # audit: object bytes kept per step for the archive plans that use them
BULK_CACHE = 2048 * CHUNK         # decode cache during audits and bulk exports (bounded by the decoded size of all groups)


def _snes_cuts(data):
    # Copier-headered dumps: cut after the 512-byte header so body blocks align with headerless dumps.
    return {512} if len(data) % 1024 == 512 else set()


def _pce_cuts(data):
    return {512} if len(data) % 0x2000 == 512 else set()


def _md_cuts(data):
    return {512} if len(data) >= 512 and len(data) % 16384 == 512 and data[8:10] == b'\xAA\xBB' else set()


# Per-platform adapter. New platforms register a parser, hardware table, extensions and block cuts here;
# storage parameters (block size, solid group limit) come from the database meta so each platform can be tuned.
PLATFORM_ADAPTERS = {
    'snes': {'name': 'Super Nintendo Entertainment System / Super Famicom', 'parser': parse_snes, 'cuts': _snes_cuts,
             'table': 'snes_hardware', 'rom_ext': ('.sfc', '.smc', '.swc', '.fig', '.bin', '.rom')},
    'megadrive': {'name': 'Sega Mega Drive / Genesis', 'parser': parse_md, 'cuts': _md_cuts,
                  'table': 'md_hardware', 'rom_ext': ('.md', '.gen', '.smd', '.bin', '.rom')},
    'gb': {'name': 'Nintendo Game Boy', 'parser': parse_gb, 'cuts': lambda data: set(),
           'table': 'gb_hardware', 'rom_ext': ('.gb', '.gbc', '.sgb', '.bin', '.rom')},
    'gbc': {'name': 'Nintendo Game Boy Color', 'parser': parse_gb, 'cuts': lambda data: set(),
            'table': 'gb_hardware', 'rom_ext': ('.gbc', '.gb', '.cgb', '.bin', '.rom')},
    'gba': {'name': 'Nintendo Game Boy Advance', 'parser': parse_gba, 'cuts': lambda data: set(),
            'table': 'gba_hardware', 'rom_ext': ('.gba', '.agb', '.gbc', '.gb', '.bin', '.srl', '.mb')},
    'satellaview': {'name': 'Nintendo Satellaview', 'parser': parse_bsx, 'cuts': lambda data: set(),
                    'table': 'bsx_hardware', 'rom_ext': ('.bs', '.sfc', '.bin')},
    'fds': {'name': 'Nintendo Family Computer Disk System', 'parser': parse_fds, 'cuts': fds_cuts,
            'table': 'fds_hardware', 'rom_ext': ('.fds', '.qd', '.bin'), 'header_len': lambda d: 16 if d[:4] == b'FDS\x1a' else 0},
    'mastersystem': {'name': 'Sega Master System / Mark III', 'parser': parse_sms, 'cuts': lambda data: set(),
            'table': 'sms_hardware', 'rom_ext': ('.sms', '.bin')},
    'sega32x': {'name': 'Sega 32X', 'parser': parse_32x, 'cuts': _md_cuts, 'table': 'md_hardware', 'rom_ext': ('.32x', '.bin')},
    'wswan': {'name': 'Bandai WonderSwan', 'parser': parse_ws, 'cuts': lambda data: set(), 'table': 'ws_hardware', 'rom_ext': ('.ws', '.bin')},
    'wswanc': {'name': 'Bandai WonderSwan Color', 'parser': parse_ws, 'cuts': lambda data: set(), 'table': 'ws_hardware', 'rom_ext': ('.wsc', '.ws', '.bin')},
    'ngp': {'name': 'SNK NeoGeo Pocket', 'parser': parse_ngp, 'cuts': lambda data: set(), 'table': 'ngp_hardware', 'rom_ext': ('.ngp', '.bin')},
    'ngpc': {'name': 'SNK NeoGeo Pocket Color', 'parser': parse_ngp, 'cuts': lambda data: set(), 'table': 'ngp_hardware', 'rom_ext': ('.ngc', '.ngp', '.bin')},
    'pokemini': {'name': 'Nintendo Pokemon Mini', 'parser': parse_pokemini, 'cuts': lambda data: set(), 'table': 'pokemini_hardware', 'rom_ext': ('.min',)},
    'gamegear': {'name': 'Sega Game Gear', 'parser': parse_sms, 'cuts': lambda data: set(), 'table': 'sms_hardware', 'rom_ext': ('.gg', '.sms', '.bin')},
    'pcengine': {'name': 'NEC PC Engine / TurboGrafx-16', 'parser': parse_pce, 'cuts': _pce_cuts, 'table': 'pce_hardware', 'rom_ext': ('.pce', '.bin')},
    'supergrafx': {'name': 'NEC PC Engine SuperGrafx', 'parser': parse_pce, 'cuts': _pce_cuts, 'table': 'pce_hardware', 'rom_ext': ('.sgx', '.pce', '.bin')},
    'msx1': {'name': 'Microsoft MSX', 'parser': parse_msx, 'cuts': lambda data: set(), 'table': 'msx_hardware', 'rom_ext': ('.rom', '.mx1', '.mx2', '.dsk', '.cas', '.bin')},
    'msx2': {'name': 'Microsoft MSX2', 'parser': parse_msx, 'cuts': lambda data: set(), 'table': 'msx_hardware', 'rom_ext': ('.rom', '.mx2', '.mx1', '.dsk', '.cas', '.bin')},
    'virtualboy': {'name': 'Nintendo Virtual Boy', 'parser': parse_vb, 'cuts': lambda data: set(), 'table': 'vb_hardware', 'rom_ext': ('.vb', '.vboy', '.bin')},
    'gameandwatch': {'name': 'Nintendo Game & Watch', 'parser': parse_plain, 'cuts': lambda data: set(), 'table': None, 'rom_ext': ('.bin',)},
    'supracan': {'name': "Funtech Super A'Can", 'parser': parse_plain, 'cuts': lambda data: set(), 'table': None, 'rom_ext': ('.bin',)},
}


def encode_solid(raw, dict_size=SOLID_LIMIT):
    """Encode one family-ordered solid group; round-trip checked before it can be stored."""
    if not raw or len(raw) > SOLID_MAX or len(raw) > max(dict_size, SOLID_LIMIT): raise ValueError('Solid group size outside the configured limit')
    filters = solid_filters(dict_size)
    encoded = lzma.compress(raw, format=lzma.FORMAT_RAW, filters=filters)
    if lzma.decompress(encoded, format=lzma.FORMAT_RAW, filters=filters) != raw:
        raise ValueError('Solid group encoder round-trip failure')
    return encoded, hashlib.sha256(raw).digest(), hashlib.sha256(encoded).digest()


def torrentzip_hashes(entries):
    """Checksums of the canonical TorrentZip for in-memory (name, bytes) members."""
    return hashes(make_torrentzip(entries))


def ra_hash(platform, data):
    """RetroAchievements content hash (rcheevos rc_hash_nes / rc_hash_fds / rc_hash_snes; plain buffer MD5 for Mega Drive, GB, GBC,
    GBA, Master System, Game Gear, 32X, WonderSwan, NeoGeo Pocket, Pokemon Mini, MSX and Virtual Boy; rc_hash_pce for PC Engine
    and SuperGrafx)."""
    if platform == 'nes' and data[:4] == b'NES\x1a':
        return hashlib.md5(data[16:]).hexdigest(), 'md5 after the 16-byte NES header (rcheevos nes)'
    if platform == 'fds' and data[:4] == b'FDS\x1a':
        return hashlib.md5(data[16:]).hexdigest(), 'md5 after the 16-byte fwNES header (rcheevos fds)'
    if platform in ('snes', 'satellaview') and len(data) % 0x2000 == 512:  # rcheevos hashes BS-X files with the SNES method
        return hashlib.md5(data[512:]).hexdigest(), 'md5 after 512-byte copier header (rcheevos snes)'
    if platform in ('pcengine', 'supergrafx') and len(data) % 0x20000 == 512:
        return hashlib.md5(data[512:]).hexdigest(), 'md5 after 512-byte copier header (rcheevos pce)'
    return hashlib.md5(data).hexdigest(), 'md5 of complete file (rcheevos buffer)'


_HASH_POOL = None


def fast_hashes(data):
    """hashes() with MD5, SHA1, SHA256 and CRC32 computed in parallel threads (hashlib/zlib release the GIL)."""
    global _HASH_POOL
    if len(data) < 1 << 20: return hashes(data)
    if _HASH_POOL is None: _HASH_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    mv = memoryview(data)
    jobs = {k: _HASH_POOL.submit(lambda k=k: hashlib.new(k, mv).hexdigest()) for k in ('sha256', 'sha1', 'md5')}
    crc = _HASH_POOL.submit(lambda: f'{zlib.crc32(mv):08x}')
    return dict(size=len(data), sha256=jobs['sha256'].result(), sha1=jobs['sha1'].result(), md5=jobs['md5'].result(), crc32=crc.result())


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
        self._solid = collections.OrderedDict(); self._solid_bytes = 0; self._fresh = set()
        self._recent = collections.OrderedDict()  # object id -> bytes just imported (archive plans of the same ZIP)
        setting = self.c.execute("SELECT value FROM meta WHERE key='nes_block_size'").fetchone()
        self._rom_block = int(setting[0]) if setting else ROM_BLOCK
        if self._rom_block not in tuple(1 << n for n in range(12, 21)): raise ValueError('Unsupported ROM block size')
        meta = dict(self.c.execute("SELECT key,value FROM meta WHERE key IN ('solid_group_max_bytes','solid_group_dictionary_bytes')").fetchall())
        self.solid_limit = min(int(meta.get('solid_group_max_bytes', SOLID_LIMIT)), SOLID_MAX)
        self.solid_dict = min(int(meta.get('solid_group_dictionary_bytes', SOLID_LIMIT)), SOLID_MAX)
        if self.solid_dict < self.solid_limit: raise ValueError('Solid dictionary must cover the group size')
        self._solid_filters = solid_filters(self.solid_dict)
        self._solid_cache = max(SOLID_CACHE, 2 * self.solid_limit)
        self._bulk = False  # set_bulk_cache(): sweeps decode whole groups, so no partial decoder (and its dictionary) stays alive
        row = self.c.execute('SELECT code FROM platforms WHERE id=1').fetchone()
        self.platform = row[0] if row else None
        self.adapter = PLATFORM_ADAPTERS.get(self.platform)

    def clear_caches(self):
        super().clear_caches(); self._solid.clear(); self._solid_bytes = 0; self._fresh = set()

    def _solid_entry(self, gid):
        """Cached incremental decoder for one solid group: (key, decoder, decoded prefix, encoded bytes, complete)."""
        r = self.c.execute('SELECT sha256,encoded_sha256,size,codec FROM compression_groups WHERE id=?', (gid,)).fetchone()
        if r is None: raise ValueError('Missing compression group')
        if r['codec'] != SOLID_CODEC: return r, None
        if self.storage_version < 4: raise ValueError('Solid groups require storage schema 4')
        if r['size'] <= 0 or r['size'] > self.solid_limit: raise ValueError('Invalid solid group size')
        key = (r['sha256'], r['encoded_sha256'], r['size'])
        e = self._solid.get(gid)
        if e and e['key'] == key: self._solid.move_to_end(gid); return r, e
        data = self.c.execute('SELECT data FROM compression_groups WHERE id=?', (gid,)).fetchone()[0]
        if hashlib.sha256(data).digest() != r['encoded_sha256']: raise ValueError('Compressed group checksum mismatch')
        e = {'key': key, 'd': lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=self._solid_filters),
             'buf': bytearray(), 'data': data, 'complete': False}
        self._solid[gid] = e
        return r, e

    def _solid_full_decoder(self, gid):
        """A callable that decodes and fully verifies solid group `gid` without SQLite or cache access (for a worker
        thread; LZMA and SHA256 release the GIL). Its result is installed with _install_solid. None if not solid."""
        r = self.c.execute('SELECT sha256,encoded_sha256,size,codec,data FROM compression_groups WHERE id=?', (gid,)).fetchone()
        if r is None or r['codec'] != SOLID_CODEC or self.storage_version < 4: return None
        sha, esha, size, data, filters, limit = r['sha256'], r['encoded_sha256'], r['size'], r['data'], self._solid_filters, self.solid_limit

        def work():
            if size <= 0 or size > limit: raise ValueError('Invalid solid group size')
            if hashlib.sha256(data).digest() != esha: raise ValueError('Compressed group checksum mismatch')
            d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters); buf = bytearray(d.decompress(data, max_length=size))
            if len(buf) < size: raise ValueError('Solid group integrity failure (truncated stream)')
            if not d.eof and (d.decompress(b'', max_length=1) or not d.eof): raise ValueError('Solid group integrity failure (longer than recorded)')
            if d.unused_data or hashlib.sha256(buf).digest() != sha: raise ValueError('Solid group integrity failure')
            return {'key': (sha, esha, size), 'd': None, 'buf': buf, 'data': None, 'complete': True}
        return work

    def _install_solid(self, gid, entry):
        self._solid[gid] = entry; self._solid.move_to_end(gid); self._solid_account()

    def _solid_cost(self, e):
        # A group still being decoded also holds its LZMA dictionary window and, before the first read, the encoded bytes.
        live = 0 if e['complete'] or e['d'] is None else self.solid_dict
        return len(e['buf']) + live + (len(e['data']) if e['data'] is not None else 0)

    def _solid_account(self):
        self._solid_bytes = sum(self._solid_cost(e) for e in self._solid.values())
        while self._solid_bytes > self._solid_cache and len(self._solid) > 1:
            _, old = self._solid.popitem(last=False); self._solid_bytes -= self._solid_cost(old)

    def group(self, gid, need=None):
        """Decoded solid group, or at least its first `need` bytes.

        Reads stop decoding at the last byte they need (a group is a single LZMA2 stream); each returned block is
        still verified against its own SHA256 by chunk(). A full decode (need=None) also checks exact length,
        end-of-stream without trailing input and the plaintext SHA256 of the whole group.
        """
        r, e = self._solid_entry(gid)
        if e is None: return super().group(gid)
        size = r['size']; target = size if need is None or self._bulk else min(need, size)
        buf = e['buf']
        while len(buf) < target and not e['d'].eof:
            src = e['data'] if e['data'] is not None and not buf and e['d'].needs_input else b''
            out = e['d'].decompress(src, max_length=target - len(buf))
            if src: e['data'] = None
            if not out and e['d'].needs_input: break
            buf += out
        if len(buf) < target: raise ValueError('Solid group integrity failure (truncated stream)')
        if target == size and not e['complete']:
            if not e['d'].eof:
                extra = e['d'].decompress(b'', max_length=1)
                if extra or not e['d'].eof: raise ValueError('Solid group integrity failure (longer than recorded)')
            if e['d'].unused_data or hashlib.sha256(buf).digest() != r['sha256']: raise ValueError('Solid group integrity failure')
            e['complete'] = True; e['d'] = None  # releases the decoder's dictionary window
        self._solid_account()
        return buf

    def set_bulk_cache(self, limit=BULK_CACHE):
        """Let sweeps (audit, bulk export) keep more decoded groups: objects that reuse blocks from several families
        (multicarts, compilations) then decode each group once instead of evicting and re-decoding."""
        total = self.c.execute('SELECT coalesce(sum(size),0) FROM compression_groups WHERE codec=?', (SOLID_CODEC,)).fetchone()[0]
        self._solid_cache = max(self._solid_cache, min(total, limit)); self._bulk = True

    def stream(self, oid, _seen=()):
        """Objects whose blocks lie in several solid groups are read group by group (each group decoded once, up to the
        last byte needed) and then assembled in order; single-group objects use the incremental path."""
        obj = self.c.execute('SELECT storage_kind,size FROM objects WHERE id=?', (oid,)).fetchone() if self.storage_version >= 4 else None
        if obj is None or obj['storage_kind'] != 'chunks':
            yield from super().stream(oid, _seen); return
        rows = self.c.execute('SELECT oc.ordinal,oc.offset,oc.repeat,oc.chunk_id,c.size,c.sha256,c.group_id,c.group_offset FROM object_chunks oc '
                              'JOIN chunks c ON c.id=oc.chunk_id WHERE oc.object_id=? ORDER BY oc.ordinal', (oid,)).fetchall()
        need = {}
        for r in rows:
            if r['group_id'] is not None: need[r['group_id']] = max(need.get(r['group_id'], 0), r['group_offset'] + r['size'])
        if len(need) <= 1:
            yield from super().stream(oid, _seen); return
        got = {}
        for gid in sorted(need):
            g = self.group(gid, need[gid])
            for r in rows:
                if r['group_id'] == gid and r['chunk_id'] not in got:
                    off, size = r['group_offset'], r['size']
                    if off < 0 or off + size > len(g): raise ValueError('Invalid compression group slice')
                    raw = bytes(g[off:off + size])
                    if hashlib.sha256(raw).digest() != r['sha256']: raise ValueError('Chunk integrity failure')
                    got[r['chunk_id']] = raw
        pos = 0
        for i, r in enumerate(rows):
            if r['offset'] != pos or r['ordinal'] != i: raise ValueError('Invalid object extent order')
            raw = got.get(r['chunk_id'])
            if raw is None: raw = self.chunk(r['chunk_id'])
            for _ in range(r['repeat']): pos += len(raw); yield raw
        if pos != obj['size']: raise ValueError('Incomplete object')

    def chunk(self, cid, seen=()):
        r = self.c.execute('SELECT * FROM chunks WHERE id=?', (cid,)).fetchone()
        if r is None or r['codec'] != 'group': return super().chunk(cid, seen)
        cached = self._decoded.get(cid)
        if cached and cached[0] == r['sha256']: return cached[1]
        offset, size = r['group_offset'], r['size']
        if offset is None or offset < 0: raise ValueError('Invalid compression group slice')
        g = self.group(r['group_id'], offset + size)
        if offset + size > len(g): raise ValueError('Invalid compression group slice')
        raw = bytes(g[offset:offset + size])
        if hashlib.sha256(raw).digest() != r['sha256']: raise ValueError('Chunk integrity failure')
        self._remember(cid, raw); return raw

    def _seed_bands(self):
        # Similarity bases come from ordinary blocks only; never decode every solid group.
        if self._band_index is not None: return
        self._band_index = {}
        for r in self.c.execute("SELECT id,depth FROM chunks WHERE depth<2 AND codec!='group' AND size BETWEEN 1024 AND 65536").fetchall():
            self._add_bands(r['id'], self.chunk(r['id']), r['depth'])

    def store_chunk(self, raw, encoded=None):
        # In storage v4 every ROM block is later packed into a solid group, so XOR deltas (v3) would only add work and
        # dependency chains; v2/v3 NES databases keep the v3 behaviour.
        if not self.adapter and self.storage_version < 4: return super().store_chunk(raw, encoded)
        sha = hashlib.sha256(raw).digest()
        old = self.c.execute('SELECT id,codec,group_id,group_offset,size FROM chunks WHERE sha256=?', (sha,)).fetchone()
        if old:
            # A deduplicated block is compared byte for byte when that is cheap: a loose block, or a grouped block whose
            # group is already decoded in the cache. Otherwise the SHA-256 identity stands; decoding a whole solid group
            # for each hit made imports of mostly-known ROMs (re-dumps, other collections) orders of magnitude slower.
            # Group integrity is checked when groups are encoded (round trip) and by every audit.
            if sha in self._fresh: return old['id']
            if old['codec'] == 'group':
                e = self._solid.get(old['group_id']); off = old['group_offset']
                if e is not None and len(e['buf']) >= off + old['size'] and bytes(e['buf'][off:off + old['size']]) != raw:
                    raise ValueError('Hash collision or corrupt block')
            elif self.chunk(old['id']) != raw: raise ValueError('Hash collision or corrupt block')
            return old['id']
        codec, data = encoded or plain_encoding(raw)
        cid = self.insert('chunks', sha256=sha, size=len(raw), codec=codec, base_id=None, depth=0, data=data)
        self._remember(cid, raw); return cid

    def put_body(self, data, cuts=()):
        if not self.adapter: return super().put_body(data, cuts)
        oid, new = self.object_record(fast_hashes(data))
        if new:
            bounds = sorted({0, len(data)} | {x for x in cuts if 0 <= x <= len(data)})
            self.store_parts(oid, (data[p:min(p + self._rom_block, b)] for a, b in zip(bounds, bounds[1:]) for p in range(a, b, self._rom_block)))
        return oid

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
        # ROM payload objects: the ROM object itself, or (NES) the body object behind a 16-byte header recipe.
        rows = self.c.execute('''SELECT oc.chunk_id,coalesce(f.family_key,'~unassigned') AS family FROM object_chunks oc
            JOIN (SELECT object_id AS pid FROM roms UNION SELECT body_object_id FROM roms WHERE body_object_id IS NOT NULL) p ON p.pid=oc.object_id
            JOIN chunks c ON c.id=oc.chunk_id LEFT JOIN object_families f ON f.object_id=oc.object_id
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
        size_of = {r[0]: r[1] for r in self.c.execute('''SELECT c.id,c.size FROM chunks c WHERE c.codec IN ('raw','zlib','lzma','xor-zlib','xor-lzma')''')}
        for fam, cids in families.items():
            sizes = {cid: size_of[cid] for cid in cids}
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
        if pending:
            # A partly filled last group goes into the newest existing group when it has room (any family), so small
            # additions do not leave small groups behind.
            tail = sum(size_of[c] for c in pending)
            newest = self.c.execute('SELECT id,size FROM compression_groups WHERE codec=? ORDER BY id DESC LIMIT 1', (SOLID_CODEC,)).fetchone()
            if newest and not any(k == 'repack' and g == newest['id'] for k, g, _, _ in plans) and newest['size'] + tail <= limit:
                plans.append(('repack', newest['id'], pending, pend_fams))
            else: plans.append(('new', None, pending, pend_fams))
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
            touched = []; jobs = collections.deque()

            def finish(kind, gid, cids, fams, base_len, fut):
                    encoded, digest, edigest = fut.result()
                    size = base_len + sum(size_of[c] for c in cids)
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
                        n = size_of[c]
                        self.c.execute("UPDATE chunks SET codec='group',data=X'',base_id=NULL,depth=0,group_id=?,group_offset=? WHERE id=?", (ng, offset, c))
                        offset += n
                    for i, fam in enumerate(order + [f for f in fams if f not in order]):
                        self.c.execute('INSERT INTO solid_group_families VALUES (?,?,?)', (ng, i, fam))
                    result['raw_bytes'] += size
                    if progress: progress(dict(result))
            # At most `workers` groups are assembled or being encoded at a time: memory stays bounded by
            # workers x (group + encoder) however much loose data is waiting (a large RA set is several GiB).
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                for kind, gid, cids, fams in merged.values():
                    while len(jobs) >= workers: finish(*jobs.popleft())
                    base = self.group(gid) if kind == 'repack' else b''
                    if kind == 'repack' and len(base) + sum(size_of[c] for c in cids) > limit:
                        kind, gid, base = 'new', None, b''
                    raw = base + b''.join(self.chunk(c) for c in cids); base_len = len(base); base = None
                    jobs.append((kind, gid, cids, fams, base_len, pool.submit(encode_solid, raw, self.solid_dict))); raw = None
                    if kind == 'repack': self._solid.pop(gid, None); self._solid_account()
                while jobs: finish(*jobs.popleft())
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
        for raw in split_blocks(data, self._rom_block, self.adapter['cuts'](data) if self.adapter else ()):
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
            self._fresh.add(sha)
            self.insert('chunks', sha256=sha, size=len(raw), codec='group', base_id=None, depth=0, data=b'', group_id=gid, group_offset=offset)
            offset += len(raw)
        for i, key in enumerate(families):
            self.c.execute('INSERT INTO solid_group_families VALUES (?,?,?)', (gid, i, key))
        return gid

    # ---------------------------------------------------------------- platform ROMs
    def _keep(self, oid, data):
        self._recent[oid] = data; self._recent.move_to_end(oid)
        while len(self._recent) > 64: self._recent.popitem(last=False)

    def put(self, data, header_boundary=False):
        oid = super().put(data, header_boundary); self._keep(oid, data); return oid

    def plan(self, entries, expected=None):
        """As v3, but a new plan's TorrentZip identity is computed from the member bytes just imported (already checked
        against the ZIP CRCs and hashed into their objects) instead of reading them back from solid groups."""
        if expected is None and entries and all(oid is None or oid in self._recent for _, oid in entries):
            norm = normalize_archive_entries(entries)
            expected = hashes(make_torrentzip([(n, b'' if oid is None else self._recent[oid]) for n, oid in norm]))
        return super().plan(entries, expected)

    def rom(self, data, mode='auto'):
        rid, oid = self._rom(data, mode); self._keep(oid, data); return rid, oid

    def _rom(self, data, mode='auto'):
        if not self.adapter: return super().rom(data, mode)
        if mode == 'auxiliary':
            p = dict(format='auxiliary', parse_status='unclassified', components=[('file', 0, len(data))] if data else [], hardware=None, warnings=[])
        else: p = self.adapter['parser'](data)
        oid = self.put_body(data, self.adapter['cuts'](data))
        old = self.c.execute('SELECT id FROM roms WHERE object_id=? AND platform_id=1', (oid,)).fetchone()
        if old: return old[0], oid
        # A copier/emulator header that DATs skip (FDS fwNES): the body after it is its own object; its blocks are the
        # same as the headered file's after the header, so it costs block references only.
        hl = self.adapter.get('header_len', lambda d: 0)(data)
        body = self.put_body(data[hl:], self.adapter['cuts'](data[hl:])) if hl else oid
        rid = self.insert('roms', object_id=oid, platform_id=1, format=p['format'], parse_status=p['parse_status'], header=data[:hl] if hl == 16 else None,
                          body_object_id=body, prg_chr_sha256=None, prg_chr_size=None, parser_version=VERSION + '/' + PARSER_VERSION,
                          warnings_json=js(p['warnings']))
        for i, (kind, off, size) in enumerate(p['components']):
            self.insert('rom_components', rom_id=rid, ordinal=i, kind=kind, offset=off, size=size, sha256=hashlib.sha256(data[off:off + size]).hexdigest())
        if p['hardware']: self.insert(p.get('table', self.adapter['table']), rom_id=rid, **p['hardware'])  # a parser may name another table (BS-X base cartridge)
        if mode != 'auxiliary':
            md5, method = ra_hash(self.platform, data)
            self.insert('rom_ra_hashes', rom_id=rid, ra_md5=md5, method=method)
        return rid, oid

    def package(self, gid, encoded=None):
        """DAT TorrentZip package; members are matched through their immutable object checksums.

        Object checksums were computed from the actual bytes at import and audit re-verifies them, so the
        members are decoded here only when a new archive plan must be encoded (export always re-verifies).
        """
        if (not self.adapter and self.storage_version < 4) or encoded is not None: return super().package(gid, encoded)
        game = self.c.execute('SELECT * FROM dat_games WHERE id=?', (gid,)).fetchone(); entries = []; members = []
        for t in self.c.execute('SELECT * FROM dat_roms WHERE dat_game_id=? ORDER BY ordinal', (gid,)).fetchall():
            v = self.c.execute("SELECT * FROM validations WHERE dat_rom_id=? AND status='match' ORDER BY CASE strength WHEN 'sha256' THEN 0 WHEN 'sha1' THEN 1 ELSE 2 END,rom_id LIMIT 1", (t['id'],)).fetchone()
            if v is None: raise ValueError('Missing verified DAT member ' + t['name'])
            o = self.c.execute('SELECT size,crc32,md5,sha1,sha256 FROM objects WHERE id=?', (v['checked_object_id'],)).fetchone()
            if self.compare(dict(o), t)[0] != 'match': raise ValueError('Stored object identity does not match DAT')
            entries.append((safe_name(t['name']), v['checked_object_id'])); members.append((t['id'], v['rom_id'], v['checked_object_id'], safe_name(t['name'])))
        plan = self.plan(entries)  # encodes (and therefore decodes members) only for a new fingerprint
        h = dict(self.c.execute('SELECT size,crc32,md5,sha1,sha256 FROM archive_plans WHERE id=?', (plan,)).fetchone())
        oid, _ = self.object_record(h, 'archive_manifest')
        fid = self.file(oid, safe_name(game['name']) + '.zip', 'archive', metadata={'profile': 'torrentzip-classic', 'dat_game_id': gid, 'virtual': True})
        self.c.execute('INSERT OR IGNORE INTO file_archives VALUES (?,?)', (fid, plan))
        old = self.c.execute('SELECT id FROM packages WHERE file_id=? AND dat_game_id=?', (fid, gid)).fetchone()
        if old: return old[0]
        pid = self.insert('packages', file_id=fid, dat_game_id=gid, profile_id=1, engine='RetroBoxDB ' + VERSION + '; zlib ' + zlib.ZLIB_RUNTIME_VERSION,
                          validation_json=js({'member_dat_hashes': 'all passed (immutable object checksums)', 'storage': 'virtual', 'archive_plan_id': plan,
                                              'zip_checksums': 'materialized once; verified on export'}), created_at=now())
        for i, m in enumerate(sorted(members, key=lambda m: m[3].lower())):
            self.insert('package_members', package_id=pid, ordinal=i, dat_rom_id=m[0], rom_id=m[1], object_id=m[2], name=m[3])
        return pid

    def import_zip_bytes(self, path, original, tz_expected=None, members=None, family=None):
        """Import one source ZIP already read into memory; ZIP bytes are a historical identity only."""
        path = pathlib.Path(path)
        oid, _ = self.object_record(fast_hashes(original), 'archive_manifest')
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
                if ext in self.adapter['rom_ext'] or ext == '.sav':
                    rid, obj = self.rom(data, 'auxiliary' if ext == '.sav' else 'auto'); result.append(rid); kind = 'other' if ext == '.sav' else 'rom'
                    if family: self.set_family(obj, *family)
                else: obj = self.put(data); kind = 'other'
                self.file(obj, info.filename, kind, str(path), fid, i, dict(zip_crc=f'{info.CRC:08x}', compression=info.compress_type, flags=info.flag_bits))
                entries.append((info.filename, obj))
        pid = self.plan(entries, tz_expected)
        self.c.execute('INSERT OR IGNORE INTO file_archives VALUES (?,?)', (fid, pid))
        return result

    def import_rom_path(self, path, mode='auto'):
        if not self.adapter: return super().import_rom_path(path, mode)
        path = pathlib.Path(path).expanduser().resolve()
        if path.suffix.lower() == '.zip': return self.import_zip_bytes(path, path.read_bytes())
        if path.stat().st_size > MAX_ROM: raise ValueError('ROM too large')
        rid, oid = self.rom(path.read_bytes(), mode); self.file(oid, path.name, path=str(path)); return [rid]

    def storage_positions(self):
        """object_id -> (group_id, group_offset) of the object's first solid-group block. NES header recipes have no
        chunks of their own and take their body's position. Visiting objects in this order decodes each group once,
        front to back (reads decode a group incrementally)."""
        pos = {}
        for oid, gid, off in self.c.execute('SELECT oc.object_id,c.group_id,min(c.group_offset) FROM object_chunks oc JOIN chunks c ON c.id=oc.chunk_id '
                                            'WHERE c.group_id IS NOT NULL GROUP BY oc.object_id,c.group_id'):
            if oid not in pos or gid < pos[oid][0]: pos[oid] = (gid, off)
        for oid, body in self.c.execute('SELECT object_id,body_object_id FROM nes_recipes'):
            if body in pos: pos.setdefault(oid, pos[body])
        return pos

    def audit(self, archives=False, workers=None):
        """v3 audit semantics in one sweep over solid groups: each group is decoded once, and the objects and
        archive plans that start in it are verified while it is cached; then the whole group is checked."""
        if self.storage_version < 4: return super().audit(archives)
        workers = workers or min(8, os.cpu_count() or 4)
        saved_cache = self._solid_cache; self.set_bulk_cache()
        self.clear_caches()
        result = {'integrity_check': [r[0] for r in self.c.execute('PRAGMA integrity_check')], 'foreign_key_errors': [tuple(r) for r in self.c.execute('PRAGMA foreign_key_check')],
                  'objects_checked': 0, 'archive_plans_checked': 0, 'compression_groups_checked': 0,
                  'historical_zip_objects': self.c.execute("SELECT count(*) FROM objects WHERE storage_kind='archive_manifest'").fetchone()[0], 'errors': []}
        pos = self.storage_positions(); first = {oid: g for oid, (g, _) in pos.items()}
        by_group = collections.defaultdict(lambda: ([], []))
        for o in sorted(self.c.execute("SELECT * FROM objects WHERE storage_kind!='archive_manifest'").fetchall(), key=lambda o: (pos.get(o['id'], (0, 0))[1], o['id'])):
            by_group[first.get(o['id'])][0].append(o)
        if archives:
            for p in self.c.execute('SELECT * FROM archive_plans ORDER BY id').fetchall():
                gs = [first.get(r[0]) for r in self.c.execute('SELECT object_id FROM archive_entries WHERE plan_id=? AND object_id IS NOT NULL', (p['id'],))]
                gs = [g for g in gs if g is not None]
                by_group[min(gs) if gs else None][1].append(p)
        groups = [r[0] for r in self.c.execute('SELECT id FROM compression_groups ORDER BY id')]
        order = [None] + groups + sorted(k for k in by_group if k is not None and k not in set(groups))

        def check_plan(plan, entries):
            actual = fast_hashes(make_torrentzip(entries))
            return 'archive_plan_id', plan['id'], ('regenerated ZIP differs: ' + ','.join(k for k in actual if actual[k] != plan[k])) if any(actual[k] != plan[k] for k in actual) else None

        def check_object(o, data):
            actual = fast_hashes(data)
            return 'object_id', o['id'], 'Object checksum mismatch' if any(actual[k] != o[k] for k in actual) else None
        group_set = set(groups); solid_order = [g for g in order if g is not None and (g in group_set or g in by_group)]
        nxt = {a: b for a, b in zip(solid_order, solid_order[1:])}
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool, concurrent.futures.ThreadPoolExecutor(max_workers=1) as decoder:
            pending = collections.deque(); ahead = {}

            def prefetch(g):
                # The next group is decoded and verified in a thread while this one's objects and plans are checked.
                fn = g is not None and self._solid_full_decoder(g)
                if fn: ahead[g] = decoder.submit(fn)
            if solid_order: prefetch(solid_order[0])

            def drain(n):
                # Hashing and TorrentZip regeneration run in the pool; the main thread only decodes and assembles bytes.
                while len(pending) > n:
                    kind, xid, err = pending.popleft().result()
                    result['archive_plans_checked' if kind == 'archive_plan_id' else 'objects_checked'] += 1
                    if err: result['errors'].append({kind: xid, 'error': err})
            for g in order:
                objs, plans = by_group.get(g, ([], []))
                if g in ahead:
                    try: self._install_solid(g, ahead.pop(g).result())
                    except Exception as e: result['errors'].append({'compression_group_id': g, 'error': str(e)})
                if g in nxt: prefetch(nxt[g])
                # Object bytes read in this step are kept for the archive plans that follow, but only for objects those
                # plans use and within REUSE_BYTES; the rest are read again when a plan needs them.
                wanted = {r[0] for plan in plans for r in self.c.execute('SELECT object_id FROM archive_entries WHERE plan_id=? AND object_id IS NOT NULL', (plan['id'],))}
                verified = {}; kept = 0
                for o in objs:
                    try: data = b''.join(self.stream(o['id']))
                    except Exception as e: result['errors'].append({'object_id': o['id'], 'error': str(e)}); result['objects_checked'] += 1; continue
                    if o['id'] in wanted and kept + len(data) <= REUSE_BYTES:
                        verified[o['id']] = data; kept += len(data)  # a mismatch is reported for the object and again by any plan using it
                    pending.append(pool.submit(check_object, o, data)); drain(workers * 2)
                for plan in plans:
                    try:
                        entries = [(r['name'], b'' if r['is_directory'] else verified.get(r['object_id']) or self.get(r['object_id']))
                                   for r in self.c.execute('SELECT * FROM archive_entries WHERE plan_id=? ORDER BY ordinal', (plan['id'],)).fetchall()]
                    except Exception as e: result['errors'].append({'archive_plan_id': plan['id'], 'error': str(e)}); continue
                    pending.append(pool.submit(check_plan, plan, entries)); drain(workers * 2)
                if g is not None and (g in groups or g in by_group):
                    try: self.group(g)  # completes the decode and checks length, end-of-stream and plaintext SHA256
                    except Exception as e: result['errors'].append({'compression_group_id': g, 'error': str(e)})
                    result['compression_groups_checked'] += 1
            drain(0)
        missing = self.c.execute("SELECT count(*) FROM files f LEFT JOIN file_archives fa ON fa.file_id=f.id WHERE f.kind='archive' AND fa.file_id IS NULL").fetchone()[0]
        if missing: result['errors'].append({'missing_archive_plans': missing})
        result['ok'] = result['integrity_check'] == ['ok'] and not result['foreign_key_errors'] and not result['errors']
        self._solid_cache = saved_cache; self._bulk = False; self._solid_account()
        return result

    def stats(self):
        out = super().stats(); out['platform'] = self.platform
        if self.storage_version >= 4:
            out['solid_groups'] = dict(self.c.execute("SELECT count(*) AS groups,coalesce(sum(size),0) AS raw_bytes,coalesce(sum(length(data)),0) AS stored_bytes FROM compression_groups WHERE codec=?", (SOLID_CODEC,)).fetchone())
        return out
