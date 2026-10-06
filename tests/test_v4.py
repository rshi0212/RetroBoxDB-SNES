"""Synthetic tests for the SNES / Mega Drive extension (storage v4). No copyrighted content is used.

python3 -B -m unittest tests/test_v4.py -v   (from the repository root)
"""
import subprocess, hashlib, importlib, io, json, pathlib, random, sqlite3, sys, tempfile, unittest, zipfile, zlib

TOOLS = pathlib.Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import build_db as B  # noqa: E402

_TMP = tempfile.TemporaryDirectory()
_engine_text, _engine_body = B.combined_engine()
(pathlib.Path(_TMP.name) / 'engine.py').write_text(_engine_text)
sys.path.insert(0, _TMP.name)
engine = importlib.import_module('engine')
import nointro_db, import_ra  # noqa: E402  (both resolve `engine` to the combined module above)


def snes_rom(size=512 * 1024, layout='lorom', title=b'SYNTHETIC TEST', seed=1):
    rom = bytearray(random.Random(seed).randbytes(size))
    off = {'lorom': 0x7FC0, 'hirom': 0xFFC0}[layout]
    h = bytearray(0x40); h[:21] = title.ljust(21, b' ')
    h[0x15] = 0x20 if layout == 'lorom' else 0x21; h[0x16] = 0x02; h[0x17] = (size // 1024).bit_length() - 1; h[0x18] = 3
    h[0x19] = 1; h[0x1A] = 0x33; h[0x1B] = 1; h[0x3C:0x3E] = (0x8000).to_bytes(2, 'little')
    rom[off - 0x10:off] = b'ZZ' + b'ATSE' + bytes(10)
    h[0x1C:0x20] = bytes(4); rom[off:off + 0x40] = h
    # Standard trick: complement + checksum always sum to 2*0xFF per byte pair -> compute after placing 0xFFFF/0x0000.
    rom[off + 0x1C:off + 0x20] = b'\xff\xff\x00\x00'
    cks = engine.snes_checksum(bytes(rom))
    rom[off + 0x1C:off + 0x20] = (cks ^ 0xFFFF).to_bytes(2, 'little') + cks.to_bytes(2, 'little')
    return bytes(rom)


def md_rom(size=256 * 1024, seed=2, valid=True):
    rom = bytearray(random.Random(seed).randbytes(size))
    h = bytearray(b' ' * 0x100)
    h[0:16] = b'SEGA MEGA DRIVE '; h[0x10:0x20] = b'(C)TEST 2026.OCT'; h[0x20:0x30] = b'SYNTHETIC DOMESTIC'[:16]
    h[0x50:0x60] = b'SYNTHETIC GLOBAL'; h[0x80:0x8E] = b'GM 00000000-00'
    h[0xA0:0xA8] = (0).to_bytes(4, 'big') + (size - 1).to_bytes(4, 'big'); h[0xA8:0xB0] = bytes.fromhex('00FF0000 00FFFFFF'.replace(' ', ''))
    h[0xB0:0xBC] = b'RA\xf8\x20' + (0x200001).to_bytes(4, 'big') + (0x203FFF).to_bytes(4, 'big'); h[0xF0:0xF3] = b'JUE'
    rom[0x100:0x200] = h
    cks = engine.md_checksum(bytes(rom)) if valid else 0x1234
    rom[0x18E:0x190] = cks.to_bytes(2, 'big')
    return bytes(rom)


def dat_xml(games):
    body = ''.join(f'<game name="{g}"{(" cloneof=%r" % c).replace(chr(39), chr(34)) if c else ""}><description>{g}</description>'
                   f'<rom name="{g}.sfc" size="{len(d)}" crc="{zlib.crc32(d):08x}" md5="{hashlib.md5(d).hexdigest()}" sha1="{hashlib.sha1(d).hexdigest()}"/></game>'
                   for g, c, d in games)
    return f'<?xml version="1.0"?><datafile><header><name>Test (Parent-Clone)</name><version>20260101-000000</version></header>{body}</datafile>'.encode()


def zip_of(name, data):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z: z.writestr(name, data)
    return out.getvalue()


class _Base(unittest.TestCase):
    platform = 'snes'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.tmp.name)
        self.path = self.root / 'full.sqlite'
        B.create(self.path, self.platform, B.schema_v4(self.platform)); self.db = engine.DB(self.path)

    def tearDown(self): self.db.c.close(); self.tmp.cleanup()

    def solid_import(self, files, family='family'):
        pending = set(); blocks = []
        for _, data in files: blocks += self.db.missing_blocks(data, pending)
        with self.db.c:
            if blocks:
                enc = engine.encode_solid(b''.join(b for _, b in blocks))
                self.db.store_solid_group(*enc, blocks, [family])
            for name, data in files:
                raw = zip_of(name, data); path = self.root / (name.rsplit('.', 1)[0] + '.zip'); path.write_bytes(raw)
                self.db.import_zip_bytes(path, raw, engine.torrentzip_hashes([(name, data)]), None, (family, 'dat'))
        return blocks

    def loose_import(self, name, data, family):
        raw = zip_of(name, data); path = self.root / (name.rsplit('.', 1)[0] + '.zip'); path.write_bytes(raw)
        with self.db.c: self.db.import_zip_bytes(path, raw, None, None, (family, 'dat'))


