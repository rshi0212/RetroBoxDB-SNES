PRAGMA application_id=1380074545;PRAGMA user_version=3;PRAGMA foreign_keys=ON;
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL) STRICT;
CREATE TABLE resources(name TEXT PRIMARY KEY,kind TEXT NOT NULL,content TEXT NOT NULL,sha256 TEXT NOT NULL CHECK(length(sha256)=64)) STRICT;
CREATE TABLE sources(id INTEGER PRIMARY KEY,title TEXT NOT NULL,url TEXT,version TEXT,retrieved_at TEXT NOT NULL,notes TEXT) STRICT;
CREATE TABLE platforms(id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE,name TEXT NOT NULL,metadata_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata_json))) STRICT;
CREATE TABLE objects(id INTEGER PRIMARY KEY,sha256 TEXT NOT NULL UNIQUE CHECK(length(sha256)=64),sha1 TEXT NOT NULL CHECK(length(sha1)=40),md5 TEXT NOT NULL CHECK(length(md5)=32),crc32 TEXT NOT NULL CHECK(length(crc32)=8),size INTEGER NOT NULL CHECK(size>=0),created_at TEXT NOT NULL,storage_kind TEXT NOT NULL DEFAULT 'chunks' CHECK(storage_kind IN ('chunks','nes_header_body','archive_manifest'))) STRICT;
CREATE TABLE files(id INTEGER PRIMARY KEY,object_id INTEGER NOT NULL REFERENCES objects(id),kind TEXT NOT NULL CHECK(kind IN ('rom','dat','archive','image','video','audio','metadata','header_database','other')),original_name TEXT NOT NULL,source_path TEXT,source_id INTEGER REFERENCES sources(id),parent_file_id INTEGER REFERENCES files(id),member_index INTEGER,member_path TEXT,mime_type TEXT,imported_at TEXT NOT NULL,metadata_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata_json))) STRICT;
CREATE TABLE games(id INTEGER PRIMARY KEY,platform_id INTEGER NOT NULL REFERENCES platforms(id),title TEXT NOT NULL,sort_title TEXT,metadata_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata_json))) STRICT;
CREATE TABLE releases(id INTEGER PRIMARY KEY,game_id INTEGER NOT NULL REFERENCES games(id),title TEXT NOT NULL,region TEXT,revision TEXT,serial TEXT,release_date TEXT,languages_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(languages_json)),metadata_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata_json))) STRICT;
CREATE TABLE roms(id INTEGER PRIMARY KEY,object_id INTEGER NOT NULL REFERENCES objects(id),platform_id INTEGER NOT NULL REFERENCES platforms(id),format TEXT NOT NULL,parse_status TEXT NOT NULL CHECK(parse_status IN ('valid','warning','invalid','unclassified')),header BLOB CHECK(header IS NULL OR length(header)=16),body_object_id INTEGER REFERENCES objects(id),prg_chr_sha256 TEXT,prg_chr_size INTEGER,parser_version TEXT NOT NULL,warnings_json TEXT NOT NULL CHECK(json_valid(warnings_json)),UNIQUE(object_id,platform_id)) STRICT;
CREATE TABLE rom_releases(rom_id INTEGER NOT NULL REFERENCES roms(id),release_id INTEGER NOT NULL REFERENCES releases(id),source_id INTEGER REFERENCES sources(id),notes TEXT,PRIMARY KEY(rom_id,release_id)) STRICT;
CREATE TABLE rom_components(rom_id INTEGER NOT NULL REFERENCES roms(id),ordinal INTEGER NOT NULL,kind TEXT NOT NULL,offset INTEGER NOT NULL CHECK(offset>=0),size INTEGER NOT NULL CHECK(size>=0),sha256 TEXT NOT NULL,PRIMARY KEY(rom_id,ordinal)) STRICT;
CREATE TABLE nes_hardware(rom_id INTEGER PRIMARY KEY REFERENCES roms(id),mapper INTEGER,submapper INTEGER,prg_rom_size INTEGER,chr_rom_size INTEGER,prg_ram_size INTEGER,prg_nvram_size INTEGER,chr_ram_size INTEGER,chr_nvram_size INTEGER,trainer_size INTEGER NOT NULL,nametable_bit INTEGER NOT NULL,alternative_nametable_bit INTEGER NOT NULL,battery INTEGER NOT NULL,console_type INTEGER,timing INTEGER,vs_ppu INTEGER,vs_hardware INTEGER,extended_console INTEGER,misc_rom_count INTEGER,expansion_device INTEGER,raw_json TEXT NOT NULL CHECK(json_valid(raw_json))) STRICT;
CREATE TABLE hardware_assertions(id INTEGER PRIMARY KEY,rom_id INTEGER REFERENCES roms(id),release_id INTEGER REFERENCES releases(id),source_file_id INTEGER REFERENCES files(id),source_id INTEGER REFERENCES sources(id),board TEXT,pcb TEXT,chip TEXT,mapper INTEGER,submapper INTEGER,cic TEXT,mirroring TEXT,metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),confidence TEXT NOT NULL CHECK(confidence IN ('unknown','inferred','documented','verified')),created_at TEXT NOT NULL,CHECK(rom_id IS NOT NULL OR release_id IS NOT NULL)) STRICT;
CREATE TABLE dat_sets(id INTEGER PRIMARY KEY,source_file_id INTEGER NOT NULL REFERENCES files(id),platform_id INTEGER NOT NULL REFERENCES platforms(id),name TEXT NOT NULL,version TEXT,author TEXT,description TEXT,mode TEXT NOT NULL CHECK(mode IN ('headered','headerless','unspecified')),hash_scope TEXT NOT NULL CHECK(hash_scope IN ('full','nes_after_header')),header_json TEXT NOT NULL CHECK(json_valid(header_json)),imported_at TEXT NOT NULL) STRICT;
CREATE TABLE dat_games(id INTEGER PRIMARY KEY,dat_set_id INTEGER NOT NULL REFERENCES dat_sets(id),ordinal INTEGER NOT NULL,name TEXT NOT NULL COLLATE BINARY,description TEXT,cloneof TEXT,romof TEXT,attrs_json TEXT NOT NULL CHECK(json_valid(attrs_json)),raw_xml TEXT NOT NULL,UNIQUE(dat_set_id,ordinal)) STRICT;
CREATE TABLE dat_roms(id INTEGER PRIMARY KEY,dat_game_id INTEGER NOT NULL REFERENCES dat_games(id),ordinal INTEGER NOT NULL,name TEXT NOT NULL COLLATE BINARY,size INTEGER CHECK(size>=0),crc32 TEXT CHECK(crc32 IS NULL OR length(crc32)=8),md5 TEXT CHECK(md5 IS NULL OR length(md5)=32),sha1 TEXT CHECK(sha1 IS NULL OR length(sha1)=40),sha256 TEXT CHECK(sha256 IS NULL OR length(sha256)=64),status TEXT,merge_name TEXT,attrs_json TEXT NOT NULL CHECK(json_valid(attrs_json)),UNIQUE(dat_game_id,ordinal)) STRICT;
CREATE TABLE validations(id INTEGER PRIMARY KEY,rom_id INTEGER NOT NULL REFERENCES roms(id),dat_rom_id INTEGER NOT NULL REFERENCES dat_roms(id),scope TEXT NOT NULL,checked_object_id INTEGER NOT NULL REFERENCES objects(id),status TEXT NOT NULL CHECK(status IN ('match','mismatch','unverifiable')),strength TEXT NOT NULL,details_json TEXT NOT NULL CHECK(json_valid(details_json)),checked_at TEXT NOT NULL,UNIQUE(rom_id,dat_rom_id,scope)) STRICT;
CREATE TABLE transformations(id INTEGER PRIMARY KEY,source_rom_id INTEGER NOT NULL REFERENCES roms(id),result_rom_id INTEGER NOT NULL REFERENCES roms(id),kind TEXT NOT NULL,target_dat_rom_id INTEGER REFERENCES dat_roms(id),evidence_file_id INTEGER REFERENCES files(id),recipe_json TEXT NOT NULL CHECK(json_valid(recipe_json)),verified INTEGER NOT NULL CHECK(verified IN (0,1)),created_at TEXT NOT NULL) STRICT;
CREATE TABLE naming_decisions(id INTEGER PRIMARY KEY,file_id INTEGER NOT NULL REFERENCES files(id),dat_rom_id INTEGER NOT NULL REFERENCES dat_roms(id),canonical_name TEXT NOT NULL COLLATE BINARY,reason TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(file_id,dat_rom_id)) STRICT;
CREATE TABLE archive_profiles(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,spec_url TEXT NOT NULL,settings_json TEXT NOT NULL CHECK(json_valid(settings_json)),limitations TEXT NOT NULL) STRICT;
CREATE TABLE packages(id INTEGER PRIMARY KEY,file_id INTEGER NOT NULL REFERENCES files(id),dat_game_id INTEGER NOT NULL REFERENCES dat_games(id),profile_id INTEGER NOT NULL REFERENCES archive_profiles(id),engine TEXT NOT NULL,validation_json TEXT NOT NULL CHECK(json_valid(validation_json)),created_at TEXT NOT NULL) STRICT;
CREATE TABLE package_members(package_id INTEGER NOT NULL REFERENCES packages(id),ordinal INTEGER NOT NULL,dat_rom_id INTEGER NOT NULL REFERENCES dat_roms(id),rom_id INTEGER NOT NULL REFERENCES roms(id),object_id INTEGER NOT NULL REFERENCES objects(id),name TEXT NOT NULL,PRIMARY KEY(package_id,ordinal),UNIQUE(package_id,name)) STRICT;
CREATE TABLE scrape_records(id INTEGER PRIMARY KEY,game_id INTEGER REFERENCES games(id),release_id INTEGER REFERENCES releases(id),provider TEXT NOT NULL,provider_key TEXT,source_url TEXT,raw_file_id INTEGER NOT NULL REFERENCES files(id),fields_json TEXT NOT NULL CHECK(json_valid(fields_json)),fetched_at TEXT NOT NULL,CHECK(game_id IS NOT NULL OR release_id IS NOT NULL)) STRICT;
CREATE TABLE media(id INTEGER PRIMARY KEY,file_id INTEGER NOT NULL REFERENCES files(id),game_id INTEGER REFERENCES games(id),release_id INTEGER REFERENCES releases(id),rom_id INTEGER REFERENCES roms(id),scrape_id INTEGER REFERENCES scrape_records(id),role TEXT NOT NULL,language TEXT,region TEXT,width INTEGER,height INTEGER,duration_ms INTEGER,codec TEXT,source_url TEXT,metadata_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata_json))) STRICT;
CREATE TABLE events(id INTEGER PRIMARY KEY,action TEXT NOT NULL,entity TEXT,entity_id INTEGER,details_json TEXT NOT NULL CHECK(json_valid(details_json)),created_at TEXT NOT NULL) STRICT;
CREATE TABLE dat_changes(id INTEGER PRIMARY KEY,old_dat_rom_id INTEGER REFERENCES dat_roms(id),new_dat_rom_id INTEGER REFERENCES dat_roms(id),classification TEXT NOT NULL CHECK(classification IN ('unchanged','renamed','case_changed','checksum_changed','added','removed')),evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json))) STRICT;
CREATE TABLE repair_attempts(id INTEGER PRIMARY KEY,target_dat_rom_id INTEGER NOT NULL REFERENCES dat_roms(id),source_rom_id INTEGER REFERENCES roms(id),status TEXT NOT NULL,details_json TEXT NOT NULL CHECK(json_valid(details_json)),created_at TEXT NOT NULL) STRICT;
CREATE TABLE release_dat_games(release_id INTEGER NOT NULL REFERENCES releases(id),dat_game_id INTEGER NOT NULL REFERENCES dat_games(id),PRIMARY KEY(release_id,dat_game_id)) STRICT;
CREATE TABLE compression_groups(
 id INTEGER PRIMARY KEY,
 sha256 BLOB NOT NULL CHECK(length(sha256)=32),
 encoded_sha256 BLOB NOT NULL CHECK(length(encoded_sha256)=32),
 size INTEGER NOT NULL CHECK(size>0 AND size<=2097152),
 codec TEXT NOT NULL CHECK(codec='lzma2-4m'),
 data BLOB NOT NULL CHECK(length(data)>0)
) STRICT;
CREATE TABLE chunks(
 id INTEGER PRIMARY KEY,
 sha256 BLOB NOT NULL UNIQUE CHECK(length(sha256)=32),
 size INTEGER NOT NULL CHECK(size>0 AND size<=1048576),
 codec TEXT NOT NULL CHECK(codec IN ('raw','fill','zlib','lzma','xor-zlib','xor-lzma','group')),
 base_id INTEGER REFERENCES chunks(id),
 depth INTEGER NOT NULL CHECK(depth BETWEEN 0 AND 2),
 data BLOB NOT NULL,
 group_id INTEGER REFERENCES compression_groups(id),
 group_offset INTEGER,
 CHECK((codec IN ('xor-zlib','xor-lzma') AND base_id IS NOT NULL AND depth>0) OR (codec NOT IN ('xor-zlib','xor-lzma') AND base_id IS NULL AND depth=0)),
 CHECK(codec!='raw' OR length(data)=size),
 CHECK(codec!='fill' OR length(data)=1),
 CHECK((codec='group' AND group_id IS NOT NULL AND group_offset IS NOT NULL AND group_offset>=0 AND length(data)=0) OR (codec!='group' AND group_id IS NULL AND group_offset IS NULL))
) STRICT;
CREATE UNIQUE INDEX chunk_group_slice ON chunks(group_id,group_offset) WHERE group_id IS NOT NULL;
CREATE TRIGGER chunk_group_insert BEFORE INSERT ON chunks WHEN NEW.codec='group' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM compression_groups WHERE id=NEW.group_id AND NEW.group_offset+NEW.size<=size) THEN RAISE(ABORT,'invalid compression group slice') END;
END;
CREATE TRIGGER chunk_group_update BEFORE UPDATE ON chunks WHEN NEW.codec='group' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM compression_groups WHERE id=NEW.group_id AND NEW.group_offset+NEW.size<=size) THEN RAISE(ABORT,'invalid compression group slice') END;
END;
CREATE TRIGGER chunk_identity_update BEFORE UPDATE ON chunks WHEN NEW.id!=OLD.id OR NEW.sha256!=OLD.sha256 OR NEW.size!=OLD.size BEGIN
 SELECT RAISE(ABORT,'logical chunk identity is immutable');
