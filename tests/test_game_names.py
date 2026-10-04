import csv
import io
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from import_game_names import import_names, match_key, parse_title


class GameNamesTest(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.execute('PRAGMA foreign_keys=ON')
        self.c.executescript('''
            CREATE TABLE resources(name TEXT PRIMARY KEY,kind TEXT,content TEXT,sha256 TEXT);
            CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE platforms(id INTEGER PRIMARY KEY,code TEXT);
            CREATE TABLE games(id INTEGER PRIMARY KEY,platform_id INTEGER);
            CREATE TABLE releases(id INTEGER PRIMARY KEY,game_id INTEGER,title TEXT);
            CREATE TABLE dat_games(id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE release_dat_games(release_id INTEGER,dat_game_id INTEGER);
            CREATE TABLE rom_releases(rom_id INTEGER,release_id INTEGER);
            INSERT INTO platforms VALUES(1,'nes'),(2,'snes');
            INSERT INTO games VALUES(1,1),(2,1),(3,2);
            INSERT INTO releases VALUES
              (1,1,'Example (Japan)'),(2,1,'Example (USA) (Rev 1)'),
              (3,2,'School (Jou) (Japan)'),(4,2,'School (Ge) (Japan)'),
              (5,3,'Example (Europe)');
            INSERT INTO dat_games VALUES(1,'Old Example (Japan)');
            INSERT INTO release_dat_games VALUES(1,1);
            INSERT INTO rom_releases VALUES(10,1),(11,2);
        ''')

    def tearDown(self):
        self.c.close()

    def run_import(self, rows):
        out = io.StringIO(newline='')
        writer = csv.writer(out)
        writer.writerow(['Name EN','Name CN'])
        writer.writerows(rows)
        return import_names(self.c, out.getvalue().encode('utf-8-sig'), 'names.csv')

    def test_normalization_preserves_identity_outside_parentheses(self):
        self.assertEqual(match_key('  EXAMPLE (USA) （修订（1））  '), 'example')
        self.assertEqual(match_key('Example (Proto (Rev 2)) - II'), 'example - ii')
        self.assertNotEqual(match_key('[BIOS] Example'), match_key('Example'))
        self.assertNotEqual(match_key('Example II'), match_key('Example III'))

    def test_regional_links_dat_aliases_platform_and_source_preservation(self):
        report = self.run_import([['Example (Europe)','示例'],['Old Example (Japan)','旧名'],
                                  ['Missing (Japan)',''],['Example (Japan)','示例']])
        self.assertEqual(report['matched_rows'], 3)
        self.assertEqual(report['matched_releases'], 2)
        self.assertEqual(report['matched_roms'], 2)
        self.assertEqual(report['unresolved_rows'][0]['status'], 'unmatched')
        self.assertEqual(self.c.execute('SELECT count(*) FROM release_name_links WHERE release_id=5').fetchone()[0], 0)
        raw = self.c.execute("SELECT content FROM resources WHERE kind='csv'").fetchone()[0]
        self.assertTrue(raw.startswith('\ufeff'))
        self.assertIn('\r\n', raw)
        self.assertEqual(self.c.execute('SELECT name_cn_id FROM game_name_entries WHERE row_number=4').fetchone()[0], None)
        self.assertEqual(report['unique_chinese_names'], 2)
        self.assertEqual(self.c.execute("SELECT count(*) FROM game_chinese_names WHERE name_cn='示例'").fetchone()[0], 1)
        self.assertEqual(self.c.execute("SELECT count(*) FROM v_release_chinese_names WHERE name_cn='示例'").fetchone()[0], 2)
        self.assertEqual(self.c.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_volume_qualifiers_resolve_separate_games(self):
        self.c.execute('INSERT INTO games VALUES(4,1)')
        self.c.execute('UPDATE releases SET game_id=4 WHERE id=4')
        report = self.run_import([['School (Jou) (Japan)','上'],['School (Ge) (Japan)','下']])
        self.assertEqual(report['matched_links'], 2)
        self.assertEqual(report['ambiguous_links'], 0)
        self.assertEqual(set(self.c.execute('SELECT release_id,name_cn FROM v_release_game_names')), {(3,'上'),(4,'下')})
        self.assertEqual(set(self.c.execute('SELECT game_id,standard_name_cn FROM v_game_chinese_name_status WHERE game_id IN (2,4)')), {(2,'上'),(4,'下')})

    def test_missing_volume_is_a_review_candidate(self):
        report = self.run_import([['School (USA)','上'],['School (Europe)','下']])
        self.assertEqual(report['matched_links'], 0)
        self.assertEqual(report['ambiguous_links'], 4)
        self.assertEqual(report['ambiguous_rows'], 2)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_release_effective_chinese_names').fetchone()[0], 0)

    def test_repeat_import_refreshes_without_duplicate_rows(self):
        rows = [['Example (Europe)','示例']]
        first = self.run_import(rows)
        self.assertEqual(first, self.run_import(rows))
        self.assertEqual(self.c.execute('SELECT count(*) FROM game_name_imports').fetchone()[0], 1)
        self.c.execute("INSERT INTO releases VALUES(6,1,'Example (Asia)')")
        self.assertEqual(self.run_import(rows)['matched_releases'], 3)
        self.assertEqual(self.c.execute('SELECT count(*) FROM game_name_entries').fetchone()[0], 1)

    def test_transaction_rollback_includes_schema_and_resources(self):
        self.c.execute('BEGIN')
        self.run_import([['Example (USA)','示例']])
        self.c.rollback()
        self.assertEqual(self.c.execute("SELECT count(*) FROM sqlite_master WHERE name='game_name_entries'").fetchone()[0], 0)
        self.assertEqual(self.c.execute('SELECT count(*) FROM resources').fetchone()[0], 0)

    def test_invalid_csv_is_rejected_before_writes(self):
        with self.assertRaises(ValueError):
            import_names(self.c, b'Name EN,Name CN\r\n,empty\r\n', 'bad.csv')
        self.assertEqual(self.c.execute('SELECT count(*) FROM resources').fetchone()[0], 0)

    def test_unique_group_name_reaches_differently_named_version(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Renamed Version (Japan)')")
        self.c.execute('INSERT INTO rom_releases VALUES(12,6)')
        self.run_import([['Example (Europe)','示例']])
        self.assertEqual(self.c.execute('SELECT name_cn,name_basis FROM v_release_effective_chinese_names WHERE release_id=6').fetchall(), [('示例','group_inherited')])
        self.assertEqual(self.c.execute('SELECT name_cn,name_basis FROM v_rom_effective_chinese_names WHERE rom_id=12').fetchall(), [('示例','group_inherited')])
        self.assertEqual(self.c.execute('SELECT count(*) FROM release_name_links WHERE release_id=6').fetchone()[0], 0)
        self.assertEqual(self.c.execute('SELECT DISTINCT source_release_id FROM v_game_chinese_name_evidence WHERE game_id=1 ORDER BY 1').fetchall(), [(1,), (2,)])
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_release_effective_chinese_names WHERE release_id IN (3,4,5)').fetchone()[0], 0)

    def test_inheritance_is_bidirectional_and_blank_translation_can_inherit(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Renamed Version (Japan)')")
        self.run_import([['Renamed Version (Japan)','示例'],['Example (USA)','']])
        self.assertEqual(self.c.execute('SELECT release_id,name_basis FROM v_release_effective_chinese_names ORDER BY release_id').fetchall(), [(1,'group_inherited'),(2,'group_inherited'),(6,'direct')])
        self.assertEqual(self.c.execute('SELECT standard_name_cn FROM v_game_chinese_name_status WHERE game_id=1').fetchone()[0], '示例')

    def test_multiple_names_preserve_aliases_and_do_not_fill_unnamed_variant(self):
        self.c.execute("INSERT INTO releases VALUES(6,2,'Renamed School (USA)')")
        self.run_import([['School (Jou)','上'],['School (Ge)','下']])
        self.assertEqual(self.c.execute('SELECT status,standard_name_cn FROM v_game_chinese_name_status WHERE game_id=2').fetchone(), ('needs_review',None))
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_game_chinese_name_review WHERE game_id=2').fetchone()[0], 2)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_release_effective_chinese_names WHERE release_id=6').fetchone()[0], 0)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_release_effective_chinese_names WHERE release_id IN (3,4)').fetchone()[0], 2)

    def test_new_conflicting_evidence_removes_stale_inheritance(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Renamed Version (Japan)')")
        self.run_import([['Example (USA)','示例']])
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_release_effective_chinese_names WHERE release_id=6').fetchone()[0], 1)
        self.run_import([['Old Example (Japan)','另一译名']])
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_release_effective_chinese_names WHERE release_id=6').fetchone()[0], 0)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_game_chinese_name_aliases WHERE game_id=1').fetchone()[0], 2)

    def test_duplicate_aliases_do_not_create_false_group_conflict(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Renamed Version (Japan)')")
        self.run_import([['Example (Japan)','示例'],['Old Example (Japan)','示例']])
        self.assertEqual(self.c.execute('SELECT chinese_name_count,status FROM v_game_chinese_name_status WHERE game_id=1').fetchone(), (1,'unique_translation'))
        before = self.c.execute('SELECT * FROM v_release_effective_chinese_names ORDER BY release_id').fetchall()
        self.run_import([['Example (Japan)','示例'],['Old Example (Japan)','示例']])
        self.assertEqual(before, self.c.execute('SELECT * FROM v_release_effective_chinese_names ORDER BY release_id').fetchall())

    def test_unknown_tags_are_identity_and_known_fields_are_retained(self):
        parsed = parse_title('Example (Japan, USA) (En,Ja) (Rev 1) (CK-001) (Jou)')
        self.assertEqual(parsed['regions'], ['japan','usa'])
        self.assertEqual(parsed['languages'], ['en','ja'])
        self.assertEqual(parsed['version'], ['rev 1'])
        self.assertEqual(parsed['identity'], ['ck-001','jou'])
        self.assertEqual(parse_title('Example (Unknown (Nested))')['identity'], ['unknown (nested)'])

    def test_structured_publisher_alias_and_tag_order(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Tetris (Japan) (En) (Bullet-Proof)')")
        self.run_import([['Tetris (Bulletproof) (Japan) (En)','俄罗斯方块']])
        self.assertEqual(self.c.execute('SELECT release_id,match_method FROM release_name_links').fetchall(), [(6,'structured_title')])

    def test_exact_match_does_not_spread_into_unrelated_same_title(self):
        self.c.execute('INSERT INTO games VALUES(4,1)')
        self.c.execute("INSERT INTO releases VALUES(6,4,'Example (USA) (Intellivision) (Aftermarket) (Unl)')")
        self.run_import([['Example (Japan)','示例']])
        self.assertEqual(self.c.execute('SELECT release_id,match_method FROM release_name_links').fetchall(), [(1,'exact_title')])
        self.assertEqual(self.c.execute('SELECT release_id,name_basis FROM v_release_effective_chinese_names ORDER BY release_id').fetchall(), [(1,'direct'),(2,'group_inherited')])

    def test_same_chinese_string_does_not_merge_publishers(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Shared (Japan) (Studio A)')")
        self.c.execute("INSERT INTO releases VALUES(7,2,'Shared (Japan) (Studio B)')")
        self.run_import([['Shared (Japan) (Studio A)','同名'],['Shared (Japan) (Studio B)','同名']])
        self.assertEqual(self.c.execute('SELECT count(*) FROM game_chinese_names').fetchone()[0], 1)
        self.assertEqual(self.c.execute('SELECT entry_id,release_id FROM release_name_links ORDER BY entry_id').fetchall(), [(1,6),(2,7)])

    def test_region_can_disambiguate_different_games(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Shared (Japan)')")
        self.c.execute("INSERT INTO releases VALUES(7,2,'Shared (USA)')")
        self.run_import([['Shared (Japan) (En) (Rev 2)','示例']])
        self.assertEqual(self.c.execute('SELECT release_id,match_method FROM release_name_links').fetchall(), [(6,'qualified_title')])

    def test_cross_game_collision_without_evidence_remains_ambiguous(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Shared (Japan)')")
        self.c.execute("INSERT INTO releases VALUES(7,2,'Shared (USA)')")
        report = self.run_import([['Shared (Asia)','未确认']])
        self.assertEqual(report['ambiguous_rows'], 1)
        self.assertEqual(self.c.execute('SELECT count(*) FROM v_release_effective_chinese_names').fetchone()[0], 0)
        self.assertEqual(self.c.execute('SELECT reason FROM v_game_name_match_review').fetchone()[0], 'multiple_game_candidates')

    def test_cartridge_identifiers_are_not_discarded(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'4-in-1 (Asia) (CK-001)')")
        self.c.execute("INSERT INTO releases VALUES(7,2,'4-in-1 (Asia) (CK-002)')")
        self.run_import([['4-in-1 (CK-002) (Asia) (Rev 1)','四合一']])
        self.assertEqual(self.c.execute('SELECT release_id FROM release_name_links').fetchall(), [(7,)])

    def test_unknown_marker_mismatch_is_not_forced_even_with_one_game(self):
        self.run_import([['Example (Japan) (New Mode)','模式版']])
        self.assertEqual(self.c.execute('SELECT status,reason FROM game_name_match_decisions').fetchone(), ('ambiguous','identity_qualifiers_differ'))

    def test_prototype_can_disambiguate_independent_games(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Shared (USA)')")
        self.c.execute("INSERT INTO releases VALUES(7,2,'Shared (USA) (Proto)')")
        self.run_import([['Shared (USA) (En) (Proto)','原型']])
        self.assertEqual(self.c.execute('SELECT release_id FROM release_name_links').fetchall(), [(7,)])

    def test_prototype_stage_is_available_without_exact_build_date(self):
        self.c.execute("INSERT INTO releases VALUES(6,1,'Shared (USA) (Beta) (1991-08-09)')")
        self.c.execute("INSERT INTO releases VALUES(7,2,'Shared (USA) (Proto) (1992-03-22)')")
        self.run_import([['Shared (USA) (Proto)','原型']])
        self.assertEqual(self.c.execute('SELECT release_id FROM release_name_links').fetchall(), [(7,)])

    def test_known_release_markers_and_partial_dates_do_not_become_identity(self):
        parsed = parse_title('Example (Alt) (Wii U Virtual Console) (1990-03-xx) (PC10)')
        self.assertEqual(parsed['identity'], ['pc10'])
        self.assertIn('1990-03-xx', parsed['version'])

    def test_other_imports_are_refreshed_when_new_catalog_collision_appears(self):
        self.run_import([['Example (Asia)','示例']])
        self.c.execute("INSERT INTO releases VALUES(6,2,'Example (Europe)')")
        self.run_import([['Old Example (Japan)','旧名']])
        self.assertEqual(self.c.execute('SELECT status FROM game_name_match_decisions WHERE entry_id=1').fetchone()[0], 'ambiguous')


if __name__ == '__main__':
    unittest.main()
