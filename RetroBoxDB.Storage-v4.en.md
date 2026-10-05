# RetroBoxDB storage v4: NES / SNES / Mega Drive / Game Boy / Game Boy Color / Game Boy Advance / Famicom Disk System

[中文说明](RetroBoxDB.Storage-v4.zh-CN.md) | [Technical design](RetroBoxDB.Storage-v4.Technical-Design.en.md)

Each platform has one populated database (ROM data, kept locally) and one public Catalog (metadata only). All seven use the same engine and the same storage format (v4); per-platform differences in block size, group cap, header parsing and import path are expressed by the database's `meta` values and platform adapter code. Original sizes include the No-Intro folders and the RetroAchievements-curated ROM folders (see Contents).

| Platform | Original size (ZIP / ROM files) | Populated database | Ratio (of ZIP / ROM) | Catalog | Single ROM (cold) | Single TorrentZip (cold) | Whole-set export |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| NES | 4.35 GiB / 11.18 GiB | 536.8 MiB | 12.1% / 4.7% | 145.1 MiB | 2.325 s | 1.983 s | 32.3 MiB/s (24,912 files) |
| SNES | 6.09 GiB / 10.90 GiB | 1.78 GiB | 29.3% / 16.4% | 53.7 MiB | 1.121 s | 1.398 s | 22.3 MiB/s (6,734 files) |
| Mega Drive | 4.66 GiB / 9.61 GiB | 998.5 MiB | 20.9% / 10.2% | 44.7 MiB | 1.734 s | 2.087 s | 21.4 MiB/s (6,216 files) |
| Game Boy | 401.1 MiB / 1.05 GiB | 177.7 MiB | 44.3% / 16.5% | 35.5 MiB | 1.594 s | 1.812 s | 21.4 MiB/s (3,392 files) |
| Game Boy Color | 1.38 GiB / 4.42 GiB | 522.2 MiB | 37.1% / 11.5% | 45.5 MiB | 1.719 s | 1.857 s | 35.7 MiB/s (3,581 files) |
| Game Boy Advance | 21.20 GiB / 44.24 GiB | 7.01 GiB | 33.1% / 15.9% | 57.8 MiB | 2.413 s | 2.682 s | 22.3 MiB/s (5,152 files) |
| Famicom Disk System | 33.8 MiB / 82.7 MiB | 21.1 MiB | 62.4% / 25.5% | 9.5 MiB | 0.364 s | 0.334 s | 20.0 MiB/s (747 files) |

Catalogs are fresh SQLite files with empty `compression_groups`, `chunks` and `object_chunks` tables: no ROM data, original DAT/DB/Dump Log payloads or compressed data. Export performance was measured on this machine (Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz, Python 3.14) while idle, with all checks included:

- **Single file (cold)**: 100 random ROMs and 50 random TorrentZips (fixed seed), engine caches cleared before each export. The time is dominated by decoding the solid group up to the file; larger groups take longer, which is the cost of choosing them for compression.
- **Whole-set export**: every ROM file in the database exported once in storage order with the bulk cache (up to 2 GiB of whole decoded groups); when all groups fit, each is decoded once, otherwise (NES) objects spanning groups make some groups decode again. This corresponds to exporting sets by DAT version, RA, 1G1R and similar criteria.

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
| Famicom Disk System (whole set) | 33.7 | — | 64 KiB / 128 MiB | 10.1 |

Change of compressed size on real data against the base group; the last column is the measured result after applying the chosen cap to the whole database:

| Platform | Data measured | 64 MiB | 128 MiB | 256 MiB | 512 MiB | Chosen | Whole database (groups, size change) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| NES | all 43 family-ordered groups, 1,289 MiB | −1.40% | −2.59% | −5.66% | — | 256 MiB | 43 → 6, −5.66% |
| SNES | first 16 family-ordered groups, 484 MiB | −0.24% | −0.51% | −0.78% | — | 128 MiB | 145 → 37, −0.50% |
| Mega Drive | first 16 family-ordered groups, 472 MiB | −1.74% | −1.99% | −2.64% | — | 256 MiB | 143 → 17, −3.90% |
| Game Boy | all 18 groups, 551 MiB | −1.31% | −2.36% | −3.73% | — | 256 MiB | 18 → 3, −3.73% |
| Game Boy Color | first 16 family-ordered groups, 487 MiB | −1.04% | −1.56% | −2.65% | — | 256 MiB | 77 → 10, −2.88% |
| Game Boy Advance | first 8 family-ordered groups, 956 MiB; 512 MiB exceeds the 256 MiB engineering ceiling | — | base | −2.08% | −3.29% | 256 MiB | 210 → 104, −1.90% |
| Famicom Disk System | whole collection with 64 KiB blocks, 77 MiB (one group from 128 MiB) | −1.15% | −4.75% | −4.75% | — | 128 MiB | — |