END;
CREATE TRIGGER immutable_compression_groups_update BEFORE UPDATE ON compression_groups BEGIN SELECT RAISE(ABORT,'immutable compression group'); END;
CREATE TRIGGER immutable_compression_groups_delete BEFORE DELETE ON compression_groups BEGIN SELECT RAISE(ABORT,'immutable compression group'); END;

CREATE TABLE object_chunks(
 object_id INTEGER NOT NULL REFERENCES objects(id),
 ordinal INTEGER NOT NULL CHECK(ordinal>=0),
 offset INTEGER NOT NULL CHECK(offset>=0),
 chunk_id INTEGER NOT NULL REFERENCES chunks(id),
 repeat INTEGER NOT NULL DEFAULT 1 CHECK(repeat>0),
 PRIMARY KEY(object_id,ordinal),UNIQUE(object_id,offset)
) STRICT, WITHOUT ROWID;
CREATE TABLE nes_recipes(
 object_id INTEGER PRIMARY KEY REFERENCES objects(id),
 body_object_id INTEGER NOT NULL REFERENCES objects(id),
 header BLOB NOT NULL CHECK(length(header)=16 AND hex(substr(header,1,4))='4E45531A'),
 CHECK(object_id!=body_object_id)
) STRICT;
CREATE TABLE archive_plans(
 id INTEGER PRIMARY KEY,
 fingerprint TEXT NOT NULL UNIQUE CHECK(length(fingerprint)=64),
 profile_id INTEGER NOT NULL REFERENCES archive_profiles(id),
 encoder TEXT NOT NULL,zlib_version TEXT NOT NULL,
 size INTEGER NOT NULL CHECK(size>=0),
 crc32 TEXT NOT NULL CHECK(length(crc32)=8),
 md5 TEXT NOT NULL CHECK(length(md5)=32),
 sha1 TEXT NOT NULL CHECK(length(sha1)=40),
 sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 verified_at TEXT NOT NULL
) STRICT;
CREATE TABLE archive_entries(
 plan_id INTEGER NOT NULL REFERENCES archive_plans(id),
 ordinal INTEGER NOT NULL CHECK(ordinal>=0),
 name TEXT NOT NULL COLLATE BINARY,
 object_id INTEGER REFERENCES objects(id),
 is_directory INTEGER NOT NULL CHECK(is_directory IN (0,1)),
 CHECK((is_directory=1 AND object_id IS NULL) OR (is_directory=0 AND object_id IS NOT NULL)),
 PRIMARY KEY(plan_id,ordinal),UNIQUE(plan_id,name)
) STRICT, WITHOUT ROWID;
CREATE TABLE file_archives(file_id INTEGER PRIMARY KEY REFERENCES files(id),plan_id INTEGER NOT NULL REFERENCES archive_plans(id)) STRICT;
CREATE INDEX archive_entries_object ON archive_entries(object_id);
CREATE INDEX file_archives_plan ON file_archives(plan_id);
CREATE VIEW v_storage AS SELECT
 (SELECT coalesce(sum(size),0) FROM objects WHERE storage_kind!='archive_manifest') AS logical_content_bytes,
 (SELECT coalesce(sum(size),0) FROM objects WHERE storage_kind='archive_manifest') AS historical_zip_bytes_not_stored,
 (SELECT coalesce(sum(size),0) FROM chunks) AS unique_raw_chunk_bytes,
 (SELECT coalesce(sum(length(data)),0) FROM chunks)+(SELECT coalesce(sum(length(data)),0) FROM compression_groups) AS stored_chunk_bytes,
 (SELECT count(*) FROM nes_recipes) AS header_body_recipes,
 (SELECT count(*) FROM archive_plans) AS zip_plans,
 (SELECT count(*) FROM files) AS file_occurrences,
 (SELECT count(*) FROM objects) AS catalog_objects;
