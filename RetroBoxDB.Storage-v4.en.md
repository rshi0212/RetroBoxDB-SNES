# RetroBoxDB storage v4: NES / SNES / Mega Drive / Game Boy / Game Boy Color / Game Boy Advance

[中文说明](RetroBoxDB.Storage-v4.zh-CN.md) | [Technical design](RetroBoxDB.Storage-v4.Technical-Design.en.md)

Each platform has one populated database (ROM data, kept locally) and one public Catalog (metadata only). All six use the same engine and the same storage format (v4); per-platform differences in block size, group cap, header parsing and import path are expressed by the database's `meta` values and platform adapter code.

| Platform | Original size (ZIP / ROM files) | Populated database | Ratio (of ZIP / ROM) | Catalog | Single ROM (cold) | Single TorrentZip (cold) | Whole-set export |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| NES | 4.12 GiB / 10.69 GiB | 506.2 MiB | 12.0% / 4.6% | 138.7 MiB | 2.339 s | 2.216 s | 54.1 MiB/s (22,943 files) |
| SNES | 3.99 GiB / 6.97 GiB | 1.54 GiB | 38.5% / 22.0% | 48.5 MiB | 1.099 s | 1.402 s | 20.6 MiB/s (4,898 files) |
| Mega Drive | 3.93 GiB / 8.25 GiB | 936.4 MiB | 23.3% / 11.1% | 42.5 MiB | 1.752 s | 1.986 s | 21.4 MiB/s (5,282 files) |
| Game Boy | 295.8 MiB / 820.0 MiB | 164.4 MiB | 55.6% / 20.0% | 33.6 MiB | 1.669 s | 1.537 s | 33.2 MiB/s (2,672 files) |
| Game Boy Color | 1.06 GiB / 3.50 GiB | 504.1 MiB | 46.6% / 14.1% | 44.2 MiB | 1.676 s | 1.923 s | 26.5 MiB/s (3,006 files) |
| Game Boy Advance | 14.42 GiB / 30.92 GiB | 5.51 GiB | 38.2% / 17.8% | 54.7 MiB | 2.374 s | 2.751 s | 22.2 MiB/s (3,946 files) |

Catalogs are fresh SQLite files with empty `compression_groups`, `chunks` and `object_chunks` tables: no ROM data, original DAT/DB/Dump Log payloads or compressed data. Export performance was measured on this machine (Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz, Python 3.14) while idle, with all checks included:

- **Single file (cold)**: 100 random ROMs and 50 random TorrentZips (fixed seed), engine caches cleared before each export. The time is dominated by decoding the solid group up to the file; larger groups take longer, which is the cost of choosing them for compression.
- **Whole-set export**: every ROM file in the database exported once in storage order with the bulk cache, each group decoded once; this corresponds to exporting sets by DAT version, RA, 1G1R and similar criteria.

## How the storage was chosen

Each platform was evaluated separately:

1. **Sample grid**: a random sample of No-Intro parent/clone families (seed 2026) for block size × group cap combinations, with the unchanged NES v3 engine as baseline.
2. **Full-data curve**: adjacent family-ordered groups of the real database merged and recompressed at 32 to 256 MiB. Samples under-represent similarity between families (shared engines, series), so the real-data curve decides.
3. **Rule**: the smallest group cap whose compressed size is within 0.5% of the 256 MiB result; 256 MiB is the engineering ceiling (beyond it an encoder needs about 6 GB per process and an average read decodes about 256 MiB).

Sample results (MiB, block metadata estimate included; group sizes were then set from the real-data curves):

| Platform | Sample ZIPs | NES v3 engine as is | Best v4 in sample (block / group) | v4 size |
| --- | ---: | ---: | --- | ---: |
| NES | 652.6 | 91.8 | 8 KiB / 128 MiB | 81.9 |
| SNES | 443.2 | 238.9 | 64 KiB / 32 MiB | 191.0 |
| Mega Drive | 408.2 | 216.9 | 64 KiB / 32 MiB | 145.7 |
| Game Boy | 48.9 | 31.6 | 64 KiB / 32 MiB | 26.1 |
| Game Boy Color | 206.5 | 126.7 | 64 KiB / 32 MiB | 104.2 |
| Game Boy Advance | 602.8 | — | 1 MiB / 128 MiB | 228.0 |

Change of compressed size on real data against the base group; the last column is the measured result after applying the chosen cap to the whole database:

| Platform | Data measured | 64 MiB | 128 MiB | 256 MiB | 512 MiB | Chosen | Whole database (groups, size change) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| NES | all 43 family-ordered groups, 1,289 MiB | −1.40% | −2.59% | −5.66% | — | 256 MiB | 43 → 6, −5.66% |
| SNES | first 16 family-ordered groups, 484 MiB | −0.24% | −0.51% | −0.78% | — | 128 MiB | 145 → 37, −0.50% |
| Mega Drive | first 16 family-ordered groups, 472 MiB | −1.74% | −1.99% | −2.64% | — | 256 MiB | 143 → 17, −3.90% |
| Game Boy | all 18 groups, 551 MiB | −1.31% | −2.36% | −3.73% | — | 256 MiB | 18 → 3, −3.73% |
| Game Boy Color | first 16 family-ordered groups, 487 MiB | −1.04% | −1.56% | −2.65% | — | 256 MiB | 77 → 10, −2.88% |
| Game Boy Advance | first 8 family-ordered groups, 956 MiB; 512 MiB exceeds the 256 MiB engineering ceiling | — | base | −2.08% | −3.29% | 256 MiB | 210 → 104, −1.90% |

