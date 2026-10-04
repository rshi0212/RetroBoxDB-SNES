"""RetroBoxDB 3.0. Python >=3.10, stdlib only. Source lives inside SQLite.

Storage v3 adds bounded shared compression groups and still reads v2 files.
"""
import argparse, datetime, functools, itertools, hashlib, io, json, os, pathlib, re, sqlite3, struct, sys, zipfile, zlib
import xml.etree.ElementTree as ET
VERSION = '1.0.0'
CHUNK = 1048576
MAX_ROM = 256 * CHUNK
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def js(x): return json.dumps(x,ensure_ascii=False,sort_keys=True)
def hashes(data):
    return dict(size=len(data),sha256=hashlib.sha256(data).hexdigest(),sha1=hashlib.sha1(data).hexdigest(),md5=hashlib.md5(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}')
def safe_name(name):
    n=name.replace('\\','/')
    if not n or n.startswith('/') or ':' in n or any(ord(c)<32 for c in n) or any(p in ('','..','.') for p in n.split('/')): raise ValueError('Unsafe or ambiguous filename: '+repr(name))
    return n
def xml(data):
    # Logiqx external DOCTYPE declarations are harmless; never load a DTD or entities.
    if b'<!ENTITY' in data.upper(): raise ValueError('XML entity declarations unsupported')
    return ET.fromstring(data)
def parse_nes(data,mode='auto'):
    out=dict(format='headerless' if mode=='headerless' else 'unknown',parse_status='unclassified',header=None,body=None,components=[],hardware=None,warnings=[])
    if mode=='headerless': out['body']=data; return out
    if mode=='auxiliary': out.update(format='auxiliary',body=data); return out
    if not data.startswith(b'NES\x1a'):
        if mode=='headered': out['parse_status']='invalid'; out['warnings']=['missing NES signature']
        return out
    if len(data)<16: out['parse_status']='invalid'; out['warnings']=['truncated header']; return out
    h=data[:16]; n2=(h[7]&12)==8
    out.update(format='nes2' if n2 else 'ines',header=h,body=data[16:],parse_status='valid')
    def romsize(lo,hi,unit): return ((1<<(lo>>2))*((lo&3)*2+1)) if hi==15 else ((hi<<8)|lo)*unit
    def ram(n): return (64<<n) if n else 0
    prg=romsize(h[4],h[9]&15,16384) if n2 else h[4]*16384
    chr_=romsize(h[5],h[9]>>4,8192) if n2 else h[5]*8192
    trainer=512 if h[6]&4 else 0
    mapper=(h[6]>>4)|(h[7]&240)|((h[8]&15)<<8 if n2 else 0)
    hw=dict(mapper=mapper,submapper=h[8]>>4 if n2 else None,prg_rom_size=prg,chr_rom_size=chr_,
        prg_ram_size=ram(h[10]&15) if n2 else None,prg_nvram_size=ram(h[10]>>4) if n2 else None,
        chr_ram_size=ram(h[11]&15) if n2 else None,chr_nvram_size=ram(h[11]>>4) if n2 else None,
        trainer_size=trainer,nametable_bit=h[6]&1,alternative_nametable_bit=(h[6]>>3)&1,battery=(h[6]>>1)&1,
        console_type=h[7]&3,timing=h[12]&3 if n2 else None,vs_ppu=h[13]&15 if n2 and h[7]&3==1 else None,
        vs_hardware=h[13]>>4 if n2 and h[7]&3==1 else None,extended_console=h[13]&15 if n2 and h[7]&3==3 else None,
        misc_rom_count=h[14]&3 if n2 else None,expansion_device=h[15]&63 if n2 else None,
        raw_json=js({'header_hex':h.hex(),'ines_legacy_ram_units':h[8] if not n2 else None,'ines_tv_byte':h[9] if not n2 else None,'interpretation':'header declaration; board and mapper-specific nametable semantics require external evidence'}))
    if prg>2**63-1 or chr_>2**63-1:
        out['warnings'].append('declared size exceeds SQLite integer range'); hw['prg_rom_size']=None; hw['chr_rom_size']=None
    out['hardware']=hw
    out['components'].append(('header',0,16))
    if 16+trainer+prg+chr_>len(data):
        out['parse_status']='invalid'; out['warnings'].append('declared ROM sections exceed actual file size'); return out
    if not n2 and ((h[7]&12)!=0 or any(h[12:16])):
        out['warnings'].append('legacy/dirty iNES header; mapper high bits may be unreliable')
    if n2 and (h[12]&252 or h[14]&252 or h[15]&192): out['warnings'].append('nonzero reserved NES 2.0 bits')
    off=16
    for kind,size in [('trainer',trainer),('prg',prg),('chr',chr_)]:
        if size: out['components'].append((kind,off,size))
        off+=size
    out['prg_chr']=data[16+trainer:off]
    if off<len(data):
        out['components'].append(('misc' if n2 and h[14]&3 else 'trailing',off,len(data)-off))
        if not (n2 and h[14]&3): out['warnings'].append('unclassified trailing data preserved')
    elif n2 and h[14]&3: out['warnings'].append('misc ROM count set but no data remains')
    if out['warnings']: out['parse_status']='warning'
    return out

class DB:
    def __init__(self,path):
        self.path=str(path); self.c=sqlite3.connect(self.path,timeout=60); self.c.row_factory=sqlite3.Row
        self.c.execute('PRAGMA foreign_keys=ON'); self.c.execute('PRAGMA journal_mode=DELETE'); self.c.execute('PRAGMA synchronous=FULL'); self.c.execute('PRAGMA temp_store=MEMORY'); self.c.execute('PRAGMA cache_size=-32768')
        if self.c.execute('PRAGMA application_id').fetchone()[0]!=1380074545: raise ValueError('Not a RetroBoxDB database')
    def insert(self,table,**kw):
        return self.c.execute('INSERT INTO '+table+' ('+','.join(kw)+') VALUES ('+','.join('?' for _ in kw)+')',tuple(kw.values())).lastrowid
    def event(self,action,entity=None,entity_id=None,**details): return self.insert('events',action=action,entity=entity,entity_id=entity_id,details_json=js(details),created_at=now())
    def put_stream(self,stream,header_boundary=False):
        hs={k:hashlib.new(k) for k in ('sha256','sha1','md5')}; crc=0; size=0; parts=[]
        first=True
        while True:
            b=stream.read(16 if first and header_boundary else CHUNK); first=False
            if not b: break
            for h in hs.values(): h.update(b)
            crc=zlib.crc32(b,crc); sha=hashlib.sha256(b).hexdigest()
            old=self.c.execute('SELECT data FROM chunks WHERE sha256=?',(sha,)).fetchone()
            if old is not None and old[0]!=b: raise ValueError('Chunk SHA256 collision/corruption')
            if old is None: self.insert('chunks',sha256=sha,size=len(b),data=b)
            parts.append((size,sha)); size+=len(b)
        digest=hs['sha256'].hexdigest()
        old=self.c.execute('SELECT id,size FROM objects WHERE sha256=?',(digest,)).fetchone()
        if old:
            if old['size']!=size: raise ValueError('Object hash collision')
            return old['id']
        oid=self.insert('objects',sha256=digest,sha1=hs['sha1'].hexdigest(),md5=hs['md5'].hexdigest(),crc32=f'{crc:08x}',size=size,created_at=now())
        self.c.executemany('INSERT INTO object_chunks VALUES (?,?,?,?)',[(oid,i,off,sha) for i,(off,sha) in enumerate(parts)])
        return oid
    def put(self,data,header_boundary=False): return self.put_stream(io.BytesIO(data),header_boundary)
    def stream(self,oid):
        pos=0
        for r in self.c.execute('SELECT oc.offset,c.data,c.sha256 FROM object_chunks oc JOIN chunks c ON c.sha256=oc.chunk_sha256 WHERE oc.object_id=? ORDER BY oc.ordinal',(oid,)):
            if pos!=r['offset'] or hashlib.sha256(r['data']).hexdigest()!=r['sha256']: raise ValueError('Corrupt object chunk')
            pos+=len(r['data']); yield r['data']
        row=self.c.execute('SELECT size FROM objects WHERE id=?',(oid,)).fetchone()
        if row is None or pos!=row[0]: raise ValueError('Incomplete object')
    def get(self,oid,limit=MAX_ROM):
        size=self.c.execute('SELECT size FROM objects WHERE id=?',(oid,)).fetchone()[0]
        if size>limit: raise ValueError('In-memory operation size limit exceeded; export streams have no such limit')
        return b''.join(self.stream(oid))
    def file(self,oid,name,kind='rom',path=None,parent=None,index=None,metadata=None):
        # Import is idempotent by bytes + original location + archive entry index.
        old=self.c.execute('SELECT id FROM files WHERE object_id=? AND original_name=? AND kind=? AND source_path IS ? AND parent_file_id IS ? AND member_index IS ?',(oid,name,kind,path,parent,index)).fetchone()
        if old: return old[0]
        return self.insert('files',object_id=oid,kind=kind,original_name=name,source_path=path,parent_file_id=parent,member_index=index,member_path=name if parent else None,imported_at=now(),metadata_json=js(metadata or {}))
    def rom(self,data,mode='auto'):
        p=parse_nes(data,mode); oid=self.put(data,p['header'] is not None)
        old=self.c.execute('SELECT id FROM roms WHERE object_id=? AND platform_id=1',(oid,)).fetchone()
        if old: return old[0],oid
        body=self.put(p['body']) if p['body'] is not None else None
        pc=p.get('prg_chr')
        rid=self.insert('roms',object_id=oid,platform_id=1,format=p['format'],parse_status=p['parse_status'],header=p['header'],body_object_id=body,prg_chr_sha256=hashlib.sha256(pc).hexdigest() if pc is not None else None,prg_chr_size=len(pc) if pc is not None else None,parser_version=VERSION,warnings_json=js(p['warnings']))
        for i,(kind,off,size) in enumerate(p['components']): self.insert('rom_components',rom_id=rid,ordinal=i,kind=kind,offset=off,size=size,sha256=hashlib.sha256(data[off:off+size]).hexdigest())
        if p['hardware']: self.insert('nes_hardware',rom_id=rid,**p['hardware'])
        return rid,oid
    def import_rom_path(self,path,mode='auto'):
        path=pathlib.Path(path).expanduser().resolve()
        if path.suffix.lower()=='.zip':
            with path.open('rb') as f: oid=self.put_stream(f)
            fid=self.file(oid,path.name,'archive',str(path))
            result=[]
            with zipfile.ZipFile(path) as z:
                total=0
                for i,info in enumerate(z.infolist()):
                    if info.is_dir(): continue
                    total+=info.file_size
                    if info.file_size>MAX_ROM or total>2*1024**3: raise ValueError('ZIP import memory safety limit')
                    data=z.read(info)
                    if pathlib.PurePosixPath(info.filename).suffix.lower() in ('.nes','.unh','.bin','.rom'):
                        rid,obj=self.rom(data,mode); kind='rom'; result.append(rid)
                    elif pathlib.PurePosixPath(info.filename).suffix.lower()=='.sav':
                        rid,obj=self.rom(data,'auxiliary'); kind='other'; result.append(rid)
                    else: obj=self.put(data); kind='other'
                    self.file(obj,info.filename,kind,str(path),fid,i,dict(zip_crc=f'{info.CRC:08x}',compression=info.compress_type,flags=info.flag_bits))
            return result
        if path.stat().st_size>MAX_ROM: raise ValueError('ROM too large')
        rid,oid=self.rom(path.read_bytes(),mode); self.file(oid,path.name,path=str(path)); return [rid]
    def import_dat(self,data,name,mode,parent=None,path=None):
        root=xml(data)
        if root.tag!='datafile': raise ValueError('Only Logiqx/No-Intro XML DAT is currently supported')
        h=root.find('header'); hd={e.tag:(e.text or '') for e in h} if h is not None else {}
        if mode=='auto': mode='headerless' if '(Headerless)' in hd.get('name',name) else 'headered' if '(Headered)' in hd.get('name',name) else 'unspecified'
        scope='nes_after_header' if mode=='headerless' else 'full'
        if h is not None:
            for plug in h.findall('clrmamepro'):
                if plug.get('header') and (mode!='headerless' or plug.get('header')!='No-Intro_NES.xml'): raise ValueError('Unsupported DAT header-skip rule; specify supported semantics first')
        oid=self.put(data); fid=self.file(oid,name,'dat',path,parent)
        old=self.c.execute('SELECT ds.id FROM dat_sets ds JOIN files f ON f.id=ds.source_file_id WHERE f.object_id=? AND ds.mode=?',(oid,mode)).fetchone()
        if old: return old[0]
        ds=self.insert('dat_sets',source_file_id=fid,platform_id=1,name=hd.get('name',name),version=hd.get('version'),author=hd.get('author'),description=hd.get('description'),mode=mode,hash_scope=scope,header_json=js({'fields':hd,'raw_xml':ET.tostring(h,encoding='unicode') if h is not None else ''}),imported_at=now())
        for gi,g in enumerate(list(root.findall('game'))+list(root.findall('machine'))):
            gid=self.insert('dat_games',dat_set_id=ds,ordinal=gi,name=g.attrib['name'],description=g.findtext('description'),cloneof=g.get('cloneof'),romof=g.get('romof'),attrs_json=js(g.attrib),raw_xml=ET.tostring(g,encoding='unicode'))
            for ri,r in enumerate(g.findall('rom')):
                vals={}
                for key,n in [('crc32',8),('md5',32),('sha1',40),('sha256',64)]:
                    v=r.get('crc' if key=='crc32' else key)
                    if v is not None and not re.fullmatch('[0-9a-fA-F]{'+str(n)+'}',v): raise ValueError('Invalid DAT checksum')
                    vals[key]=v.lower() if v else None
                self.insert('dat_roms',dat_game_id=gid,ordinal=ri,name=r.attrib['name'],size=int(r.get('size')) if r.get('size') is not None else None,status=r.get('status'),merge_name=r.get('merge'),attrs_json=js(r.attrib),**vals)
        self.event('import_dat','dat_sets',ds); return ds
    def import_dat_path(self,path,mode='auto'):
        p=pathlib.Path(path).expanduser().resolve()
        if p.suffix.lower()!='.zip': return [self.import_dat(p.read_bytes(),p.name,mode,path=str(p))]
        with p.open('rb') as f: oid=self.put_stream(f)
        fid=self.file(oid,p.name,'archive',str(p)); result=[]
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                if info.filename.lower().endswith(('.dat','.xml')):
                    if info.file_size>MAX_ROM: raise ValueError('DAT size limit')
                    result.append(self.import_dat(z.read(info),info.filename,mode,fid,str(p)))
        if not result: raise ValueError('No XML DAT members')
        return result
    def target(self,drid):
        r=self.c.execute('SELECT dr.*,ds.hash_scope,ds.mode FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id JOIN dat_sets ds ON ds.id=dg.dat_set_id WHERE dr.id=?',(drid,)).fetchone()
        if r is None: raise ValueError('Unknown DAT ROM')
        return r
    @staticmethod
    def compare(actual,target):
        fields=[k for k in ('size','crc32','md5','sha1','sha256') if target[k] is not None]
        strength=next((k for k in ('sha256','sha1','md5','crc32') if target[k] is not None),'none')
        bad={k:{'expected':target[k],'actual':actual[k]} for k in fields if target[k]!=actual[k]}
        status='unverifiable' if strength=='none' or (target['status'] or '').lower()=='nodump' else 'mismatch' if bad else 'match'
        return status,strength,{'checked':fields,'differences':bad}
    def validate(self,rid,drid):
        target=self.target(drid); r=self.c.execute('SELECT * FROM roms WHERE id=?',(rid,)).fetchone()
        oid=r['body_object_id'] if target['hash_scope']=='nes_after_header' else r['object_id']
        if oid is None: return 'unverifiable'
        o=self.c.execute('SELECT * FROM objects WHERE id=?',(oid,)).fetchone(); status,strength,detail=self.compare(o,target)
        self.c.execute('INSERT INTO validations(rom_id,dat_rom_id,scope,checked_object_id,status,strength,details_json,checked_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(rom_id,dat_rom_id,scope) DO UPDATE SET status=excluded.status,strength=excluded.strength,details_json=excluded.details_json,checked_at=excluded.checked_at',(rid,drid,target['hash_scope'],oid,status,strength,js(detail),now()))
        if status=='match':
            for f in self.c.execute('SELECT id,original_name FROM files WHERE object_id=? AND kind=\'rom\'',(r['object_id'],)).fetchall():
                if f['original_name']!=target['name']:
                    reason='case_only' if f['original_name'].casefold()==target['name'].casefold() else 'dat_name'
                    self.c.execute('INSERT OR IGNORE INTO naming_decisions(file_id,dat_rom_id,canonical_name,reason,created_at) VALUES (?,?,?,?,?)',(f['id'],drid,target['name'],reason,now()))
        return status
    def scan(self,ds):
        scope=self.c.execute('SELECT hash_scope FROM dat_sets WHERE id=?',(ds,)).fetchone()[0]
        col='body_object_id' if scope=='nes_after_header' else 'object_id'
        counts={'match':0,'mismatch':0,'unverifiable':0,'no_candidate':0}
        for t in self.c.execute('SELECT dr.* FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id WHERE dg.dat_set_id=?',(ds,)).fetchall():
            key=next((k for k in ('sha256','sha1','md5','crc32') if t[k]),None)
            if key is None: counts['unverifiable']+=1; continue
            rows=self.c.execute('SELECT r.id FROM roms r JOIN objects o ON o.id=r.'+col+' WHERE o.'+key+'=? AND r.platform_id=1',(t[key],)).fetchall()
            if not rows: counts['no_candidate']+=1
            for r in rows: counts[self.validate(r[0],t['id'])]+=1
        self.event('scan_dat','dat_sets',ds,counts=counts); return counts
    def repair_header(self,rid,drid,header,evidence_file_id):
        if len(header)!=16 or header[:4]!=b'NES\x1a': raise ValueError('Expected 16-byte NES header')
        t=self.target(drid)
        if t['mode']!='headered' or t['hash_scope']!='full': raise ValueError('Repair requires full headered target DAT')
        if not (t['sha256'] or t['sha1']): raise ValueError('Repair requires SHA1 or SHA256, not CRC-only evidence')
        if not self.c.execute('SELECT 1 FROM files WHERE id=?',(evidence_file_id,)).fetchone(): raise ValueError('Missing header evidence')
        r=self.c.execute('SELECT * FROM roms WHERE id=?',(rid,)).fetchone()
        if r['body_object_id'] is None: raise ValueError('No unambiguous NES body')
        body=self.get(r['body_object_id']); result=header+body
        status,strength,detail=self.compare(hashes(result),t)
        if status!='match': raise ValueError('Proposed header fails target DAT: '+js(detail))
        nrid,oid=self.rom(result,'headered')
        fid=self.file(oid,t['name'],'rom',metadata={'derived_from_rom':rid,'target_dat_rom':drid})
        self.validate(nrid,drid)
        self.insert('transformations',source_rom_id=rid,result_rom_id=nrid,kind='nes_header_replace' if r['header'] else 'nes_header_add',target_dat_rom_id=drid,evidence_file_id=evidence_file_id,recipe_json=js({'old_header_hex':bytes(r['header']).hex() if r['header'] else None,'new_header_hex':header.hex(),'body_object_id':r['body_object_id'],'algorithm':VERSION}),verified=1,created_at=now())
        self.event('repair_header','roms',nrid,source_rom_id=rid,target_dat_rom_id=drid); return nrid
    def package(self,gid,encoded=None):
        game=self.c.execute('SELECT * FROM dat_games WHERE id=?',(gid,)).fetchone()
        entries=[]; members=[]
        for t in self.c.execute('SELECT * FROM dat_roms WHERE dat_game_id=? ORDER BY ordinal',(gid,)).fetchall():
            v=self.c.execute("SELECT * FROM validations WHERE dat_rom_id=? AND status='match' ORDER BY CASE strength WHEN 'sha256' THEN 0 WHEN 'sha1' THEN 1 ELSE 2 END,rom_id LIMIT 1",(t['id'],)).fetchone()
            if v is None: raise ValueError('Missing verified DAT member '+t['name'])
            data=self.get(v['checked_object_id']); status,_,_=self.compare(hashes(data),t)
            if status!='match': raise ValueError('Stored data no longer matches DAT')
            entries.append((safe_name(t['name']),data)); members.append((t['id'],v['rom_id'],v['checked_object_id'],safe_name(t['name'])))
        data=make_torrentzip(entries) if encoded is None else encoded
        if encoded is not None:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                expected=sorted(entries,key=lambda e:e[0].lower())
                if z.namelist()!=[n for n,d in expected] or any(z.read(n)!=d for n,d in expected): raise ValueError('Prepared ZIP contents do not match DAT members')
        oid=self.put(data); fid=self.file(oid,safe_name(game['name'])+'.zip','archive',metadata={'profile':'torrentzip-classic','dat_game_id':gid})
        old=self.c.execute('SELECT id FROM packages WHERE file_id=? AND dat_game_id=?',(fid,gid)).fetchone()
        if old: return old[0]
        pid=self.insert('packages',file_id=fid,dat_game_id=gid,profile_id=1,engine='RetroBoxDB '+VERSION+'; zlib '+zlib.ZLIB_RUNTIME_VERSION,validation_json=js({'member_dat_hashes':'all passed','structure':'classic TorrentZip','reference_compatibility':'see resources/test-report; arbitrary encoder versions not presumed bit-identical'}),created_at=now())
        for i,m in enumerate(sorted(members,key=lambda m:m[3].lower())): self.insert('package_members',package_id=pid,ordinal=i,dat_rom_id=m[0],rom_id=m[1],object_id=m[2],name=m[3])
        return pid
    def export(self,fid,path):
        row=self.c.execute('SELECT object_id FROM files WHERE id=?',(fid,)).fetchone()
        if not row: raise ValueError('Unknown file')
        p=pathlib.Path(path).expanduser()
        # Exclusive create: never replace originals, the DB, or previous exports.
        try:
            with p.open('xb') as f:
                h=hashlib.sha256()
                for data in self.stream(row[0]): f.write(data); h.update(data)
                expected=self.c.execute('SELECT sha256 FROM objects WHERE id=?',(row[0],)).fetchone()[0]
                if h.hexdigest()!=expected: raise ValueError('Export hash mismatch')
                f.flush(); os.fsync(f.fileno())
        except FileExistsError: raise
        except BaseException:
            if p.exists(): p.unlink()
            raise
        return {'path':str(p),'sha256':expected}
    def import_asset(self,path,kind,role=None,game_id=None,release_id=None,rom_id=None):
        p=pathlib.Path(path).expanduser().resolve()
        with p.open('rb') as f: oid=self.put_stream(f)
        fid=self.file(oid,p.name,kind,str(p))
        if kind in ('image','video','audio'): self.insert('media',file_id=fid,game_id=game_id,release_id=release_id,rom_id=rom_id,role=role or kind)
        return fid
    def audit(self):
        result={'integrity_check':[r[0] for r in self.c.execute('PRAGMA integrity_check')],'foreign_key_errors':[tuple(r) for r in self.c.execute('PRAGMA foreign_key_check')],'objects_checked':0,'errors':[]}
        for o in self.c.execute('SELECT * FROM objects').fetchall():
            hs={k:hashlib.new(k) for k in ('sha256','sha1','md5')}; crc=0; size=0
            try:
                for b in self.stream(o['id']):
                    size+=len(b); crc=zlib.crc32(b,crc)
                    for h in hs.values(): h.update(b)
                actual={k:h.hexdigest() for k,h in hs.items()}; actual.update(size=size,crc32=f'{crc:08x}')
                if any(actual[k]!=o[k] for k in actual): result['errors'].append({'object':o['id'],'error':'object checksum mismatch'})
            except ValueError as e: result['errors'].append({'object':o['id'],'error':str(e)})
            result['objects_checked']+=1
        result['ok']=result['integrity_check']==['ok'] and not result['foreign_key_errors'] and not result['errors']; return result
    def stats(self):
        return {'counts':{t:self.c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('files','objects','chunks','roms','dat_sets','dat_roms','transformations','packages','media')},'storage':dict(self.c.execute('SELECT * FROM v_storage').fetchone()),'dat_coverage':[dict(r) for r in self.c.execute('SELECT dat_set_id,status,count(*) AS count FROM v_dat_coverage GROUP BY dat_set_id,status')]}

def _crc_shift_uncached(crc,length):
    """CRC32 concatenation contribution; independently implemented GF(2) exponentiation."""
    def apply(matrix,value):
        result=0; i=0
        while value:
            if value&1: result^=matrix[i]
            value>>=1; i+=1
        return result
    matrix=[]
    for i in range(32):
        v=1<<i
        for _ in range(8): v=(v>>1)^(0xedb88320 if v&1 else 0)
        matrix.append(v)
    while length:
        if length&1: crc=apply(matrix,crc)
        length>>=1
        if length: matrix=[apply(matrix,x) for x in matrix]
    return crc

@functools.lru_cache(maxsize=256)
def _crc_shift_basis(length): return tuple(_crc_shift_uncached(1<<i,length) for i in range(32))

def crc_shift(crc,length):
    matrix=_crc_shift_basis(length); out=0; i=0
    while crc:
        if crc&1: out^=matrix[i]
        crc>>=1; i+=1
    return out

def reconcile(db,old_ds,new_ds,headerless_ds):
    """DAT diff and exact verified header recovery, never modifying originals."""
    for ds,mode in [(old_ds,'headered'),(new_ds,'headered'),(headerless_ds,'headerless')]:
        r=db.c.execute('SELECT mode,platform_id FROM dat_sets WHERE id=?',(ds,)).fetchone()
        if r is None or r['mode']!=mode or r['platform_id']!=1: raise ValueError('Expected NES DAT mode '+mode)
    def rows(ds): return [dict(r) for r in db.c.execute('SELECT dr.*,dg.name AS game_name FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id WHERE dg.dat_set_id=? ORDER BY dr.id',(ds,))]
    def signature(r): return tuple(r[k] for k in ('size','crc32','md5','sha1','sha256'))
    old=rows(old_ds); new=rows(new_ds); headerless=rows(headerless_ds)
    old_by_name={r['name'].casefold():r for r in old}; old_by_sig={signature(r):r for r in old if r['sha1'] or r['sha256']}; used=set(); change_counts={}
    for t in new:
        previous=old_by_name.get(t['name'].casefold()) or old_by_sig.get(signature(t))
        if previous:
            used.add(previous['id'])
            kind=('unchanged' if t['name']==previous['name'] else 'case_changed' if t['name'].casefold()==previous['name'].casefold() else 'renamed') if signature(t)==signature(previous) else 'checksum_changed'
        else: kind='added'
        db.insert('dat_changes',old_dat_rom_id=previous['id'] if previous else None,new_dat_rom_id=t['id'],classification=kind,evidence_json=js({'method':'same casefold filename, then identical full signature','same_name_is_not_payload_equality':True}))
        change_counts[kind]=change_counts.get(kind,0)+1
    for r in old:
        if r['id'] not in used: db.insert('dat_changes',old_dat_rom_id=r['id'],classification='removed',evidence_json=js({})); change_counts['removed']=change_counts.get('removed',0)+1
    headers={}
    for r in db.c.execute('SELECT r.header,min(f.id) AS fid FROM roms r JOIN files f ON f.object_id=r.object_id WHERE r.header IS NOT NULL GROUP BY r.header'):
        headers[bytes(r['header'])]=r['fid']
    hless_by_name={r['name'].rsplit('.',1)[0]:r for r in headerless}
    shifted_headers={}; shifted_changes={}; results={'already_matched':0,'recovered_existing_header':0,'recovered_bounded_search':0,'unresolved':0,'diff':change_counts}
    # For any base header, changing byte p by XOR v changes CRC by this value.
    base=bytes(16); base_crc=zlib.crc32(base); deltas=[]
    for p in range(4,16):
        for v in range(1,256):
            b=bytearray(base); b[p]=v; deltas.append((zlib.crc32(b)^base_crc,p,v))
    for t in new:
        if db.c.execute("SELECT 1 FROM validations WHERE dat_rom_id=? AND status='match' LIMIT 1",(t['id'],)).fetchone(): results['already_matched']+=1; continue
        hl=hless_by_name.get(t['name'].rsplit('.',1)[0]); candidates=[]
        if hl:
            candidates=db.c.execute("SELECT DISTINCT r.*,o.size AS body_size,o.crc32 AS body_crc FROM validations v JOIN roms r ON r.id=v.rom_id JOIN objects o ON o.id=r.body_object_id WHERE v.dat_rom_id=? AND v.status='match' ORDER BY (r.header IS NULL),r.id",(hl['id'],)).fetchall()
        chosen=None; method=None; source=None
        for r in candidates:
            if t['size']!=r['body_size']+16 or not t['crc32'] or not (t['sha1'] or t['sha256']): continue
            length=r['body_size']; required=int(t['crc32'],16)^int(r['body_crc'],16)
            if length not in shifted_headers:
                shifted_headers[length]={}
                for header,fid in headers.items(): shifted_headers[length].setdefault(crc_shift(zlib.crc32(header),length),[]).append((header,fid))
            body=None
            def matches(header):
                nonlocal body
                if body is None: body=db.get(r['body_object_id'])
                return db.compare(hashes(header+body),t)[0]=='match'
            for header,fid in shifted_headers[length].get(required,[]):
                if matches(header): chosen=(header,fid); method='existing_header'; break
            if not chosen and r['header']:
                header=bytes(r['header']); need=required^crc_shift(zlib.crc32(header),length)
                if length not in shifted_changes:
                    shifted_changes[length]=[(crc_shift(d,length),p,v) for d,p,v in deltas]
                changes=shifted_changes[length]; lookup={d:(p,v) for d,p,v in changes}
                proposals=[]
                if need in lookup: proposals.append((lookup[need],))
                for d,p,v in changes:
                    other=lookup.get(need^d)
                    if other and other[0]>p: proposals.append(((p,v),other))
                for edits in proposals:
                    h=bytearray(header)
                    for p,v in edits: h[p]^=v
                    h=bytes(h)
                    if matches(h):
                        fid=db.c.execute('SELECT min(id) FROM files WHERE object_id=?',(r['object_id'],)).fetchone()[0]
                        chosen=(h,fid); method='bounded_search'; break
            if chosen: source=r; break
        if chosen:
            out=db.repair_header(source['id'],t['id'],chosen[0],chosen[1]); results['recovered_'+method if method=='existing_header' else 'recovered_bounded_search']+=1
            db.insert('repair_attempts',target_dat_rom_id=t['id'],source_rom_id=source['id'],status='recovered',details_json=js({'method':method,'result_rom_id':out,'all_target_hashes_verified':True,'bounded_search_max_changed_header_bytes':2 if method=='bounded_search' else None}),created_at=now())
        else:
            results['unresolved']+=1; db.insert('repair_attempts',target_dat_rom_id=t['id'],source_rom_id=candidates[0]['id'] if candidates else None,status='unresolved',details_json=js({'reason':'no exact verified header in observed pool or <=2-byte correction; or matching body unavailable','body_candidates':len(candidates)}),created_at=now())
    db.event('reconcile_dat',old_dat_set=old_ds,new_dat_set=new_ds,headerless_dat_set=headerless_ds,results=results)
    return results

def three_byte_header_candidates(header,body_crc,body_size,target_crc):
    """Enumerate <=3 different byte edits using CRC linearity, not CRC acceptance."""
    base=bytes(16); zero=zlib.crc32(base); groups={}; lookup={}
    for p in range(4,16):
        group=[]
        for v in range(1,256):
            b=bytearray(base); b[p]=v
            d=crc_shift(zlib.crc32(b)^zero,body_size); group.append((d,p,v)); lookup[d]=(p,v)
        groups[p]=group
    need=target_crc^body_crc^crc_shift(zlib.crc32(header),body_size)
    def edited(edits):
        b=bytearray(header)
        for p,v in edits: b[p]^=v
        return bytes(b)
    if need in lookup: yield edited([lookup[need]])
    for p in range(4,16):
        for d,p,v in groups[p]:
            other=lookup.get(need^d)
            if other and other[0]>p: yield edited([(p,v),other])
    for p1 in range(4,14):
        for p2 in range(p1+1,15):
            for d1,_,v1 in groups[p1]:
                remaining=need^d1
                for d2,_,v2 in groups[p2]:
                    third=lookup.get(remaining^d2)
                    if third and third[0]>p2: yield edited([(p1,v1),(p2,v2),third])

def recover_deep(db,new_ds,headerless_ds):
    result={'auxiliary_matched':0,'three_byte_recovered':0,'unresolved_with_body':0}
    # Auxiliary DAT members retain raw bytes; no NES-header assumptions apply.
    for f in db.c.execute("SELECT DISTINCT object_id FROM files WHERE kind='other' AND lower(original_name) LIKE '%.sav'").fetchall(): db.rom(db.get(f[0]),'auxiliary')
    db.scan(new_ds)
    for a in db.c.execute("SELECT ra.* FROM repair_attempts ra WHERE ra.status='unresolved' AND EXISTS(SELECT 1 FROM validations v JOIN roms r ON r.id=v.rom_id WHERE v.dat_rom_id=ra.target_dat_rom_id AND v.status='match' AND r.format='auxiliary')").fetchall():
        db.c.execute("UPDATE repair_attempts SET status='resolved_auxiliary' WHERE id=?",(a['id'],)); result['auxiliary_matched']+=1
    targets=db.c.execute("SELECT DISTINCT dr.* FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id WHERE dg.dat_set_id=? AND NOT EXISTS(SELECT 1 FROM validations v WHERE v.dat_rom_id=dr.id AND v.status='match')",(new_ds,)).fetchall()
    for t in targets:
        if not t['name'].lower().endswith('.nes') or not t['crc32'] or not (t['sha1'] or t['sha256']): continue
        name=t['name'].rsplit('.',1)[0]+'.unh'
        rows=db.c.execute("SELECT DISTINCT r.*,o.size AS body_size,o.crc32 AS body_crc FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id JOIN validations v ON v.dat_rom_id=dr.id JOIN roms r ON r.id=v.rom_id JOIN objects o ON o.id=r.body_object_id WHERE dg.dat_set_id=? AND dr.name=? AND v.status='match' AND r.header IS NOT NULL",(headerless_ds,name)).fetchall()
        solved=False
        for r in rows:
            if t['size']!=r['body_size']+16: continue
            body=db.get(r['body_object_id'])
            for header in three_byte_header_candidates(bytes(r['header']),int(r['body_crc'],16),r['body_size'],int(t['crc32'],16)):
                if db.compare(hashes(header+body),t)[0]!='match': continue
                fid=db.c.execute('SELECT min(id) FROM files WHERE object_id=?',(r['object_id'],)).fetchone()[0]
                out=db.repair_header(r['id'],t['id'],header,fid)
                db.c.execute("UPDATE repair_attempts SET status='recovered_after_extended_search' WHERE target_dat_rom_id=? AND status='unresolved'",(t['id'],))
                db.insert('repair_attempts',target_dat_rom_id=t['id'],source_rom_id=r['id'],status='recovered',details_json=js({'method':'bounded_three_byte_search','max_changed_header_bytes':3,'result_rom_id':out,'all_target_hashes_verified':True}),created_at=now())
                result['three_byte_recovered']+=1; solved=True; break
            if solved: break
        if rows and not solved: result['unresolved_with_body']+=1
    db.event('deep_header_recovery',new_dat_set=new_ds,headerless_dat_set=headerless_ds,results=result)
    return result

def _crc_solutions(columns,need):
 pivots={}; null=[]
 for i,v in enumerate(columns):
  mask=1<<i
  while v:
   p=v.bit_length()-1
   if p in pivots: v^=pivots[p][0]; mask^=pivots[p][1]
   else: pivots[p]=(v,mask); break
  if not v: null.append(mask)
 mask=0
 while need:
  p=need.bit_length()-1
  if p not in pivots:return
  need^=pivots[p][0]; mask^=pivots[p][1]
 masks=[mask]
 for n in null: masks += [v^n for v in masks]
 yield from masks
def four_byte_header_candidates(base,body,target):
 length=len(body); need=int(target['crc32'],16)^zlib.crc32(body)^crc_shift(zlib.crc32(base),length)
 zero=zlib.crc32(bytes(16)); bits={}
 for p in range(4,16):
  bits[p]=[]
  for b in range(8):
   h=bytearray(16);h[p]=1<<b;bits[p].append(crc_shift(zlib.crc32(h)^zero,length))
 for positions in itertools.combinations(range(4,16),4):
  for mask in _crc_solutions([v for p in positions for v in bits[p]],need):
   h=bytearray(base)
   for i,p in enumerate(positions):h[p]^=(mask>>(i*8))&255
   yield bytes(h)

def recover_linear(db,new_ds,headerless_ds):
    """Try recovered-header reuse and CRC-linear four-byte candidate generation; accept only full DAT hashes."""
    recovered=[]
    headers=[(bytes(r[0]),r[1]) for r in db.c.execute('SELECT r.header,min(f.id) FROM roms r JOIN files f ON f.object_id=r.object_id WHERE header IS NOT NULL GROUP BY header')]
    targets=db.c.execute("SELECT dr.* FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id WHERE dg.dat_set_id=? AND NOT EXISTS(SELECT 1 FROM validations v WHERE v.dat_rom_id=dr.id AND v.status='match')",(new_ds,)).fetchall()
    for t in targets:
        if not t['name'].lower().endswith('.nes') or not t['crc32'] or not (t['sha1'] or t['sha256']): continue
        rows=db.c.execute("SELECT DISTINCT r.* FROM dat_roms dr JOIN dat_games dg ON dg.id=dr.dat_game_id JOIN validations v ON v.dat_rom_id=dr.id JOIN roms r ON r.id=v.rom_id WHERE dg.dat_set_id=? AND dr.name=? AND v.status='match' ORDER BY (r.header IS NULL),r.id",(headerless_ds,t['name'].rsplit('.',1)[0]+'.unh')).fetchall()
        found=None
        for r in rows:
            body=db.get(r['body_object_id'])
            if len(body)+16!=t['size']: continue
            body_crc=zlib.crc32(body)
            def accept(h): return db.compare(hashes(h+body),t)[0]=='match'
            for h,fid in headers:
                if crc_shift(zlib.crc32(h),len(body))^body_crc==int(t['crc32'],16) and accept(h): found=(h,fid,'reused_newly_recovered_header'); break
            if not found:
                if r['header']: bases=[(bytes(r['header']),db.c.execute('SELECT min(id) FROM files WHERE object_id=?',(r['object_id'],)).fetchone()[0])]
                else: bases=[(bytes(x[0]),x[1]) for x in db.c.execute('SELECT r.header,min(f.id) FROM roms r JOIN objects o ON o.id=r.body_object_id JOIN files f ON f.object_id=r.object_id WHERE r.header IS NOT NULL AND o.size=? GROUP BY r.header ORDER BY count(*) DESC LIMIT 40',(len(body),))]
                for base,fid in bases:
                    for h in four_byte_header_candidates(base,body,t):
                        if accept(h): found=(h,fid,'crc_linear_four_byte_search'); break
                    if found: break
            if found:
                out=db.repair_header(r['id'],t['id'],found[0],found[1])
                db.c.execute("UPDATE repair_attempts SET status='recovered_after_linear_search' WHERE target_dat_rom_id=? AND status='unresolved'",(t['id'],))
                detail={'method':found[2],'result_rom_id':out,'max_changed_template_bytes':4,'all_target_hashes_verified':True,'evidence_file_id':found[1]}
                db.insert('repair_attempts',target_dat_rom_id=t['id'],source_rom_id=r['id'],status='recovered',details_json=js(detail),created_at=now())
                recovered.append({'dat_rom_id':t['id'],'rom_id':out,**detail}); break
    db.event('linear_header_recovery',new_dat_set=new_ds,headerless_dat_set=headerless_ds,recovered=recovered)
    return recovered

def make_torrentzip(entries):
    if not entries: raise ValueError('No package members')
    entries=[(n,b'' if d is None else d) for n,d in normalize_archive_entries([(n,None if n.endswith('/') and not d else d) for n,d in entries])]
    if len({n.casefold() for n,d in entries})!=len(entries): raise ValueError('Case-insensitive member collision')
    if len(entries)>=65535: raise ValueError('ZIP64 not implemented in classic profile')
    out=io.BytesIO(); central=io.BytesIO()
    for name,data in entries:
        try: nb=name.encode('cp437'); flag=2
        except UnicodeEncodeError: nb=name.encode('utf8'); flag=2050
        if len(nb)>65535: raise ValueError('ZIP filename too long')
        co=zlib.compressobj(9,zlib.DEFLATED,-15,8,zlib.Z_DEFAULT_STRATEGY); compressed=co.compress(data)+co.flush()
        crc=zlib.crc32(data); offset=out.tell()
        if max(len(data),len(compressed),offset)>=0xffffffff: raise ValueError('ZIP64 not implemented')
        out.write(struct.pack('<IHHHHHIIIHH',0x04034b50,20,flag,8,48128,8600,crc,len(compressed),len(data),len(nb),0)); out.write(nb); out.write(compressed)
        central.write(struct.pack('<IHHHHHHIIIHHHHHII',0x02014b50,0,20,flag,8,48128,8600,crc,len(compressed),len(data),len(nb),0,0,0,0,0,offset)); central.write(nb)
    cd=central.getvalue(); offset=out.tell()
    if max(len(cd),offset,offset+len(cd))>=0xffffffff: raise ValueError('ZIP64 not implemented')
    out.write(cd); comment=f'TORRENTZIPPED-{zlib.crc32(cd):08X}'.encode('ascii')
    out.write(struct.pack('<IHHHHIIH',0x06054b50,0,0,len(entries),len(entries),len(cd),offset,len(comment))); out.write(comment)
    return out.getvalue()

def main(db_path,argv):
    p=argparse.ArgumentParser(description='RetroBoxDB embedded NES toolkit; operations remain inside SQLite except explicit export')
    sp=p.add_subparsers(dest='command',required=True)
    sp.add_parser('stats'); sp.add_parser('audit'); sp.add_parser('help')
    a=sp.add_parser('import-dat'); a.add_argument('path'); a.add_argument('--mode',choices=['auto','headered','headerless','unspecified'],default='auto')
    a=sp.add_parser('import-rom'); a.add_argument('path'); a.add_argument('--mode',choices=['auto','headered','headerless'],default='auto')
    a=sp.add_parser('scan'); a.add_argument('dat_set_id',type=int)
    a=sp.add_parser('reconcile'); a.add_argument('old_dat_set_id',type=int); a.add_argument('new_dat_set_id',type=int); a.add_argument('headerless_dat_set_id',type=int)
    a=sp.add_parser('recover-deep'); a.add_argument('new_dat_set_id',type=int); a.add_argument('headerless_dat_set_id',type=int)
    a=sp.add_parser('recover-linear'); a.add_argument('new_dat_set_id',type=int); a.add_argument('headerless_dat_set_id',type=int)
    a=sp.add_parser('package'); a.add_argument('dat_game_id',type=int)
    a=sp.add_parser('repair-header'); a.add_argument('rom_id',type=int); a.add_argument('dat_rom_id',type=int); a.add_argument('header_hex'); a.add_argument('evidence_file_id',type=int)
    a=sp.add_parser('export'); a.add_argument('file_id',type=int); a.add_argument('path')
    a=sp.add_parser('import-asset'); a.add_argument('path'); a.add_argument('--kind',choices=['image','video','audio','metadata','header_database','other'],required=True); a.add_argument('--role'); a.add_argument('--game-id',type=int); a.add_argument('--release-id',type=int); a.add_argument('--rom-id',type=int)
    args=p.parse_args(argv); db=DB(db_path)
    try:
        with db.c:
            if args.command=='help': print(db.c.execute("SELECT content FROM resources WHERE name='README.zh-CN'").fetchone()[0]); return
            elif args.command=='stats': result=db.stats()
            elif args.command=='audit': result=db.audit()
            elif args.command=='import-dat': result=db.import_dat_path(args.path,args.mode)
            elif args.command=='import-rom': result=db.import_rom_path(args.path,args.mode)
            elif args.command=='scan': result=db.scan(args.dat_set_id)
            elif args.command=='reconcile': result=reconcile(db,args.old_dat_set_id,args.new_dat_set_id,args.headerless_dat_set_id)
            elif args.command=='recover-deep': result=recover_deep(db,args.new_dat_set_id,args.headerless_dat_set_id)
            elif args.command=='recover-linear': result=recover_linear(db,args.new_dat_set_id,args.headerless_dat_set_id)
            elif args.command=='package': result=db.package(args.dat_game_id)
            elif args.command=='repair-header': result=db.repair_header(args.rom_id,args.dat_rom_id,bytes.fromhex(args.header_hex),args.evidence_file_id)
            elif args.command=='export': result=db.export(args.file_id,args.path)
            elif args.command=='import-asset': result=db.import_asset(args.path,args.kind,args.role,args.game_id,args.release_id,args.rom_id)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if args.command=='audit' and not result['ok']: raise SystemExit(2)
    finally: db.c.close()


# This module is embedded after the original API definitions, before main().
import collections, lzma, concurrent.futures
VERSION='3.0.0'
ROM_BLOCK=4096
LZ_FILTERS=[{'id':lzma.FILTER_LZMA2,'dict_size':65536,'lc':3,'lp':0,'pb':0,'mode':lzma.MODE_NORMAL,'nice_len':64,'mf':lzma.MF_BT4}]
GROUP_LIMIT=2*CHUNK
GROUP_FILTERS=[{'id':lzma.FILTER_LZMA2,'dict_size':4*CHUNK,'lc':3,'lp':0,'pb':0,'mode':lzma.MODE_NORMAL,'nice_len':273,'mf':lzma.MF_BT4}]

def encode_group(raw):
    encoded=lzma.compress(raw,format=lzma.FORMAT_RAW,filters=GROUP_FILTERS)
    if lzma.decompress(encoded,format=lzma.FORMAT_RAW,filters=GROUP_FILTERS)!=raw:raise ValueError('Group encoder round-trip failure')
    return encoded,hashlib.sha256(raw).digest(),hashlib.sha256(encoded).digest()

def plain_encoding(raw):
    if not raw: raise ValueError('Empty chunk')
    if raw.count(raw[:1])==len(raw): return ('fill',raw[:1])
    candidates=[('raw',raw),('zlib',zlib.compress(raw,9)),('lzma',lzma.compress(raw,format=lzma.FORMAT_RAW,filters=LZ_FILTERS))]
    return min(candidates,key=lambda x:len(x[1]))

def bands(raw):
    if len(raw)<1024 or len(raw)>65536: return []
    step=len(raw)//8; out=[]
    for i in range(8):
        b=raw[i*step:(i+1)*step]
        if b.count(b[:1])!=len(b):out.append((len(raw)<<35)|(i<<32)|zlib.crc32(b))
    return out

BaseDB=DB
class DB(BaseDB):
    def __init__(self,path):
        super().__init__(path)
        self.storage_version=self.c.execute('PRAGMA user_version').fetchone()[0]
        if self.storage_version not in (2,3): raise ValueError('This engine requires RetroBoxDB schema 2 or 3')
        self._decoded=collections.OrderedDict(); self._cache_bytes=0; self._band_index=None
        self._groups=collections.OrderedDict();self._group_cache_bytes=0
        setting=self.c.execute("SELECT value FROM meta WHERE key='nes_block_size'").fetchone()
        self._rom_block=int(setting[0]) if setting else ROM_BLOCK
        if self._rom_block not in (4096,8192,16384,65536):raise ValueError('Unsupported NES block size')
    def _remember(self,cid,raw):
        old=self._decoded.pop(cid,None)
        if old:self._cache_bytes-=len(old[1])
        self._decoded[cid]=(hashlib.sha256(raw).digest(),raw);self._cache_bytes+=len(raw)
        while len(self._decoded)>8192 or self._cache_bytes>64*CHUNK:
            _,old=self._decoded.popitem(last=False);self._cache_bytes-=len(old[1])
    def clear_caches(self):
        self._decoded.clear();self._cache_bytes=0;self._groups.clear();self._group_cache_bytes=0
    def group(self,gid):
        r=self.c.execute('SELECT sha256,encoded_sha256,size,codec FROM compression_groups WHERE id=?',(gid,)).fetchone()
        if r is None:raise ValueError('Missing compression group')
        if r['size']<=0 or r['size']>GROUP_LIMIT or r['codec']!='lzma2-4m':raise ValueError('Invalid compression group format/size')
        key=(r['sha256'],r['encoded_sha256'],r['size'])
        cached=self._groups.get(gid)
        if cached and cached[0]==key:self._groups.move_to_end(gid);return cached[1]
        data=self.c.execute('SELECT data FROM compression_groups WHERE id=?',(gid,)).fetchone()[0]
        if hashlib.sha256(data).digest()!=r['encoded_sha256']:raise ValueError('Compressed group checksum mismatch')
        d=lzma.LZMADecompressor(format=lzma.FORMAT_RAW,filters=GROUP_FILTERS)
        raw=d.decompress(data,max_length=r['size']+1)
        if len(raw)!=r['size'] or not d.eof or d.unused_data or hashlib.sha256(raw).digest()!=r['sha256']:raise ValueError('Compression group integrity failure')
        old=self._groups.pop(gid,None)
        if old:self._group_cache_bytes-=len(old[1])
        self._groups[gid]=(key,raw);self._group_cache_bytes+=len(raw)
        while self._group_cache_bytes>16*CHUNK:
            _,old=self._groups.popitem(last=False);self._group_cache_bytes-=len(old[1])
        return raw
    def chunk(self,cid,seen=()):
        if cid in seen or len(seen)>2:raise ValueError('Invalid delta dependency chain')
        r=self.c.execute('SELECT * FROM chunks WHERE id=?',(cid,)).fetchone()
        if r is None:raise ValueError('Missing chunk')
        cached=self._decoded.get(cid)
        if cached and cached[0]==r['sha256']:return cached[1]
        codec=r['codec']; data=r['data']; size=r['size']
        if codec=='group':
            if self.storage_version<3:raise ValueError('Group codec requires storage schema 3')
            offset=r['group_offset'];group=self.group(r['group_id'])
            if offset is None or offset<0 or offset+size>len(group):raise ValueError('Invalid compression group slice')
            raw=group[offset:offset+size]
        elif codec=='raw':raw=data
        elif codec=='fill':raw=data*size
        elif codec.endswith('zlib'):
            d=zlib.decompressobj();raw=d.decompress(data,size+1)
            if not d.eof or d.unused_data or d.unconsumed_tail:raise ValueError('Invalid compressed chunk')
        elif codec.endswith('lzma'):
            d=lzma.LZMADecompressor(format=lzma.FORMAT_RAW,filters=LZ_FILTERS);raw=d.decompress(data,max_length=size+1)
            if not d.eof or d.unused_data:raise ValueError('Invalid LZMA chunk')
        else:raise ValueError('Unknown codec')
        if codec.startswith('xor-'):
            base=self.chunk(r['base_id'],seen+(cid,))
            if len(base)!=size or len(raw)!=size:raise ValueError('Delta size mismatch')
            raw=(int.from_bytes(raw,'little')^int.from_bytes(base,'little')).to_bytes(size,'little')
        if len(raw)!=size or hashlib.sha256(raw).digest()!=r['sha256']:raise ValueError('Chunk integrity failure')
        self._remember(cid,raw);return raw
    def compact_groups(self,group_bytes=GROUP_LIMIT,workers=4,progress=None):
        """Atomically repack independent LZMA blocks; callers VACUUM after commit.

        Dedup IDs, raw block hashes, object extents and delta bases never change.
        Imported content remains ordinary blocks until this maintenance pass.
        """
        if self.storage_version!=3:raise ValueError('Migrate to storage schema 3 before compacting')
        edition=self.c.execute("SELECT value FROM meta WHERE key='payload_available'").fetchone()
        if edition and edition[0]=='false':raise ValueError('Catalog-only database cannot compact payloads')
        if not isinstance(group_bytes,int) or not 4096<=group_bytes<=GROUP_LIMIT:raise ValueError('Compression group size must be 4 KiB..2 MiB')
        if not 1<=workers<=4:raise ValueError('Compression workers must be 1..4')
        rows=self.c.execute("SELECT id,size,length(data) AS stored FROM chunks WHERE codec='lzma' AND size<=? ORDER BY id",(min(group_bytes,65536),)).fetchall()
        result={'eligible_chunks':len(rows),'groups_created':0,'chunks_grouped':0,'compressed_bytes_before':0,'compressed_bytes_after':0,'saved_compressed_bytes':0,'group_raw_limit':group_bytes}
        if not rows:return result
        trigger=self.c.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name='immutable_chunks_update'").fetchone()
        if trigger is None:raise ValueError('Missing immutable chunk guard')
        self.c.execute('SAVEPOINT compact_groups')
        try:
            self.c.execute('DROP TRIGGER immutable_chunks_update')
            pending=collections.deque()
            def commit_one(item):
                future,members,raw_size,old_size=item
                encoded,digest,encoded_digest=future.result()
                # Include estimated member references and group metadata; do not grow tiny groups.
                if len(encoded)+16*len(members)+128>=old_size:return
                gid=self.insert('compression_groups',sha256=digest,encoded_sha256=encoded_digest,size=raw_size,codec='lzma2-4m',data=encoded)
                offset=0
                for member in members:
                    self.c.execute("UPDATE chunks SET codec='group',data=X'',group_id=?,group_offset=? WHERE id=?",(gid,offset,member['id']))
                    offset+=member['size']
                result['groups_created']+=1;result['chunks_grouped']+=len(members)
                result['compressed_bytes_before']+=old_size;result['compressed_bytes_after']+=len(encoded)
                if progress and result['groups_created']%50==0:progress(dict(result))
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                members=[];pieces=[];total=0;old_size=0
                def queue_group():
                    pending.append((pool.submit(encode_group,b''.join(pieces)),list(members),total,old_size))
                    if len(pending)>=workers*2:commit_one(pending.popleft())
                for row in rows:
                    if total+row['size']>group_bytes and members:
                        queue_group();members=[];pieces=[];total=0;old_size=0
                    pieces.append(self.chunk(row['id']));members.append(row);total+=row['size'];old_size+=row['stored']
                if members:queue_group()
                while pending:commit_one(pending.popleft())
            self.c.execute(trigger[0])
            result['saved_compressed_bytes']=result['compressed_bytes_before']-result['compressed_bytes_after']
            if result['groups_created']:self.event('compact_groups',details=result)
            self.c.execute('RELEASE compact_groups')
        except BaseException:
            self.c.execute('ROLLBACK TO compact_groups');self.c.execute('RELEASE compact_groups')
            self.clear_caches();self._band_index=None
            raise
        self.clear_caches();self._band_index=None
        return result
    def _add_bands(self,cid,raw,depth):
        if depth>=2:return
        for key in bands(raw):
            values=self._band_index.setdefault(key,[])
            if len(values)==6:values.pop(0)
            values.append(cid)
    def _seed_bands(self):
        if self._band_index is not None:return
        self._band_index={}
        for r in self.c.execute('SELECT id,depth FROM chunks WHERE depth<2 AND size BETWEEN 1024 AND 65536').fetchall():self._add_bands(r['id'],self.chunk(r['id']),r['depth'])
    def store_chunk(self,raw,encoded=None):
        sha=hashlib.sha256(raw).digest(); old=self.c.execute('SELECT id FROM chunks WHERE sha256=?',(sha,)).fetchone()
        if old:
            if self.chunk(old[0])!=raw:raise ValueError('Hash collision or corrupt block')
            return old[0]
        codec,data=encoded or plain_encoding(raw); base_id=None;depth=0
        self._seed_bands()
        if len(data)>96 and 1024<=len(raw)<=65536:
            scores=collections.Counter(cid for key in bands(raw) for cid in self._band_index.get(key,()))
            best=None
            for cid,score in scores.most_common(8):
                if score<2:continue
                try:base=self.chunk(cid)
                except ValueError:continue
                if len(base)!=len(raw):continue
                delta=(int.from_bytes(raw,'little')^int.from_bytes(base,'little')).to_bytes(len(raw),'little')
                compressed=zlib.compress(delta,9)
                if best is None or len(compressed)<len(best[1]):best=(cid,compressed,delta)
            if best:
                cid,z,delta=best;l=lzma.compress(delta,format=lzma.FORMAT_RAW,filters=LZ_FILTERS)
                dc,dd=min([('xor-zlib',z),('xor-lzma',l)],key=lambda x:len(x[1]))
                # Require a saving beyond the base reference and future decode cost.
                if len(dd)+16<len(data):
                    codec,data,base_id=dc,dd,cid;depth=self.c.execute('SELECT depth FROM chunks WHERE id=?',(cid,)).fetchone()[0]+1
        cid=self.insert('chunks',sha256=sha,size=len(raw),codec=codec,base_id=base_id,depth=depth,data=data)
        self._remember(cid,raw);self._add_bands(cid,raw,depth);return cid
    def object_record(self,h,kind='chunks'):
        old=self.c.execute('SELECT id,size,storage_kind FROM objects WHERE sha256=?',(h['sha256'],)).fetchone()
        if old:
            if old['size']!=h['size']:raise ValueError('Object collision')
            return old['id'],False
        return self.insert('objects',**h,storage_kind=kind,created_at=now()),True
    def store_parts(self,oid,segments,encoded_map=None):
        parts=[];offset=0
        for raw in segments:
            if not raw:continue
            enc=encoded_map.get(hashlib.sha256(raw).digest()) if encoded_map else None
            cid=self.store_chunk(raw,enc)
            if parts and parts[-1][3]==cid:parts[-1][4]+=1
            else:parts.append([oid,len(parts),offset,cid,1])
            offset+=len(raw)
        self.c.executemany('INSERT INTO object_chunks(object_id,ordinal,offset,chunk_id,repeat) VALUES (?,?,?,?,?)',parts)
        expected=self.c.execute('SELECT size FROM objects WHERE id=?',(oid,)).fetchone()[0]
        if offset!=expected:raise ValueError('Stored object size differs')
    def put_stream(self,stream,header_boundary=False):
        if not stream.seekable():raise ValueError('A seekable file or in-memory stream is required')
        start=stream.tell(); hs={k:hashlib.new(k) for k in ('sha256','sha1','md5')};crc=0;size=0
        for raw in iter(lambda:stream.read(CHUNK),b''):
            size+=len(raw);crc=zlib.crc32(raw,crc)
            for h in hs.values():h.update(raw)
        h={k:v.hexdigest() for k,v in hs.items()};h.update(size=size,crc32=f'{crc:08x}')
        oid,new=self.object_record(h)
        if not new:
            if self.c.execute('SELECT storage_kind FROM objects WHERE id=?',(oid,)).fetchone()[0]=='archive_manifest':raise ValueError('This ZIP digest is historical; import as an archive')
            return oid
        stream.seek(start);self.store_parts(oid,iter(lambda:stream.read(CHUNK),b''));return oid
    def put(self,data,header_boundary=False):return self.put_stream(io.BytesIO(data))
    def put_body(self,data,cuts=()):
        oid,new=self.object_record(hashes(data))
        if new:
            bounds=sorted({0,len(data)}|{x for x in cuts if 0<=x<=len(data)})
            self.store_parts(oid,(data[p:min(p+self._rom_block,b)] for a,b in zip(bounds,bounds[1:]) for p in range(a,b,self._rom_block)))
        return oid
    def stream(self,oid,_seen=()):
        if oid in _seen or len(_seen)>64:raise ValueError('Object recipe cycle')
        obj=self.c.execute('SELECT * FROM objects WHERE id=?',(oid,)).fetchone()
        if obj is None:raise ValueError('Missing object')
        if obj['storage_kind']=='archive_manifest':raise ValueError('Original ZIP bytes are historical; export by file_id to generate its checksummed archive plan')
        if obj['storage_kind']=='nes_header_body':
            recipe=self.c.execute('SELECT * FROM nes_recipes WHERE object_id=?',(oid,)).fetchone()
            if recipe is None:raise ValueError('Missing header/body recipe')
            yield recipe['header'];size=16
            for b in self.stream(recipe['body_object_id'],_seen+(oid,)):size+=len(b);yield b
            if size!=obj['size']:raise ValueError('Recipe size mismatch')
            return
        pos=0;ordinal=0
        for r in self.c.execute('SELECT * FROM object_chunks WHERE object_id=? ORDER BY ordinal',(oid,)):
            if r['offset']!=pos or r['ordinal']!=ordinal:raise ValueError('Invalid object extent order')
            raw=self.chunk(r['chunk_id'])
            for _ in range(r['repeat']):pos+=len(raw);yield raw
            ordinal+=1
        if pos!=obj['size']:raise ValueError('Incomplete object')
    def rom(self,data,mode='auto'):
        p=parse_nes(data,mode);body=None
        if p['body'] is not None:
            cuts={off-16 for kind,off,size in p['components'] if kind!='header'}|{off+size-16 for kind,off,size in p['components'] if kind!='header'}
            body=self.put_body(p['body'],cuts)
        if p['header'] is not None:
            oid,new=self.object_record(hashes(data),'nes_header_body')
            if new:self.insert('nes_recipes',object_id=oid,body_object_id=body,header=p['header'])
        else:oid=body if body is not None else self.put(data)
        old=self.c.execute('SELECT id FROM roms WHERE object_id=? AND platform_id=1',(oid,)).fetchone()
        if old:return old[0],oid
        pc=p.get('prg_chr')
        rid=self.insert('roms',object_id=oid,platform_id=1,format=p['format'],parse_status=p['parse_status'],header=p['header'],body_object_id=body,prg_chr_sha256=hashlib.sha256(pc).hexdigest() if pc is not None else None,prg_chr_size=len(pc) if pc is not None else None,parser_version=VERSION,warnings_json=js(p['warnings']))
        for i,(kind,off,size) in enumerate(p['components']):self.insert('rom_components',rom_id=rid,ordinal=i,kind=kind,offset=off,size=size,sha256=hashlib.sha256(data[off:off+size]).hexdigest())
        if p['hardware']:self.insert('nes_hardware',rom_id=rid,**p['hardware'])
        return rid,oid
    def plan(self,entries,expected=None):
        # entries: (path, object_id or None for an empty directory)
        entries=normalize_archive_entries(entries)
        description=[]
        for name,oid in entries:
            digest=None if oid is None else self.c.execute('SELECT sha256 FROM objects WHERE id=?',(oid,)).fetchone()[0]
            description.append([name,digest])
        fingerprint=hashlib.sha256(js({'profile':'torrentzip-classic-v1','members':description}).encode()).hexdigest()
        old=self.c.execute('SELECT id FROM archive_plans WHERE fingerprint=?',(fingerprint,)).fetchone()
        if old:return old[0]
        if expected is None:expected=hashes(make_torrentzip([(n,b'' if oid is None else self.get(oid)) for n,oid in entries]))
        pid=self.insert('archive_plans',fingerprint=fingerprint,profile_id=1,encoder='torrentzip-classic-v1',zlib_version=zlib.ZLIB_RUNTIME_VERSION,**expected,verified_at=now())
        for i,(name,oid) in enumerate(entries):self.insert('archive_entries',plan_id=pid,ordinal=i,name=name,object_id=oid,is_directory=int(oid is None))
        return pid
    def archive_bytes(self,plan_id):
        p=self.c.execute('SELECT * FROM archive_plans WHERE id=?',(plan_id,)).fetchone()
        if not p:raise ValueError('Missing archive plan')
        entries=[(r['name'],b'' if r['is_directory'] else self.get(r['object_id'])) for r in self.c.execute('SELECT * FROM archive_entries WHERE plan_id=? ORDER BY ordinal',(plan_id,)).fetchall()]
        result=make_torrentzip(entries);actual=hashes(result)
        if any(actual[k]!=p[k] for k in actual):raise ValueError('Generated ZIP does not match registered checksums; encoder/zlib version may differ')
        return result
    def file_checksums(self,fid):
        r=self.c.execute('SELECT * FROM v_file_checksums WHERE file_id=?',(fid,)).fetchone()
        if not r:raise ValueError('Unknown file')
        return dict(r)
    def export(self,fid,path):
        row=self.c.execute('SELECT object_id FROM files WHERE id=?',(fid,)).fetchone()
        if not row:raise ValueError('Unknown file')
        ar=self.c.execute('SELECT plan_id FROM file_archives WHERE file_id=?',(fid,)).fetchone()
        if ar:
            data=self.archive_bytes(ar[0]);iterator=iter([data]);expected=dict(self.c.execute('SELECT * FROM archive_plans WHERE id=?',(ar[0],)).fetchone())
        else:iterator=self.stream(row[0]);expected=dict(self.c.execute('SELECT * FROM objects WHERE id=?',(row[0],)).fetchone())
        p=pathlib.Path(path).expanduser();created=False
        try:
            with p.open('xb') as f:
                created=True;hs={k:hashlib.new(k) for k in ('sha256','sha1','md5')};crc=0;size=0
                for b in iterator:
                    f.write(b);size+=len(b);crc=zlib.crc32(b,crc)
                    for h in hs.values():h.update(b)
                actual={k:h.hexdigest() for k,h in hs.items()};actual.update(size=size,crc32=f'{crc:08x}')
                if any(actual[k]!=expected[k] for k in actual):raise ValueError('Export checksum mismatch')
                f.flush();os.fsync(f.fileno())
        except BaseException:
            if created:p.unlink(missing_ok=True)
            raise
        return {'path':str(p),'generated_archive':bool(ar),**actual}
    def import_rom_path(self,path,mode='auto'):
        path=pathlib.Path(path).expanduser().resolve()
        if path.suffix.lower()!='.zip':return super().import_rom_path(path,mode)
        original=path.read_bytes();oid,_=self.object_record(hashes(original),'archive_manifest');fid=self.file(oid,path.name,'archive',str(path));result=[];entries=[]
        with zipfile.ZipFile(io.BytesIO(original)) as z:
            total=0
            for i,info in enumerate(z.infolist()):
                if info.is_dir():entries.append((info.filename,None));continue
                total+=info.file_size
                if info.file_size>MAX_ROM or total>2*1024**3:raise ValueError('ZIP import size limit')
                data=z.read(info);ext=pathlib.PurePosixPath(info.filename).suffix.lower()
                if ext in ('.nes','.unh','.bin','.rom','.sav'):
                    rid,obj=self.rom(data,'auxiliary' if ext=='.sav' else mode);result.append(rid);kind='other' if ext=='.sav' else 'rom'
                else:obj=self.put(data);kind='other'
                self.file(obj,info.filename,kind,str(path),fid,i,dict(zip_crc=f'{info.CRC:08x}',compression=info.compress_type,flags=info.flag_bits));entries.append((info.filename,obj))
        pid=self.plan(entries);self.c.execute('INSERT OR IGNORE INTO file_archives VALUES (?,?)',(fid,pid));return result
    def import_dat_path(self,path,mode='auto'):
        p=pathlib.Path(path).expanduser().resolve()
        if p.suffix.lower()!='.zip':return super().import_dat_path(p,mode)
        original=p.read_bytes();oid,_=self.object_record(hashes(original),'archive_manifest');fid=self.file(oid,p.name,'archive',str(p));result=[];entries=[]
        with zipfile.ZipFile(io.BytesIO(original)) as z:
            for i,info in enumerate(z.infolist()):
                if info.is_dir():entries.append((info.filename,None));continue
                if info.file_size>MAX_ROM:raise ValueError('DAT size limit')
                data=z.read(info)
                if info.filename.lower().endswith(('.dat','.xml')):result.append(self.import_dat(data,info.filename,mode,fid,str(p)))
                obj=self.put(data);entries.append((info.filename,obj))
                if not info.filename.lower().endswith(('.dat','.xml')):self.file(obj,info.filename,'other',str(p),fid,i)
        if not result:raise ValueError('No DAT members')
        pid=self.plan(entries);self.c.execute('INSERT OR IGNORE INTO file_archives VALUES (?,?)',(fid,pid));return result
    def package(self,gid,encoded=None):
        game=self.c.execute('SELECT * FROM dat_games WHERE id=?',(gid,)).fetchone();entries=[];members=[]
        for t in self.c.execute('SELECT * FROM dat_roms WHERE dat_game_id=? ORDER BY ordinal',(gid,)).fetchall():
            v=self.c.execute("SELECT * FROM validations WHERE dat_rom_id=? AND status='match' ORDER BY CASE strength WHEN 'sha256' THEN 0 WHEN 'sha1' THEN 1 ELSE 2 END,rom_id LIMIT 1",(t['id'],)).fetchone()
            if v is None:raise ValueError('Missing verified DAT member '+t['name'])
            data=self.get(v['checked_object_id'])
            if self.compare(hashes(data),t)[0]!='match':raise ValueError('Stored data no longer matches DAT')
            entries.append((safe_name(t['name']),v['checked_object_id']));members.append((t['id'],v['rom_id'],v['checked_object_id'],safe_name(t['name'])))
        if encoded is not None:
            expected=make_torrentzip([(n,self.get(o)) for n,o in entries])
            if encoded!=expected:raise ValueError('Prepared ZIP is not the canonical DAT package')
        plan=self.plan(entries);h=dict(self.c.execute('SELECT size,crc32,md5,sha1,sha256 FROM archive_plans WHERE id=?',(plan,)).fetchone())
        oid,_=self.object_record(h,'archive_manifest');fid=self.file(oid,safe_name(game['name'])+'.zip','archive',metadata={'profile':'torrentzip-classic','dat_game_id':gid,'virtual':True})
        self.c.execute('INSERT OR IGNORE INTO file_archives VALUES (?,?)',(fid,plan))
        old=self.c.execute('SELECT id FROM packages WHERE file_id=? AND dat_game_id=?',(fid,gid)).fetchone()
        if old:return old[0]
        pid=self.insert('packages',file_id=fid,dat_game_id=gid,profile_id=1,engine='RetroBoxDB '+VERSION+'; zlib '+zlib.ZLIB_RUNTIME_VERSION,validation_json=js({'member_dat_hashes':'all passed','storage':'virtual','archive_plan_id':plan,'zip_checksums':'materialized once; verified on export'}),created_at=now())
        for i,m in enumerate(sorted(members,key=lambda m:m[3].lower())):self.insert('package_members',package_id=pid,ordinal=i,dat_rom_id=m[0],rom_id=m[1],object_id=m[2],name=m[3])
        return pid
    def audit(self,archives=False):
        self.clear_caches()
        result={'integrity_check':[r[0] for r in self.c.execute('PRAGMA integrity_check')],'foreign_key_errors':[tuple(r) for r in self.c.execute('PRAGMA foreign_key_check')],'objects_checked':0,'archive_plans_checked':0,'historical_zip_objects':self.c.execute("SELECT count(*) FROM objects WHERE storage_kind='archive_manifest'").fetchone()[0],'errors':[]}
        result['compression_groups_checked']=0
        if self.storage_version>=3:
            for gid, in self.c.execute('SELECT id FROM compression_groups').fetchall():
                try:self.group(gid)
                except Exception as e:result['errors'].append({'compression_group_id':gid,'error':str(e)})
                result['compression_groups_checked']+=1
        for o in self.c.execute("SELECT * FROM objects WHERE storage_kind!='archive_manifest'").fetchall():
            try:
                hs={k:hashlib.new(k) for k in ('sha256','sha1','md5')};crc=0;size=0
                for b in self.stream(o['id']):
                    size+=len(b);crc=zlib.crc32(b,crc)
                    for h in hs.values():h.update(b)
                actual={k:h.hexdigest() for k,h in hs.items()};actual.update(size=size,crc32=f'{crc:08x}')
                if any(actual[k]!=o[k] for k in actual):raise ValueError('Object checksum mismatch')
            except Exception as e:result['errors'].append({'object_id':o['id'],'error':str(e)})
            result['objects_checked']+=1
        if archives:
            for p in self.c.execute('SELECT id FROM archive_plans').fetchall():
                try:self.archive_bytes(p[0]);result['archive_plans_checked']+=1
                except Exception as e:result['errors'].append({'archive_plan_id':p[0],'error':str(e)})
        missing=self.c.execute("SELECT count(*) FROM files f LEFT JOIN file_archives fa ON fa.file_id=f.id WHERE f.kind='archive' AND fa.file_id IS NULL").fetchone()[0]
        if missing:result['errors'].append({'missing_archive_plans':missing})
        result['ok']=result['integrity_check']==['ok'] and not result['foreign_key_errors'] and not result['errors'];return result
    def stats(self):
        out=super().stats();out['codecs']=[dict(r) for r in self.c.execute('SELECT codec,count(*) AS blocks,sum(size) AS raw_bytes,sum(length(data)) AS stored_bytes FROM chunks GROUP BY codec')]
        out['storage_schema_version']=self.storage_version
        if self.storage_version>=3:out['compression_groups']=dict(self.c.execute('SELECT count(*) AS groups,coalesce(sum(size),0) AS raw_bytes,coalesce(sum(length(data)),0) AS stored_bytes FROM compression_groups').fetchone())
        return out

def normalize_archive_entries(entries):
    cleaned=[]
    for name,oid in entries:
        if oid is None:
            if not name.endswith('/'):raise ValueError('Directory names must end with /')
            name=safe_name(name[:-1])+'/'
        else:name=safe_name(name)
        cleaned.append((name,oid))
    cleaned=[(n,o) for n,o in cleaned if o is not None or not any(other!=n and other.startswith(n) for other,_ in cleaned)]
    cleaned.sort(key=lambda x:x[0].lower())
    if len({n.casefold() for n,o in cleaned})!=len(cleaned):raise ValueError('Case-insensitive ZIP member collision')
    return cleaned

_legacy_main=main
def main(db_path,argv):
    if argv and argv[0] in ('checksums','audit-all','compact'):
        db=DB(db_path)
        try:
            if argv[0]=='compact':
                with db.c:result=db.compact_groups()
                if result['groups_created']:db.c.execute('VACUUM')
            else:result=db.file_checksums(int(argv[1])) if argv[0]=='checksums' else db.audit(archives=True)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            if argv[0]=='audit-all' and not result['ok']:raise SystemExit(2)
        finally:db.c.close()
    else:_legacy_main(db_path,argv)

if __name__=='__main__': main(sys.argv[1],sys.argv[2:])