Base group: 32 MiB for NES, SNES, MD, GB, GBC and FDS; 128 MiB for GBA. FDS was built directly with 128 MiB (one group for the platform), so it has no retune result.

Other measurements:

- **BCJ filters**: xz's ARM and ARM-Thumb filters only apply to GBA. On six real 128 MiB groups ARM-Thumb made the output 2.35% larger and ARM 0.73% larger, so neither is used. The other CPUs (6502, 65816, 68000, SM83) have no xz filter.
- **LZMA parameters**: lc/lp/pb variations changed sizes by less than 0.2%; lc3/lp0/pb0, BT4 and nice_len 273 are used throughout.
- **zstd**: parent-dictionary deltas were 8–16% larger than the LZMA layout, and the standard-library `compression.zstd` module requires Python 3.14 while the tools target the Python 3.10+ standard library; not used.
- **NES**: migrated to v4 with 8 KiB blocks (cut at header/trainer/PRG/CHR boundaries) and 256 MiB groups. On the full database the v3 payload (489 lzma2-4m groups plus XOR-delta loose blocks, 382,082,581 bytes) became 344,223,238 bytes (−9.91%); the real-data curve was 64 MiB −1.40%, 128 MiB −2.59%, 256 MiB −5.66% against 32 MiB groups, smaller caps stay more than 0.5% above the 256 MiB result, so 256 MiB is used.
- **FDS**: 64 KiB blocks (one block per side) in a single 128 MiB group: 10.055 MiB in total against 33.72 MiB of ZIPs and 28.21 MiB with per-file LZMA. With one group the compressed size is about 9.9 MiB for every block size; smaller blocks only add metadata. 64 MiB groups split the platform into two groups (+3.8%). Side-aligned cuts do not change the compressed size but let headered and headerless copies of a side deduplicate.

## Storage v4 in brief

- ROM data is split into fixed-size blocks deduplicated by SHA256 and packed in No-Intro family order into `lzma2-solid` groups; block size, group cap and dictionary are stored in each database's `meta`.
- Each block keeps its ID, size and SHA256; objects are assembled from blocks and exports check the full CRC32/MD5/SHA1/SHA256 set.
- Reads decode a group only up to the bytes they need; every block is still checked against its SHA256. The decode cache holds two groups; an object whose blocks lie in several groups (for example a multicart) is read group by group, decoding each group once; audits and bulk exports raise the cache to at most 2 GiB (and at most the decoded size of all groups) and decode whole groups, so no partial decoder keeps its dictionary window.
- NES keeps 16-byte headers separate from bodies, headered and headerless dumps share one body, and 8 KiB blocks follow header/PRG/CHR boundaries.
- Source ZIPs are kept as checksums and regenerated from TorrentZip plans. The seven databases hold 49,621 source ZIPs (No-Intro and RetroAchievements sets, all TorrentZips); 49,621 of them are checked to reproduce byte-for-byte (`v_file_checksums.exported_bytes_equal_source`).
- The format marker is `user_version=4`. The v3 engine refuses v4 files; the v4 engine reads v2, v3 and v4.

| Platform | Block | Group cap / dictionary | Groups | Unique block bytes → stored |
| --- | ---: | ---: | ---: | --- |
| NES | 8 KiB | 256 MiB | 9 | 1.35 GiB → 344.7 MiB |
| SNES | 64 KiB | 128 MiB | 57 | 5.43 GiB → 1.71 GiB |
| Mega Drive | 64 KiB | 256 MiB | 20 | 4.07 GiB → 940.5 MiB |
| Game Boy | 64 KiB | 256 MiB | 5 | 631.2 MiB → 139.5 MiB |
| Game Boy Color | 64 KiB | 256 MiB | 13 | 2.40 GiB → 469.2 MiB |
| Game Boy Advance | 1 MiB | 256 MiB | 123 | 27.43 GiB → 6.95 GiB |
| Famicom Disk System | 64 KiB | 128 MiB | 1 | 78.8 MiB → 10.2 MiB |

## Contents