CREATE VIEW v_file_checksums AS SELECT f.id AS file_id,f.kind,f.original_name,o.storage_kind,
 o.size AS source_size,o.crc32 AS source_crc32,o.md5 AS source_md5,o.sha1 AS source_sha1,o.sha256 AS source_sha256,
 CASE WHEN f.kind='archive' THEN ap.size ELSE o.size END AS export_size,
 CASE WHEN f.kind='archive' THEN ap.crc32 ELSE o.crc32 END AS export_crc32,
 CASE WHEN f.kind='archive' THEN ap.md5 ELSE o.md5 END AS export_md5,
 CASE WHEN f.kind='archive' THEN ap.sha1 ELSE o.sha1 END AS export_sha1,
 CASE WHEN f.kind='archive' THEN ap.sha256 ELSE o.sha256 END AS export_sha256,
 ap.id AS archive_plan_id,ap.encoder,ap.zlib_version,
 CASE WHEN f.kind='archive' THEN ap.sha256=o.sha256 ELSE 1 END AS exported_bytes_equal_source
 FROM files f JOIN objects o ON o.id=f.object_id LEFT JOIN file_archives fa ON fa.file_id=f.id LEFT JOIN archive_plans ap ON ap.id=fa.plan_id;
CREATE VIEW v_rom_checksums AS SELECT r.id AS rom_id,r.format,r.header,o.size,o.crc32,o.md5,o.sha1,o.sha256,
 b.id AS body_object_id,b.size AS body_size,b.crc32 AS body_crc32,b.md5 AS body_md5,b.sha1 AS body_sha1,b.sha256 AS body_sha256
 FROM roms r JOIN objects o ON o.id=r.object_id LEFT JOIN objects b ON b.id=r.body_object_id;
