"""Appended to the production engine without its __main__ invocation."""
_FullDB=DB
class DB(_FullDB):
    def __init__(self,path):
        super().__init__(path)
        self.c.execute('PRAGMA query_only=ON')
    def stream(self,*args,**kwargs):
        raise ValueError('Catalog-only database: file content is absent; use populated RetroBoxDB.sqlite')
    def group(self,*args,**kwargs):
        raise ValueError('Catalog-only database: compression group payloads are absent')
    def compact_groups(self,*args,**kwargs):
        raise ValueError('Catalog-only database: cannot compact absent payloads')
    def archive_bytes(self,*args,**kwargs):
        raise ValueError('Catalog-only database: archive members are absent; use populated RetroBoxDB.sqlite')
    def stats(self):
        result=super().stats();result['edition']='catalog-only';result['payload_available']=False
        return result
    def audit(self,archives=False):
        if archives:raise ValueError('Full archive audit requires populated database')
        integrity=[r[0] for r in self.c.execute('PRAGMA integrity_check')]
        foreign=[tuple(r) for r in self.c.execute('PRAGMA foreign_key_check')]
        missing=self.c.execute('SELECT count(*) FROM v_file_checksums WHERE source_size IS NULL OR source_crc32 IS NULL OR source_md5 IS NULL OR source_sha1 IS NULL OR source_sha256 IS NULL OR export_size IS NULL OR export_crc32 IS NULL OR export_md5 IS NULL OR export_sha1 IS NULL OR export_sha256 IS NULL').fetchone()[0]
        tables=['chunks','object_chunks']+(['compression_groups'] if self.storage_version>=3 else [])
        payload_rows={name:self.c.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in tables}
        return {'audit_scope':'catalog metadata only','payloads_available':False,'payloads_verified':False,'integrity_check':integrity,'foreign_key_errors':foreign,'files_missing_checksum_fields':missing,'payload_table_rows':payload_rows,'ok':integrity==['ok'] and not foreign and missing==0 and not any(payload_rows.values())}
_full_main=main
def main(db_path,argv):
    if argv and argv[0] not in ('stats','checksums','audit','help'):
        raise SystemExit('Catalog-only database: supported commands are stats, checksums, audit, help; populated database required for content operations')
    return _full_main(db_path,argv)

if __name__=='__main__':main(sys.argv[1],sys.argv[2:])
