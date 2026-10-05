"""Build a reproducible family sample: local No-Intro zips grouped by DAT parent/clone (fallback: base title)."""
import zipfile,pathlib,re,random,json,sys,hashlib,xml.etree.ElementTree as ET,collections,pickle
DAT={'snes':"Nintendo - Super Nintendo Entertainment System (Parent-Clone) (20260710-203222).zip",'md':"Sega - Mega Drive - Genesis (Parent-Clone) (20260714-063411).zip"}
PRE={'snes':"Nintendo - Super Nintendo Entertainment System",'md':"Sega - Mega Drive - Genesis"}
def families(plat):
    z=zipfile.ZipFile(pathlib.Path('~/Sync/Datfiles').expanduser()/DAT[plat]); root=ET.fromstring(z.read(z.namelist()[0]))
    parent={g.get('name'):(g.get('cloneof') or g.get('name')) for g in root.findall('game')}
    sha={r.get('sha1'):g.get('name') for g in root.findall('game') for r in g.findall('rom')}
    fam=collections.defaultdict(list)
    for d in sorted(pathlib.Path('/mnt/MyShare/No-Intro').glob(PRE[plat]+'*')):
        for p in sorted(d.iterdir()):
            key=parent.get(p.stem)
            if key is None: key='~'+re.sub(r'\s*\(.*$','',p.stem).strip().lower()
            fam[key].append(str(p))
    return fam
if __name__=='__main__':
    plat=sys.argv[1]; n=int(sys.argv[2]); fam=families(plat)
    keys=sorted(fam); random.Random(2026).shuffle(keys); pick=keys[:n]
    files={}
    for k in pick:
        for p in fam[k]:
            with zipfile.ZipFile(p) as z:
                for i in z.infolist():
                    if not i.is_dir(): files.setdefault(k,[]).append((p,i.filename,z.read(i)))
    zipbytes=sum(pathlib.Path(p).stat().st_size for k in pick for p in fam[k])
    raw=sum(len(d) for v in files.values() for _,_,d in v)
    print(plat,'families',len(fam),'sampled',len(pick),'files',sum(len(v) for v in files.values()),'zip MiB',zipbytes/2**20,'raw MiB',raw/2**20)
    pickle.dump({'files':files,'zipbytes':zipbytes,'all_families':len(fam),'all_zipbytes':sum(pathlib.Path(p).stat().st_size for v in fam.values() for p in v)},open(f'sample_{plat}.pkl','wb'))