CREATE TRIGGER chunk_base_guard BEFORE INSERT ON chunks WHEN NEW.base_id IS NOT NULL BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM chunks b WHERE b.id=NEW.base_id AND b.size=NEW.size AND b.depth=NEW.depth-1) THEN RAISE(ABORT,'invalid delta base') END;
END;
CREATE TRIGGER nes_recipe_guard BEFORE INSERT ON nes_recipes BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM objects o JOIN objects b ON b.id=NEW.body_object_id WHERE o.id=NEW.object_id AND o.size=b.size+16 AND o.storage_kind='nes_header_body') THEN RAISE(ABORT,'invalid NES reconstruction recipe') END;
END;

CREATE INDEX object_sha1 ON objects(sha1,size);
CREATE INDEX object_crc ON objects(crc32,size);
CREATE INDEX file_object ON files(object_id);
CREATE INDEX dat_rom_sha1 ON dat_roms(sha1,size);
CREATE VIEW v_inventory AS SELECT f.id AS file_id,f.kind,f.original_name,f.source_path,o.id AS object_id,o.size,o.sha256,o.sha1,o.md5,o.crc32,r.id AS rom_id,r.format,r.parse_status FROM files f JOIN objects o ON o.id=f.object_id LEFT JOIN roms r ON r.object_id=o.id;
CREATE VIEW v_exact_duplicates AS SELECT o.id AS object_id,o.sha256,o.size,count(f.id) AS occurrence_count FROM objects o JOIN files f ON f.object_id=o.id GROUP BY o.id HAVING count(f.id)>1;
CREATE VIEW v_nes_body_duplicates AS SELECT body_object_id,count(*) AS variant_count,group_concat(id) AS rom_ids FROM roms WHERE platform_id=(SELECT id FROM platforms WHERE code='nes') AND body_object_id IS NOT NULL GROUP BY body_object_id HAVING count(*)>1;
CREATE VIEW v_nes_prg_chr_candidates AS SELECT prg_chr_sha256,prg_chr_size,count(*) AS variant_count,group_concat(id) AS rom_ids FROM roms WHERE prg_chr_sha256 IS NOT NULL GROUP BY prg_chr_sha256,prg_chr_size HAVING count(*)>1;
CREATE VIEW v_dat_coverage AS SELECT ds.id AS dat_set_id,dr.id AS dat_rom_id,dg.name AS game_name,dr.name AS rom_name,CASE WHEN lower(coalesce(dr.status,''))='nodump' THEN 'nodump' WHEN EXISTS(SELECT 1 FROM validations v WHERE v.dat_rom_id=dr.id AND v.status='match') THEN 'matched' ELSE 'unmatched' END AS status FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id JOIN dat_sets ds ON ds.id=dg.dat_set_id;
CREATE INDEX rom_body ON roms(body_object_id);
CREATE INDEX validation_target ON validations(dat_rom_id,status);
CREATE INDEX dat_game_set ON dat_games(dat_set_id);
CREATE INDEX dat_rom_game ON dat_roms(dat_game_id);
CREATE INDEX files_provenance ON files(source_path,parent_file_id,member_index);
CREATE TRIGGER immutable_chunks_update BEFORE UPDATE ON chunks BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_chunks_delete BEFORE DELETE ON chunks BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_objects_update BEFORE UPDATE ON objects BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_objects_delete BEFORE DELETE ON objects BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_object_chunks_update BEFORE UPDATE ON object_chunks BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_object_chunks_delete BEFORE DELETE ON object_chunks BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_files_update BEFORE UPDATE ON files BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_files_delete BEFORE DELETE ON files BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_roms_update BEFORE UPDATE ON roms BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_roms_delete BEFORE DELETE ON roms BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_rom_components_update BEFORE UPDATE ON rom_components BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_rom_components_delete BEFORE DELETE ON rom_components BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_nes_hardware_update BEFORE UPDATE ON nes_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_nes_hardware_delete BEFORE DELETE ON nes_hardware BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_dat_sets_update BEFORE UPDATE ON dat_sets BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_dat_sets_delete BEFORE DELETE ON dat_sets BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_dat_games_update BEFORE UPDATE ON dat_games BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_dat_games_delete BEFORE DELETE ON dat_games BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_dat_roms_update BEFORE UPDATE ON dat_roms BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_dat_roms_delete BEFORE DELETE ON dat_roms BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_transformations_update BEFORE UPDATE ON transformations BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE TRIGGER immutable_transformations_delete BEFORE DELETE ON transformations BEGIN SELECT RAISE(ABORT,'immutable archival data; create a new version'); END;
CREATE VIEW v_nes_hardware_candidates AS SELECT r.id AS queried_rom_id,h.* FROM roms r JOIN roms variant ON variant.body_object_id=r.body_object_id JOIN nes_hardware h ON h.rom_id=variant.id;
CREATE TRIGGER immutable_nes_recipes_update BEFORE UPDATE ON nes_recipes BEGIN SELECT RAISE(ABORT,'immutable recipe; create a new version'); END;
CREATE TRIGGER immutable_nes_recipes_delete BEFORE DELETE ON nes_recipes BEGIN SELECT RAISE(ABORT,'immutable recipe; create a new version'); END;
CREATE TRIGGER immutable_archive_plans_update BEFORE UPDATE ON archive_plans BEGIN SELECT RAISE(ABORT,'immutable recipe; create a new version'); END;
CREATE TRIGGER immutable_archive_plans_delete BEFORE DELETE ON archive_plans BEGIN SELECT RAISE(ABORT,'immutable recipe; create a new version'); END;
CREATE TRIGGER immutable_archive_entries_update BEFORE UPDATE ON archive_entries BEGIN SELECT RAISE(ABORT,'immutable recipe; create a new version'); END;
CREATE TRIGGER immutable_archive_entries_delete BEFORE DELETE ON archive_entries BEGIN SELECT RAISE(ABORT,'immutable recipe; create a new version'); END;
CREATE TRIGGER immutable_file_archives_update BEFORE UPDATE ON file_archives BEGIN SELECT RAISE(ABORT,'immutable recipe; create a new version'); END;
CREATE TRIGGER immutable_file_archives_delete BEFORE DELETE ON file_archives BEGIN SELECT RAISE(ABORT,'immutable recipe; create a new version'); END;
-- Additive frontend extension 1; the underlying RetroBoxDB storage schema remains v2.
CREATE TABLE scraper_providers(code TEXT PRIMARY KEY,name TEXT NOT NULL,api_base TEXT NOT NULL,documentation_url TEXT NOT NULL) STRICT;
CREATE TABLE frontend_profiles(code TEXT PRIMARY KEY,name TEXT NOT NULL,gamelist_filename TEXT NOT NULL,documentation_url TEXT NOT NULL) STRICT;
CREATE TABLE frontend_platforms(frontend_code TEXT NOT NULL REFERENCES frontend_profiles(code),platform_code TEXT NOT NULL,system_code TEXT NOT NULL,provider_code TEXT NOT NULL REFERENCES scraper_providers(code),provider_system_id TEXT,PRIMARY KEY(frontend_code,platform_code)) STRICT, WITHOUT ROWID;
CREATE TABLE frontend_fields(
 frontend_code TEXT NOT NULL REFERENCES frontend_profiles(code),field_key TEXT NOT NULL,
 category TEXT NOT NULL CHECK(category IN ('info','runtime','media')),
 value_type TEXT NOT NULL,xml_location TEXT NOT NULL DEFAULT 'element' CHECK(xml_location IN ('element','attribute')),
 provider_field TEXT,provider_media_type TEXT,default_extension TEXT,notes TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(frontend_code,field_key)
) STRICT, WITHOUT ROWID;
CREATE TABLE scraper_game_links(
 release_id INTEGER NOT NULL REFERENCES releases(id),provider_code TEXT NOT NULL REFERENCES scraper_providers(code),
 provider_game_id TEXT,status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','matched','not_found','error')),
 raw_file_id INTEGER REFERENCES files(id),source_url TEXT,checked_at TEXT,details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json)),
 CHECK(status!='matched' OR provider_game_id IS NOT NULL),PRIMARY KEY(release_id,provider_code)
) STRICT, WITHOUT ROWID;
CREATE TABLE frontend_game_values(
 release_id INTEGER NOT NULL REFERENCES releases(id),frontend_code TEXT NOT NULL,field_key TEXT NOT NULL,
 language TEXT NOT NULL DEFAULT '',region TEXT NOT NULL DEFAULT '',value_text TEXT NOT NULL,
 provider_code TEXT REFERENCES scraper_providers(code),source_file_id INTEGER REFERENCES files(id),updated_at TEXT,
 FOREIGN KEY(frontend_code,field_key) REFERENCES frontend_fields(frontend_code,field_key),
 CHECK(field_key!='rating' OR CASE WHEN json_valid(value_text) THEN json_type(value_text) IN ('integer','real') AND CAST(value_text AS REAL) BETWEEN 0 AND 1 ELSE 0 END),
 CHECK(field_key NOT IN ('favorite','hidden','kidgame') OR value_text IN ('true','false')),
 PRIMARY KEY(release_id,frontend_code,field_key,language,region)
) STRICT, WITHOUT ROWID;
CREATE TABLE frontend_media_slots(
 release_id INTEGER NOT NULL REFERENCES releases(id),frontend_code TEXT NOT NULL,field_key TEXT NOT NULL,
 language TEXT NOT NULL DEFAULT '',region TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','available','not_found','error')),
 provider_code TEXT REFERENCES scraper_providers(code),provider_media_type TEXT,
 media_id INTEGER REFERENCES media(id),source_url TEXT,export_path TEXT,updated_at TEXT,
 details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json)),
 FOREIGN KEY(frontend_code,field_key) REFERENCES frontend_fields(frontend_code,field_key),
 CHECK(status!='available' OR media_id IS NOT NULL),
 PRIMARY KEY(release_id,frontend_code,field_key,language,region)
) STRICT, WITHOUT ROWID;
CREATE TRIGGER frontend_values_kind_insert BEFORE INSERT ON frontend_game_values BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM frontend_fields WHERE frontend_code=NEW.frontend_code AND field_key=NEW.field_key AND category!='media') THEN RAISE(ABORT,'field is not game information') END;
END;
CREATE TRIGGER frontend_values_kind_update BEFORE UPDATE ON frontend_game_values BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM frontend_fields WHERE frontend_code=NEW.frontend_code AND field_key=NEW.field_key AND category!='media') THEN RAISE(ABORT,'field is not game information') END;
END;
CREATE TRIGGER frontend_media_kind_insert BEFORE INSERT ON frontend_media_slots BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM frontend_fields WHERE frontend_code=NEW.frontend_code AND field_key=NEW.field_key AND category='media') THEN RAISE(ABORT,'field is not a media slot') END;
 SELECT CASE WHEN NEW.media_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM media m JOIN releases r ON r.id=NEW.release_id WHERE m.id=NEW.media_id AND (m.release_id=r.id OR (m.release_id IS NULL AND m.game_id=r.game_id))) THEN RAISE(ABORT,'media belongs to another release/game') END;
