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
 basis TEXT NOT NULL CHECK(basis IN ('newest_dat','dat','nointro_db','title','solid_group','shared_blocks'))
) STRICT;
CREATE INDEX object_family_key ON object_families(family_key);
-- Which objects use a block (shared-block family assignment, deduplication reports).
CREATE INDEX object_chunk_block ON object_chunks(chunk_id);
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
-- Famicom Disk System disk images (FDS: sides of 65500 bytes; QD: sides of 65536 bytes with block CRCs; optional
-- 16-byte fwNES header). Values are the disk information block declarations; sides_json has one entry per side.
CREATE TABLE fds_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 image_format TEXT NOT NULL CHECK(image_format IN ('fds','qd','unknown')),fwnes_header INTEGER NOT NULL,fwnes_sides INTEGER,
 side_size INTEGER NOT NULL,sides INTEGER NOT NULL,valid_sides INTEGER NOT NULL,manufacturer_code INTEGER,game_code TEXT,game_type TEXT,
 revision INTEGER,disk_type INTEGER,manufacturing_date TEXT,manufacturing_date_bcd TEXT,country_code INTEGER,trailing_bytes INTEGER NOT NULL,
 sides_json TEXT NOT NULL CHECK(json_valid(sides_json)),raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
CREATE TRIGGER immutable_fds_hardware_update BEFORE UPDATE ON fds_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_fds_hardware_delete BEFORE DELETE ON fds_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE VIEW v_fds_headers AS
 SELECT r.id AS rom_id,o.sha1,o.size,r.format,r.parse_status,h.image_format,h.fwnes_header,h.sides,h.valid_sides,h.manufacturer_code,
 h.game_code,h.game_type,h.revision,h.disk_type,h.manufacturing_date,h.country_code,h.trailing_bytes
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN fds_hardware h ON h.rom_id=r.id;
-- Satellaview (BS-X) memory-pack header at 0x7FB0 (LoROM) or 0xFFB0 (HiROM); the base cartridge uses snes_hardware.
CREATE TABLE bsx_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 header_offset INTEGER NOT NULL,mapping TEXT NOT NULL CHECK(mapping IN ('lorom','hirom')),maker_code TEXT,program_type TEXT NOT NULL,
 title TEXT,title_hex TEXT NOT NULL,block_allocation TEXT NOT NULL,limited_starts INTEGER NOT NULL,broadcast_month INTEGER,broadcast_day INTEGER,
 map_mode INTEGER NOT NULL,execution_type INTEGER NOT NULL,version INTEGER NOT NULL,checksum_declared INTEGER NOT NULL,
 checksum_complement INTEGER NOT NULL,checksum_pair_valid INTEGER NOT NULL,raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
CREATE TRIGGER immutable_bsx_hardware_update BEFORE UPDATE ON bsx_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_bsx_hardware_delete BEFORE DELETE ON bsx_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE VIEW v_bsx_headers AS
 SELECT r.id AS rom_id,o.sha1,o.size,r.format,r.parse_status,h.mapping,h.maker_code,h.title,h.broadcast_month,h.broadcast_day,
 h.limited_starts,h.map_mode,h.version,h.checksum_pair_valid
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN bsx_hardware h ON h.rom_id=r.id;
-- Sega Master System / Mark III 'TMR SEGA' header (0x7FF0, or 0x3FF0/0x1FF0), Codemasters and SDSC headers (0x7FE0).
CREATE TABLE sms_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 header_offset INTEGER,region_code INTEGER,region TEXT,size_code INTEGER,size_declared INTEGER,product_code TEXT,version INTEGER,
 checksum_declared INTEGER,checksum_computed INTEGER,checksum_valid INTEGER,codemasters INTEGER NOT NULL,sdsc INTEGER NOT NULL,sdsc_title TEXT,
 raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
-- Bandai WonderSwan / WonderSwan Color 16-byte footer (both platforms).
CREATE TABLE ws_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 publisher_id INTEGER NOT NULL,color INTEGER NOT NULL,game_id INTEGER NOT NULL,version INTEGER NOT NULL,rom_size_code INTEGER NOT NULL,rom_size_declared INTEGER,
 save_type_code INTEGER NOT NULL,save_type TEXT,save_size INTEGER,flags INTEGER NOT NULL,orientation TEXT NOT NULL,bus_width INTEGER NOT NULL,rtc INTEGER NOT NULL,
 checksum_declared INTEGER NOT NULL,checksum_computed INTEGER NOT NULL,checksum_valid INTEGER NOT NULL,raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
