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
