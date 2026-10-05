# RetroBoxDB SNES

English | [中文说明](README.zh-CN.md)

Single-file SQLite preservation database for Super Nintendo Entertainment System / Super Famicom. The public Catalog holds metadata only (checksums, DAT and provenance records, header fields, archive recipes and the processing code); it contains no ROM data and cannot restore files. The populated database stays local.

| Item | Value |
| --- | --- |
| Original size | 4,898 No-Intro ZIPs, 3.99 GiB; 4,898 ROM files, 6.97 GiB uncompressed |
| Stored size | populated database 1.54 GiB; public Catalog 48.5 MiB (no ROM data) |
| Ratio | 38.5% of the source ZIPs, 22.0% of the uncompressed ROM files |
| Technology | storage v4: SHA256-deduplicated 64 KiB blocks packed in No-Intro family order into solid LZMA2 groups of up to 128 MiB (128 MiB dictionary); per-block SHA256 and per-object CRC32/MD5/SHA1/SHA256 verification; source ZIPs reproduced byte-for-byte from TorrentZip plans |
| Export performance | Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz, idle, Python 3.14.4, all checks included. Whole-set export (4,898 ROM files in storage order, each group decoded once): 20.6 MiB/s, 71 ms per file on average; single file with a cold cache (the group is decoded up to the file): ROM 1.099 s, TorrentZip 1.402 s on average |

## Downloads and documents

| File / document | Content |
| --- | --- |
| [RetroBoxDB.SNES.Catalog.sqlite](https://github.com/rshi0212/RetroBoxDB-SNES/releases/latest/download/RetroBoxDB.SNES.Catalog.sqlite) | Public Catalog (Release asset with `SHA256SUMS`) |
| [Storage v4 guide](RetroBoxDB.Storage-v4.en.md) / [中文](RetroBoxDB.Storage-v4.zh-CN.md) | Storage evaluation, contents, RA, names and maintenance for all six platforms |
| [Technical design](RetroBoxDB.Storage-v4.Technical-Design.en.md) | Storage format, platform adapters, incremental updates, verification |
| [RA list](reports/ra-snes-games.csv) / [summary](reports/ra-snes.json), [build report](reports/snes-build-report.json), [audit resolution](reports/audit-resolution-20261004.md) | Detailed data |

## Storage choice and platform specifics

Change against 32 MiB groups on real data (first 16 family-ordered groups, 484 MiB): 64 MiB −0.24%, 128 MiB −0.51%, 256 MiB −0.78%; 128 MiB chosen by the rule.

- ROM sizes are 0.25–6 MiB; regional versions and revisions are similar but often shifted, so aligned XOR deltas (the NES v3 approach) catch little and a large LZMA2 dictionary over family-ordered data captures the redundancy.
- Internal header: the location (LoROM 0x7FC0, HiROM 0xFFC0, ExLoROM, ExHiROM) is chosen by a score over checksum/complement, map mode, title, ROM-size byte and reset vector; below the threshold a dump stays `unclassified` (mostly betas, prototypes, pirate carts and enhancement-chip firmware). Map mode, FastROM, chipset and coprocessor, SRAM size, region, maker/game codes and both checksums are stored.
- A 512-byte copier header (file size % 1024 = 512) would be cut off as its own block so the body deduplicates with headerless dumps, and the RA hash is computed after it; the local collection contains none.
- Most RA games without a No-Intro counterpart are hacks, translation patches (for example the RA sets for Bahamut Lagoon and Rushing Beat use English-patched ROMs) and subsets.

## Contents

| Item | Value |
| --- | --- |
| ROM records / games / releases | 4,293 / 1,996 / 4,329 |
| DAT coverage per version | 20260710-203222: 4,255/4,318; 20261003-140326: 4,261/4,331 |
| Local ROMs in no DAT | 32 |
| No-Intro DB Export + Dump Log 20261003-140326 | 4,365 archives, 5,457 file identities, 5,399 documented hardware assertions; Dump Log Verified 1,871 |
| RetroAchievements (console 3) | 1,185 games with achievements: 673 with a local ROM (914 ROMs), 0 DAT only, 1 DB file only, 511 without a No-Intro counterpart |
| Chinese names | 3,942 of 4,154 rows translated (2,030 unique); 3,909 local ROMs have a Chinese name |
| Populated-database audit | 4,297 objects, 37 groups, 4,813 archive plans, all passed |

Every source ZIP is reproduced byte-for-byte from its TorrentZip plan (`v_file_checksums.exported_bytes_equal_source`).

## Usage

```bash
# Query-only audit with the Catalog's embedded engine (also: stats, checksums FILE_ID, help)
python3 -B -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); s=c.execute("SELECT content FROM resources WHERE name=?",("engine.py",)).fetchone()[0]; c.close(); exec(compile(s,"RetroBoxDB:engine.py","exec"))' ./RetroBoxDB.SNES.Catalog.sqlite audit
# Populated database: export by DAT version, 1G1R, RA achievements, TorrentZip or plain ROMs
python3 -B tools/export_set.py RetroBoxDB.SNES.sqlite OUT --set 1g1r --ra achievements --container torrentzip --layout ra-category
# Add new DATs, DB Export / Dump Log snapshots, ROMs and an RA snapshot incrementally
python3 -B tools/update_db.py RetroBoxDB.SNES.sqlite --discover --ra --catalog RetroBoxDB.SNES.Catalog.sqlite
```

Python 3.10+ standard library only. `engine.py` and the other `resources` entries are executable code; run them only from a database you built or a Release asset whose SHA256 you verified. Releases are produced by `.github/workflows/publish-catalog.yml`: it starts from the base Catalog pinned in `release/catalog-release.json`, injects the engine and documents of this commit, checks every data-table digest, runs the tests and the audit, then publishes.
