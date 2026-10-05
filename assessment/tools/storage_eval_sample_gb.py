"""Reproducible family sample per platform: local No-Intro ZIPs grouped by newest DAT parent/clone (fallback: title)."""
import zipfile, pathlib, re, random, sys, xml.etree.ElementTree as ET, collections, pickle
DAT = {'gb': "Nintendo - Game Boy (Parent-Clone) (20261001-130150).zip",
       'gbc': "Nintendo - Game Boy Color (Parent-Clone) (20261001-131920).zip",
       'gba': "Nintendo - Game Boy Advance (Parent-Clone) (20260929-130236).zip"}
PRE = {'gb': "Nintendo - Game Boy", 'gbc': "Nintendo - Game Boy Color", 'gba': "Nintendo - Game Boy Advance"}


def dirs(plat):
    root = pathlib.Path('/mnt/MyShare/No-Intro')
    return sorted(d for d in root.iterdir() if d.is_dir() and (d.name == PRE[plat] or d.name.startswith(PRE[plat] + ' (')))


def families(plat):
    z = zipfile.ZipFile(pathlib.Path('~/Sync/Datfiles').expanduser() / DAT[plat]); root = ET.fromstring(z.read(z.namelist()[0]))
    parent = {g.get('name'): (g.get('cloneof') or g.get('name')) for g in root.findall('game')}
    fam = collections.defaultdict(list)
    for d in dirs(plat):
        for p in sorted(d.iterdir()):
            key = parent.get(p.stem) or '~' + re.sub(r'\s*\(.*$', '', p.stem).strip().lower()
            fam[key].append(str(p))
    return fam


if __name__ == '__main__':
    plat = sys.argv[1]; n = int(sys.argv[2]); fam = families(plat)
    keys = sorted(fam); random.Random(2026).shuffle(keys); pick = keys[:n]
    files = {}
    for k in pick:
        for p in fam[k]:
            with zipfile.ZipFile(p) as z:
                for i in z.infolist():
                    if not i.is_dir(): files.setdefault(k, []).append((p, i.filename, z.read(i)))
    zipbytes = sum(pathlib.Path(p).stat().st_size for k in pick for p in fam[k])
    raw = sum(len(d) for v in files.values() for _, _, d in v)
    allzip = sum(pathlib.Path(p).stat().st_size for v in fam.values() for p in v)
    print(plat, 'dirs', [d.name for d in dirs(plat)], 'families', len(fam), 'sampled', len(pick), 'files', sum(len(v) for v in files.values()),
          'zip MiB', round(zipbytes / 2**20, 1), 'raw MiB', round(raw / 2**20, 1), 'all zip MiB', round(allzip / 2**20))
    pickle.dump({'files': files, 'zipbytes': zipbytes, 'all_families': len(fam), 'all_zipbytes': allzip}, open(f'sample_{plat}.pkl', 'wb'))
