-- Game name extension v4; confirmed matches resolve to one game before inheritance.
CREATE TABLE IF NOT EXISTS game_chinese_names (
 id INTEGER PRIMARY KEY,
 name_cn TEXT NOT NULL UNIQUE CHECK(length(trim(name_cn))>0)
) STRICT;
CREATE TABLE IF NOT EXISTS game_name_imports (
 id INTEGER PRIMARY KEY,
 platform_id INTEGER NOT NULL REFERENCES platforms(id),
 source_name TEXT NOT NULL,
 source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64),
 resource_name TEXT NOT NULL REFERENCES resources(name),
 normalization_version TEXT NOT NULL,
 imported_at TEXT NOT NULL,
 UNIQUE(platform_id, source_sha256)
) STRICT;
CREATE TABLE IF NOT EXISTS game_name_entries (
 id INTEGER PRIMARY KEY,
 import_id INTEGER NOT NULL REFERENCES game_name_imports(id),
 row_number INTEGER NOT NULL CHECK(row_number>=2),
 name_en_original TEXT NOT NULL,
 name_en TEXT NOT NULL,
 name_cn_id INTEGER REFERENCES game_chinese_names(id),
 match_key TEXT NOT NULL CHECK(length(match_key)>0),
 UNIQUE(import_id, row_number)
) STRICT;
CREATE INDEX IF NOT EXISTS idx_game_name_entries_key ON game_name_entries(match_key);
CREATE TABLE IF NOT EXISTS release_name_links (
 entry_id INTEGER NOT NULL REFERENCES game_name_entries(id),
 release_id INTEGER NOT NULL REFERENCES releases(id),
 status TEXT NOT NULL CHECK(status IN ('matched','ambiguous')),
 match_method TEXT NOT NULL CHECK(match_method IN ('exact_title','structured_title','qualified_title','normalized_title')),
 PRIMARY KEY(entry_id, release_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_release_name_links_release ON release_name_links(release_id);
CREATE TABLE IF NOT EXISTS game_name_match_decisions (
 entry_id INTEGER PRIMARY KEY REFERENCES game_name_entries(id),
 algorithm_version TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('matched','ambiguous','unmatched')),
 game_id INTEGER REFERENCES games(id),
 match_method TEXT NOT NULL,
 reason TEXT NOT NULL,
 parsed_name_json TEXT NOT NULL CHECK(json_valid(parsed_name_json)),
 candidate_game_ids_json TEXT NOT NULL CHECK(json_valid(candidate_game_ids_json)),
 CHECK((status='matched' AND game_id IS NOT NULL) OR (status!='matched' AND game_id IS NULL))
) STRICT;
CREATE VIEW IF NOT EXISTS v_release_game_names AS
 SELECT l.release_id,r.game_id,r.title AS catalog_title,
 e.id AS entry_id,e.name_en_original,e.name_en,e.name_cn_id,cn.name_cn,l.match_method,
 e.import_id,e.row_number,i.source_name,i.source_sha256
 FROM release_name_links l JOIN game_name_entries e ON e.id=l.entry_id
 JOIN game_name_imports i ON i.id=e.import_id JOIN releases r ON r.id=l.release_id
 LEFT JOIN game_chinese_names cn ON cn.id=e.name_cn_id
 WHERE l.status='matched';
CREATE VIEW IF NOT EXISTS v_game_names AS
 SELECT DISTINCT game_id,name_en,name_cn FROM v_release_game_names;
CREATE VIEW IF NOT EXISTS v_release_chinese_names AS
 SELECT DISTINCT release_id,game_id,name_cn_id,name_cn FROM v_release_game_names
 WHERE name_cn_id IS NOT NULL;
CREATE VIEW IF NOT EXISTS v_rom_game_names AS
 SELECT rr.rom_id,n.* FROM rom_releases rr
 JOIN v_release_game_names n ON n.release_id=rr.release_id;
CREATE VIEW IF NOT EXISTS v_game_name_alternatives AS
 SELECT import_id,match_key,count(DISTINCT name_cn_id) AS chinese_name_count
 FROM game_name_entries WHERE name_cn_id IS NOT NULL
 GROUP BY import_id,match_key HAVING count(DISTINCT name_cn_id)>1;
CREATE VIEW IF NOT EXISTS v_game_name_import_status AS
 SELECT e.*,cn.name_cn,
 CASE WHEN EXISTS(SELECT 1 FROM release_name_links l WHERE l.entry_id=e.id AND l.status='matched')
 THEN 'matched' WHEN EXISTS(SELECT 1 FROM release_name_links l WHERE l.entry_id=e.id)
 THEN 'ambiguous' ELSE 'unmatched' END AS status,
 (SELECT count(*) FROM release_name_links l WHERE l.entry_id=e.id AND l.status='matched') AS release_count
 FROM game_name_entries e LEFT JOIN game_chinese_names cn ON cn.id=e.name_cn_id;
CREATE VIEW IF NOT EXISTS v_game_chinese_name_aliases AS
 SELECT DISTINCT game_id,name_cn_id,name_cn FROM v_release_chinese_names;
CREATE VIEW IF NOT EXISTS v_game_chinese_name_status AS
 SELECT g.id AS game_id,g.platform_id,count(a.name_cn_id) AS chinese_name_count,
 CASE count(a.name_cn_id) WHEN 0 THEN 'missing' WHEN 1 THEN 'unique_translation'
 ELSE 'needs_review' END AS status,
 CASE WHEN count(a.name_cn_id)=1 THEN min(a.name_cn_id) END AS standard_name_cn_id,
 CASE WHEN count(a.name_cn_id)=1 THEN min(a.name_cn) END AS standard_name_cn
 FROM games g LEFT JOIN v_game_chinese_name_aliases a ON a.game_id=g.id
 GROUP BY g.id,g.platform_id;
CREATE VIEW IF NOT EXISTS v_release_effective_chinese_names AS
 WITH direct AS MATERIALIZED (SELECT * FROM v_release_chinese_names)
 SELECT d.release_id,d.game_id,r.title AS catalog_title,d.name_cn_id,d.name_cn,
 'direct' AS name_basis
 FROM direct d JOIN releases r ON r.id=d.release_id
 UNION ALL
 SELECT r.id,r.game_id,r.title,s.standard_name_cn_id,s.standard_name_cn,'group_inherited'
 FROM releases r JOIN v_game_chinese_name_status s ON s.game_id=r.game_id
 LEFT JOIN direct d ON d.release_id=r.id
 WHERE s.status='unique_translation' AND d.release_id IS NULL;
CREATE VIEW IF NOT EXISTS v_rom_effective_chinese_names AS
 SELECT rr.rom_id,n.* FROM rom_releases rr
 JOIN v_release_effective_chinese_names n ON n.release_id=rr.release_id;
CREATE VIEW IF NOT EXISTS v_game_chinese_name_evidence AS
 SELECT game_id,name_cn_id,name_cn,release_id AS source_release_id,
 catalog_title AS source_title,entry_id,import_id,row_number,source_name,source_sha256
 FROM v_release_game_names WHERE name_cn_id IS NOT NULL;
CREATE VIEW IF NOT EXISTS v_game_chinese_name_review AS
 SELECT a.* FROM v_game_chinese_name_aliases a
 JOIN v_game_chinese_name_status s ON s.game_id=a.game_id WHERE s.status='needs_review';
CREATE VIEW IF NOT EXISTS v_game_name_match_review AS
 SELECT e.id AS entry_id,e.import_id,e.row_number,e.name_en_original,cn.name_cn,
 d.status,d.reason,d.parsed_name_json,d.candidate_game_ids_json
 FROM game_name_match_decisions d JOIN game_name_entries e ON e.id=d.entry_id
 LEFT JOIN game_chinese_names cn ON cn.id=e.name_cn_id WHERE d.status!='matched';
