"""Build a fresh payload-free catalog; never copy payload pages and delete later."""
import hashlib,json,pathlib,sqlite3,sys

def resource(c,name,kind,content):
 c.execute('INSERT INTO resources VALUES (?,?,?,?) ON CONFLICT(name) DO UPDATE SET kind=excluded.kind,content=excluded.content,sha256=excluded.sha256',(name,kind,content,hashlib.sha256(content.encode()).hexdigest()))

def build(full,target,catalog_engine):
 full=pathlib.Path(full);target=pathlib.Path(target)
 if target.exists():raise ValueError('Refusing to replace existing catalog output')
 c=sqlite3.connect(target);c.execute('PRAGMA page_size=4096');c.execute('PRAGMA journal_mode=DELETE')
 c.execute('ATTACH DATABASE ? AS original',('file:'+str(full.resolve())+'?mode=ro',))
 schema=c.execute("SELECT type,name,sql FROM original.sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY rowid").fetchall()
 for typ,name,sql in schema:
  if typ=='table':c.execute(sql)
 for typ,name,sql in schema:
  if typ=='table' and name not in ('chunks','object_chunks','compression_groups'):c.execute('INSERT INTO main."'+name+'" SELECT * FROM original."'+name+'"')
 for typ,name,sql in schema:
  if typ!='table':c.execute(sql)
 c.execute('PRAGMA application_id=1380074545');c.execute('PRAGMA user_version='+str(c.execute('PRAGMA original.user_version').fetchone()[0]))
 for key,value in {'edition':'catalog-only','payload_available':'false','storage':'Metadata catalog; compression_groups, chunks and object_chunks intentionally empty; complete expected checksums retained','execution':'Embedded catalog engine permits queries and metadata audit only; populated database required for content operations'}.items():c.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(key,value))
 engine=c.execute("SELECT content FROM resources WHERE name='engine.py'").fetchone()[0]
 resource(c,'engine.full.py','python',engine);resource(c,'engine.py','python',pathlib.Path(catalog_engine).read_text())
 c.commit();c.execute('DETACH DATABASE original');c.execute('VACUUM')
 report={'edition':'catalog-only','payload_available':False,'payloads_verified':False,'excluded_tables':['compression_groups','chunks','object_chunks'],'source_file':full.name,'fresh_database':True,'page_size':c.execute('PRAGMA page_size').fetchone()[0],'integrity_check':c.execute('PRAGMA integrity_check').fetchone()[0],'foreign_key_errors':c.execute('PRAGMA foreign_key_check').fetchall(),'counts':{name:c.execute('SELECT count(*) FROM "'+name+'"').fetchone()[0] for typ,name,sql in schema if typ=='table'},'size_bytes':0}
 for _ in range(3):
  report['size_bytes']=target.stat().st_size;resource(c,'catalog-report','json',json.dumps(report,ensure_ascii=False,indent=2));c.commit()
 assert c.execute('SELECT count(*) FROM chunks').fetchone()[0]==0
 assert c.execute('SELECT count(*) FROM object_chunks').fetchone()[0]==0
 if any(name=='compression_groups' for typ,name,sql in schema):assert c.execute('SELECT count(*) FROM compression_groups').fetchone()[0]==0
 assert c.execute('PRAGMA freelist_count').fetchone()[0]==0
 c.close();return report

if __name__=='__main__':print(json.dumps(build(*sys.argv[1:]),ensure_ascii=False,indent=2))
