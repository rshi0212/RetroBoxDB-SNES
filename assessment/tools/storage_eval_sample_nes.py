"""NES family sample: bodies (headered files minus their 16-byte header, plus headerless files) grouped by Headered DAT parent/clone."""
import zipfile, pathlib, re, random, sys, xml.etree.ElementTree as ET, collections, pickle, glob, os
dat = sorted(glob.glob(os.path.expanduser('~/Sync/Datfiles/Nintendo - Nintendo Entertainment System (Headered) (Parent-Clone) (*).zip')))[-1]
z = zipfile.ZipFile(dat); root = ET.fromstring(z.read(z.namelist()[0]))
parent = {g.get('name'): (g.get('cloneof') or g.get('name')) for g in root.findall('game')}
fam = collections.defaultdict(list)
for d in sorted(pathlib.Path('/mnt/MyShare/No-Intro').iterdir()):
    if not d.is_dir() or not d.name.startswith('Nintendo - Nintendo Entertainment System ('): continue
    for p in sorted(d.glob('*.zip')): fam[parent.get(p.stem) or '~' + re.sub(r'\s*\(.*$', '', p.stem).strip().lower()].append(p)
keys = sorted(fam); random.Random(2026).shuffle(keys); pick = keys[:int(sys.argv[1])]
files = {}; raw = []
for k in pick:
    for p in fam[k]:
        with zipfile.ZipFile(p) as z:
            for i in z.infolist():
                if i.is_dir(): continue
                d = z.read(i); raw.append((str(p), i.filename, d))
                files.setdefault(k, []).append((str(p), i.filename, d[16:] if d[:4] == b'NES\x1a' else d))
print('families', len(fam), 'sampled', len(pick), 'files', len(raw), 'zip MiB', round(sum(os.path.getsize(p) for k in pick for p in fam[k]) / 2**20, 1),
      'raw MiB', round(sum(len(d) for _, _, d in raw) / 2**20, 1))
pickle.dump({'files': files, 'zipbytes': sum(os.path.getsize(p) for k in pick for p in fam[k])}, open('sample_nes.pkl', 'wb'))
pickle.dump(raw, open('sample_nes_raw.pkl', 'wb'))
