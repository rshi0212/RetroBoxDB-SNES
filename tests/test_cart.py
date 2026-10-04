"""Synthetic tests for the SNES / Mega Drive extension (storage v4). No copyrighted content is used.

python3 -B -m unittest tests/test_cart.py -v   (from the repository root)
"""
import hashlib, importlib, io, json, pathlib, random, sqlite3, sys, tempfile, unittest, zipfile, zlib

TOOLS = pathlib.Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import build_cart_db as B  # noqa: E402

_TMP = tempfile.TemporaryDirectory()
_engine_text, _engine_body = B.combined_engine()
(pathlib.Path(_TMP.name) / 'engine.py').write_text(_engine_text)
sys.path.insert(0, _TMP.name)
engine = importlib.import_module('engine')
import cart_nointro, import_ra  # noqa: E402  (both resolve `engine` to the combined module above)


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
        B.create(self.path, self.platform, B.cart_schema(self.platform)); self.db = engine.DB(self.path)

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
            self.db.insert('compression_groups', sha256=bytes(32), encoded_sha256=bytes(32), size=(32 << 20) + 1, codec='lzma2-solid', data=b'x')
        with self.assertRaises(sqlite3.IntegrityError), self.db.c:
            self.db.insert('compression_groups', sha256=bytes(32), encoded_sha256=bytes(32), size=(2 << 20) + 1, codec='lzma2-4m', data=b'x')

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
        with self.db.c: rep = cart_nointro.import_snapshot(self.db, self.root / 'db.xml', self.root / 'log.csv')
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
        upd = importlib.import_module('update_cart_db')
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


class MegaDriveTests(_Base):
    platform = 'megadrive'

    def test_md_rom_rows(self):
        self.solid_import([('M (USA).md', md_rom())])
        row = self.db.c.execute('SELECT * FROM v_md_headers').fetchone()
        self.assertEqual((row['system_type'], row['checksum_valid'], row['parse_status']), ('SEGA MEGA DRIVE', 1, 'valid'))
        self.assertEqual(self.db.c.execute('SELECT format FROM roms').fetchone()[0], 'md')


if __name__ == '__main__':
    unittest.main()