-- SNK NeoGeo Pocket / Pocket Color 64-byte cartridge header (both platforms).
CREATE TABLE ngp_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 license TEXT NOT NULL,licensed INTEGER NOT NULL,start_address INTEGER NOT NULL,software_id INTEGER NOT NULL,sub_code INTEGER NOT NULL,
 color_mode INTEGER NOT NULL,color INTEGER NOT NULL,title TEXT,title_hex TEXT NOT NULL,raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
-- Nintendo Pokemon Mini cartridge header at 0x2100.
CREATE TABLE pokemini_hardware(
 rom_id INTEGER PRIMARY KEY REFERENCES roms(id),
 nintendo INTEGER NOT NULL,game_code TEXT,region_code TEXT,title TEXT,title_hex TEXT NOT NULL,two_player INTEGER NOT NULL,
 raw_json TEXT NOT NULL CHECK(json_valid(raw_json))
) STRICT;
CREATE TRIGGER immutable_sms_hardware_update BEFORE UPDATE ON sms_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_sms_hardware_delete BEFORE DELETE ON sms_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_ws_hardware_update BEFORE UPDATE ON ws_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_ws_hardware_delete BEFORE DELETE ON ws_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_ngp_hardware_update BEFORE UPDATE ON ngp_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_ngp_hardware_delete BEFORE DELETE ON ngp_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_pokemini_hardware_update BEFORE UPDATE ON pokemini_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_pokemini_hardware_delete BEFORE DELETE ON pokemini_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE VIEW v_sms_headers AS
 SELECT r.id AS rom_id,o.sha1,o.size,r.parse_status,printf('%04X',h.header_offset) AS header_offset,h.region,h.size_declared,h.product_code,h.version,
 printf('%04X',h.checksum_declared) AS checksum_declared,printf('%04X',h.checksum_computed) AS checksum_computed,h.checksum_valid,h.codemasters,h.sdsc,h.sdsc_title
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN sms_hardware h ON h.rom_id=r.id;
CREATE VIEW v_ws_headers AS
 SELECT r.id AS rom_id,o.sha1,o.size,r.format,r.parse_status,h.publisher_id,h.color,h.game_id,h.version,h.rom_size_declared,h.save_type,h.save_size,
 h.orientation,h.bus_width,h.rtc,printf('%04X',h.checksum_declared) AS checksum_declared,printf('%04X',h.checksum_computed) AS checksum_computed,h.checksum_valid
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN ws_hardware h ON h.rom_id=r.id;
CREATE VIEW v_ngp_headers AS
 SELECT r.id AS rom_id,o.sha1,o.size,r.format,r.parse_status,h.license,h.licensed,printf('%06X',h.start_address) AS start_address,
 printf('%04X',h.software_id) AS software_id,h.sub_code,h.color,h.title
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN ngp_hardware h ON h.rom_id=r.id;
CREATE VIEW v_pokemini_headers AS
 SELECT r.id AS rom_id,o.sha1,o.size,r.parse_status,h.nintendo,h.game_code,h.region_code,h.title,h.two_player
 FROM roms r JOIN objects o ON o.id=r.object_id JOIN pokemini_hardware h ON h.rom_id=r.id;
-- DAT diff joins (old/new entry -> release linkage) need both directions indexed.
CREATE INDEX dat_change_old ON dat_changes(old_dat_rom_id);
CREATE INDEX dat_change_new ON dat_changes(new_dat_rom_id);

-- Every information source in this database, grouped as existing (DAT/ROM bytes), extended (No-Intro DB,
-- RetroAchievements, names) and future/placeholder (frontend media and scraping). New snapshots appear as new rows.
-- Source collections: every local folder ROM ZIPs were imported from (No-Intro sets, RetroAchievements sets, others).
-- Files belong to a collection by path; members of a ZIP carry the ZIP's source_path.
CREATE TABLE source_collections(
 id INTEGER PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN ('nointro','retroachievements','other')),
 name TEXT NOT NULL,
 root_path TEXT NOT NULL UNIQUE,
 registered_at TEXT NOT NULL
) STRICT;
CREATE VIEW v_collection_files AS
 SELECT sc.id AS collection_id,sc.kind,sc.name AS collection,f.id AS file_id,f.kind AS file_kind,f.parent_file_id,
  f.original_name,f.source_path,f.object_id
 FROM source_collections sc JOIN files f ON f.source_path LIKE replace(replace(sc.root_path,'%','\%'),'_','\_') || '/%' ESCAPE '\';