Source collections (`source_collections`, registered per folder; ZIP members carry their ZIP's path):

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No-Intro (ZIPs / size) | 21,792 / 4.12 GiB | 4,898 / 3.99 GiB | 5,281 / 3.93 GiB | 2,671 / 295.8 MiB | 3,006 / 1.06 GiB | 3,946 / 14.42 GiB | 720 / 32.4 MiB |
| RetroAchievements sets (ZIPs / size) | 1,969 / 229.8 MiB | 1,876 / 2.09 GiB | 934 / 753.3 MiB | 720 / 105.3 MiB | 575 / 326.7 MiB | 1,206 / 6.78 GiB | 27 / 1.4 MiB |

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Local ZIPs | 23,761 | 6,774 | 6,215 | 3,391 | 3,581 | 5,152 | 747 |
| ROM records | 18,414 | 5,239 | 3,959 | 2,538 | 2,784 | 4,143 | 703 |
| Games / releases | 3,477 / 7,385 | 1,996 / 4,329 | 1,581 / 3,503 | 1,419 / 2,299 | 1,576 / 2,622 | 1,901 / 3,750 | 307 / 408 |
| Local ROMs in no DAT | 2,849 | 978 | 561 | 306 | 279 | 467 | 9 |

Every local Parent-Clone DAT version is imported and scanned; `dat_changes` diffs each older version against the newest and older DAT entries join the newest DAT's release through that diff. Platforms with several DAT formats (NES headered/headerless, FDS FDS/QD) diff each format against its own older versions; the primary format (first in the list) creates games and releases, and entries of other formats join the primary release of the same name, else the game of their parent.

The RetroAchievements-curated ROM folders (`/mnt/MyShare/RetroAchievements/RA - <platform>`) are imported like the No-Intro folders: ROMs already stored only gain file records and a source link; new ROMs (hacks, translations, homebrew, versions No-Intro does not list) are stored with block deduplication. A ROM outside every DAT joins the family of the stored ROMs it shares the most blocks with (`object_families.basis='shared_blocks'`; most hacks land next to their original), else a title family. The RA NES folder also holds FDS disk images; the NES import skips and reports them and the FDS database imports them.

- **NES** (2 DATs): 20260713-141345: 7,100/7,288; 20261002-002752: 7,095/7,390
- **SNES** (2 DATs): 20260710-203222: 4,255/4,318; 20261003-140326: 4,261/4,331
- **Mega Drive** (2 DATs): 20260714-063411: 3,398/3,486; 20260927-122056: 3,398/3,504
- **Game Boy** (4 DATs): 20260602-070215: 2,225/2,276; 20260707-013717: 2,226/2,284; 20260814-115131: 2,230/2,292; 20261001-130150: 2,232/2,299
- **Game Boy Color** (5 DATs): 20260602-074724: 2,502/2,604; 20260713-134329: 2,503/2,612; 20260715-062319: 2,503/2,612; 20260814-104253: 2,503/2,614; 20261001-131920: 2,503/2,622
- **Game Boy Advance** (4 DATs): 20260531-074517: 3,676/3,745; 20260707-143610: 3,676/3,748; 20260812-060017: 3,676/3,749; 20260929-130236: 3,676/3,750
- **Famicom Disk System** (3 DATs): 20260517-061737: 405/407; 20260617-195332: 295/296; 20260930-033941: 294/295

## No-Intro DB Export and Dump Log

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Snapshot | 20261002-002752 | 20261003-140326 | 20260927-122056 | 20261001-130150 | 20261001-131920 | 20260929-130236 | 20260930-033941 |
| Archives / file identities | 7,704 / 16,154 | 4,365 / 5,457 | 3,640 / 4,142 | 2,335 / 2,450 | 2,678 / 2,921 | 3,793 / 4,563 | 408 / 1,437 |
| Files with local payload | 14,885 | 4,276 | 3,537 | 2,248 | 2,514 | 3,713 | 701 |
| Documented hardware assertions | 6,412 | 5,399 | 2,017 | 2,810 | 2,830 | 3,188 | 8 |
| Dump Log: verified / trusted unverified / unverified | 2,794 / 3,814 / 1,028 | 1,871 / 1,708 / 736 | 868 / 2,085 / 615 | 719 / 1,118 / 490 | 448 / 1,521 / 703 | 770 / 1,703 / 1,307 | 7 / 262 / 136 |

## RetroAchievements

RA public-API snapshots (`API_GetGameList`) are stored without credentials. Each ROM's RA hash follows rcheevos (NES: body MD5 without the 16-byte header; FDS: drop a 16-byte fwNES header when present; SNES: drop a 512-byte copier header when size % 8192 = 512; other platforms: whole-file MD5). Matching is exact. Console IDs: NES 7, SNES 3, MD 1, GB 4, GBC 6, GBA 5, FDS 81.

`v_ra_collection` lists every ROM file of an RA set with its RA game, No-Intro DAT entries and release, with status `in_nointro_dat`, `ra_only` or `ra_hash_unknown` (hash absent from the latest RA snapshot). The `local_sources` column of `reports/ra-<platform>-games.csv` names the source collections holding each game's local ROMs; `reports/ra-<platform>-collection-unknown.csv` lists the files with unknown hashes and `reports/ra-<platform>-missing.csv` the RA games still without a local ROM (gap list).

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RA games with achievements | 1,123 | 1,185 | 613 | 505 | 419 | 775 | 38 |
| With a local ROM | 1,110 | 1,089 | 606 | 492 | 402 | 750 | 34 |
| DAT only (ROM missing) | 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| DB Export file only | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| No No-Intro counterpart (hacks) | 13 (9) | 96 (62) | 7 (5) | 13 (5) | 16 (3) | 23 (12) | 3 (1) |
| Local ROMs with achievements | 3,385 | 1,845 | 942 | 725 | 584 | 1,230 | 47 |

## Chinese names

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV rows / translated / unique Chinese names | 4,453 / 3,703 / 1,875 | 4,154 / 3,942 / 2,030 | 2,869 / 2,694 / 1,226 | 1,974 / 1,816 / 1,237 | 2,124 / 1,763 / 1,156 | 3,522 / 3,410 / 1,882 | 404 / 404 / 296 |
| Matched / ambiguous / unmatched | 4,420 / 22 / 11 | 4,099 / 10 / 45 | 2,715 / 58 / 96 | 1,956 / 0 / 18 | 1,945 / 7 / 172 | 3,444 / 26 / 52 | 403 / 1 / 0 |
| Releases with Chinese names (direct + inherited) | 3,698 + 389 | 3,864 + 73 | 2,550 + 117 | 1,803 + 59 | 1,590 + 110 | 3,315 + 47 | 402 + 4 |
| Local ROMs with Chinese names | 8,104 | 3,909 | 2,656 | 1,835 | 1,663 | 3,350 | 692 |

## Information layers

`v_information_sources` lists every information source with its version: existing (DAT versions, ROM files, source collections), extended (No-Intro DB/Dump Log snapshots, RA snapshots, name sources, documented hardware assertions) and future placeholders (Batocera/ScreenScraper fields, media slots, scrape records). Each source is imported as a versioned, idempotent snapshot; older snapshots are kept.

## Export and maintenance

`tools/export_set.py` combines DAT version (and the format: NES headered/headerless, FDS FDS/QD with `--dat-format`), set (all, parents, 1G1R with region priority and RA preference), RA filter and category, name include/exclude patterns, container (TorrentZip or plain ROM) and layout (flat, parent, RA category, region); every member is checked against all DAT hashes and `export-manifest.json` records the criteria and checksums. `tools/update_db.py` adds new DATs, DB/Dump Log snapshots, ROMs (No-Intro and RetroAchievements folders with `--discover`; files of another platform are skipped and reported), RA snapshots and name CSVs idempotently; new ROMs join their family's newest group when it has room. A new block whose SHA-256 is already stored is compared byte for byte when the stored block is loose or its group is already decoded; otherwise the SHA-256 identity stands (groups are verified when encoded and by every audit). The TorrentZip plan of a new ZIP is computed from the member bytes just imported. On NES this cut the import of the RA set (1,969 ZIPs) from 27 minutes to about 3.5 minutes, and DAT packaging no longer reads members back. `tools/retune_db.py` merges groups to a larger cap and `tools/migrate_v4.py` converts a v3 database; both keep block identities and run in one verified transaction.

The handling of the 2026-10-04 audit findings is recorded in [reports/audit-resolution-20261004.md](reports/audit-resolution-20261004.md). `engine.py` and the other `resources` entries are executable code; run them only from a database you built or a Release asset whose SHA256 you verified.

Populated-database audits: NES 19,069 objects / 9 groups / 25,368 archive plans; SNES 5,283 objects / 57 groups / 5,814 archive plans; Mega Drive 3,963 objects / 20 groups / 5,367 archive plans; Game Boy 2,546 objects / 5 groups / 2,776 archive plans; Game Boy Color 2,791 objects / 13 groups / 2,931 archive plans; Game Boy Advance 4,149 objects / 123 groups / 4,396 archive plans; Famicom Disk System 712 objects / 1 groups / 728 archive plans; all passed.
