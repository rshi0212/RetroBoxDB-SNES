"""No-Intro NES DB Export/Dumplog importer. Python stdlib only; no bundled inputs.

Run after extracting nointro.py, nointro_schema.sql and the production engine.py:
python3 -B nointro.py FULL.sqlite DB.zip DUMPLOG.zip
Snapshots are transactional and idempotent by the two uncompressed input hashes.
"""
import collections,csv,hashlib,io,json,pathlib,re,sys,zipfile
import xml.etree.ElementTree as ET
from engine import DB,hashes,now,js,parse_nes,crc_shift,safe_name

FIELDS=('size','crc32','md5','sha1','sha256')
SERIAL_FIELDS={'Media Sn 1':'media_serial1','Media Sn 2':'media_serial2','Media Sn 3':'media_serial3','PCB Sn':'pcb_serial','ROMChip Sn 1':'romchip_serial1','ROMChip Sn 2':'romchip_serial2','Lockout Sn':'lockout_serial','SaveChip Sn':'savechip_serial','Chip Sn':'chip_serial','Box Sn':'box_serial','Media Stamp':'mediastamp','Digital Sn 1':'digital_serial1','Digital Sn 2':'digital_serial2'}

def agrees(actual,expected):
 return all(str(actual[k]).lower()==str(expected[k]).lower() for k in FIELDS if expected.get(k) is not None)

def read_input(path):
 path=pathlib.Path(path);raw=path.read_bytes()
 if path.suffix.lower()!='.zip':return path.name,raw,None
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  members=[i for i in z.infolist() if not i.is_dir()]
  if len(members)!=1 or members[0].file_size>128*1024*1024:raise ValueError('Expected one bounded metadata member')
  member=members[0];safe_name(member.filename)
  return member.filename,z.read(member),raw

def parse_export(raw):
 if b'<!ENTITY' in raw.upper() or b'<!DOCTYPE' in raw.upper():raise ValueError('Entity/DTD declarations unsupported')
 raw=re.sub(br'^\s*<\?xml[^>]*\?>',b'',raw)
 root=ET.fromstring(b'<export>'+raw+b'</export>')
 if root.find('datafile') is None:raise ValueError('Missing DB datafile')
 archives={};files={};sources=[];pairs=set();ambiguous=set()
 for game in root.find('datafile').findall('game'):
  a=dict(game.find('archive').attrib);aid=a['number']
  if aid in archives:raise ValueError('Repeated archive ID '+aid)
  archives[aid]={'title':game.get('name'),'attrs':a}
  for kind in ('source','release'):
   for node in game.findall(kind):
    d=node.find('details');s=node.find('serials')
    details={} if d is None else dict(d.attrib);serials={} if s is None else dict(s.attrib)
    record={'kind':kind,'id':details['id'],'archive':aid,'details':details,'serials':serials,'files':[]}
    for f in node.findall('file'):
     f=dict(f.attrib);fid=f['id']
     if fid in files and files[fid]!=f:raise ValueError('Conflicting repeated file ID '+fid)
     for k,n in [('crc32',8),('md5',32),('sha1',40),('sha256',64)]:
      if not re.fullmatch('[0-9a-fA-F]{'+str(n)+'}',f[k]):raise ValueError('Invalid '+k)
     if int(f['size'])<0:raise ValueError('Negative file size')
     files[fid]=f;record['files'].append(fid)
    hs={i for i in record['files'] if files[i]['format']=='Headered'}
    bs={i for i in record['files'] if files[i]['format']=='Headerless'}
    for h in hs:
     for b in bs:
      if len(hs)==len(bs)==1 or int(files[h]['size'])==int(files[b]['size'])+16:
       pairs.add((h,b))
       if len(hs)>1 or len(bs)>1:ambiguous.add((h,b))
    sources.append(record)
 keys=[(s['kind'],s['id']) for s in sources]
 if len(set(keys))!=len(keys):raise ValueError('Repeated source identity')
 return {'version':root.findtext('header/version') or 'unknown','archives':archives,'files':files,'sources':sources,'pairs':pairs,'ambiguous':ambiguous}