class CartTests(_Base):
    # ------------------------------------------------------------ parsers
    def test_snes_lorom_and_hirom_headers(self):
        for layout in ('lorom', 'hirom'):
            p = engine.parse_snes(snes_rom(layout=layout))
            self.assertEqual(p['parse_status'], 'valid', p['warnings']); h = p['hardware']
            self.assertEqual(h['layout'], layout); self.assertEqual(h['title'], 'SYNTHETIC TEST')
            self.assertEqual(h['maker_code'], 'ZZ'); self.assertEqual(h['game_code'], 'ATSE'); self.assertEqual(h['checksum_valid'], 1)
            self.assertEqual(h['ram_size_declared'], 8192); self.assertEqual(h['region'], 'USA'); self.assertEqual(h['battery'], 1)

    def test_snes_copier_header_kept_and_ra_hash_strips_it(self):
        rom = snes_rom(); data = b'\0' * 512 + rom
        p = engine.parse_snes(data)
        self.assertEqual(p['format'], 'snes_copier'); self.assertEqual(p['components'][0], ('copier_header', 0, 512))
        self.assertEqual(engine.ra_hash('snes', data)[0], hashlib.md5(rom).hexdigest())
        self.assertEqual(engine.ra_hash('megadrive', data)[0], hashlib.md5(data).hexdigest())

    def test_snes_checksum_mirrors_irregular_size(self):
        a = bytes([1]) * (1 << 20); b = bytes([2]) * (1 << 19)
        self.assertEqual(engine.snes_checksum(a + b), (sum(a) + 2 * sum(b)) & 0xFFFF)
        self.assertIsNone(engine.snes_checksum(bytes(3 * 7 * 1024)))

    def test_md_header_valid_mismatch_and_absent(self):
        p = engine.parse_md(md_rom()); h = p['hardware']
        self.assertEqual(p['parse_status'], 'valid', p['warnings']); self.assertEqual(h['serial'], 'GM 00000000-00')
        self.assertEqual(h['sram_start'], 0x200001); self.assertEqual(h['regions'], 'JUE')
        self.assertEqual(engine.md_checksum(md_rom()), engine._md_checksum_fast(md_rom()))
        self.assertEqual(engine.parse_md(md_rom(valid=False))['parse_status'], 'warning')
        self.assertEqual(engine.parse_md(bytes(4096))['parse_status'], 'unclassified')
        smd = bytearray(16384 + 512); smd[8:10] = b'\xAA\xBB'
        self.assertEqual(engine.parse_md(bytes(smd))['format'], 'smd_interleaved')

    # ------------------------------------------------------------ storage v4
    def test_solid_group_roundtrip_dedup_and_export(self):
        a = snes_rom(seed=5); b = bytearray(a); b[0x1234] ^= 0xFF; b = bytes(b)
        blocks = self.solid_import([('A (Japan).sfc', a), ('A (Japan) (Rev 1).sfc', b), ('A (USA).sfc', a)])
        self.assertEqual(len(blocks), 9)  # 8 blocks of A + one differing block of B; identical ROM adds none
        self.assertEqual(self.db.c.execute("SELECT count(*) FROM chunks WHERE codec!='group'").fetchone()[0], 0)
        fid = self.db.c.execute("SELECT id FROM files WHERE original_name='A (Japan) (Rev 1).sfc'").fetchone()[0]
        out = self.root / 'out.sfc'; self.db.export(fid, out); self.assertEqual(out.read_bytes(), b)
        zfid = self.db.c.execute("SELECT id FROM files WHERE original_name='A (USA).zip'").fetchone()[0]
        zout = self.root / 'out.zip'; self.db.export(zfid, zout)
        with zipfile.ZipFile(zout) as z: self.assertEqual(z.read('A (USA).sfc'), a); self.assertTrue(z.comment.startswith(b'TORRENTZIPPED-'))
        audit = self.db.audit(archives=True); self.assertTrue(audit['ok'], audit)
        self.assertEqual(self.db.c.execute('SELECT count(*) FROM snes_hardware').fetchone()[0], 2)
        self.assertEqual(self.db.c.execute('SELECT count(*) FROM rom_ra_hashes').fetchone()[0], 2)

    def test_corrupt_solid_group_is_detected(self):
        self.solid_import([('C.sfc', snes_rom(seed=9))])
        self.db.c.execute('DROP TRIGGER immutable_compression_groups_update')
        data = bytearray(self.db.c.execute('SELECT data FROM compression_groups').fetchone()[0]); data[len(data) // 2] ^= 0x55
        with self.db.c: self.db.c.execute('UPDATE compression_groups SET data=?', (bytes(data),))
        self.db.clear_caches(); audit = self.db.audit()
        self.assertFalse(audit['ok']); self.assertTrue(any('checksum' in e.get('error', '') for e in audit['errors']))

    def test_solid_group_size_limits(self):
        with self.assertRaises(ValueError): engine.encode_solid(b'')
        with self.assertRaises(sqlite3.IntegrityError), self.db.c:
            self.db.insert('compression_groups', sha256=bytes(32), encoded_sha256=bytes(32), size=B.PLATFORMS[self.platform]['solid'] + 1, codec='lzma2-solid', data=b'x')
        with self.assertRaises(sqlite3.IntegrityError), self.db.c:
            self.db.insert('compression_groups', sha256=bytes(32), encoded_sha256=bytes(32), size=(2 << 20) + 1, codec='lzma2-4m', data=b'x')

    def test_object_across_groups_decodes_each_group_once(self):
        a = snes_rom(seed=31); b = snes_rom(seed=32); k = 65536
        self.solid_import([('A (USA).sfc', a)], 'a'); self.solid_import([('B (USA).sfc', b)], 'b')
        mixed = b''.join((a if i % 2 == 0 else b)[i * k:(i + 1) * k] for i in range(len(a) // k))  # multicart-like: blocks of both groups
        self.assertEqual(self.solid_import([('M (USA).sfc', mixed)], 'm'), [])
        oid = self.db.c.execute('SELECT object_id FROM files WHERE original_name=?', ('M (USA).sfc',)).fetchone()[0]
        self.assertEqual(len({r[0] for r in self.db.c.execute('SELECT c.group_id FROM object_chunks oc JOIN chunks c ON c.id=oc.chunk_id WHERE oc.object_id=?', (oid,))}), 2)
        self.db.clear_caches(); self.db._solid_cache = 1  # keeps a single group: block-order reads would alternate and re-decode
        fresh = []; entry = self.db._solid_entry
        self.db._solid_entry = lambda gid: (fresh.append(gid) if gid not in self.db._solid else None, entry(gid))[1]
        self.assertEqual(self.db.get(oid), mixed)
        self.assertEqual(sorted(fresh), sorted(set(fresh)))
        self.db.set_bulk_cache(); self.assertGreaterEqual(self.db._solid_cache, sum(r[0] for r in self.db.c.execute('SELECT size FROM compression_groups')))
        self.assertTrue(self.db.audit(archives=True)['ok'])

    def test_reimport_of_grouped_blocks_decodes_no_group(self):
        a = snes_rom(seed=41); self.solid_import([('A (USA).sfc', a)], 'a')
        self.db.clear_caches(); decoded = []; entry = self.db._solid_entry
        self.db._solid_entry = lambda gid: (decoded.append(gid), entry(gid))[1]
        self.loose_import('A (USA) (Copy).sfc', a, 'a')  # every block already stored in a solid group
        self.assertEqual(decoded, [])
        self.db._solid_entry = entry
        oid = self.db.c.execute('SELECT object_id FROM files WHERE original_name=?', ('A (USA) (Copy).sfc',)).fetchone()[0]
        self.assertEqual(self.db.get(oid), a)

    def test_v3_engine_rejects_v4_database(self):
        ns = {'__name__': 'v3'}; exec(compile((TOOLS / 'base' / 'engine.py').read_text(), 'v3', 'exec'), ns)
        with self.assertRaises(ValueError): ns['DB'](self.path)

    # ------------------------------------------------------------ DAT, No-Intro DB, RA, catalog
    def test_dat_scan_diff_nointro_ra_and_catalog(self):
        a = snes_rom(seed=11); b = snes_rom(seed=12)
        self.solid_import([('Game (Japan).sfc', a)])
        old = self.root / 'old.dat'; old.write_bytes(dat_xml([('Game (Japan)', None, a)]))
        new = self.root / 'new.dat'; new.write_bytes(dat_xml([('Game (Japan) (Renamed)', None, a), ('Other (USA)', None, b)]))
        with self.db.c:
            o = self.db.import_dat_path(old)[0]; n = self.db.import_dat_path(new)[0]
            self.assertEqual(self.db.scan(n)['match'], 1)
            self.assertEqual(engine.dat_diff(self.db, o, n), {'renamed': 1, 'added': 1})
            cat = B.build_catalog_records(self.db, n, [o])
        self.assertEqual((cat['games'], cat['releases'], cat['old_dat_games_linked'], cat['rom_release_links']), (2, 2, 1, 1))
        files = f'<file id="1" extension="sfc" size="{len(a)}" crc32="{zlib.crc32(a):08x}" md5="{hashlib.md5(a).hexdigest()}" sha1="{hashlib.sha1(a).hexdigest()}" header="!none" format="Default"/>'
        export = (f'<?xml version="1.0"?><header><version>20260102-000000</version></header><datafile><game name="Game (Japan) (Renamed)">'
                  f'<archive number="0001" clone="P" name="Game" name_alt="ゲーム" region="Japan"/><source><details id="7" section="Trusted Dump"/>'
                  f'<serials pcb_serial="SHVC-1A0N-01"/>{files}</source></game></datafile>').encode()
        (self.root / 'db.xml').write_bytes(export)
        (self.root / 'log.csv').write_text('"ID";"Name";"Size";"MD5";"Status"\n"0001";"Game (Japan) (Renamed)";"%d";"%s";"Trusted (2) (Verified)"\n' % (len(a), hashlib.md5(a).hexdigest()))
        with self.db.c: rep = nointro_db.import_snapshot(self.db, self.root / 'db.xml', self.root / 'log.csv')
        self.assertEqual((rep['files_with_local_payload'], rep['hardware_assertions'], rep['archive_release_links']), (1, 1, 1))
        self.assertEqual(rep['anomalies'], {'file_without_sha256': 1})
        self.assertIsNone(self.db.c.execute('SELECT sha256 FROM ni_files').fetchone()[0])
        ra = json.dumps([{'ID': 99, 'Title': 'Game', 'ConsoleID': 3, 'NumAchievements': 5, 'Hashes': [hashlib.md5(a).hexdigest()]},
                         {'ID': 98, 'Title': '~Hack~ Other', 'ConsoleID': 3, 'NumAchievements': 1, 'Hashes': [hashlib.md5(b).hexdigest(), 'f' * 32]}]).encode()
        with self.db.c: rr = import_ra.import_snapshot(self.db.c, 'snes', ra, 'now')
        self.assertEqual((rr['local_roms_matched'], rr['dat_entries_matched'], rr['hashes_with_achievements_unexplained']), (1, 3, 1))  # old+new DAT entries of A, new entry of B
        self.assertEqual(self.db.c.execute('SELECT ra_category FROM v_dat_ra_matches WHERE ra_game_id=98').fetchone()[0], 'Hack')
        with self.db.c: B.put_resource(self.db.c, 'engine.py', 'python', _engine_text)
        self.db.c.execute('VACUUM'); self.db.c.close()
        cat_engine = self.root / 'catalog_engine.py'; cat_engine.write_text(_engine_body + '\n' + (TOOLS / 'base' / 'catalog_wrapper.py').read_text())
        sys.path.insert(0, str(TOOLS / 'base')); bc = importlib.import_module('build_catalog')
        rep = bc.build(self.path, self.root / 'catalog.sqlite', cat_engine)
        self.assertEqual(rep['integrity_check'], 'ok'); self.assertEqual(rep['foreign_key_errors'], [])
        c = sqlite3.connect(self.root / 'catalog.sqlite')
        for t in ('chunks', 'object_chunks', 'compression_groups'): self.assertEqual(c.execute(f'SELECT count(*) FROM {t}').fetchone()[0], 0)
        self.assertEqual(c.execute('SELECT count(*) FROM solid_group_families').fetchone()[0], 1)
        self.assertEqual(c.execute('SELECT count(*) FROM v_rom_ra_matches').fetchone()[0], 1)
        ns = {'__name__': 'catalog'}; exec(compile(c.execute("SELECT content FROM resources WHERE name='engine.py'").fetchone()[0], 'cat', 'exec'), ns); c.close()
        cdb = ns['DB'](self.root / 'catalog.sqlite'); self.assertTrue(cdb.audit()['ok'])
        with self.assertRaises(ValueError): cdb.get(1)
        self.db = engine.DB(self.path)


class IncrementalTests(_Base):
    def test_new_revision_repacks_family_group_and_new_family_gets_own_group(self):
        a = snes_rom(seed=21); self.solid_import([('Fam (Japan).sfc', a)], 'Fam (Japan)')
        g1 = self.db.c.execute('SELECT id FROM compression_groups').fetchone()[0]
        rev = bytearray(a); rev[0x30000:0x30000] = b'INSERTED'; rev = bytes(rev[:len(a)])  # shifted data: no block dedup
        other = snes_rom(seed=22)
        self.loose_import('Fam (Japan) (Rev 1).sfc', rev, 'Fam (Japan)'); self.loose_import('Other (USA).sfc', other, 'Other (USA)')
        loose = self.db.c.execute("SELECT count(*) FROM chunks WHERE codec!='group'").fetchone()[0]
        self.assertGreater(loose, 0)
        with self.db.c: r = self.db.compact_solid(workers=2)
        self.assertEqual((r['groups_repacked'], r['groups_created']), (1, 1)); self.assertEqual(r['loose_blocks'], loose)
        self.assertEqual(self.db.c.execute("SELECT count(*) FROM chunks WHERE codec!='group'").fetchone()[0], 0)
        self.assertIsNone(self.db.c.execute('SELECT 1 FROM compression_groups WHERE id=?', (g1,)).fetchone())
        fams = self.db.c.execute('SELECT group_concat(family_key) FROM solid_group_families GROUP BY group_id ORDER BY group_id').fetchall()
        self.assertEqual([f[0] for f in fams], ['Fam (Japan)', 'Other (USA)'])
        for name, data in (('Fam (Japan).sfc', a), ('Fam (Japan) (Rev 1).sfc', rev), ('Other (USA).sfc', other)):
            fid = self.db.c.execute('SELECT id FROM files WHERE original_name=?', (name,)).fetchone()[0]
            out = self.root / ('x' + name); self.db.export(fid, out); self.assertEqual(out.read_bytes(), data)
        self.assertTrue(self.db.audit(archives=True)['ok'])
        with self.db.c: self.assertEqual(self.db.compact_solid()['loose_blocks'], 0)  # idempotent

    def test_copier_header_version_shares_body_blocks(self):
        rom = snes_rom(seed=31); self.solid_import([('H (USA).sfc', rom)])
        new = self.db.missing_blocks(b'\x00' * 512 + rom, set())
        self.assertEqual([len(b) for _, b in new], [512])

    def test_new_dat_extends_releases(self):
        upd = importlib.import_module('update_db')
        a = snes_rom(seed=41); b = snes_rom(seed=42); c = snes_rom(seed=43)
        self.solid_import([('P (Japan).sfc', a), ('C (USA).sfc', b), ('N (USA).sfc', c)])
        d1 = self.root / 'd1.dat'; d1.write_bytes(dat_xml([('P (Japan)', None, a), ('C (USA)', 'P (Japan)', b)]))
        d2 = self.root / 'd2.dat'; d2.write_bytes(dat_xml([('P (Japan)', None, a), ('C (USA) (Rev 1)', 'P (Japan)', b), ('N (USA)', 'P (Japan)', c)]).replace(b'20260101-000000', b'20260201-000000'))
        with self.db.c:
            o = self.db.import_dat_path(d1)[0]; self.db.scan(o); B.build_catalog_records(self.db, o, [])
            n = self.db.import_dat_path(d2)[0]; self.db.scan(n)
            self.assertEqual(engine.dat_diff(self.db, o, n), {'unchanged': 1, 'renamed': 1, 'added': 1})
            self.assertEqual(upd.extend_catalog(self.db, n, o), {'linked': 2, 'releases_added': 1})
            self.assertEqual(upd.link_roms(self.db), 1)
            self.assertEqual(self.db.import_dat_path(d2)[0], n)  # re-import is a no-op
        self.assertEqual(self.db.c.execute('SELECT count(DISTINCT game_id) FROM releases').fetchone()[0], 1)


class AuditRegressionTests(_Base):
    """Locks behaviours the 2026-10-04 audit found unprotected by tests (mutation survivors and findings)."""

    def test_zip_member_crc_lie_is_rejected(self):  # C12
        data = snes_rom(seed=51); raw = zip_of('L.sfc', data); path = self.root / 'L.zip'; path.write_bytes(raw)
        lie = bytearray(data); lie[100] ^= 1
        with self.assertRaises(ValueError), self.db.c: self.db.import_zip_bytes(path, raw, None, {0: bytes(lie)})
        self.assertEqual(self.db.c.execute('SELECT count(*) FROM roms').fetchone()[0], 0)

    def test_family_index_prefers_newest_dat(self):  # C07
        a = snes_rom(seed=52)
        old = self.root / 'old.dat'; old.write_bytes(dat_xml([('A1 (Japan)', None, a)]))
        new = self.root / 'new.dat'; new.write_bytes(dat_xml([('B2 (Japan)', None, a)]).replace(b'20260101-000000', b'20260301-000000'))
        with self.db.c: self.db.import_dat_path(new); self.db.import_dat_path(old)
        crc = f'{zlib.crc32(a):08x}'
        self.assertEqual(self.db.family_index()[(crc, len(a))], ('B2 (Japan)', 'newest_dat'))

    def test_snes_low_score_header_is_unclassified(self):  # C04
        rom = bytearray(random.Random(53).randbytes(512 * 1024))
        rom[0x7FC0:0x7FD5] = b'ONLY A TITLE HERE    '; rom[0x7FD5] = 0x20  # mode + title, no checksum pair
        rom[0x7FDC:0x7FE0] = b'\x12\x34\x56\x78'; rom[0xFFDC:0xFFE0] = b'\x9a\xbc\xde\xf0'
        p = engine.parse_snes(bytes(rom))
        self.assertEqual(p['parse_status'], 'unclassified'); self.assertIsNone(p['hardware'])

    def test_nes_magic_required_in_headered_mode(self):  # M12
        p = engine.parse_nes(b'NES\x00' + bytes(12) + bytes(16384), 'headered')
        self.assertEqual(p['parse_status'], 'invalid'); self.assertIsNone(p['header'])

    def test_torrentzip_canonical_bytes(self):  # M02/M03/M14/M16
        import struct
        z = engine.make_torrentzip([('b.bin', b'abc' * 100), ('A.bin', b''), ('dir/c.txt', b'x')])
        self.assertEqual(hashlib.sha256(z).hexdigest(), '05e74dc7d303d1f830a5f6c908ab3c7fc3f1cb37803641092ba12e1394de5e6b')
        sig, ver, flag, method, dtime, ddate = struct.unpack_from('<IHHHHH', z, 0)
        self.assertEqual((sig, ver, flag, method, dtime, ddate), (0x04034b50, 20, 2, 8, 48128, 8600))
        with zipfile.ZipFile(io.BytesIO(z)) as zz:
            self.assertEqual(zz.namelist(), ['A.bin', 'b.bin', 'dir/c.txt'])  # lowercase sort, case preserved
            info = zz.getinfo('b.bin'); start = info.header_offset + 30 + len('b.bin')
            co = zlib.compressobj(9, zlib.DEFLATED, -15, 8, zlib.Z_DEFAULT_STRATEGY)
            self.assertEqual(z[start:start + info.compress_size], co.compress(b'abc' * 100) + co.flush())
        self.assertRegex(z[-22:].decode(), r'^TORRENTZIPPED-[0-9A-F]{8}$')

    def test_audit_detects_corrupt_object_and_missing_plan(self):  # M19
        self.solid_import([('O.sfc', snes_rom(seed=54))])
        self.assertTrue(self.db.audit(archives=True)['ok'])
        self.db.c.execute('DROP TRIGGER immutable_objects_update')
        with self.db.c: self.db.c.execute("UPDATE objects SET md5='0'||substr(md5,2) WHERE storage_kind='chunks'")
        a = self.db.audit(); self.assertFalse(a['ok']); self.assertTrue(any('mismatch' in e.get('error', '') for e in a['errors']))
        with self.db.c:
            oid, _ = self.db.object_record(engine.hashes(b'not a zip'), 'archive_manifest'); self.db.file(oid, 'orphan.zip', 'archive')
        self.assertIn({'missing_archive_plans': 1}, self.db.audit()['errors'])

    def test_export_rejects_tampered_identity_and_leaves_no_file(self):  # M10, F-24
        self.solid_import([('E.sfc', snes_rom(seed=55))])
        fid = self.db.c.execute("SELECT id FROM files WHERE original_name='E.sfc'").fetchone()[0]
        with self.assertRaises(ValueError): self.db.export(fid, self.root / 'missing-dir' / 'x.sfc')
        self.db.c.execute('DROP TRIGGER immutable_objects_update')
        with self.db.c: self.db.c.execute("UPDATE objects SET sha1='0'||substr(sha1,2) WHERE id=(SELECT object_id FROM files WHERE id=?)", (fid,))
        out = self.root / 'tampered.sfc'
        with self.assertRaises(ValueError): self.db.export(fid, out)
        self.assertFalse(out.exists())

    def test_dat_size_out_of_range_is_value_error(self):  # F-22
        bad = b'<datafile><header><name>X</name></header><game name="G"><rom name="g.sfc" size="99999999999999999999" crc="00000000"/></game></datafile>'
        with self.assertRaises(ValueError), self.db.c: self.db.import_dat(bad, 'bad.dat', 'auto')

    def test_safe_name_rejects_format_characters(self):  # F-23
        for name in ('evil\u202egnp.sfc', 'zero\u200bwidth.sfc', '../x.sfc', 'a:b.sfc'):
            with self.assertRaises(ValueError): engine.safe_name(name)
        self.assertEqual(engine.safe_name('Pokémon - Edición Azul (Spain).gb'), 'Pokémon - Edición Azul (Spain).gb')

    def test_naming_decisions_only_for_full_file_scope(self):  # F-01, on an NES (storage v3) database
        path = self.root / 'nes.sqlite'; c = sqlite3.connect(path); c.executescript((TOOLS / 'base' / 'schema.sql').read_text())
        with c:
            c.execute("INSERT INTO meta VALUES ('nes_block_size','8192')"); c.execute("INSERT INTO platforms(id,code,name) VALUES (1,'nes','NES')")
            c.execute('INSERT INTO archive_profiles VALUES (?,?,?,?,?)', json.loads((TOOLS / 'base' / 'seed.json').read_text()))
        c.close(); db = engine.DB(path)
        try:
            body = bytes(range(256)) * 64; data = b'NES\x1a' + bytes([1, 0]) + bytes(10) + body
            def dat(mode, name, blob):
                return (f'<datafile><header><name>T ({mode})</name></header><game name="T"><rom name="{name}" size="{len(blob)}" '
                        f'crc="{zlib.crc32(blob):08x}" sha1="{hashlib.sha1(blob).hexdigest()}"/></game></datafile>').encode()
            with db.c:
                rid, oid = db.rom(data, 'headered'); db.file(oid, 'local name.nes')
                hl = db.import_dat(dat('Headerless', 'T.unh', body), 'hl.dat', 'auto'); hd = db.import_dat(dat('Headered', 'T.nes', data), 'hd.dat', 'auto')
                self.assertEqual((db.scan(hl)['match'], db.scan(hd)['match']), (1, 1))
            names = [r[0] for r in db.c.execute('SELECT canonical_name FROM naming_decisions')]
            self.assertEqual(names, ['T.nes'])  # never the headerless .unh name for the headered file
        finally: db.c.close()

    def test_dat_package_uses_object_identity_and_exports_canonical_zip(self):
        a = snes_rom(seed=56); self.solid_import([('Different local name.sfc', a)])
        d = self.root / 'p.dat'; d.write_bytes(dat_xml([('Pkg (USA)', None, a)]))
        with self.db.c: ds = self.db.import_dat_path(d)[0]; self.db.scan(ds)
        gid = self.db.c.execute('SELECT id FROM dat_games WHERE dat_set_id=?', (ds,)).fetchone()[0]
        with self.db.c: pid = self.db.package(gid); self.assertEqual(self.db.package(gid), pid)
        fid = self.db.c.execute('SELECT file_id FROM packages WHERE id=?', (pid,)).fetchone()[0]
        out = self.root / 'pkg.zip'; self.db.export(fid, out)
        with zipfile.ZipFile(out) as z: self.assertEqual((z.namelist(), z.read('Pkg (USA).sfc')), (['Pkg (USA).sfc'], a))
        self.db.c.execute('DROP TRIGGER immutable_objects_update')
        with self.db.c: self.db.c.execute("UPDATE objects SET sha1='0'||substr(sha1,2) WHERE sha256=?", (hashlib.sha256(a).hexdigest(),))
        with self.assertRaises(ValueError): self.db.package(gid)  # identity is compared before any existing package is reused

    def test_casefold_name_keys(self):  # F-26
        names = importlib.import_module('import_game_names')
        self.assertEqual(names.match_key('Straße (Germany)'), names.match_key('STRASSE (Germany)'))


def gb_rom(size=128 * 1024, seed=61, cgb=0x80, ctype=0x1B):
    rom = bytearray(random.Random(seed).randbytes(size))
    rom[0x134:0x144] = b'SYNTHGAME  ABCD' + bytes([cgb]); rom[0x144:0x146] = b'01'; rom[0x146] = 0; rom[0x147] = ctype
    rom[0x148] = (size // 32768).bit_length() - 1; rom[0x149] = 3; rom[0x14A] = 1; rom[0x14B] = 0x33; rom[0x14C] = 2
    rom[0x14D] = engine.gb_header_checksum(bytes(rom))
    rom[0x14E:0x150] = ((sum(rom) - rom[0x14E] - rom[0x14F]) & 0xFFFF).to_bytes(2, 'big')
    return bytes(rom)


def gba_rom(size=1 << 20, seed=62, pad=256 * 1024):
    rom = bytearray(random.Random(seed).randbytes(size - pad)) + b'\xff' * pad
    rom[0xA0:0xAC] = b'SYNTHETICGBA'; rom[0xAC:0xB0] = b'ZZZE'; rom[0xB0:0xB2] = b'01'; rom[0xB2] = 0x96; rom[0xB3:0xBD] = bytes(10)
    rom[0xBD] = engine.gba_complement(bytes(rom)); rom[0x1000:0x100C] = b'FLASH1M_V103'
    return bytes(rom)


class GameBoyTests(_Base):
    platform = 'gbc'

    def test_gb_header_fields(self):
        p = engine.parse_gb(gb_rom()); h = p['hardware']
        self.assertEqual((p['parse_status'], p['format'], h['title'], h['manufacturer_code'], h['cgb_mode']), ('valid', 'gbc', 'SYNTHGAME', 'ABCD', 'cgb_enhanced'))
        self.assertEqual((h['cartridge_type_name'], h['battery'], h['rumble'], h['ram_size_declared'], h['licensee_new']), ('MBC5+RAM+BATTERY', 1, 0, 32768, '01'))
        bad = bytearray(gb_rom()); bad[0x14D] ^= 1
        self.assertIn('header checksum invalid; fields may not describe this dump', engine.parse_gb(bytes(bad))['warnings'])
        self.assertEqual(engine.parse_gb(bytes(256))['parse_status'], 'unclassified')
        self.assertEqual(engine.parse_gb(gb_rom(cgb=0))['format'], 'gb')

    def test_gb_platform_roundtrip_and_ra_hash(self):
        a = gb_rom(seed=63); self.solid_import([('G (USA).gbc', a)])
        row = self.db.c.execute('SELECT * FROM v_gb_headers').fetchone()
        self.assertEqual((row['cgb_mode'], row['logo_is_common'], row['header_checksum_valid']), ('cgb_enhanced', 1, 1))
        self.assertEqual(self.db.c.execute('SELECT ra_md5 FROM rom_ra_hashes').fetchone()[0], hashlib.md5(a).hexdigest())
        self.assertTrue(self.db.audit(archives=True)['ok'])


def fds_side(code=b'ABC', rev=1, side=0, size=65500, seed=0, qd=False):
    info = bytes([1]) + b'*NINTENDO-HVC*' + bytes([0xA4]) + code + b' ' + bytes([rev, side, 0, 0, 0, 15]) + b'\xff' * 5 + bytes.fromhex('611201') + bytes([0x49])
    info += bytes(56 - len(info))
    body = info + (b'\x00\x00' if qd else b'') + bytes([2, 3])
    return body + random.Random(seed * 2 + side).randbytes(size - len(body))


def fds_image(qd=False, seed=1, header=False):
    size = 65536 if qd else 65500
    d = b''.join(fds_side(side=n, size=size, seed=seed, qd=qd) for n in range(2))
    return (b'FDS\x1a\x02' + bytes(11) + d) if header else d


class FamicomDiskSystemTests(_Base):
    platform = 'fds'

    def test_fds_qd_bios_parsing(self):
        p = engine.parse_fds(fds_image()); h = p['hardware']
        self.assertEqual((p['format'], p['parse_status'], h['sides'], h['valid_sides'], h['game_code'], h['revision'], h['manufacturing_date']),
                         ('fds', 'valid', 2, 2, 'ABC', 1, '1986-12-01'))
        self.assertEqual(json.loads(h['sides_json'])[1]['file_amount'], 3)
        q = engine.parse_fds(fds_image(qd=True))
        self.assertEqual((q['format'], q['hardware']['side_size'], json.loads(q['hardware']['sides_json'])[0]['file_amount']), ('qd', 65536, 3))
        hd = engine.parse_fds(fds_image(header=True))
        self.assertEqual((hd['hardware']['fwnes_header'], hd['hardware']['fwnes_sides'], hd['parse_status']), (1, 2, 'valid'))
        self.assertEqual(engine.parse_fds(bytes(8192))['format'], 'bios')
        self.assertEqual(sorted(engine.fds_cuts(fds_image(header=True))), [16, 16 + 65500])

    def test_fds_headered_and_headerless_share_sides_and_ra_hash(self):
        plain = fds_image(seed=5); headered = fds_image(seed=5, header=True)
        self.solid_import([('D (Japan).fds', plain)], 'd')
        new = self.solid_import([('D (Japan) (fwNES).fds', headered)], 'd')
        self.assertEqual([d for _, d in new], [headered[:16]])  # only the fwNES header is new; both sides deduplicate
        rows = {r[0]: r[1] for r in self.db.c.execute('SELECT f.original_name,h.ra_md5 FROM files f JOIN roms r ON r.object_id=f.object_id JOIN rom_ra_hashes h ON h.rom_id=r.id')}
        self.assertEqual(rows['D (Japan).fds'], hashlib.md5(plain).hexdigest()); self.assertEqual(rows['D (Japan) (fwNES).fds'], hashlib.md5(plain).hexdigest())
        shared = self.db.c.execute('''SELECT count(DISTINCT a.chunk_id) FROM object_chunks a JOIN object_chunks b ON a.chunk_id=b.chunk_id AND a.object_id<b.object_id''').fetchone()[0]
        self.assertEqual(shared, 2)  # both sides are stored once
        self.assertTrue(self.db.audit(archives=True)['ok'])

    def test_fds_header_skip_dat_rule(self):
        plain = fds_image(seed=9); headered = fds_image(seed=9, header=True)
        self.solid_import([('H (Japan) (fwNES).fds', headered)], 'h')
        dat = (f'<?xml version="1.0"?><datafile><header><name>Nintendo - Family Computer Disk System (FDS) (Parent-Clone)</name><version>20260101-000000</version>'
               f'<clrmamepro header="No-Intro_FDS.xml"/></header><game name="H (Japan)"><description>H</description><rom name="H (Japan).fds" size="{len(plain)}" '
               f'crc="{zlib.crc32(plain):08x}" sha1="{hashlib.sha1(plain).hexdigest()}"/></game></datafile>').encode()
        with self.db.c:
            ds = self.db.import_dat(dat, 'f.dat', 'auto'); counts = self.db.scan(ds)
        self.assertEqual(tuple(self.db.c.execute('SELECT mode,hash_scope FROM dat_sets WHERE id=?', (ds,)).fetchone()), ('headerless', 'fds_after_header'))
        self.assertEqual(counts['match'], 1)
        r = self.db.c.execute('SELECT header,body_object_id,object_id FROM roms').fetchone()
        self.assertEqual(bytes(r['header']), headered[:16]); self.assertNotEqual(r['body_object_id'], r['object_id'])
        self.assertEqual(self.db.get(r['body_object_id']), plain)
        with self.assertRaises(ValueError):  # other header-skip rules stay unsupported
            self.db.import_dat(dat.replace(b'No-Intro_FDS.xml', b'Other.xml'), 'g.dat', 'auto')

    def test_qd_dat_joins_fds_release(self):
        fds, qd = fds_image(seed=7), fds_image(seed=7, qd=True)
        self.solid_import([('Game (Japan).fds', fds), ('Game (Japan).qd', qd)])
        def dat(name, ext, data):
            return (f'<?xml version="1.0"?><datafile><header><name>{name} (Parent-Clone)</name><version>20260101-000000</version></header>'
                    f'<game name="Game (Japan)"><description>G</description><rom name="Game (Japan).{ext}" size="{len(data)}" crc="{zlib.crc32(data):08x}" '
                    f'sha1="{hashlib.sha1(data).hexdigest()}"/></game></datafile>').encode()
        with self.db.c:
            a = self.db.import_dat(dat('Nintendo - Family Computer Disk System (FDS)', 'fds', fds), 'f.dat', 'auto')
            b = self.db.import_dat(dat('Nintendo - Family Computer Disk System (QD)', 'qd', qd), 'q.dat', 'auto')
            for ds in (a, b): self.db.scan(ds)
            B.build_catalog_records(self.db, a, []); st = B.link_format(self.db, b, [], a)
        self.assertEqual(st, {'joined_same_name': 1})
        self.assertEqual(B.dat_format(B.PLATFORMS['fds'], 'Nintendo - Family Computer Disk System (QD) (Parent-Clone)'), 1)
        self.assertEqual(tuple(self.db.c.execute('SELECT count(DISTINCT release_id),count(*) FROM rom_releases').fetchone()), (1, 2))


def bsx_pack(seed=3, base=0xFFB0, size=1 << 20):
    d = bytearray(random.Random(seed).randbytes(size)); h = bytearray(0x30)
    h[0:2] = b'01'; h[2:6] = bytes([0, 1, 0, 0]); h[0x10:0x20] = b'BS TEST TITLE   '; h[0x20:0x24] = bytes([15, 0, 0, 0])
    h[0x26] = 5 << 4; h[0x27] = 20 << 3; h[0x28] = 0x21 if base == 0xFFB0 else 0x20; h[0x29] = 0x30; h[0x2A] = 0x33; h[0x2B] = 2
    h[0x2C:0x2E] = (0xFFFF ^ 0x1234).to_bytes(2, 'little'); h[0x2E:0x30] = (0x1234).to_bytes(2, 'little')
    d[base:base + 0x30] = h; return bytes(d)


class SatellaviewTests(_Base):
    platform = 'satellaview'

    def test_bsx_header_and_base_cartridge(self):
        p = engine.parse_bsx(bsx_pack()); h = p['hardware']
        self.assertEqual((p['format'], p['parse_status'], h['mapping'], h['maker_code'], h['title'], h['broadcast_month'], h['broadcast_day'], h['checksum_pair_valid']),
                         ('bs', 'valid', 'hirom', '01', 'BS TEST TITLE', 5, 20, 1))
        self.assertEqual(engine.parse_bsx(bsx_pack(base=0x7FB0))['hardware']['mapping'], 'lorom')
        self.assertEqual(engine.parse_bsx(bytes(1 << 20))['parse_status'], 'unclassified')
        cart = snes_rom(seed=101); b = engine.parse_bsx(cart)
        self.assertEqual((b['format'], b['table']), ('snes_cartridge', 'snes_hardware'))
        self.solid_import([('P (Japan).bs', bsx_pack(seed=4)), ('[BIOS] BS-X (Japan).sfc', cart)])
        self.assertEqual(self.db.c.execute('SELECT count(*) FROM bsx_hardware').fetchone()[0], 1)
        self.assertEqual(self.db.c.execute('SELECT count(*) FROM snes_hardware').fetchone()[0], 1)
        self.assertTrue(self.db.audit(archives=True)['ok'])

    def test_ra_report_sibling_and_shared_console(self):
        rr = importlib.import_module('ra_report')
        mine = bsx_pack(seed=6); self.solid_import([('Mine (Japan).bs', mine)])
        other = self.root / 'snes.sqlite'; B.create(other, 'snes', B.schema_v4('snes')); sdb = engine.DB(other)
        theirs = snes_rom(seed=102)
        raw = zip_of('Theirs (Japan).sfc', theirs); zp = self.root / 't.zip'; zp.write_bytes(raw)
        with sdb.c: sdb.import_zip_bytes(zp, raw, None, None, None)
        sdb.c.close()
        ra = importlib.import_module('import_ra')
        resp = [{'ID': 1, 'ConsoleID': 3, 'Title': 'Mine', 'NumAchievements': 5, 'Hashes': [hashlib.md5(mine).hexdigest()]},
                {'ID': 2, 'ConsoleID': 3, 'Title': 'Theirs', 'NumAchievements': 5, 'Hashes': [hashlib.md5(theirs).hexdigest()]},
                {'ID': 3, 'ConsoleID': 3, 'Title': 'Nobody', 'NumAchievements': 5, 'Hashes': ['0' * 32]}]
        with self.db.c: ra.import_snapshot(self.db.c, 'satellaview', json.dumps(resp).encode(), '2026-10-05T00:00:00+00:00')
        out = rr.main(str(self.path), str(self.root / 'r'), {'snes': str(other)}, False)
        self.assertEqual(out['status_totals'], {'local': 1, 'local_other_platform': 1, 'dat_only': 0, 'nointro_db_only': 0, 'unmatched': 1})
        self.assertEqual(rr.main(str(self.path), str(self.root / 'r2'), {'snes': str(other)}, True)['ra_games_with_achievements'], 1)


class GameBoyAdvanceTests(_Base):
    platform = 'gba'

    def test_gba_header_padding_and_save_ids(self):
        p = engine.parse_gba(gba_rom()); h = p['hardware']
        self.assertEqual((p['parse_status'], h['title'], h['game_code'], h['save_types'], h['padding_byte'], h['padding_bytes']),
                         ('valid', 'SYNTHETICGBA', 'ZZZE', 'FLASH1M_V103', 0xFF, 256 * 1024))
        self.assertEqual(p['components'][-1], ('padding', (1 << 20) - 256 * 1024, 256 * 1024))
        unaligned = bytearray(gba_rom()); unaligned[0x2001:0x200D] = b'SRAM_V113XXX'
        self.assertEqual(engine.parse_gba(bytes(unaligned))['hardware']['save_types'], 'FLASH1M_V103')
        nofix = bytearray(gba_rom()); nofix[0xB2] = 0
        self.assertEqual(engine.parse_gba(bytes(nofix))['parse_status'], 'unclassified')

    def test_gba_padding_blocks_dedup_to_one(self):
        a = gba_rom(size=2 << 20, seed=64, pad=1 << 20); b = gba_rom(size=2 << 20, seed=65, pad=1 << 20)
        blocks = self.solid_import([('A (USA).gba', a), ('B (USA).gba', b)])
        per_rom = (1 << 20) // self.db._rom_block  # 1 MiB of content each; the padding shares one block
        self.assertEqual(len(blocks), 2 * per_rom + 1)
        self.assertTrue(self.db.audit(archives=True)['ok'])
        self.assertEqual(self.db.c.execute('SELECT count(*) FROM v_gba_headers WHERE padding_bytes=1048576').fetchone()[0], 2)

    def test_platform_storage_settings_come_from_meta(self):
        self.assertEqual((self.db.solid_limit, self.db.solid_dict), (B.PLATFORMS['gba']['solid'], B.PLATFORMS['gba']['dictionary']))


def sms_rom(size=0x20000, seed=70, offset=0x7FF0, sdsc=False):
    rom = bytearray(random.Random(seed).randbytes(size))
    h = bytearray(b'TMR SEGA' + bytes(8)); h[12:14] = bytes([0x34, 0x12]); h[14] = 0x51; h[15] = 0x4F  # product 51234, version 1, export, 128 KiB
    rom[offset:offset + 16] = h
    if sdsc:
        rom[0x7FE0:0x7FF0] = b'SDSC' + bytes([1, 0, 1, 6, 0x26, 0x20]) + bytes(2) + (0x100).to_bytes(2, 'little') + bytes(2)
        rom[0x100:0x10A] = b'HOMEBREW\x00\x00'
    if offset == 0x7FF0: rom[offset + 10:offset + 12] = engine.sms_checksum(bytes(rom), 0x20000).to_bytes(2, 'little')
    return bytes(rom)


def ws_rom(size=1 << 20, seed=71, color=1):
    rom = bytearray(random.Random(seed).randbytes(size))
    rom[-16:] = bytes([0xEA, 0, 0, 0xFE, 0xFF, 0, 0x24, color, 3, 0, 0x03, 0x20, 0x05, 0x00, 0, 0])
    rom[-2:] = (sum(rom[:-2]) & 0xFFFF).to_bytes(2, 'little')
    return bytes(rom)


def ngp_rom(size=1 << 20, seed=72, color=0x10):
    rom = bytearray(random.Random(seed).randbytes(size))
    rom[:0x40] = b' LICENSED BY SNK CORPORATION' + (0x200040).to_bytes(4, 'little') + (0x0053).to_bytes(2, 'little') + bytes([0, color]) + b'SYNTH POCKET' + bytes(16)
    return bytes(rom)


def pokemini_rom(size=1 << 19, seed=73):
    rom = bytearray(random.Random(seed).randbytes(size))
    rom[0x2100:0x2102] = b'MN'; rom[0x21A4:0x21BE] = b'NINTENDO' + b'MZZE' + b'SYNTH MINI\x00\x00' + b'2P'
    return bytes(rom)


class NewCartridgePlatformTests(_Base):
    """Master System, 32X, WonderSwan, NeoGeo Pocket and Pokemon Mini headers (2026-10-06 platforms)."""
    platform = 'wswanc'

    def test_sms_header_checksum_and_variants(self):
        p = engine.parse_sms(sms_rom()); h = p['hardware']
        self.assertEqual((p['parse_status'], h['header_offset'], h['region'], h['size_declared'], h['product_code'], h['version'], h['checksum_valid']),
                         ('valid', 0x7FF0, 'SMS Export', 0x20000, '51234', 1, 1))
        self.assertEqual(engine.parse_sms(sms_rom(offset=0x3FF0))['parse_status'], 'warning')  # export BIOS reads only 0x7FF0
        self.assertEqual(engine.parse_sms(bytes(0x8000))['parse_status'], 'unclassified')     # Mark III cartridges without header
        self.assertEqual(engine.parse_sms(sms_rom(sdsc=True))['hardware']['sdsc_title'], 'HOMEBREW')
        bad = bytearray(sms_rom()); bad[5] ^= 1
        self.assertIn('declared checksum differs from computed checksum', engine.parse_sms(bytes(bad))['warnings'])
        gg = bytearray(sms_rom()); gg[0x7FFF] = (gg[0x7FFF] & 0x0F) | 0x60; gg[0x7FFA:0x7FFC] = b'\0\0'  # GG Export, checksum 0
        self.assertEqual((engine.parse_sms(bytes(gg))['parse_status'], engine.parse_sms(bytes(gg))['hardware']['region']), ('valid', 'GG Export'))
        gg[0x7FFF] = (gg[0x7FFF] & 0x0F) | 0x40  # SMS Export with checksum 0
        self.assertEqual(engine.parse_sms(bytes(gg))['warnings'], ['no checksum declared (0)'])

    def test_32x_uses_md_header_and_tolerates_zero_checksum(self):
        rom = bytearray(md_rom(size=1 << 20, seed=74)); rom[0x100:0x110] = b'SEGA 32X        '; rom[0x3C0:0x3D0] = b'MARS CHECK MODE '
        rom[0x18E:0x190] = engine.md_checksum(bytes(rom)).to_bytes(2, 'big')
        p = engine.parse_32x(bytes(rom)); self.assertEqual((p['format'], p['parse_status'], p['table'] if 'table' in p else 'md_hardware'), ('32x', 'valid', 'md_hardware'))
        rom[0x18E:0x190] = b'\0\0'; rom[0x100:0x110] = b'SEGA MEGA DRIVE '  # many retail 32X cartridges
        self.assertEqual(engine.parse_32x(bytes(rom))['warnings'], ['no checksum declared (0)'])

    def test_ws_footer_ngp_and_pokemini_headers(self):
        p = engine.parse_ws(ws_rom()); h = p['hardware']
        self.assertEqual((p['format'], h['publisher_id'], h['rom_size_declared'], h['save_type'], h['save_size'], h['orientation'], h['bus_width'], h['checksum_valid']),
                         ('wsc', 0x24, 1 << 20, 'EEPROM', 2048, 'vertical', 8, 1))
        self.assertEqual(engine.parse_ws(ws_rom(color=0))['format'], 'ws')
        n = engine.parse_ngp(ngp_rom()); self.assertEqual((n['format'], n['hardware']['licensed'], n['hardware']['title'], n['hardware']['software_id']), ('ngpc', 1, 'SYNTH POCKET', 0x53))
        self.assertEqual(engine.parse_ngp(bytes(4096))['parse_status'], 'unclassified')  # BIOS / unheadered
        m = engine.parse_pokemini(pokemini_rom()); self.assertEqual((m['parse_status'], m['hardware']['game_code'], m['hardware']['region_code'], m['hardware']['two_player']), ('valid', 'MZZE', 'E', 1))

    def test_wsc_platform_roundtrip_ra_hash_and_settings(self):
        a = ws_rom(seed=75); self.solid_import([('W (Japan).wsc', a)])
        row = self.db.c.execute('SELECT * FROM v_ws_headers').fetchone()
        self.assertEqual((row['format'], row['color'], row['checksum_valid']), ('wsc', 1, 1))
        self.assertEqual(self.db.c.execute('SELECT ra_md5 FROM rom_ra_hashes').fetchone()[0], hashlib.md5(a).hexdigest())
        self.assertEqual((self.db.solid_limit, self.db.solid_dict), (B.PLATFORMS['wswanc']['solid'], B.PLATFORMS['wswanc']['dictionary']))
        self.assertTrue(self.db.audit(archives=True)['ok'])
        self.assertEqual(importlib.import_module('import_ra').CONSOLES['wswanc'], importlib.import_module('import_ra').CONSOLES['wswan'])


class NormalizeTests(_Base):
    platform = 'wswan'

    def test_normalize_code_meta_and_idempotence(self):
        nd = importlib.import_module('normalize_db'); self.db.c.close()
        c = sqlite3.connect(self.path)
        with c:  # an old abbreviated code and a stale storage description
            c.execute("UPDATE platforms SET code='ws'"); c.execute("UPDATE frontend_platforms SET platform_code='ws'")
            c.execute("UPDATE meta SET value='ws' WHERE key='platform'"); c.execute("UPDATE meta SET value='stale' WHERE key='storage'")
            c.execute("DELETE FROM meta WHERE key='game_names_extension_version'")
        c.close()
        r = nd.normalize(self.path, 'wswan')
        self.assertEqual(sorted(r['changes']), ['meta.game_names_extension_version', 'meta.platform', 'meta.storage', 'platform_code'])
        c = sqlite3.connect(self.path); meta = dict(c.execute('SELECT key,value FROM meta'))
        self.assertEqual((c.execute('SELECT code FROM platforms').fetchone()[0], meta['platform']), ('wswan', 'wswan'))
        self.assertEqual(meta['storage'], B.storage_text('wswan', B.PLATFORMS['wswan']['block'], B.PLATFORMS['wswan']['solid'], B.PLATFORMS['wswan']['dictionary']))
        self.assertEqual(c.execute("SELECT count(*) FROM events WHERE action='normalize_db'").fetchone()[0], 1); c.close()
        self.assertEqual(nd.normalize(self.path)['changes'], {})  # idempotent
        with self.assertRaises(SystemExit): nd.normalize(self.path, 'ws')  # codes must be Batocera system names
        self.db = engine.DB(self.path)


class RetuneTests(_Base):
    def test_retune_merges_groups_and_keeps_every_identity(self):
        retune = importlib.import_module('retune_db')
        files = [(f'R{i} (USA).sfc', snes_rom(seed=70 + i)) for i in range(3)]
        for name, data in files: self.solid_import([(name, data)], family=name)
        before = self.db.c.execute("SELECT count(*) FROM compression_groups").fetchone()[0]
        blocks = self.db.c.execute('SELECT id,sha256,size FROM chunks ORDER BY id').fetchall()
        self.db.c.execute('UPDATE meta SET value=? WHERE key=?', (str(1 << 20), 'solid_group_max_bytes'))  # tiny caps for the test
        self.db.c.execute('UPDATE meta SET value=? WHERE key=?', (str(1 << 20), 'solid_group_dictionary_bytes')); self.db.c.commit(); self.db.c.close()
        rep = retune.retune(self.path, 2, workers=1, eng=engine)
        self.db = engine.DB(self.path)
        self.assertEqual((before, rep['groups_after']), (3, 1))
        self.assertEqual([tuple(r) for r in self.db.c.execute('SELECT id,sha256,size FROM chunks ORDER BY id')], [tuple(r) for r in blocks])
        self.assertEqual(self.db.c.execute("SELECT group_concat(family_key) FROM solid_group_families").fetchone()[0], 'R0 (USA).sfc,R1 (USA).sfc,R2 (USA).sfc')
        self.assertTrue(self.db.audit(archives=True)['ok'])
        for name, data in files:
            fid = self.db.c.execute('SELECT id FROM files WHERE original_name=?', (name,)).fetchone()[0]
            out = self.root / ('o' + name); self.db.export(fid, out); self.assertEqual(out.read_bytes(), data)


class MaintenanceTests(_Base):
    def test_small_new_family_joins_newest_group(self):
        a = snes_rom(seed=81); self.solid_import([('A (USA).sfc', a)], 'A (USA)')
        b = snes_rom(seed=82); self.loose_import('B (USA).sfc', b, 'B (USA)')
        with self.db.c: r = self.db.compact_solid(workers=1)
        self.assertEqual((r['groups_repacked'], r['groups_created']), (1, 0))
        self.assertEqual(self.db.c.execute('SELECT count(*) FROM compression_groups').fetchone()[0], 1)
        self.assertEqual(self.db.c.execute("SELECT group_concat(family_key) FROM solid_group_families").fetchone()[0], 'A (USA),B (USA)')
        self.assertTrue(self.db.audit(archives=True)['ok'])

    def test_retune_same_cap_consolidates_only(self):
        retune = importlib.import_module('retune_db')
        for i in range(3): self.solid_import([(f'C{i} (USA).sfc', snes_rom(seed=90 + i))], family=f'C{i}')
        sizes = [r[0] for r in self.db.c.execute('SELECT size FROM compression_groups ORDER BY id')]
        cap = 1 << 20; self.assertLessEqual(sizes[0] + sizes[1], cap); self.assertGreater(sum(sizes), cap)
        with self.db.c:
            for k in ('solid_group_max_bytes', 'solid_group_dictionary_bytes'): self.db.c.execute('UPDATE meta SET value=? WHERE key=?', (str(cap), k))
        last = self.db.c.execute('SELECT id,encoded_sha256 FROM compression_groups ORDER BY id DESC LIMIT 1').fetchone(); self.db.c.close()
        rep = retune.retune(self.path, 1, workers=1, eng=engine)
        self.db = engine.DB(self.path)
        self.assertEqual(rep['groups_after'], 2)
        self.assertEqual(tuple(self.db.c.execute('SELECT id,encoded_sha256 FROM compression_groups WHERE id=?', (last[0],)).fetchone()), tuple(last))  # left alone
        self.assertTrue(self.db.audit(archives=True)['ok'])

    def test_shared_block_family_and_other_platform_files(self):
        U = importlib.import_module('update_db')
        a = snes_rom(seed=95); self.solid_import([('Orig (USA).sfc', a)], 'Orig (USA)')
        hack = a[:-65536] + random.Random(5).randbytes(65536)  # a hack: last bank changed
        raw = zip_of('Orig (USA) (Hack).sfc', hack); path = self.root / 'h.zip'; path.write_bytes(raw)
        other = snes_rom(seed=96); raw2 = zip_of('New (USA).sfc', other); path2 = self.root / 'n.zip'; path2.write_bytes(raw2)
        with self.db.c:
            self.db.import_zip_bytes(path, raw, None, None, None); self.db.import_zip_bytes(path2, raw2, None, None, None)
        oid = lambda n: self.db.c.execute('SELECT object_id FROM files WHERE original_name=?', (n,)).fetchone()[0]
        self.assertEqual(U.shared_block_family(self.db, oid('Orig (USA) (Hack).sfc')), ('Orig (USA)', 'shared_blocks'))
        self.assertIsNone(U.shared_block_family(self.db, oid('New (USA).sfc')))
        self.assertIn('.fds', U.OTHER_PLATFORM_EXT['nes']); self.assertIn('.bs', U.OTHER_PLATFORM_EXT['snes'])
        self.assertIn('.nes', U.OTHER_PLATFORM_EXT['fds'])


class ExportSetTests(_Base):
    def test_duplicate_dat_member_exported_once(self):
        a = snes_rom(seed=111); self.solid_import([('Dup (Japan).sfc', a)])
        rom = f'<rom name="Dup (Japan).sfc" size="{len(a)}" crc="{zlib.crc32(a):08x}" sha1="{hashlib.sha1(a).hexdigest()}"/>'
        dat = f'<?xml version="1.0"?><datafile><header><name>T (Parent-Clone)</name><version>20260101-000000</version></header><game name="Dup (Japan)"><description>D</description>{rom}{rom}</game></datafile>'
        with self.db.c: ds = self.db.import_dat(dat.encode(), 't.dat', 'auto'); self.db.scan(ds)
        self.db.c.close()
        out = self.root / 'exp'
        for container in ('rom', 'torrentzip'):
            r = subprocess.run([sys.executable, '-B', str(TOOLS / 'export_set.py'), str(self.path), str(out / container), '--set', 'all', '--container', container, '--engine-file', engine.__file__], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-500:] + r.stdout[-500:])
            m = json.loads((out / container / 'export-manifest.json').read_text())
            self.assertEqual((m['exported'], len(m['errors']), m['duplicate_members'][0]['exported']), (1, 0, 1))
        self.db = engine.DB(self.path)


class NesMigrationTests(unittest.TestCase):
    """v3 NES database (header recipes, headered/headerless bodies, v3 groups) -> storage v4."""

    def test_migrate_v3_nes_keeps_identities_recipes_and_exports(self):
        mig = importlib.import_module('migrate_v4')
        tmp = tempfile.TemporaryDirectory(); root = pathlib.Path(tmp.name); old = root / 'nes-v3.sqlite'
        c = sqlite3.connect(old); c.executescript((TOOLS / 'base' / 'schema.sql').read_text())
        with c:
            c.execute("INSERT INTO meta VALUES ('nes_block_size','8192')"); c.execute("INSERT INTO platforms(id,code,name) VALUES (1,'nes','NES')")
            c.execute('INSERT INTO archive_profiles VALUES (?,?,?,?,?)', json.loads((TOOLS / 'base' / 'seed.json').read_text()))
        c.close()
        ns = {'__name__': 'v3engine'}; exec(compile((TOOLS / 'base' / 'engine.py').read_text(), 'v3', 'exec'), ns)
        db = ns['DB'](old); bodies = [random.Random(80 + i).randbytes(32768) for i in range(3)]
        header = b'NES\x1a' + bytes([2, 0]) + bytes(10)
        with db.c:
            for i, body in enumerate(bodies):
                rid, oid = db.rom(header + body, 'headered'); db.file(oid, f'G{i} (USA).nes')
                rid2, oid2 = db.rom(body, 'headerless'); db.file(oid2, f'G{i} (USA).unh')
            d = '<datafile><header><name>T (Headerless)</name></header>' + ''.join(
                f'<game name="G{i} (USA)"><rom name="G{i} (USA).unh" size="{len(b)}" crc="{zlib.crc32(b):08x}" sha1="{hashlib.sha1(b).hexdigest()}"/></game>' for i, b in enumerate(bodies)) + '</datafile>'
            ds = db.import_dat(d.encode(), 't.dat', 'headerless'); db.scan(ds)
        with db.c: db.compact_groups(group_bytes=65536, workers=1)
        blocks = db.c.execute('SELECT id,sha256,size FROM chunks ORDER BY id').fetchall(); recipes = db.c.execute('SELECT * FROM nes_recipes ORDER BY object_id').fetchall()
        db.c.close()
        rep = mig.migrate(old, root / 'nes-v4.sqlite', 1, workers=1)
        self.assertEqual(rep['solid_groups'], 1); self.assertEqual(rep['family_basis'], {'newest_dat': 3})
        v4 = engine.DB(root / 'nes-v4.sqlite')
        self.assertEqual(v4.storage_version, 4)
        self.assertEqual([tuple(r) for r in v4.c.execute('SELECT id,sha256,size FROM chunks ORDER BY id')], [tuple(r) for r in blocks])
        self.assertEqual([tuple(r) for r in v4.c.execute('SELECT * FROM nes_recipes ORDER BY object_id')], [tuple(r) for r in recipes])
        self.assertEqual(v4.c.execute("SELECT count(*) FROM compression_groups WHERE codec='lzma2-4m'").fetchone()[0], 0)
        self.assertEqual({r[0] for r in v4.c.execute('SELECT ra_md5 FROM rom_ra_hashes')}, {hashlib.md5(b).hexdigest() for b in bodies})
        self.assertTrue(v4.audit(archives=True)['ok'])
        pos = v4.storage_positions()  # header recipes sweep with their body (audit / export order)
        for oid, body_oid in v4.c.execute('SELECT object_id,body_object_id FROM nes_recipes'): self.assertEqual(pos[oid], pos[body_oid])
        for i, body in enumerate(bodies):
            for name, data in ((f'G{i} (USA).nes', header + body), (f'G{i} (USA).unh', body)):
                fid = v4.c.execute('SELECT id FROM files WHERE original_name=?', (name,)).fetchone()[0]
                out = root / ('o' + name); v4.export(fid, out); self.assertEqual(out.read_bytes(), data)
        v4.c.close(); tmp.cleanup()


class MegaDriveTests(_Base):
    platform = 'megadrive'

    def test_md_rom_rows(self):
        self.solid_import([('M (USA).md', md_rom())])
        row = self.db.c.execute('SELECT * FROM v_md_headers').fetchone()
        self.assertEqual((row['system_type'], row['checksum_valid'], row['parse_status']), ('SEGA MEGA DRIVE', 1, 'valid'))
        self.assertEqual(self.db.c.execute('SELECT format FROM roms').fetchone()[0], 'md')


def pce_rom(size=0x40000, seed=80):
    rom = bytearray(random.Random(seed).randbytes(size)); rom[0x1FFE:0x2000] = (0xE000).to_bytes(2, 'little'); return bytes(rom)


def vb_rom(size=1 << 20, seed=81, code=b'VZZE'):
    rom = bytearray(random.Random(seed).randbytes(size)); h = len(rom) - 0x220
    rom[h:h + 20] = b'SYNTH VIRTUAL'.ljust(20, b' '); rom[h + 0x19:h + 0x1B] = b'01'; rom[h + 0x1B:h + 0x1F] = code; rom[h + 0x1F] = 1
    return bytes(rom)


def msx_cart(seed=82, offset=0x0000, size=0x8000):
    rom = bytearray(random.Random(seed).randbytes(size)); rom[offset:offset + 10] = b'AB' + (0x4010).to_bytes(2, 'little') + bytes(6); return bytes(rom)


class PcEngineTests(_Base):
    """PC Engine / SuperGrafx HuCards, MSX, Virtual Boy (2026-10-06 platforms)."""
    platform = 'pcengine'

    def test_pce_copier_header_shares_body_blocks_and_ra_hash(self):
        body = pce_rom(); headered = random.Random(83).randbytes(512) + body
        p = engine.parse_pce(headered); h = p['hardware']
        self.assertEqual((p['parse_status'], h['copier_header'], h['rom_size'], h['banks'], h['reset_vector']), ('warning', 1, 0x40000, 32, 0xE000))
        q = engine.parse_pce(body); self.assertEqual((q['parse_status'], q['hardware']['copier_header']), ('valid', 0))
        self.solid_import([('P (Japan).pce', body)])
        self.assertEqual([len(b) for _, b in self.db.missing_blocks(headered, set())], [512])  # only the copier header is new
        self.loose_import('P (Japan) [h].pce', headered, 'P (Japan)')
        self.assertEqual({r[0] for r in self.db.c.execute('SELECT ra_md5 FROM rom_ra_hashes')}, {hashlib.md5(body).hexdigest()})
        self.assertEqual(self.db.c.execute('SELECT count(*) FROM v_pce_headers').fetchone()[0], 2)
        self.assertTrue(self.db.audit(archives=True)['ok'])
        U = importlib.import_module('update_db'); self.assertIn('.sgx', U.OTHER_PLATFORM_EXT['pcengine']); self.assertIn('.pce', U.OTHER_PLATFORM_EXT['supergrafx'])

    def test_msx_media_and_vb_header(self):
        m = engine.parse_msx(msx_cart()); self.assertEqual((m['format'], m['parse_status'], m['hardware']['header_offset'], m['hardware']['init']), ('msx_cart', 'valid', 0, 0x4010))
        self.assertEqual(engine.parse_msx(msx_cart(offset=0x4000))['hardware']['header_offset'], 0x4000)
        self.assertEqual(engine.parse_msx(b'\xeb' + bytes(737279))['hardware']['media'], 'disk')
        self.assertEqual(engine.parse_msx(engine.MSX_CAS_MAGIC + bytes(64))['format'], 'msx_tape')
        self.assertEqual(engine.parse_msx(bytes(0x8000))['parse_status'], 'unclassified')
        v = engine.parse_vb(vb_rom()); self.assertEqual((v['parse_status'], v['hardware']['title'], v['hardware']['maker_code'], v['hardware']['game_code'], v['hardware']['version']),
                                                       ('valid', 'SYNTH VIRTUAL', '01', 'VZZE', 1))
        self.assertEqual(engine.parse_vb(vb_rom(code=bytes(4)))['parse_status'], 'warning')
        self.assertEqual(engine.parse_vb(bytes(3000))['parse_status'], 'unclassified')
        self.assertEqual(engine.ra_hash('virtualboy', vb_rom())[0], hashlib.md5(vb_rom()).hexdigest())


class MsxTests(_Base):
    platform = 'msx2'

    def test_msx_rows_and_platform_annotation(self):
        self.solid_import([('M (Japan).rom', msx_cart(seed=84))])
        rid = self.db.c.execute('SELECT id FROM roms').fetchone()[0]
        with self.db.c: self.db.c.execute("INSERT INTO rom_annotations VALUES (?,'platform','tag','tools/msx_route.py','2026-10-06T00:00:00+00:00')", (rid,))
        row = self.db.c.execute('SELECT * FROM v_msx_headers').fetchone()
        self.assertEqual((row['media'], row['header_offset'], row['platform_evidence']), ('cartridge', '0000', 'tag'))
        self.assertTrue(self.db.audit(archives=True)['ok'])

    def test_route_platform_first_medium_second(self):
        R = importlib.import_module('msx_route'); d = self.root / 'dats'; d.mkdir()
        one, two, hack_base = msx_cart(seed=85), msx_cart(seed=86, size=0x20000), msx_cart(seed=87, size=0x20000)
        for name, games in (('Microsoft - MSX', [('Alpha (Japan)', None, one)]), ('Microsoft - MSX2', [('Beta (Japan)', None, two), ('Gamma (Japan)', None, hack_base)])):
            with zipfile.ZipFile(d / f'{name} (Parent-Clone) (20260101-000000).zip', 'w') as z: z.writestr('x.dat', dat_xml(games))
        R.add_dat_rom_blocks('msx2', hack_base, d)
        cur = self.root / 'routing.csv'; cur.write_text('zip_name,platform,basis,note\nOdd (Japan).zip,msx2,manual,\n', encoding='utf-8')
        route = lambda n, data, member='x.rom': R.route(n, [(member, data)], d, cur)
        self.assertEqual(route('Whatever.zip', two), ('msx2', 'dat'))
        self.assertEqual(route('Whatever.zip', one), ('msx1', 'dat'))
        self.assertEqual(route('New (Japan) (MSX2).zip', b'new'), ('msx2', 'tag'))
        self.assertEqual(route('Disk.zip', b'new', 'Disk.mx2'), ('msx2', 'tag'))
        self.assertEqual(route('Beta (Japan) (Rev 1).zip', b'rev'), ('msx2', 'title'))
        self.assertEqual(route('Alpha (Japan) [T-En].zip', b'tr'), ('msx1', 'title'))
        self.assertEqual(route('Hack (Japan).zip', hack_base[:-8192] + bytes(8192)), ('msx2', 'blocks'))
        self.assertEqual(route('Odd (Japan).zip', b'odd'), ('msx2', 'curated:manual'))
        self.assertEqual(route('Unknown (Japan).zip', b'unknown'), ('msx1', 'default'))
        import_ra = importlib.import_module('import_ra'); F = importlib.import_module('finalize_db')
        self.assertEqual(import_ra.CONSOLES['msx1'], import_ra.CONSOLES['msx2']); self.assertIn('msx1', F.SHARED_RA_CONSOLE)
        self.assertEqual(F.SIBLINGS['msx2'], ('msx1',)); self.assertIn('msx-routing.csv', F.resource_files('msx1')); self.assertNotIn('msx-routing.csv', F.resource_files('gb'))


class UnsupportedRaTests(_Base):
    platform = 'gameandwatch'

    def test_plain_platform_and_empty_ra_report(self):
        self.solid_import([('Ball (World).bin', random.Random(88).randbytes(4096))])
        r = self.db.c.execute('SELECT format,parse_status FROM roms').fetchone(); self.assertEqual(tuple(r), ('bin', 'unclassified'))
        self.assertTrue(self.db.audit(archives=True)['ok'])
        ra = importlib.import_module('import_ra'); self.assertNotIn('gameandwatch', ra.CONSOLES); self.assertIn('supracan', ra.UNSUPPORTED)
        out = importlib.import_module('ra_report').main(str(self.path), str(self.root / 'r'), {}, False)
        self.assertEqual((out['supported'], out['ra_games_with_achievements']), (False, 0))
        self.assertEqual((self.root / 'r-missing.csv').read_text().splitlines()[0].split(',')[0], 'ra_game_id')


if __name__ == '__main__':
    unittest.main()