-- One row per ROM file of a RetroAchievements collection: RA game (latest snapshot), No-Intro validation and release.
CREATE VIEW v_ra_collection AS
 SELECT cf.collection,cf.file_id,cf.original_name,
  (SELECT p.original_name FROM files p WHERE p.id=cf.parent_file_id) AS zip_name,
  r.id AS rom_id,h.ra_md5,g.ra_game_id,g.title AS ra_title,g.category AS ra_category,g.num_achievements,
  (SELECT group_concat(DISTINCT dg.name) FROM validations v JOIN dat_roms dr ON dr.id=v.dat_rom_id JOIN dat_games dg ON dg.id=dr.dat_game_id
    WHERE v.rom_id=r.id AND v.status='match') AS nointro_dat_games,
  (SELECT min(rr.release_id) FROM rom_releases rr WHERE rr.rom_id=r.id) AS release_id,
  CASE WHEN g.ra_game_id IS NULL THEN 'ra_hash_unknown' WHEN EXISTS(SELECT 1 FROM validations v WHERE v.rom_id=r.id AND v.status='match')
   THEN 'in_nointro_dat' ELSE 'ra_only' END AS status
 FROM v_collection_files cf JOIN roms r ON r.object_id=cf.object_id
 LEFT JOIN rom_ra_hashes h ON h.rom_id=r.id
 LEFT JOIN ra_games g ON g.ra_game_id=(SELECT rh.ra_game_id FROM ra_hashes rh WHERE rh.md5=h.ra_md5 AND rh.snapshot_id=(SELECT max(id) FROM ra_snapshots) LIMIT 1)
  AND g.snapshot_id=(SELECT max(id) FROM ra_snapshots)
 WHERE cf.kind='retroachievements' AND cf.file_kind='rom';
CREATE VIEW v_information_sources AS
 SELECT 'existing' AS layer,'No-Intro DAT' AS source,ds.version AS version,ds.imported_at AS imported_at,
  (SELECT count(*) FROM dat_games g WHERE g.dat_set_id=ds.id) AS entries,ds.name AS detail FROM dat_sets ds
 UNION ALL SELECT 'existing','ROM files',NULL,min(imported_at),count(*),'local files (all kinds)' FROM files
 UNION ALL SELECT 'existing','Source collection: '||sc.kind,NULL,sc.registered_at,(SELECT count(*) FROM v_collection_files cf WHERE cf.collection_id=sc.id AND cf.parent_file_id IS NULL),sc.name FROM source_collections sc
 UNION ALL SELECT 'extended','No-Intro DB Export + Dump Log',s.version,s.imported_at,(SELECT count(*) FROM ni_archives a WHERE a.snapshot_id=s.id),'snapshot '||s.id FROM ni_snapshots s
 UNION ALL SELECT 'extended','RetroAchievements',r.fetched_at,r.fetched_at,r.games,'console '||r.console_id||', '||r.hashes||' hashes' FROM ra_snapshots r
 UNION ALL SELECT 'extended','English/Chinese names',i.source_sha256,i.imported_at,(SELECT count(*) FROM game_name_entries e WHERE e.import_id=i.id),i.source_name FROM game_name_imports i
 UNION ALL SELECT 'extended','Documented hardware assertions',NULL,min(created_at),count(*),'from No-Intro serial fields' FROM hardware_assertions
 UNION ALL SELECT 'scraped',CASE s.provider_code WHEN 'launchbox' THEN 'LaunchBox Games Database' ELSE 'ScreenScraper' END,s.source_sha256,s.started_at,
  (SELECT count(*) FROM provider_snapshot_records x WHERE x.snapshot_id=s.id),s.scope||' '||s.source FROM provider_snapshots s
 UNION ALL SELECT 'future','Frontend values (Batocera/ScreenScraper)',NULL,max(updated_at),count(*),'local overrides; scraped values are in provider_record_values' FROM frontend_game_values
 UNION ALL SELECT 'future','Frontend media slots',NULL,max(updated_at),count(*),'placeholders until media is stored' FROM frontend_media_slots
 UNION ALL SELECT 'future','Scrape records',NULL,max(fetched_at),count(*),'provider responses' FROM scrape_records;

