"""Family-ordered dedup blocks packed into bounded solid LZMA groups."""
import pickle,sys,lzma,hashlib,json,multiprocessing as mp,time
def lz(data,dict_size):
    f=[{'id':lzma.FILTER_LZMA2,'dict_size':dict_size,'lc':3,'lp':0,'pb':0,'mode':lzma.MODE_NORMAL,'nice_len':273,'mf':lzma.MF_BT4}]
    return len(lzma.compress(data,format=lzma.FORMAT_RAW,filters=f))
def plan(S,B,C):
    seen=set(); groups=[]; cur=[]; size=0; nblocks=0; refs=0
    fams=sorted(S['files'].items())
    for k,items in fams:
        uniq={}
        for p,n,d in sorted(items,key=lambda x:x[1]): uniq.setdefault(hashlib.sha256(d).digest(),d)
        fam=[]
        for d in uniq.values():
            for i in range(0,len(d),B):
                b=d[i:i+B]; refs+=1; h=hashlib.sha256(b).digest()
                if h in seen: continue
                seen.add(h); fam.append(b); nblocks+=1
        fsize=sum(map(len,fam))
        if cur and size+fsize>C: groups.append(b''.join(cur)); cur=[]; size=0
        for b in fam:
            if size+len(b)>C: groups.append(b''.join(cur)); cur=[]; size=0
            cur.append(b); size+=len(b)
    if cur: groups.append(b''.join(cur))
    return groups,nblocks,refs
if __name__=='__main__':
    S=pickle.load(open(sys.argv[1],'rb')); res={}
    for B,C in [(8192,2<<20),(8192,16<<20),(65536,16<<20),(65536,32<<20),(65536,64<<20),(1<<20,32<<20)]:
        t=time.time(); groups,nb,refs=plan(S,B,C); d=1<<max(20,(C-1).bit_length())
        with mp.Pool(8) as pool: sizes=pool.starmap(lz,[(g,d) for g in groups],chunksize=1)
        res[f'B{B//1024}K_C{C>>20}M']=dict(MiB=round(sum(sizes)/2**20,1),unique_MiB=round(sum(map(len,groups))/2**20,1),groups=len(groups),blocks=nb,block_refs=refs,meta_MiB_est=round((nb*90+refs*40)/2**20,1),s=round(time.time()-t))
        print(sys.argv[1],json.dumps(res[f'B{B//1024}K_C{C>>20}M']),f'B{B//1024}K_C{C>>20}M',flush=True)
