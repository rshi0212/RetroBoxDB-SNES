import pickle,sys,lzma,multiprocessing as mp
from cart_storage_fg import plan
def run(a):
    g,lc,lp,pb=a
    f=[{'id':lzma.FILTER_LZMA2,'dict_size':32<<20,'lc':lc,'lp':lp,'pb':pb,'mode':lzma.MODE_NORMAL,'nice_len':273,'mf':lzma.MF_BT4}]
    return (lc,lp,pb),len(lzma.compress(g,format=lzma.FORMAT_RAW,filters=f))
if __name__=='__main__':
    for plat in ('snes','md'):
        S=pickle.load(open(f'sample_{plat}.pkl','rb')); groups,_,_=plan(S,65536,32<<20); gs=groups[::4][:4]
        combos=[(3,0,0),(3,0,2),(0,1,1),(1,1,1),(2,1,1),(3,1,1),(4,0,0),(0,0,0)]
        with mp.Pool(8) as p: res=p.map(run,[(g,*c) for c in combos for g in gs])
        tot={}
        for k,v in res: tot[k]=tot.get(k,0)+v
        base=tot[(3,0,0)]; print(plat,{str(k):round(v/base,4) for k,v in tot.items()},flush=True)
