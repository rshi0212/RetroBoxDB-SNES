-- RetroBoxDB cartridge extension (SNES / Mega Drive), applied after the transformed base schema.
-- Storage v4 = v3 + 'lzma2-solid' compression groups (<=32 MiB, family-ordered 64 KiB blocks).
CREATE TABLE snes_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 header_offset INTEGER NOT NULL,layout TEXT NOT NULL,map_mode INTEGER NOT NULL,map_mode_name TEXT,fast_rom INTEGER NOT NULL,
 chipset INTEGER NOT NULL,coprocessor TEXT,battery INTEGER NOT NULL,title TEXT,title_hex TEXT NOT NULL,
 rom_size_declared INTEGER,ram_size_declared INTEGER NOT NULL,region_code INTEGER NOT NULL,region TEXT,
 developer_id INTEGER NOT NULL,maker_code TEXT,game_code TEXT,expansion_ram_size INTEGER,version INTEGER NOT NULL,
 checksum_declared INTEGER NOT NULL,checksum_complement INTEGER NOT NULL,checksum_computed INTEGER,checksum_valid INTEGER,
 raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
CREATE TABLE md_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 system_type TEXT,copyright TEXT,title_domestic TEXT,title_overseas TEXT,serial TEXT,
 checksum_declared INTEGER NOT NULL,checksum_computed INTEGER NOT NULL,checksum_valid INTEGER NOT NULL,
 devices TEXT,rom_start INTEGER NOT NULL,rom_end INTEGER NOT NULL,ram_start INTEGER NOT NULL,ram_end INTEGER NOT NULL,
 sram_type INTEGER,sram_start INTEGER,sram_end INTEGER,modem TEXT,notes TEXT,regions TEXT,
 raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
CREATE TRIGGER immutable_snes_hardware_update BEFORE UPDATE ON snes_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_snes_hardware_delete BEFORE DELETE ON snes_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_md_hardware_update BEFORE UPDATE ON md_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_md_hardware_delete BEFORE DELETE ON md_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;

-- Solid groups record which import batch (family list) they were built from.
CREATE TABLE solid_group_families(
 group_id INTEGER NOT NULL,ordinal INTEGER NOT NULL,family_key TEXT NOT NULL,
 PRIMARY KEY(group_id,ordinal)
) STRICT, WITHOUT ROWID;
-- Checked by trigger, not a foreign key: the payload-free Catalog keeps this provenance while compression_groups is empty.
CREATE TRIGGER solid_group_families_guard BEFORE INSERT ON solid_group_families BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM compression_groups WHERE id=NEW.group_id AND codec='lzma2-solid') THEN RAISE(ABORT,'unknown solid group') END;
END;
CREATE INDEX chunk_group ON chunks(group_id) WHERE group_id IS NOT NULL;

CREATE VIEW v_snes_headers AS
 SELECT r.id AS rom_id,o.sha1,o.size,r.parse_status,h.layout,h.map_mode_name,h.fast_rom,h.coprocessor,h.battery,h.title,h.region,
 h.maker_code,h.game_code,h.version,h.rom_size_declared,h.ram_size_declared,
 printf('%04X',h.checksum_declared) AS checksum_declared,printf('%04X',h.checksum_computed) AS checksum_computed,h.checksum_valid
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN snes_hardware h ON h.rom_id=r.id;
CREATE VIEW v_md_headers AS
 SELECT r.id AS rom_id,o.sha1,o.size,r.parse_status,h.system_type,h.copyright,h.title_domestic,h.title_overseas,h.serial,h.devices,h.regions,
 printf('%04X',h.checksum_declared) AS checksum_declared,printf('%04X',h.checksum_computed) AS checksum_computed,h.checksum_valid,
 printf('%06X',h.rom_end) AS rom_end,h.sram_type,printf('%06X',h.sram_start) AS sram_start,printf('%06X',h.sram_end) AS sram_end
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN md_hardware h ON h.rom_id=r.id;
CREATE VIEW v_solid_groups AS
 SELECT g.id AS group_id,g.size AS raw_bytes,length(g.data) AS stored_bytes,round(1.0*length(g.data)/g.size,4) AS ratio,
 (SELECT count(*) FROM chunks c WHERE c.group_id=g.id) AS blocks,
 (SELECT group_concat(family_key,' | ') FROM solid_group_families f WHERE f.group_id=g.id) AS families
 FROM compression_groups g WHERE g.codec='lzma2-solid';