Base group: 32 MiB for NES, SNES, MD, GB and GBC; 128 MiB for GBA.

Other measurements:

- **BCJ filters**: xz's ARM and ARM-Thumb filters only apply to GBA. On six real 128 MiB groups ARM-Thumb made the output 2.35% larger and ARM 0.73% larger, so neither is used. The other CPUs (6502, 65816, 68000, SM83) have no xz filter.
- **LZMA parameters**: lc/lp/pb variations changed sizes by less than 0.2%; lc3/lp0/pb0, BT4 and nice_len 273 are used throughout.
- **zstd**: parent-dictionary deltas were 8–16% larger than the LZMA layout, and the standard-library `compression.zstd` module requires Python 3.14 while the tools target the Python 3.10+ standard library; not used.
- **NES**: migrated to v4 with 8 KiB blocks (cut at header/trainer/PRG/CHR boundaries) and 256 MiB groups. On the full database the v3 payload (489 lzma2-4m groups plus XOR-delta loose blocks, 382,082,581 bytes) became 344,223,238 bytes (−9.91%); the real-data curve was 64 MiB −1.40%, 128 MiB −2.59%, 256 MiB −5.66% against 32 MiB groups, smaller caps stay more than 0.5% above the 256 MiB result, so 256 MiB is used.

## Storage v4 in brief

- ROM data is split into fixed-size blocks deduplicated by SHA256 and packed in No-Intro family order into `lzma2-solid` groups; block size, group cap and dictionary are stored in each database's `meta`.
- Each block keeps its ID, size and SHA256; objects are assembled from blocks and exports check the full CRC32/MD5/SHA1/SHA256 set.
- Reads decode a group only up to the bytes they need; every block is still checked against its SHA256. The decode cache holds two groups; an object whose blocks lie in several groups (for example a multicart) is read group by group, decoding each group once; audits and bulk exports raise the cache to at most 2 GiB (and at most the decoded size of all groups) and decode whole groups, so no partial decoder keeps its dictionary window.
- NES keeps 16-byte headers separate from bodies, headered and headerless dumps share one body, and 8 KiB blocks follow header/PRG/CHR boundaries.
- Source ZIPs are kept as checksums and regenerated from TorrentZip plans; all 41,594 source ZIPs of the six databases are reproduced byte-for-byte (`v_file_checksums.exported_bytes_equal_source`).
- The format marker is `user_version=4`. The v3 engine refuses v4 files; the v4 engine reads v2, v3 and v4.

| Platform | Block | Group cap / dictionary | Groups | Unique block bytes → stored |
| --- | ---: | ---: | ---: | --- |
| NES | 8 KiB | 256 MiB | 6 | 1.28 GiB → 328.3 MiB |
| SNES | 64 KiB | 128 MiB | 37 | 4.25 GiB → 1.48 GiB |
| Mega Drive | 64 KiB | 256 MiB | 17 | 3.87 GiB → 882.3 MiB |
| Game Boy | 64 KiB | 256 MiB | 3 | 558.1 MiB → 128.3 MiB |
| Game Boy Color | 64 KiB | 256 MiB | 10 | 2.26 GiB → 453.3 MiB |
| Game Boy Advance | 1 MiB | 256 MiB | 104 | 23.72 GiB → 5.45 GiB |

## Contents

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Local ZIPs | 21,792 | 4,898 | 5,281 | 2,671 | 3,006 | 3,946 |
| ROM records | 17,726 | 4,293 | 3,687 | 2,315 | 2,605 | 3,734 |
| Games / releases | 3,477 / 7,385 | 1,996 / 4,329 | 1,581 / 3,503 | 1,419 / 2,299 | 1,576 / 2,622 | 1,901 / 3,750 |
| Local ROMs in no DAT | 2,194 | 32 | 289 | 91 | 137 | 58 |

Every local Parent-Clone DAT version is imported and scanned; `dat_changes` diffs each older version against the newest and older DAT entries join the newest DAT's release through that diff.

- **NES** (2 DATs): 20260713-141345: 7,100/7,288; 20261002-002752: 7,094/7,390
- **SNES** (2 DATs): 20260710-203222: 4,255/4,318; 20261003-140326: 4,261/4,331
- **Mega Drive** (2 DATs): 20260714-063411: 3,398/3,486; 20260927-122056: 3,398/3,504
- **Game Boy** (4 DATs): 20260602-070215: 2,218/2,276; 20260707-013717: 2,218/2,284; 20260814-115131: 2,222/2,292; 20261001-130150: 2,224/2,299
- **Game Boy Color** (5 DATs): 20260602-074724: 2,467/2,604; 20260713-134329: 2,467/2,612; 20260715-062319: 2,467/2,612; 20260814-104253: 2,467/2,614; 20261001-131920: 2,466/2,622
- **Game Boy Advance** (4 DATs): 20260531-074517: 3,676/3,745; 20260707-143610: 3,676/3,748; 20260812-060017: 3,676/3,749; 20260929-130236: 3,676/3,750