END;
CREATE TRIGGER frontend_media_kind_update BEFORE UPDATE ON frontend_media_slots BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM frontend_fields WHERE frontend_code=NEW.frontend_code AND field_key=NEW.field_key AND category='media') THEN RAISE(ABORT,'field is not a media slot') END;
 SELECT CASE WHEN NEW.media_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM media m JOIN releases r ON r.id=NEW.release_id WHERE m.id=NEW.media_id AND (m.release_id=r.id OR (m.release_id IS NULL AND m.game_id=r.game_id))) THEN RAISE(ABORT,'media belongs to another release/game') END;
END;
CREATE VIEW v_screenscraper_games AS
 SELECT r.id AS release_id,r.game_id,r.title,p.code AS platform_code,fp.system_code,
 fp.provider_system_id,l.provider_game_id,coalesce(l.status,'pending') AS status,
 l.raw_file_id,l.source_url,l.checked_at
 FROM releases r JOIN games g ON g.id=r.game_id JOIN platforms p ON p.id=g.platform_id
 JOIN frontend_platforms fp ON fp.platform_code=p.code AND fp.frontend_code='batocera'
 LEFT JOIN scraper_game_links l ON l.release_id=r.id AND l.provider_code=fp.provider_code
 WHERE fp.provider_code='screenscraper';