-- No-Intro archive metadata (local-script names, categories, parent archive) from the DB Export.
CREATE VIEW v_nointro_archives AS
 SELECT a.snapshot_id,a.archive_id,a.title,json_extract(a.attrs_json,'$.name') AS name,json_extract(a.attrs_json,'$.name_alt') AS name_alt,
 json_extract(a.attrs_json,'$.clone') AS clone,json_extract(a.attrs_json,'$.region') AS region,json_extract(a.attrs_json,'$.languages') AS languages,
 json_extract(a.attrs_json,'$.categories') AS categories,json_extract(a.attrs_json,'$.regparent') AS regparent,a.attrs_json
 FROM ni_archives a;

-- RetroAchievements (public Web API snapshot; no credentials stored). RA hash per rcheevos:
-- SNES: MD5 after dropping a 512-byte copier header when size % 8192 == 512; Mega Drive: MD5 of the whole file.
CREATE TABLE ra_snapshots(
 id INTEGER PRIMARY KEY,console_id INTEGER NOT NULL,endpoint TEXT NOT NULL,fetched_at TEXT NOT NULL,
 response_sha256 TEXT NOT NULL CHECK(length(response_sha256)=64),resource_name TEXT NOT NULL REFERENCES resources(name),
 games INTEGER NOT NULL,hashes INTEGER NOT NULL,UNIQUE(console_id,response_sha256)
) STRICT;
CREATE TABLE ra_games(
 snapshot_id INTEGER NOT NULL REFERENCES ra_snapshots(id),ra_game_id INTEGER NOT NULL,title TEXT NOT NULL,category TEXT NOT NULL,
 num_achievements INTEGER NOT NULL,num_leaderboards INTEGER,points INTEGER,date_modified TEXT,
 PRIMARY KEY(snapshot_id,ra_game_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE ra_hashes(
 snapshot_id INTEGER NOT NULL,md5 TEXT NOT NULL CHECK(length(md5)=32),ra_game_id INTEGER NOT NULL,
 PRIMARY KEY(snapshot_id,md5,ra_game_id),FOREIGN KEY(snapshot_id,ra_game_id) REFERENCES ra_games(snapshot_id,ra_game_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX ra_hashes_md5 ON ra_hashes(md5);
CREATE TABLE rom_ra_hashes(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),ra_md5 TEXT NOT NULL CHECK(length(ra_md5)=32),method TEXT NOT NULL
) STRICT;
CREATE INDEX rom_ra_md5 ON rom_ra_hashes(ra_md5);
CREATE VIEW v_ra_latest AS SELECT max(id) AS snapshot_id FROM ra_snapshots;
-- Local ROM bytes -> RA game (latest snapshot). has_achievements distinguishes registered hashes without a set.
CREATE VIEW v_rom_ra_matches AS
 SELECT rr.rom_id,rr.ra_md5,g.ra_game_id,g.title AS ra_title,g.category AS ra_category,g.num_achievements,g.points,
 g.num_achievements>0 AS has_achievements,rel.release_id,r.title AS release_title
 FROM rom_ra_hashes rr JOIN ra_hashes h ON h.md5=rr.ra_md5 AND h.snapshot_id=(SELECT snapshot_id FROM v_ra_latest)
 JOIN ra_games g ON g.snapshot_id=h.snapshot_id AND g.ra_game_id=h.ra_game_id
 LEFT JOIN rom_releases rel ON rel.rom_id=rr.rom_id LEFT JOIN releases r ON r.id=rel.release_id;
-- DAT entries -> RA game by DAT MD5 (no local payload needed). Copier-header-sized DAT entries are excluded.
CREATE VIEW v_dat_ra_matches AS
 SELECT ds.id AS dat_set_id,ds.version AS dat_version,dg.id AS dat_game_id,dg.name AS game_name,dg.cloneof,dr.id AS dat_rom_id,dr.md5,
 g.ra_game_id,g.title AS ra_title,g.category AS ra_category,g.num_achievements,g.num_achievements>0 AS has_achievements,
 EXISTS(SELECT 1 FROM validations v WHERE v.dat_rom_id=dr.id AND v.status='match') AS local_rom_available
 FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id JOIN dat_sets ds ON ds.id=dg.dat_set_id
 JOIN ra_hashes h ON h.md5=dr.md5 AND h.snapshot_id=(SELECT snapshot_id FROM v_ra_latest)
 JOIN ra_games g ON g.snapshot_id=h.snapshot_id AND g.ra_game_id=h.ra_game_id
 WHERE dr.size % 8192 != 512;
-- RA hashes that no local ROM and no DAT entry explains (for review, never auto-linked).
CREATE VIEW v_ra_unmatched_hashes AS
 SELECT h.md5,g.ra_game_id,g.title,g.category,g.num_achievements FROM ra_hashes h
 JOIN ra_games g ON g.snapshot_id=h.snapshot_id AND g.ra_game_id=h.ra_game_id
 WHERE h.snapshot_id=(SELECT snapshot_id FROM v_ra_latest)
 AND NOT EXISTS(SELECT 1 FROM rom_ra_hashes rr WHERE rr.ra_md5=h.md5) AND NOT EXISTS(SELECT 1 FROM dat_roms dr WHERE dr.md5=h.md5);
CREATE INDEX dat_rom_md5 ON dat_roms(md5);
CREATE INDEX ni_files_md5 ON ni_files(md5);
-- No-Intro DB Export files (incl. bad dumps and alternative sources not in the DAT) -> RA game.
CREATE VIEW v_nointro_ra_matches AS
 SELECT f.snapshot_id AS nointro_snapshot_id,f.file_id,f.bad,f.object_id,a.archive_id,a.title AS nointro_title,
 g.ra_game_id,g.title AS ra_title,g.category AS ra_category,g.num_achievements,g.num_achievements>0 AS has_achievements,
 EXISTS(SELECT 1 FROM dat_roms d WHERE d.md5=f.md5) AS in_dat
 FROM ni_files f JOIN ra_hashes h ON h.md5=f.md5 AND h.snapshot_id=(SELECT snapshot_id FROM v_ra_latest)
 JOIN ra_games g ON g.snapshot_id=h.snapshot_id AND g.ra_game_id=h.ra_game_id
 JOIN ni_source_files sf ON sf.snapshot_id=f.snapshot_id AND sf.file_id=f.file_id
 JOIN ni_sources s ON s.snapshot_id=sf.snapshot_id AND s.kind=sf.kind AND s.external_id=sf.external_id
 JOIN ni_archives a ON a.snapshot_id=s.snapshot_id AND a.archive_id=s.archive_id
 GROUP BY f.snapshot_id,f.file_id,g.ra_game_id,a.archive_id;
-- Family assignment of each stored ROM object: drives solid-group placement for later imports and compaction.
CREATE TABLE object_families(
 object_id INTEGER PRIMARY KEY REFERENCES objects(id),family_key TEXT NOT NULL,
 basis TEXT NOT NULL CHECK(basis IN ('newest_dat','dat','nointro_db','title','solid_group'))
) STRICT;
CREATE INDEX object_family_key ON object_families(family_key);
CREATE INDEX solid_group_family_key ON solid_group_families(family_key);