-- Provider game information (LaunchBox Games Database, ScreenScraper), filled by local tools that are not published.
-- Local only: the public Catalog keeps these tables with the same structure and no rows.
-- Deduplicated: identical strings are stored once (scrape_texts); a provider game is stored once per distinct content
-- (provider_records keyed by content hash, shared by every release/ROM that links to it and by later snapshots); raw
-- responses are stored once, xz-compressed (scrape_blobs). Per release/ROM only links and check results are stored.
-- No credentials: ScreenScraper URLs are stored without devid/devpassword/ssid/sspassword, responses without ssuser.
CREATE TABLE scrape_texts(id INTEGER PRIMARY KEY,sha256 TEXT NOT NULL UNIQUE CHECK(length(sha256)=64),text TEXT NOT NULL) STRICT;
CREATE TABLE scrape_blobs(
 sha256 TEXT PRIMARY KEY CHECK(length(sha256)=64),codec TEXT NOT NULL CHECK(codec='xz'),size INTEGER NOT NULL,data BLOB NOT NULL
) STRICT, WITHOUT ROWID;
-- LaunchBox: one snapshot per Metadata.zip and platform. ScreenScraper: one snapshot per scraping run.
CREATE TABLE provider_snapshots(
 id INTEGER PRIMARY KEY,provider_code TEXT NOT NULL REFERENCES scraper_providers(code),scope TEXT NOT NULL,source TEXT NOT NULL,
 source_sha256 TEXT,started_at TEXT NOT NULL,finished_at TEXT,details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json))
) STRICT;
CREATE TABLE provider_records(
 id INTEGER PRIMARY KEY,provider_code TEXT NOT NULL REFERENCES scraper_providers(code),provider_key TEXT NOT NULL,
 content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64),raw_sha256 TEXT NOT NULL REFERENCES scrape_blobs(sha256),
 first_seen_at TEXT NOT NULL,UNIQUE(provider_code,provider_key,content_sha256)
) STRICT;
CREATE TABLE provider_snapshot_records(
 snapshot_id INTEGER NOT NULL REFERENCES provider_snapshots(id),record_id INTEGER NOT NULL REFERENCES provider_records(id),
 PRIMARY KEY(snapshot_id,record_id)
) STRICT, WITHOUT ROWID;
-- Field values of a record: name/alt_name (by region), desc (by language), genre, developer, publisher, releasedate (by region),
-- players, rating, ... ; text_id points to the shared deduplicated string.
CREATE TABLE provider_record_values(
 record_id INTEGER NOT NULL REFERENCES provider_records(id),field TEXT NOT NULL,language TEXT NOT NULL DEFAULT '',
 region TEXT NOT NULL DEFAULT '',ordinal INTEGER NOT NULL DEFAULT 0,text_id INTEGER NOT NULL REFERENCES scrape_texts(id),
 PRIMARY KEY(record_id,field,language,region,ordinal)
) STRICT, WITHOUT ROWID;
CREATE INDEX provider_value_text ON provider_record_values(text_id);
-- Media references (no media bytes). locator: LaunchBox image file name, or the ScreenScraper mediaJeu.php query
-- without credentials; v_scraped_media builds the URL.
CREATE TABLE provider_record_media(
 record_id INTEGER NOT NULL REFERENCES provider_records(id),ordinal INTEGER NOT NULL,media_type TEXT NOT NULL,
 region TEXT NOT NULL DEFAULT '',locator TEXT NOT NULL,crc32 TEXT,md5 TEXT,sha1 TEXT,size INTEGER,format TEXT,
 PRIMARY KEY(record_id,ordinal)
) STRICT, WITHOUT ROWID;
-- Every ROM file ScreenScraper lists for a game (jeu/roms): hash evidence for all local variants without extra requests.
CREATE TABLE ss_record_roms(
 record_id INTEGER NOT NULL REFERENCES provider_records(id),ss_rom_id INTEGER NOT NULL,size INTEGER,crc32 TEXT,md5 TEXT,sha1 TEXT,
 file_name TEXT,flags TEXT NOT NULL DEFAULT '',regions TEXT NOT NULL DEFAULT '',PRIMARY KEY(record_id,ss_rom_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX ss_record_rom_sha1 ON ss_record_roms(sha1);
CREATE INDEX ss_record_rom_md5 ON ss_record_roms(md5);
CREATE INDEX ss_record_rom_crc ON ss_record_roms(crc32,size);
-- One row per jeuInfos.php request. outcome: hash_match = the returned game lists a ROM with this file's checksum;
-- name_fallback = ScreenScraper returned a game by file name although no listed ROM has this checksum (doubtful).
CREATE TABLE ss_lookups(
 id INTEGER PRIMARY KEY,snapshot_id INTEGER NOT NULL REFERENCES provider_snapshots(id),
 sha1 TEXT NOT NULL CHECK(length(sha1)=40),md5 TEXT,crc32 TEXT,size INTEGER NOT NULL,rom_name TEXT NOT NULL,system_id INTEGER NOT NULL,
 account TEXT NOT NULL,requested_at TEXT NOT NULL,http_status INTEGER,
 outcome TEXT NOT NULL CHECK(outcome IN ('hash_match','name_fallback','not_found','error')),
 record_id INTEGER REFERENCES provider_records(id),ss_game_id INTEGER,ss_rom_id INTEGER,message TEXT,
 CHECK((outcome IN ('hash_match','name_fallback'))=(record_id IS NOT NULL))
) STRICT;
CREATE INDEX ss_lookup_sha1 ON ss_lookups(sha1);
-- Cross-check of all sources per subject (a release, or a local ROM file without a release).
-- severity: ok = sources agree; info = one source, no contradiction; doubtful = needs review; error = contradiction.
CREATE TABLE scrape_checks(
 subject_kind TEXT NOT NULL CHECK(subject_kind IN ('release','rom')),subject_id INTEGER NOT NULL,title TEXT NOT NULL,
 verdict TEXT NOT NULL,severity TEXT NOT NULL CHECK(severity IN ('ok','info','doubtful','error','pending')),
 accepted TEXT CHECK(accepted IN ('screenscraper','launchbox')),
 ss_game_id INTEGER,ss_method TEXT,lb_database_id INTEGER,lb_method TEXT,flags TEXT NOT NULL DEFAULT '',
 details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json)),checked_at TEXT NOT NULL,
 PRIMARY KEY(subject_kind,subject_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX scrape_check_verdict ON scrape_checks(severity,verdict);
CREATE VIEW v_provider_latest_records AS
 SELECT r.* FROM provider_records r WHERE r.id=(SELECT max(x.id) FROM provider_records x WHERE x.provider_code=r.provider_code AND x.provider_key=r.provider_key);
CREATE VIEW v_provider_record_values AS
 SELECT r.provider_code,r.provider_key,v.record_id,v.field,v.language,v.region,v.ordinal,t.text AS value
 FROM provider_record_values v JOIN provider_records r ON r.id=v.record_id JOIN scrape_texts t ON t.id=v.text_id;
CREATE VIEW v_scraped_media AS
 SELECT r.provider_code,r.provider_key,m.record_id,m.ordinal,m.media_type,m.region,m.format,m.size,m.crc32,m.md5,m.sha1,
 CASE r.provider_code WHEN 'launchbox' THEN 'https://images.launchbox-app.com/'||m.locator
  ELSE 'https://neoclone.screenscraper.fr/api2/mediaJeu.php?'||m.locator END AS url_without_credentials
 FROM provider_record_media m JOIN provider_records r ON r.id=m.record_id;
-- Scraped values per subject from the source the cross-check accepted (accepted is NULL for doubtful/error subjects),
-- latest record of that game. Values are read from the shared records, never copied per release.
CREATE VIEW v_subject_scraped_values AS
 SELECT c.subject_kind,c.subject_id,c.title,c.severity,c.verdict,v.provider_code,v.provider_key,v.field,v.language,v.region,v.ordinal,v.value
 FROM scrape_checks c JOIN v_provider_latest_records r ON r.provider_code=c.accepted
  AND r.provider_key=CAST(CASE c.accepted WHEN 'screenscraper' THEN c.ss_game_id ELSE c.lb_database_id END AS TEXT)
 JOIN v_provider_record_values v ON v.record_id=r.id;
CREATE VIEW v_scrape_check_summary AS
 SELECT subject_kind,severity,verdict,count(*) AS subjects FROM scrape_checks GROUP BY 1,2,3;