CREATE VIEW v_batocera_game_fields AS
 SELECT r.id AS release_id,r.game_id,r.title AS catalog_title,fp.system_code,d.field_key,d.category,d.value_type,d.xml_location,
 coalesce(v.language,'') AS language,coalesce(v.region,'') AS region,
 CASE WHEN v.value_text IS NOT NULL THEN v.value_text WHEN d.field_key='name' THEN r.title ELSE NULL END AS value_text,
 CASE WHEN v.value_text IS NOT NULL THEN 'populated' WHEN d.field_key='name' THEN 'catalog_fallback' ELSE 'pending' END AS status,
 d.provider_field,v.provider_code,v.source_file_id,v.updated_at
 FROM releases r JOIN games g ON g.id=r.game_id JOIN platforms p ON p.id=g.platform_id
 JOIN frontend_platforms fp ON fp.platform_code=p.code AND fp.frontend_code='batocera'
 JOIN frontend_fields d ON d.frontend_code=fp.frontend_code AND d.category!='media'
 LEFT JOIN frontend_game_values v ON v.release_id=r.id AND v.frontend_code=d.frontend_code AND v.field_key=d.field_key;
CREATE VIEW v_batocera_media_slots AS
 SELECT r.id AS release_id,r.game_id,r.title AS catalog_title,fp.system_code,d.field_key,
 coalesce(s.language,'') AS language,coalesce(s.region,'') AS region,coalesce(s.status,'pending') AS status,
 coalesce(s.provider_code,fp.provider_code) AS provider_code,coalesce(s.provider_media_type,d.provider_media_type) AS provider_media_type,
 d.default_extension,s.media_id,s.source_url,s.export_path,
 m.file_id,m.width,m.height,m.duration_ms,m.codec,o.size,o.crc32,o.md5,o.sha1,o.sha256,
 CASE WHEN o.id IS NULL THEN 0 WHEN (SELECT value FROM meta WHERE key='payload_available')='false' THEN 0 ELSE EXISTS(SELECT 1 FROM object_chunks oc WHERE oc.object_id=o.id) END AS payload_available
 FROM releases r JOIN games g ON g.id=r.game_id JOIN platforms p ON p.id=g.platform_id
 JOIN frontend_platforms fp ON fp.platform_code=p.code AND fp.frontend_code='batocera'
 JOIN frontend_fields d ON d.frontend_code=fp.frontend_code AND d.category='media'
 LEFT JOIN frontend_media_slots s ON s.release_id=r.id AND s.frontend_code=d.frontend_code AND s.field_key=d.field_key
 LEFT JOIN media m ON m.id=s.media_id LEFT JOIN files f ON f.id=m.file_id LEFT JOIN objects o ON o.id=f.object_id;