def parse_log(raw):
 rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter=';',escapechar='\\'))
 seen=set()
 for r in rows:
  if None in r or any(v is None for v in r.values()):raise ValueError('Malformed Dumplog row')
  if r['ID'] in seen:raise ValueError('Repeated Dumplog archive')
  seen.add(r['ID']);parts=[]
  if r['Size']!='!no_file':
   sizes=r['Size'].split('-');md5s=r['MD5'].split('-')
   if len(sizes)!=len(md5s):raise ValueError('Unbalanced Dumplog multi-file list')
   for size,md5 in zip(sizes,md5s):
    if not size.isdigit() or not re.fullmatch('[0-9a-fA-F]{32}',md5):raise ValueError('Invalid Dumplog file identity')
    parts.append((int(size),md5.lower()))
  status=r['Status'];m=re.fullmatch(r'Trusted \((\d+)\) \((Verified|Not Verified)\)',status)
  state=('verified' if m[2]=='Verified' else 'trusted_unverified') if m else {'Not verified':'unverified','Bad':'bad','No dump':'no_dump','Missing':'missing'}.get(status,'unknown')
  r={'fields':r,'parts':parts,'status':state,'trusted_count':int(m[1]) if m else None}
  yield r

def header_metadata(header):
 # Parsing a header alone intentionally has no payload-size validation claim.
 p=parse_nes(header,'headered')
 return {'hardware':p['hardware'],'meaning':'header declaration, not verified physical hardware; payload layout must be checked separately'}

def install(db):
 # Execute individual CREATE statements without an implicit transaction commit.
 for statement in (pathlib.Path(__file__).with_name('nointro_schema.sql')).read_text().split(';'):
  if statement.strip():db.c.execute(statement)
 db.c.execute("INSERT OR REPLACE INTO meta VALUES ('nointro_extension_version','1')")

