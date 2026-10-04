import pickle,sys,lzma,hashlib,time,multiprocessing as mp,json
from compression import zstd
def lz(data,dict_size,preset_nice=273):
    f=[{'id':lzma.FILTER_LZMA2,'dict_size':dict_size,'lc':3,'lp':0,'pb':0,'mode':lzma.MODE_NORMAL,'nice_len':preset_nice,'mf':lzma.MF_BT4}]
    return len(lzma.compress(data,format=lzma.FORMAT_RAW,filters=f))
def pow2(n,lo=1<<20,hi=1<<26):
    d=lo
    while d<n and d<hi: d<<=1
    return d
ZP={zstd.CompressionParameter.compression_level:19,zstd.CompressionParameter.window_log:27,zstd.CompressionParameter.enable_long_distance_matching:1}
def zs(data,ref=None):
    d=zstd.ZstdDict(ref,is_raw=True) if ref else None
    return len(zstd.compress(data,options=ZP,zstd_dict=d))
def family(args):
    key,items=args
    uniq={}
    for p,n,d in items: uniq.setdefault(hashlib.sha256(d).digest(),(n,d))
    files=[v for k,v in sorted(uniq.items(),key=lambda kv:kv[1][0])]
    datas=[d for n,d in files]; total=sum(map(len,datas)); r={'raw':sum(len(d) for p,n,d in items),'unique':total}
    r['lzma_file']=sum(lz(d,pow2(len(d))) for d in datas)
    r['zstd_file']=sum(zs(d) for d in datas)
    solid=b''.join(datas)
    r['lzma_family_solid']=lz(solid,pow2(len(solid)))
    for G in (2,8,32):
        lim=G<<20; s=0; buf=[]; size=0
        for d in datas:
            # whole files packed; a file larger than G becomes its own group
            if buf and size+len(d)>lim: s+=lz(b''.join(buf),pow2(size,hi=1<<27)); buf=[];size=0
            buf.append(d); size+=len(d)
        if buf: s+=lz(b''.join(buf),pow2(size,hi=1<<27))
        r[f'lzma_group_{G}M']=s
    # zstd reference delta: first file standalone; each next one vs best previous (and vs first only)
    s_first=zs(datas[0]); s_best=s_first; s_par=s_first; lz_ref=lz(datas[0],pow2(len(datas[0])))
    lz_pair=lz_ref
    for i in range(1,len(datas)):
        own=zs(datas[i]); vs_par=zs(datas[i],datas[0]); s_par+=min(own,vs_par)
        best=min([own]+[zs(datas[i],datas[j]) for j in range(i)]) if i<=8 else min(own,vs_par)
        s_best+=best
        # LZMA pair estimate: cost of clone given parent inside one stream
        lz_pair+=min(lz(datas[i],pow2(len(datas[i]))), lz(datas[0]+datas[i],pow2(len(datas[0])+len(datas[i])))-lz_ref)
    r['zstd_ref_parent']=s_par; r['zstd_ref_best']=s_best; r['lzma_ref_parent_est']=lz_pair
    return r
if __name__=='__main__':
    S=pickle.load(open(sys.argv[1],'rb')); t=time.time()
    with mp.Pool(8) as pool: res=pool.map(family,sorted(S['files'].items(),key=lambda kv:-sum(len(d) for _,_,d in kv[1])),chunksize=1)
    tot={}
    for r in res:
        for k,v in r.items(): tot[k]=tot.get(k,0)+v
    tot['zip']=S['zipbytes']
    out={k:round(v/2**20,1) for k,v in tot.items()}
    out['seconds']=round(time.time()-t); print(sys.argv[1],json.dumps(out)); json.dump({'tot':tot,'per':res},open(sys.argv[1]+'.json','w'))