INSERT INTO scraper_providers VALUES ('screenscraper','ScreenScraper','https://api.screenscraper.fr/api2/','https://www.screenscraper.fr/webapi2.php');
INSERT INTO frontend_profiles VALUES ('batocera','Batocera EmulationStation','gamelist.xml','https://github.com/batocera-linux/batocera-emulationstation/blob/master/es-app/src/MetaData.cpp');
INSERT INTO frontend_platforms VALUES ('batocera','nes','nes','screenscraper',NULL);
INSERT INTO frontend_fields VALUES ('batocera','name','info','text','element','noms/nom',NULL,NULL,'Regional title; existing catalog title is a labeled fallback, not a scraped match.');
INSERT INTO frontend_fields VALUES ('batocera','desc','info','text','element','synopsis/synopsis',NULL,NULL,'Select by language; preserve full source response separately.');
INSERT INTO frontend_fields VALUES ('batocera','genre','info','text','element','genres/genre',NULL,NULL,'Language-specific display genre; provider group IDs remain in raw response.');
INSERT INTO frontend_fields VALUES ('batocera','developer','info','text','element','developpeur',NULL,NULL,'');
INSERT INTO frontend_fields VALUES ('batocera','publisher','info','text','element','editeur',NULL,NULL,'');
INSERT INTO frontend_fields VALUES ('batocera','family','info','text','element','familles/famille',NULL,NULL,'');
INSERT INTO frontend_fields VALUES ('batocera','releasedate','info','datetime','element','dates/date',NULL,NULL,'Convert provider date to YYYYMMDDTHHMMSS for gamelist XML; retain original precision in source metadata.');
INSERT INTO frontend_fields VALUES ('batocera','rating','info','rating','element','note',NULL,NULL,'ScreenScraper score / 20; Batocera value range 0..1. Unknown remains NULL.');
INSERT INTO frontend_fields VALUES ('batocera','players','info','text','element','joueurs',NULL,NULL,'Preserve ranges such as 1-2 as text.');
INSERT INTO frontend_fields VALUES ('batocera','lang','info','text','element',NULL,NULL,NULL,'Locale selection is separate from this display field.');
INSERT INTO frontend_fields VALUES ('batocera','region','info','text','element',NULL,NULL,NULL,'');
INSERT INTO frontend_fields VALUES ('batocera','path','info','path','element',NULL,NULL,NULL,'Choose an actual ROM/archive variant before assigning an export path.');
INSERT INTO frontend_fields VALUES ('batocera','sortname','info','text','element',NULL,NULL,NULL,'');
INSERT INTO frontend_fields VALUES ('batocera','tags','info','text','element',NULL,NULL,NULL,'');
INSERT INTO frontend_fields VALUES ('batocera','crc32','info','checksum','element',NULL,NULL,NULL,'Use the selected file variant checksum; do not mix source and output identities.');
INSERT INTO frontend_fields VALUES ('batocera','md5','info','checksum','element',NULL,NULL,NULL,'Use the selected file variant checksum; do not mix source and output identities.');
INSERT INTO frontend_fields VALUES ('batocera','id','info','identifier','attribute','jeu/@id',NULL,NULL,'ScreenScraper game ID is an XML game attribute, not a guessed catalog ID.');
INSERT INTO frontend_fields VALUES ('batocera','favorite','runtime','boolean','element',NULL,NULL,NULL,'Local frontend state, not fetched game information.');
INSERT INTO frontend_fields VALUES ('batocera','hidden','runtime','boolean','element',NULL,NULL,NULL,'Local frontend state, not fetched game information.');
INSERT INTO frontend_fields VALUES ('batocera','kidgame','runtime','boolean','element',NULL,NULL,NULL,'Local frontend state, not fetched game information.');
INSERT INTO frontend_fields VALUES ('batocera','playcount','runtime','integer','element',NULL,NULL,NULL,'Local frontend state, not fetched game information.');
INSERT INTO frontend_fields VALUES ('batocera','lastplayed','runtime','datetime','element',NULL,NULL,NULL,'Local frontend state, not fetched game information.');
INSERT INTO frontend_fields VALUES ('batocera','gametime','runtime','integer','element',NULL,NULL,NULL,'Local frontend state, not fetched game information.');
INSERT INTO frontend_fields VALUES ('batocera','emulator','runtime','text','element',NULL,NULL,NULL,'Local frontend state, not fetched game information.');
INSERT INTO frontend_fields VALUES ('batocera','core','runtime','text','element',NULL,NULL,NULL,'Local frontend state, not fetched game information.');
INSERT INTO frontend_fields VALUES ('batocera','image','media','image','element',NULL,'ss','jpg','Configurable primary illustration; screenshot is the initial mapping.');
INSERT INTO frontend_fields VALUES ('batocera','thumbnail','media','image','element',NULL,'box-2D','png','Configurable box/thumbnail mapping.');
INSERT INTO frontend_fields VALUES ('batocera','marquee','media','image','element',NULL,'wheel-hd','png','Configurable logo mapping.');
INSERT INTO frontend_fields VALUES ('batocera','video','media','video','element',NULL,'video','mp4','');
INSERT INTO frontend_fields VALUES ('batocera','fanart','media','image','element',NULL,'fanart','jpg','');
INSERT INTO frontend_fields VALUES ('batocera','titleshot','media','image','element',NULL,'sstitle','jpg','');
INSERT INTO frontend_fields VALUES ('batocera','manual','media','document','element',NULL,'manuel','pdf','Use files.kind=other for PDF bytes.');
INSERT INTO frontend_fields VALUES ('batocera','magazine','media','document','element',NULL,NULL,'pdf','Reserved field; no assumed ScreenScraper mapping.');
INSERT INTO frontend_fields VALUES ('batocera','map','media','image','element',NULL,'maps','jpg','');
INSERT INTO frontend_fields VALUES ('batocera','bezel','media','image','element',NULL,'bezel-16-9','png','');
INSERT INTO frontend_fields VALUES ('batocera','cartridge','media','image','element',NULL,NULL,'png','Reserved artwork slot; select an available provider type after discovery.');
INSERT INTO frontend_fields VALUES ('batocera','boxart','media','image','element',NULL,'box-3D','png','Alternate box artwork.');
INSERT INTO frontend_fields VALUES ('batocera','boxback','media','image','element',NULL,'box-2D-back','png','');
INSERT INTO frontend_fields VALUES ('batocera','wheel','media','image','element',NULL,'wheel','png','');
INSERT INTO frontend_fields VALUES ('batocera','mix','media','image','element',NULL,'mixrbv1','png','Composite artwork; configurable mapping, not generated by this extension.');