## No-Intro DB Export and Dump Log

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Snapshot | 20261002-002752 | 20261003-140326 | 20260927-122056 | 20261001-130150 | 20261001-131920 | 20260929-130236 |
| Archives / file identities | 7,704 / 16,154 | 4,365 / 5,457 | 3,640 / 4,142 | 2,335 / 2,450 | 2,678 / 2,921 | 3,793 / 4,563 |
| Files with local payload | 14,885 | 4,276 | 3,537 | 2,248 | 2,514 | 3,713 |
| Documented hardware assertions | 6,412 | 5,399 | 2,017 | 2,810 | 2,830 | 3,188 |
| Dump Log: verified / trusted unverified / unverified | 2,794 / 3,814 / 1,028 | 1,871 / 1,708 / 736 | 868 / 2,085 / 615 | 719 / 1,118 / 490 | 448 / 1,521 / 703 | 770 / 1,703 / 1,307 |

## RetroAchievements

RA public-API snapshots (`API_GetGameList`) are stored without credentials. Each ROM's RA hash follows rcheevos (NES: body MD5 without the 16-byte header; SNES: drop a 512-byte copier header when size % 8192 = 512; other platforms: whole-file MD5). Matching is exact. Console IDs: NES 7, SNES 3, MD 1, GB 4, GBC 6, GBA 5.

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| RA games with achievements | 1,123 | 1,185 | 612 | 505 | 419 | 774 |
| With a local ROM | 933 | 673 | 520 | 394 | 327 | 581 |
| DAT only (ROM missing) | 1 | 0 | 0 | 2 | 8 | 2 |
| DB Export file only | 2 | 1 | 1 | 0 | 4 | 3 |
| No No-Intro counterpart (hacks) | 187 (133) | 511 (444) | 91 (67) | 109 (33) | 80 (20) | 188 (108) |
| Local ROMs with achievements | 2,708 | 914 | 673 | 506 | 413 | 823 |

## Chinese names

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV rows / translated / unique Chinese names | 4,453 / 3,703 / 1,875 | 4,154 / 3,942 / 2,030 | 2,869 / 2,694 / 1,226 | 1,974 / 1,816 / 1,237 | 2,124 / 1,763 / 1,156 | 3,522 / 3,410 / 1,882 |
| Matched / ambiguous / unmatched | 4,420 / 22 / 11 | 4,099 / 10 / 45 | 2,715 / 58 / 96 | 1,956 / 0 / 18 | 1,945 / 7 / 172 | 3,444 / 26 / 52 |
| Releases with Chinese names (direct + inherited) | 3,698 + 389 | 3,864 + 73 | 2,550 + 117 | 1,803 + 59 | 1,590 + 110 | 3,315 + 47 |
| Local ROMs with Chinese names | 8,100 | 3,909 | 2,656 | 1,829 | 1,639 | 3,350 |

## Information layers

`v_information_sources` lists every information source with its version: existing (DAT versions, ROM files), extended (No-Intro DB/Dump Log snapshots, RA snapshots, name sources, documented hardware assertions) and future placeholders (Batocera/ScreenScraper fields, media slots, scrape records). Each source is imported as a versioned, idempotent snapshot; older snapshots are kept.

## Export and maintenance

`tools/export_set.py` combines DAT version (and NES headered/headerless), set (all, parents, 1G1R with region priority and RA preference), RA filter and category, name include/exclude patterns, container (TorrentZip or plain ROM) and layout (flat, parent, RA category, region); every member is checked against all DAT hashes and `export-manifest.json` records the criteria and checksums. `tools/update_db.py` adds new DATs, DB/Dump Log snapshots, ROMs, RA snapshots and name CSVs idempotently; new ROMs join their family's newest group when it has room. `tools/retune_db.py` merges groups to a larger cap and `tools/migrate_v4.py` converts a v3 database; both keep block identities and run in one verified transaction.

The handling of the 2026-10-04 audit findings is recorded in [reports/audit-resolution-20261004.md](reports/audit-resolution-20261004.md). `engine.py` and the other `resources` entries are executable code; run them only from a database you built or a Release asset whose SHA256 you verified.

Populated-database audits: NES 17,734 objects / 6 groups / 24,487 archive plans; SNES 4,297 objects / 37 groups / 4,813 archive plans; Mega Drive 3,691 objects / 17 groups / 5,044 archive plans; Game Boy 2,323 objects / 3 groups / 2,491 archive plans; Game Boy Color 2,612 objects / 10 groups / 2,679 archive plans; Game Boy Advance 3,740 objects / 104 groups / 3,940 archive plans; all passed.
