-- RetroBoxDB storage v4 extension (SNES, Mega Drive, GB, GBC, GBA), applied after the transformed base schema.
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

-- Game Boy / Game Boy Color cartridge header (0x100-0x14F) and Game Boy Advance header (0x00-0xBF).
-- Only a SHA1 of the Nintendo logo bitmap is stored; the views flag the logo that most dumps share.
CREATE TABLE gb_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 title TEXT,title_hex TEXT NOT NULL,manufacturer_code TEXT,cgb_flag INTEGER NOT NULL,cgb_mode TEXT NOT NULL,sgb_flag INTEGER NOT NULL,
 licensee_old INTEGER NOT NULL,licensee_new TEXT,cartridge_type INTEGER NOT NULL,cartridge_type_name TEXT,
 battery INTEGER NOT NULL,rtc INTEGER NOT NULL,rumble INTEGER NOT NULL,rom_size_code INTEGER NOT NULL,rom_size_declared INTEGER,
 ram_size_code INTEGER NOT NULL,ram_size_declared INTEGER,destination INTEGER NOT NULL,version INTEGER NOT NULL,
 header_checksum_declared INTEGER NOT NULL,header_checksum_computed INTEGER NOT NULL,header_checksum_valid INTEGER NOT NULL,
 global_checksum_declared INTEGER NOT NULL,global_checksum_computed INTEGER NOT NULL,global_checksum_valid INTEGER NOT NULL,
 logo_sha1 TEXT NOT NULL CHECK(length(logo_sha1)=40),raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
CREATE TABLE gba_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 title TEXT,game_code TEXT,maker_code TEXT,fixed_value INTEGER NOT NULL,unit_code INTEGER NOT NULL,device_type INTEGER NOT NULL,
 version INTEGER NOT NULL,complement_declared INTEGER NOT NULL,complement_computed INTEGER NOT NULL,complement_valid INTEGER NOT NULL,
 entry_hex TEXT NOT NULL,logo_sha1 TEXT NOT NULL CHECK(length(logo_sha1)=40),save_types TEXT,padding_byte INTEGER,padding_bytes INTEGER NOT NULL,
 raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
CREATE TRIGGER immutable_gb_hardware_update BEFORE UPDATE ON gb_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_gb_hardware_delete BEFORE DELETE ON gb_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_gba_hardware_update BEFORE UPDATE ON gba_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_gba_hardware_delete BEFORE DELETE ON gba_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE VIEW v_gb_headers AS
 WITH common AS (SELECT logo_sha1 FROM gb_hardware GROUP BY logo_sha1 ORDER BY count(*) DESC LIMIT 1)
 SELECT r.id AS rom_id,o.sha1,o.size,r.format,r.parse_status,h.title,h.manufacturer_code,h.cgb_mode,h.sgb_flag=3 AS sgb_enhanced,
 h.cartridge_type_name,h.battery,h.rtc,h.rumble,h.rom_size_declared,h.ram_size_declared,h.destination,h.version,
 coalesce(h.licensee_new,printf('%02X',h.licensee_old)) AS licensee,h.header_checksum_valid,h.global_checksum_valid,
 h.logo_sha1=(SELECT logo_sha1 FROM common) AS logo_is_common
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN gb_hardware h ON h.rom_id=r.id;
CREATE VIEW v_gba_headers AS
 WITH common AS (SELECT logo_sha1 FROM gba_hardware GROUP BY logo_sha1 ORDER BY count(*) DESC LIMIT 1)
 SELECT r.id AS rom_id,o.sha1,o.size,r.parse_status,h.title,h.game_code,h.maker_code,h.version,h.complement_valid,h.save_types,
 h.padding_byte,h.padding_bytes,o.size-h.padding_bytes AS content_bytes,h.logo_sha1=(SELECT logo_sha1 FROM common) AS logo_is_common
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN gba_hardware h ON h.rom_id=r.id;
-- DAT diff joins (old/new entry -> release linkage) need both directions indexed.
CREATE INDEX dat_change_old ON dat_changes(old_dat_rom_id);
CREATE INDEX dat_change_new ON dat_changes(new_dat_rom_id);

-- Every information source in this database, grouped as existing (DAT/ROM bytes), extended (No-Intro DB,
-- RetroAchievements, names) and future/placeholder (frontend media and scraping). New snapshots appear as new rows.
CREATE VIEW v_information_sources AS
 SELECT 'existing' AS layer,'No-Intro DAT' AS source,ds.version AS version,ds.imported_at AS imported_at,
  (SELECT count(*) FROM dat_games g WHERE g.dat_set_id=ds.id) AS entries,ds.name AS detail FROM dat_sets ds
 UNION ALL SELECT 'existing','ROM files',NULL,min(imported_at),count(*),'local files (all kinds)' FROM files
 UNION ALL SELECT 'extended','No-Intro DB Export + Dump Log',s.version,s.imported_at,(SELECT count(*) FROM ni_archives a WHERE a.snapshot_id=s.id),'snapshot '||s.id FROM ni_snapshots s
 UNION ALL SELECT 'extended','RetroAchievements',r.fetched_at,r.fetched_at,r.games,'console '||r.console_id||', '||r.hashes||' hashes' FROM ra_snapshots r
 UNION ALL SELECT 'extended','English/Chinese names',i.source_sha256,i.imported_at,(SELECT count(*) FROM game_name_entries e WHERE e.import_id=i.id),i.source_name FROM game_name_imports i
 UNION ALL SELECT 'extended','Documented hardware assertions',NULL,min(created_at),count(*),'from No-Intro serial fields' FROM hardware_assertions
 UNION ALL SELECT 'future','Frontend values (Batocera/ScreenScraper)',NULL,max(updated_at),count(*),'placeholders until scraped' FROM frontend_game_values
 UNION ALL SELECT 'future','Frontend media slots',NULL,max(updated_at),count(*),'placeholders until media is stored' FROM frontend_media_slots
 UNION ALL SELECT 'future','Scrape records',NULL,max(fetched_at),count(*),'provider responses' FROM scrape_records;