CREATE TABLE IF NOT EXISTS ni_snapshots(
 id INTEGER PRIMARY KEY,platform_id INTEGER NOT NULL REFERENCES platforms(id),
 source_id INTEGER NOT NULL REFERENCES sources(id),version TEXT NOT NULL,
 db_file_id INTEGER NOT NULL REFERENCES files(id),dumplog_file_id INTEGER NOT NULL REFERENCES files(id),
 db_sha256 TEXT NOT NULL CHECK(length(db_sha256)=64),dumplog_sha256 TEXT NOT NULL CHECK(length(dumplog_sha256)=64),
 imported_at TEXT NOT NULL,UNIQUE(db_sha256,dumplog_sha256)
) STRICT;
CREATE TABLE IF NOT EXISTS ni_archives(
 snapshot_id INTEGER NOT NULL REFERENCES ni_snapshots(id),archive_id TEXT NOT NULL,
 title TEXT NOT NULL,attrs_json TEXT NOT NULL CHECK(json_valid(attrs_json)),
 PRIMARY KEY(snapshot_id,archive_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ni_files(
 snapshot_id INTEGER NOT NULL REFERENCES ni_snapshots(id),file_id TEXT NOT NULL,
 format TEXT NOT NULL,extension TEXT,size INTEGER NOT NULL CHECK(size>=0),
 crc32 TEXT NOT NULL CHECK(length(crc32)=8),md5 TEXT NOT NULL CHECK(length(md5)=32),
 sha1 TEXT NOT NULL CHECK(length(sha1)=40),sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 bad INTEGER NOT NULL CHECK(bad IN (0,1)),mia INTEGER NOT NULL CHECK(mia IN (0,1)),
 object_id INTEGER REFERENCES objects(id),attrs_json TEXT NOT NULL CHECK(json_valid(attrs_json)),
 PRIMARY KEY(snapshot_id,file_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ni_files_sha256 ON ni_files(sha256);
CREATE TABLE IF NOT EXISTS ni_sources(
 snapshot_id INTEGER NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('source','release')),external_id TEXT NOT NULL,
 archive_id TEXT NOT NULL,source_id INTEGER NOT NULL REFERENCES sources(id),
 details_json TEXT NOT NULL CHECK(json_valid(details_json)),serials_json TEXT NOT NULL CHECK(json_valid(serials_json)),
 hardware_assertion_id INTEGER REFERENCES hardware_assertions(id),
 PRIMARY KEY(snapshot_id,kind,external_id),
 FOREIGN KEY(snapshot_id,archive_id) REFERENCES ni_archives(snapshot_id,archive_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ni_sources_archive ON ni_sources(snapshot_id,archive_id);
CREATE TABLE IF NOT EXISTS ni_source_files(
 snapshot_id INTEGER NOT NULL,kind TEXT NOT NULL,external_id TEXT NOT NULL,ordinal INTEGER NOT NULL,file_id TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,kind,external_id,ordinal),
 FOREIGN KEY(snapshot_id,kind,external_id) REFERENCES ni_sources(snapshot_id,kind,external_id),
 FOREIGN KEY(snapshot_id,file_id) REFERENCES ni_files(snapshot_id,file_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ni_source_files_file ON ni_source_files(snapshot_id,file_id);
CREATE TABLE IF NOT EXISTS ni_headers(
 snapshot_id INTEGER NOT NULL,file_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('declared','original_note')),
 header BLOB NOT NULL CHECK(length(header)=16 AND hex(substr(header,1,4))='4E45531A'),
 interpretation_json TEXT NOT NULL CHECK(json_valid(interpretation_json)),
 PRIMARY KEY(snapshot_id,file_id,kind),FOREIGN KEY(snapshot_id,file_id) REFERENCES ni_files(snapshot_id,file_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ni_dat_links(
 snapshot_id INTEGER NOT NULL,file_id TEXT NOT NULL,dat_rom_id INTEGER NOT NULL REFERENCES dat_roms(id),
 PRIMARY KEY(snapshot_id,file_id,dat_rom_id),FOREIGN KEY(snapshot_id,file_id) REFERENCES ni_files(snapshot_id,file_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ni_archive_releases(
 snapshot_id INTEGER NOT NULL,archive_id TEXT NOT NULL,release_id INTEGER NOT NULL REFERENCES releases(id),basis TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,archive_id,release_id),FOREIGN KEY(snapshot_id,archive_id) REFERENCES ni_archives(snapshot_id,archive_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ni_dumplog(
 snapshot_id INTEGER NOT NULL,archive_id TEXT NOT NULL,status_raw TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('verified','trusted_unverified','unverified','bad','no_dump','missing','unknown')),
 trusted_count INTEGER,fields_json TEXT NOT NULL CHECK(json_valid(fields_json)),
 PRIMARY KEY(snapshot_id,archive_id),FOREIGN KEY(snapshot_id,archive_id) REFERENCES ni_archives(snapshot_id,archive_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ni_dumplog_files(
 snapshot_id INTEGER NOT NULL,archive_id TEXT NOT NULL,ordinal INTEGER NOT NULL,size INTEGER NOT NULL,md5 TEXT NOT NULL CHECK(length(md5)=32),
 PRIMARY KEY(snapshot_id,archive_id,ordinal),FOREIGN KEY(snapshot_id,archive_id) REFERENCES ni_dumplog(snapshot_id,archive_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ni_pair_checks(
 snapshot_id INTEGER NOT NULL,headered_file_id TEXT NOT NULL,headerless_file_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('verified','mismatch','body_unavailable','no_header')),
 details_json TEXT NOT NULL CHECK(json_valid(details_json)),
 PRIMARY KEY(snapshot_id,headered_file_id,headerless_file_id),
 FOREIGN KEY(snapshot_id,headered_file_id) REFERENCES ni_files(snapshot_id,file_id),
 FOREIGN KEY(snapshot_id,headerless_file_id) REFERENCES ni_files(snapshot_id,file_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ni_reconstructions(
 snapshot_id INTEGER NOT NULL,file_id TEXT NOT NULL,body_object_id INTEGER NOT NULL REFERENCES objects(id),
 result_object_id INTEGER NOT NULL REFERENCES objects(id),rom_id INTEGER NOT NULL REFERENCES roms(id),file_record_id INTEGER NOT NULL REFERENCES files(id),
 checked_at TEXT NOT NULL,PRIMARY KEY(snapshot_id,file_id),FOREIGN KEY(snapshot_id,file_id) REFERENCES ni_files(snapshot_id,file_id)
) STRICT, WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ni_anomalies(
 id INTEGER PRIMARY KEY,snapshot_id INTEGER NOT NULL REFERENCES ni_snapshots(id),archive_id TEXT,
 category TEXT NOT NULL,details_json TEXT NOT NULL CHECK(json_valid(details_json)),
 FOREIGN KEY(snapshot_id,archive_id) REFERENCES ni_archives(snapshot_id,archive_id)
) STRICT;
CREATE VIEW IF NOT EXISTS v_nointro_files AS
 SELECT f.*,CASE WHEN f.object_id IS NOT NULL AND COALESCE((SELECT value FROM meta WHERE key='payload_available'),'true')!='false' THEN 1 ELSE 0 END AS payload_available,
 hex(h.header) AS declared_header_hex FROM ni_files f LEFT JOIN ni_headers h ON h.snapshot_id=f.snapshot_id AND h.file_id=f.file_id AND h.kind='declared';
CREATE VIEW IF NOT EXISTS v_nointro_hardware AS
 SELECT s.snapshot_id,s.archive_id,a.title,s.kind,s.external_id,s.source_id,s.hardware_assertion_id,
 json_extract(s.serials_json,'$.pcb_serial') AS pcb,
 json_extract(s.serials_json,'$.romchip_serial1') AS romchip1,
 json_extract(s.serials_json,'$.romchip_serial2') AS romchip2,
 json_extract(s.serials_json,'$.lockout_serial') AS lockout,
 json_extract(s.serials_json,'$.savechip_serial') AS savechip,s.serials_json,s.details_json
 FROM ni_sources s JOIN ni_archives a USING(snapshot_id,archive_id) WHERE s.serials_json!='{}';
CREATE VIEW IF NOT EXISTS v_nointro_status AS
 SELECT d.snapshot_id,d.archive_id,a.title,d.status_raw,d.status,d.trusted_count
 FROM ni_dumplog d JOIN ni_archives a USING(snapshot_id,archive_id);
CREATE VIEW IF NOT EXISTS v_nointro_headers AS
 SELECT h.snapshot_id,h.file_id,h.kind,hex(h.header) AS header_hex,h.interpretation_json,f.format,f.sha256,f.object_id
 FROM ni_headers h JOIN ni_files f USING(snapshot_id,file_id);

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
