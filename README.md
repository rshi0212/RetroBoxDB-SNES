# RetroBoxDB SNES

English | [中文说明](README.zh-CN.md)

A single-file SQLite archive design for Super Nintendo Entertainment System / Super Famicom preservation: exact ROM identities, deduplicated storage, DAT validation across No-Intro snapshots, dump provenance, internal-header metadata, RetroAchievements hash matching, English/Chinese names and checksummed TorrentZip export plans. It is the cartridge sibling of [RetroBoxDB-NES](https://github.com/rshi0212/RetroBoxDB-NES).

**The public Catalog contains no ROM bodies, original DAT/DB/Dumplog payloads, compressed content groups or media.** The populated database stays local. The Catalog keeps metadata, expected checksums, header fields, archive recipes, provenance and the processing source code; it cannot restore or export files.

| Download / document | Purpose |
| --- | --- |
| [RetroBoxDB.SNES.Catalog.sqlite](https://github.com/rshi0212/RetroBoxDB-SNES/releases/latest/download/RetroBoxDB.SNES.Catalog.sqlite) | Metadata-only SQLite (48 MiB), attached to GitHub Releases |
| [Technical design](RetroBoxDB.Cartridge.Technical-Design.en.md) | Storage v4, adapters, incremental updates, RetroAchievements, verification |
| [中文说明](RetroBoxDB.Cartridge.zh-CN.md) | Full Chinese guide for SNES and Mega Drive |
| [RA coverage](reports/ra-snes-games.csv) / [summary](reports/ra-snes.json) | Every RetroAchievements game with achievements and its match status |
| [Build report](reports/snes-build-report.json) | Import, scan, diff, No-Intro, packages, names and audit results |

## Collection

| | |
| --- | --- |
| Local No-Intro ZIPs (incl. Aftermarket/Private) | 4,898 files, 3.99 GiB |
| Populated database | 1.54 GiB (38.6% of the source ZIPs) |
| ROM records / games / releases | 4,293 / 1,996 / 4,329 |
| DAT 20260710-203222 coverage | 4,255/4,318 |
| DAT 20261003-140326 coverage | 4,261/4,331 |
| DAT diff (old → new) | 4,313 unchanged, 13 added, 5 renamed |
| No-Intro DB Export + Dump Log 20261003-140326 | 4,365 archives, 5,457 file identities, 12,153 sources, 5,399 documented hardware assertions; Dump Log 1,871 Verified |

## Storage chosen by measurement

The NES layout (8 KiB blocks, XOR deltas, 2 MiB LZMA groups) was not copied blindly. A 10% random family sample compared seven strategies; SNES sample: 443 MiB ZIP → 239 MiB with the NES v3 engine → 191 MiB with storage v4 (−20%). Storage v4 deduplicates 64 KiB blocks by SHA256 and packs them in No-Intro family order (parent and clones together) into solid LZMA2 groups of at most 32 MiB. Here, 4.25 GiB of unique blocks are stored as 1.48 GiB in 145 groups. Every block keeps its own SHA256, every object is verified against CRC32/MD5/SHA1/SHA256, and the v3 engine refuses v4 files rather than misreading them. See [assessment/data/cart-storage-experiment.json](assessment/data/cart-storage-experiment.json).

## RetroAchievements

A snapshot of the public RA API (console 3) is stored in `ra_games` / `ra_hashes`; no credentials are stored. Each ROM's RA hash is computed with rcheevos rules. Of 1,185 RA games with achievements, **673 have a matching local ROM** (914 ROMs), **none is missing among games No-Intro lists**, 1 matches only a No-Intro DB bad dump, and 511 (440 hacks, 64 official sets that target translation patches or subsets).

```sql
SELECT * FROM v_rom_ra_matches WHERE has_achievements;
SELECT * FROM v_dat_ra_matches WHERE has_achievements AND NOT local_rom_available;
```

## Names

3,942 of 4,154 rows translated (2,030 unique names); 3,864 direct + 73 inherited releases; 3,909 local ROMs.

```sql
SELECT * FROM v_release_effective_chinese_names WHERE catalog_title LIKE '%Mario%';
```

## Using the Catalog

```bash
python3 -B -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); s=c.execute("SELECT content FROM resources WHERE name=?",("engine.py",)).fetchone()[0]; c.close(); exec(compile(s,"RetroBoxDB:engine.py","exec"))' ./RetroBoxDB.SNES.Catalog.sqlite audit
```

Replace `audit` with `stats`, `checksums FILE_ID` or `help`. The catalog engine is query-only and reports `payloads_verified=false`.

## Building and growing your own database

Python 3.10+ standard library only. `tools/build_cart_db.py snes FULL.sqlite --catalog CATALOG.sqlite` builds from local No-Intro inputs (read-only). `tools/update_cart_db.py FULL.sqlite --discover --ra --catalog CATALOG.sqlite` adds new DATs, DB Export/Dump Log snapshots and ROMs idempotently and repacks new revisions into their family's solid group. Tests: `python3 -B -m unittest tests/test_cart.py tests/test_game_names.py`.

Audit of the populated database: 4,297 objects, 145 solid groups, 4,813 archive plans; SQLite integrity and foreign keys clean; no errors.
