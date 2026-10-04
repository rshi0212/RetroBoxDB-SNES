import pickle,sys,time,json,sqlite3,pathlib,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from build_v3 import create
import engine
block=int(sys.argv[3]) if len(sys.argv)>3 else 8192
out=pathlib.Path(sys.argv[2]); out.unlink(missing_ok=True); create(out)
c=sqlite3.connect(out); c.execute("INSERT OR REPLACE INTO meta VALUES('nes_block_size',?)",(str(block),)); c.commit(); c.close()
db=engine.DB(out); S=pickle.load(open(sys.argv[1],'rb')); t=time.time()
items=[(p,n,d) for k in sorted(S['files']) for p,n,d in S['files'][k]]
items.sort(key=lambda x:x[0])  # import order = path order, as the NES importer did
with db.c:
    for p,n,d in items: db.rom(d,'headerless')
t1=time.time()
with db.c: g=db.compact_groups()
db.c.execute('VACUUM')
st=db.c.execute("SELECT (SELECT sum(length(data)) FROM chunks)+(SELECT coalesce(sum(length(data)),0) FROM compression_groups)").fetchone()[0]
print(sys.argv[1],'block',block,json.dumps({'stored_MiB':round(st/2**20,1),'file_MiB':round(out.stat().st_size/2**20,1),'import_s':round(t1-t),'compact_s':round(time.time()-t1),'chunks':db.c.execute('select count(*) from chunks').fetchone()[0],'codecs':[tuple(r) for r in db.c.execute('select codec,count(*) from chunks group by codec')]}),flush=True)