def import_snapshot(db,dbpath,logpath,progress=lambda text:None):
 c=db.c
 edition=c.execute("SELECT value FROM meta WHERE key='payload_available'").fetchone()
 if edition and edition[0]=='false':raise ValueError('Cannot import into a payload-free catalog')
 name,raw,zipraw=read_input(dbpath);lname,lraw,lzipraw=read_input(logpath)
 parsed=parse_export(raw);logs=list(parse_log(lraw));dh=hashes(raw);lh=hashes(lraw)
 for row in logs:
  r=row['fields'];a=parsed['archives'].get(r['ID'])
  if not a or a['title']!=r['Name']:raise ValueError('Dumplog/DB archive identity mismatch: '+r['ID'])
 c.execute('SAVEPOINT nointro_import')
 try:
  install(db)
  old=c.execute('SELECT id FROM ni_snapshots WHERE db_sha256=? AND dumplog_sha256=?',(dh['sha256'],lh['sha256'])).fetchone()
  if old:c.execute('RELEASE nointro_import');return {'snapshot_id':old[0],'already_imported':True}
  src=db.insert('sources',title='No-Intro NES DB Export and Headered Dumplog',url='https://datomatic.no-intro.org/',version=parsed['version'],retrieved_at=now(),notes='Original snapshot identities retained; per-dump provenance is separate')
  def store_input(path,name,data,zipped):
   parent=None
   if zipped is not None:
    oid,_=db.object_record(hashes(zipped),'archive_manifest')
    parent=db.file(oid,pathlib.Path(path).name,'archive',path=str(path),metadata={'nointro_snapshot':parsed['version']})
   oid=db.put(data);fid=db.insert('files',object_id=oid,original_name=name,kind='dat',source_path=str(path),source_id=src,parent_file_id=parent,member_index=0 if parent else None,member_path=name if parent else None,imported_at=now(),metadata_json='{}')
   if parent:
    plan=db.plan([(name,oid)]);c.execute('INSERT OR IGNORE INTO file_archives VALUES (?,?)',(parent,plan))
   return fid
  df=store_input(dbpath,name,raw,zipraw);lf=store_input(logpath,lname,lraw,lzipraw)
  sid=db.insert('ni_snapshots',platform_id=1,source_id=src,version=parsed['version'],db_file_id=df,dumplog_file_id=lf,db_sha256=dh['sha256'],dumplog_sha256=lh['sha256'],imported_at=now())
  def anomaly(category,detail,aid=None):db.insert('ni_anomalies',snapshot_id=sid,archive_id=aid,category=category,details_json=js(detail))
  for aid,a in parsed['archives'].items():c.execute('INSERT INTO ni_archives VALUES (?,?,?,?)',(sid,aid,a['title'],js(a['attrs'])))
  objs=[dict(r) for r in c.execute('SELECT * FROM objects')];bysha={o['sha256']:o for o in objs};bycrc=collections.defaultdict(list)
  for o in objs:
   if o['storage_kind']!='archive_manifest':bycrc[o['size'],o['crc32']].append(o['id'])
  known={};headers={};file_archives=collections.defaultdict(set)
  for s in parsed['sources']:
   for fid in s['files']:file_archives[fid].add(s['archive'])
  for fid,f in parsed['files'].items():
   o=bysha.get(f['sha256'].lower());oid=o['id'] if o and agrees(o,f) else None
   if oid is not None:known[fid]=oid
   extra={k:v for k,v in f.items() if k not in set(FIELDS)|{'id','format','extension','bad','mia','header'}}
   c.execute('INSERT INTO ni_files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,fid,f['format'],f.get('extension'),int(f['size']),f['crc32'].lower(),f['md5'].lower(),f['sha1'].lower(),f['sha256'].lower(),int(f.get('bad')=='1'),int(f.get('mia')=='1'),oid,js(extra)))
   candidates=[]
   if f.get('header'):candidates.append(('declared',f['header']))
   m=re.search(r'original(?: file| iNES| NES 2\.0)? header:?\s*((?:[0-9A-Fa-f]{2}[ \t]*){16})',f.get('note',''),re.I)
   if m:candidates.append(('original_note',m[1]))
   elif re.search(r'original.*header',f.get('note',''),re.I):anomaly('unparsed_original_header_note',{'file_id':fid,'note':f['note'],'policy':'Preserve text; do not guess missing hexadecimal digits'})
   for kind,value in candidates:
    try:
     h=bytes.fromhex(value)
     if len(h)!=16 or h[:4]!=b'NES\x1a':raise ValueError('Not an NES header')
    except ValueError:anomaly('invalid_header',{'file_id':fid,'kind':kind,'value':value});continue
    c.execute('INSERT INTO ni_headers VALUES (?,?,?,?,?)',(sid,fid,kind,h,js(header_metadata(h))))
    if kind=='declared':headers[fid]=h
   if f.get('header') and f['format']!='Headered':anomaly('header_on_headerless',{'file_id':fid})
  targets=[dict(r) for r in c.execute('SELECT dr.*,dg.dat_set_id,dg.name AS game_name FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id')]
  target_index=collections.defaultdict(list)
  for t in targets:target_index[t['size'],t['md5']].append(t)
  links=collections.defaultdict(list)
  for fid,f in parsed['files'].items():
   for t in target_index[int(f['size']),f['md5'].lower()]:
    if agrees(f,t):links[fid].append(t);c.execute('INSERT INTO ni_dat_links VALUES (?,?,?)',(sid,fid,t['id']))
  progress('Parsed normalized file identities and DAT links')
  source_ids={}
  for s in parsed['sources']:
   aid=s['archive'];d=s['details'];sourceid=db.insert('sources',title='No-Intro '+s['kind']+' '+s['id']+' / '+aid,url=d.get('link1'),version=parsed['version'],retrieved_at=now(),notes='Snapshot '+str(sid)+'; detailed provenance in ni_sources')
   source_ids[s['kind'],s['id']]=sourceid
   c.execute('INSERT INTO ni_sources VALUES (?,?,?,?,?,?,?,NULL)',(sid,s['kind'],s['id'],aid,sourceid,js(d),js({k:v for k,v in s['serials'].items() if v})))
   c.executemany('INSERT INTO ni_source_files VALUES (?,?,?,?,?)',[(sid,s['kind'],s['id'],i,fid) for i,fid in enumerate(s['files'])])
  # Exact title association is explicit and does not merge distinct archive IDs.
  releases=collections.defaultdict(list)
  for r in c.execute('SELECT id,title FROM releases'):releases[r['title']].append(r['id'])
  for aid,a in parsed['archives'].items():
   for release in releases[a['title']]:c.execute('INSERT INTO ni_archive_releases VALUES (?,?,?,?)',(sid,aid,release,'exact canonical title'))
  new=[];new_targets=set();roms_by_object={r['object_id']:dict(r) for r in c.execute('SELECT * FROM roms WHERE platform_id=1')}
  for fid,h in headers.items():
   f=parsed['files'][fid]
   if fid in known or f['format']!='Headered':continue
   size=int(f['size'])-16
   if size<0:continue
   import zlib
   needed=int(f['crc32'],16)^crc_shift(zlib.crc32(h),size)
   for bodyoid in bycrc[size,format(needed,'08x')]:
    data=h+db.get(bodyoid)
    if not agrees(hashes(data),f):continue
    rid,oid=db.rom(data,'headered')
    # Every reconstruction reuses an existing complete body; adding ROM chunks is forbidden.
    recipe=c.execute('SELECT body_object_id,header FROM nes_recipes WHERE object_id=?',(oid,)).fetchone()
    if recipe is None or recipe[0]!=bodyoid or recipe[1]!=h:raise ValueError('Unexpected storage recipe')
    aid=sorted(file_archives[fid])[0];title=parsed['archives'][aid]['title']
    rf=db.insert('files',object_id=oid,original_name=title+'.'+f.get('extension','nes'),kind='rom',source_id=src,imported_at=now(),metadata_json=js({'nointro_snapshot':sid,'nointro_file_id':fid,'bad':f.get('bad')=='1','reconstructed':True}));known[fid]=oid
    c.execute('UPDATE ni_files SET object_id=? WHERE snapshot_id=? AND file_id=?',(oid,sid,fid))
    c.execute('INSERT INTO ni_reconstructions VALUES (?,?,?,?,?,?,?)',(sid,fid,bodyoid,oid,rid,rf,now()))
    oldrom=roms_by_object.get(bodyoid)
    if not oldrom:
     oldrom=next((r for r in roms_by_object.values() if r['body_object_id']==bodyoid),None)
    if oldrom:
     db.insert('transformations',source_rom_id=oldrom['id'],result_rom_id=rid,kind='nointro_header_reconstruction',evidence_file_id=df,recipe_json=js({'snapshot_id':sid,'file_id':fid,'old_header_hex':oldrom['header'].hex() if oldrom['header'] else None,'new_header_hex':h.hex(),'body_object_id':bodyoid,'verified_fields':list(FIELDS),'bad':f.get('bad')=='1'}),verified=1,created_at=now())
    for t in links[fid]:
     if db.validate(rid,t['id'])!='match':raise ValueError('Reconstructed DAT validation failed')
     new_targets.add(t['id'])
    for a in file_archives[fid]:
     for release in releases[parsed['archives'][a]['title']]:c.execute('INSERT OR IGNORE INTO rom_releases VALUES (?,?,?,?)',(rid,release,src,'No-Intro archive exact title; DB file '+fid))
    new.append(fid);break
  progress('Reconstructed '+str(len(new))+' independently verified header variants')
  # Retain raw source associations separately from independently verified recipes.
  checked=0
  for h,b in sorted(parsed['pairs']):
   detail={'ambiguous_source_candidates':(h,b) in parsed['ambiguous']}
   if h not in headers:status='no_header'
   elif b not in known:status='body_unavailable'
   else:
    a=hashes(headers[h]+db.get(known[b]));status='verified' if agrees(a,parsed['files'][h]) else 'mismatch';checked+=1
    if status=='mismatch':detail.update(actual=a,expected={k:parsed['files'][h][k] for k in FIELDS})
   c.execute('INSERT INTO ni_pair_checks VALUES (?,?,?,?,?)',(sid,h,b,status,js(detail)))
   if status=='mismatch':anomaly('source_pair_mismatch',{'headered_file_id':h,'headerless_file_id':b,**detail})
   if checked and checked%1500==0:progress('Checked source pairs: '+str(checked))
  roms_by_object={r['object_id']:r['id'] for r in c.execute('SELECT object_id,id FROM roms WHERE platform_id=1')}
  for s in parsed['sources']:
   serials={k:v for k,v in s['serials'].items() if v}
   if not serials:continue
   candidates=sorted(s['files'],key=lambda i:parsed['files'][i]['format']!='Headered')
   rid=next((roms_by_object[known[f]] for f in candidates if f in known and known[f] in roms_by_object),None)
   rels=releases[parsed['archives'][s['archive']]['title']]
   if rid is None and not rels:continue
   ha=db.insert('hardware_assertions',rom_id=rid,release_id=None if rid else rels[0],source_file_id=df,source_id=source_ids[s['kind'],s['id']],pcb=serials.get('pcb_serial'),chip=serials.get('romchip_serial1') or serials.get('chip_serial'),cic=serials.get('lockout_serial'),metadata_json=js({'snapshot_id':sid,'archive_id':s['archive'],'source_kind':s['kind'],'source_external_id':s['id'],'serials':serials,'interpretation':'documented by this source; does not imply every ROM variant has this PCB'}),confidence='documented',created_at=now())
   c.execute('UPDATE ni_sources SET hardware_assertion_id=? WHERE snapshot_id=? AND kind=? AND external_id=?',(ha,sid,s['kind'],s['id']))
  serials_by_archive=collections.defaultdict(lambda:collections.defaultdict(set))
  tilde=set()
  for s in parsed['sources']:
   for k,v in s['serials'].items():
    if v:serials_by_archive[s['archive']][k].add(v)
    if '~' in v:tilde.add(s['archive'])
  file_index={(int(f['size']),f['md5'].lower()) for f in parsed['files'].values()}
  for row in logs:
   r=row['fields'];aid=r['ID'];c.execute('INSERT INTO ni_dumplog VALUES (?,?,?,?,?,?)',(sid,aid,r['Status'],row['status'],row['trusted_count'],js(r)))
   for i,(size,md5) in enumerate(row['parts']):
    c.execute('INSERT INTO ni_dumplog_files VALUES (?,?,?,?,?)',(sid,aid,i,size,md5))
    if (size,md5) not in file_index:anomaly('dumplog_file_missing_from_db',{'ordinal':i,'size':size,'md5':md5},aid)
   conflicts={col:r[col] for col,key in SERIAL_FIELDS.items() if r.get(col) and not serials_by_archive[aid][key]}
   if aid in tilde or conflicts:anomaly('dumplog_hardware_review',{'csv_values_without_db_field':conflicts,'tilde_in_db_serial':aid in tilde,'policy':'Use DB per-source serials; CSV retained as observed, not promoted to hardware assertions'},aid)
  package_ids=[]
  for gid in sorted({t['dat_game_id'] for t in targets if t['id'] in new_targets}):
   if c.execute("SELECT 1 FROM v_dat_coverage WHERE dat_rom_id IN (SELECT id FROM dat_roms WHERE dat_game_id=?) AND status!='matched'",(gid,)).fetchone():continue
   package_ids.append(db.package(gid))
  report={'snapshot_id':sid,'version':parsed['version'],'archives':len(parsed['archives']),'files':len(parsed['files']),'sources':len(parsed['sources']),'dumplog_rows':len(logs),'new_headered_objects':len(new),'new_bad_objects':sum(parsed['files'][f].get('bad')=='1' for f in new),'new_dat_target_ids':sorted(new_targets),'package_ids':package_ids,'source_pairs_checked':checked,'coverage':[dict(r) for r in c.execute('SELECT dat_set_id,status,count(*) AS count FROM v_dat_coverage GROUP BY dat_set_id,status')],'checksums':{'db':dh,'dumplog':lh},'payloads_reconstructed_and_verified':True}
  db.event('import_nointro_snapshot','ni_snapshots',sid,report=report)
  c.execute('RELEASE nointro_import');return report
 except BaseException:
  c.execute('ROLLBACK TO nointro_import');c.execute('RELEASE nointro_import');raise

if __name__=='__main__':
 if len(sys.argv)!=4:raise SystemExit('Usage: nointro.py FULL.sqlite DB.zip DUMPLOG.zip')
 db=DB(sys.argv[1])
 try:
  with db.c:result=import_snapshot(db,sys.argv[2],sys.argv[3],lambda s:print(s,file=sys.stderr,flush=True))
  print(json.dumps(result,ensure_ascii=False,indent=2))
 finally:db.c.close()
