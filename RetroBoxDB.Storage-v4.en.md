# RetroBoxDB storage v4: NES / SNES / Mega Drive / Game Boy / Game Boy Color / Game Boy Advance / Famicom Disk System / Satellaview / Master System / 32X / WonderSwan / WonderSwan Color / NeoGeo Pocket / NeoGeo Pocket Color / Pokémon Mini / Game Gear / PC Engine / SuperGrafx / MSX / MSX2 / Virtual Boy / Game & Watch / Super A'Can

[中文说明](RetroBoxDB.Storage-v4.zh-CN.md) | [Technical design](RetroBoxDB.Storage-v4.Technical-Design.en.md)

Each platform has one populated database (ROM data, kept locally) and one public Catalog (metadata only). All 23 use the same engine and the same storage format (v4); per-platform differences in block size, group cap, header parsing and import path are expressed by the database's `meta` values and platform adapter code. Original sizes include the No-Intro folders and the RetroAchievements-curated ROM folders (see Contents).

| Platform | Original size (ZIP / ROM files) | Populated database | Ratio (of ZIP / ROM) | Catalog | Single ROM (cold) | Single TorrentZip (cold) | Whole-set export by DAT |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| NES | 4.35 GiB / 11.18 GiB | 530.1 MiB | 11.9% / 4.6% | 145.5 MiB | 2.325 s | 1.983 s | 71.7 MiB/s (7,090 files) |
| SNES | 6.06 GiB / 10.90 GiB | 1.77 GiB | 29.1% / 16.2% | 54.1 MiB | 1.094 s | 1.397 s | 28.0 MiB/s (4,261 files) |
| Mega Drive | 4.66 GiB / 9.61 GiB | 999.0 MiB | 20.9% / 10.2% | 45.1 MiB | 1.734 s | 2.087 s | 18.8 MiB/s (3,398 files) |
| Game Boy | 401.1 MiB / 1.05 GiB | 178.2 MiB | 44.4% / 16.5% | 35.9 MiB | 1.594 s | 1.812 s | 41.0 MiB/s (2,232 files) |
| Game Boy Color | 1.38 GiB / 4.42 GiB | 522.6 MiB | 37.1% / 11.5% | 45.9 MiB | 1.719 s | 1.857 s | 56.2 MiB/s (2,503 files) |
| Game Boy Advance | 21.20 GiB / 44.24 GiB | 7.01 GiB | 33.1% / 15.9% | 58.2 MiB | 2.413 s | 2.682 s | 25.1 MiB/s (3,676 files) |
| Famicom Disk System | 35.2 MiB / 85.7 MiB | 22.1 MiB | 62.7% / 25.8% | 10.3 MiB | 0.364 s | 0.334 s | 30.4 MiB/s (405 files) |
| Satellaview | 324.1 MiB / 703.6 MiB | 116.1 MiB | 35.8% / 16.5% | 10.7 MiB | 2.78 s | 2.613 s | 61.6 MiB/s (561 files) |
| Master System | 177.4 MiB / 392.5 MiB | 84.9 MiB | 47.9% / 21.6% | 19.0 MiB | 1.783 s | 1.799 s | 43.9 MiB/s (1,189 files) |
| 32X | 593.1 MiB / 1.09 GiB | 87.9 MiB | 14.8% / 7.8% | 3.9 MiB | 1.524 s | 1.707 s | 69.9 MiB/s (219 files) |
| WonderSwan | 150.5 MiB / 383.0 MiB | 81.4 MiB | 54.1% / 21.3% | 4.0 MiB | 2.225 s | 2.433 s | 53.2 MiB/s (257 files) |
| WonderSwan Color | 246.6 MiB / 659.1 MiB | 126.7 MiB | 51.4% / 19.2% | 4.0 MiB | 1.226 s | 1.398 s | 54.2 MiB/s (253 files) |
| NeoGeo Pocket | 5.3 MiB / 13.7 MiB | 6.3 MiB | 120.3% / 46.2% | 1.8 MiB | 0.091 s | 0.186 s | 29.5 MiB/s (13 files) |
| NeoGeo Pocket Color | 93.0 MiB / 261.8 MiB | 38.2 MiB | 41.1% / 14.6% | 3.7 MiB | 0.943 s | 1.184 s | 52.5 MiB/s (128 files) |
| Pokémon Mini | 8.9 MiB / 35.9 MiB | 5.1 MiB | 57.3% / 14.2% | 2.2 MiB | 0.074 s | 0.118 s | 47.6 MiB/s (46 files) |
| Game Gear | 254.2 MiB / 501.3 MiB | 80.0 MiB | 31.5% / 16.0% | 13.7 MiB | 1.913 s | 1.784 s | 47.5 MiB/s (905 files) |
| PC Engine | 172.7 MiB / 334.9 MiB | 71.7 MiB | 41.5% / 21.4% | 6.5 MiB | 1.798 s | 1.8 s | 39.3 MiB/s (509 files) |
| SuperGrafx | 6.6 MiB / 11.1 MiB | 5.5 MiB | 83.4% / 49.4% | 1.9 MiB | 0.084 s | 0.122 s | 14.1 MiB/s (6 files) |
| MSX | 24.4 MiB / 50.3 MiB | 22.2 MiB | 91.3% / 44.2% | 8.0 MiB | 0.311 s | 0.326 s | 27.0 MiB/s (952 files) |
| MSX2 | 50.6 MiB / 111.1 MiB | 30.5 MiB | 60.2% / 27.4% | 3.5 MiB | 0.399 s | 0.473 s | 30.7 MiB/s (201 files) |
| Virtual Boy | 76.4 MiB / 315.1 MiB | 26.5 MiB | 34.6% / 8.4% | 2.7 MiB | 0.717 s | 0.99 s | 51.1 MiB/s (78 files) |
| Game & Watch | 0.1 MiB / 0.2 MiB | 3.5 MiB | 2356.2% / 2004.3% | 2.1 MiB | 0.01 s | 0.011 s | 1.1 MiB/s (52 files) |
| Super A'Can | 11.7 MiB / 22.5 MiB | 12.5 MiB | 106.8% / 55.6% | 1.7 MiB | 0.252 s | 0.412 s | 20.0 MiB/s (10 files) |

Catalogs are fresh SQLite files with empty `compression_groups`, `chunks` and `object_chunks` tables: no ROM data, original DAT/DB/Dump Log payloads or compressed data. Export performance was measured on this machine (Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz, Python 3.14) while idle, with all checks included:

- **Single file (cold)**: 100 random ROMs and 50 random TorrentZips (fixed seed), engine caches cleared before each export. The time is dominated by decoding the solid group up to the file; larger groups take longer, which is the cost of choosing them for compression.
- **Whole-set export by DAT**: `tools/export_set.py` exports every game of the newest DAT as plain ROMs (NES: headered DAT; FDS: FDS format), reading in storage order with the bulk cache (up to 2 GiB of whole decoded groups), checking each file against all DAT hashes, hashing and writing in a thread pool and syncing once at the end; process start and selection are included. A single-file export (`engine.py export`) fsyncs each file.

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
| Satellaview (whole set) | 324.1 | — | 32 KiB / 256 MiB | 103.8 |
| Master System (whole set) | 177.4 | — | 128 KiB / 256 MiB | 62.6 |
| 32X (whole set) | 593.1 | — | 32 KiB / 256 MiB | 83.9 |
| WonderSwan (whole set) | 150.5 | — | 64 KiB / 256 MiB | 76.0 |
| WonderSwan Color (whole set) | 246.6 | — | 64 KiB / 128 MiB | 122.1 |
| NeoGeo Pocket (whole set) | 5.3 | — | 128 KiB / 32 MiB | 3.1 |
| NeoGeo Pocket Color (whole set) | 93.0 | — | 128 KiB / 256 MiB | 33.0 |
| Pokémon Mini (whole set) | 8.9 | — | 256 KiB / 32 MiB | 1.5 |
| Game Gear (whole set) | 254.2 | — | 32 KiB / 256 MiB | 63.8 |
| PC Engine (whole set) | 172.7 | — | 128 KiB / 256 MiB | 62.7 |
| SuperGrafx (whole set) | 6.6 | — | 128 KiB / 32 MiB | 2.2 |
| MSX (whole set) | 24.4 | — | 64 KiB / 64 MiB | 12.5 |
| MSX2 (whole set) | 50.6 | — | 128 KiB / 128 MiB | 24.5 |
| Virtual Boy (whole set) | 76.5 | — | 256 KiB / 128 MiB | 21.9 |
| Game & Watch (whole set) | 0.1 | — | 4 KiB / 32 MiB | 0.1 |
| Super A'Can (whole set) | 11.7 | — | 64 KiB / 32 MiB | 9.4 |

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
| Satellaview | whole collection with 16 KiB blocks, 256 MiB unique | −1.28% | −3.33% | −6.32% | — | 256 MiB | — |

Base group: 32 MiB for NES, SNES, MD, GB, GBC, FDS and Satellaview; 128 MiB for GBA. FDS and Satellaview were built directly with the chosen parameters, so they have no retune result.

Other measurements:

- **BCJ filters**: xz's ARM and ARM-Thumb filters only apply to GBA. On six real 128 MiB groups ARM-Thumb made the output 2.35% larger and ARM 0.73% larger, so neither is used. The other CPUs (6502, 65816, 68000, SM83) have no xz filter.
- **LZMA parameters**: lc/lp/pb variations changed sizes by less than 0.2%; lc3/lp0/pb0, BT4 and nice_len 273 are used throughout.
- **zstd**: parent-dictionary deltas were 8–16% larger than the LZMA layout, and the standard-library `compression.zstd` module requires Python 3.14 while the tools target the Python 3.10+ standard library; not used.
- **NES**: migrated to v4 with 8 KiB blocks (cut at header/trainer/PRG/CHR boundaries) and 256 MiB groups. On the full database the v3 payload (489 lzma2-4m groups plus XOR-delta loose blocks, 382,082,581 bytes) became 344,223,238 bytes (−9.91%); the real-data curve was 64 MiB −1.40%, 128 MiB −2.59%, 256 MiB −5.66% against 32 MiB groups, smaller caps stay more than 0.5% above the 256 MiB result, so 256 MiB is used.
- **FDS**: 64 KiB blocks (one block per side) in a single 128 MiB group: 10.055 MiB in total against 33.72 MiB of ZIPs and 28.21 MiB with per-file LZMA. With one group the compressed size is about 9.9 MiB for every block size; smaller blocks only add metadata. 64 MiB groups split the platform into two groups (+3.8%). Side-aligned cuts do not change the compressed size but let headered and headerless copies of a side deduplicate.
- **Satellaview**: 32 KiB blocks and 256 MiB groups: 103.779 MiB in total against 324.15 MiB of ZIPs and 240.46 MiB with per-file LZMA. Block deduplication removes most of the data (BS memory packs share padding and repeated broadcasts): 703.62 MiB of files become 278.78 MiB of unique 32 KiB blocks. At 256 MiB groups 8, 16, 32 and 64 KiB blocks give 106.862, 103.935, 103.779 and 104.615 MiB; with 16 KiB blocks 128 MiB groups are 3.18% larger than 256 MiB groups, so the 256 MiB ceiling is used.
- **Master System, 32X, WonderSwan, WonderSwan Color, NeoGeo Pocket, NeoGeo Pocket Color, Pokémon Mini, and the third batch Game Gear, PC Engine, SuperGrafx, MSX, MSX2, Virtual Boy, Game & Watch, Super A'Can** (added 2026-10-06): each whole local collection (No-Intro folders plus the platform's files in its RA folder) was measured for block sizes (normally 8–256 KiB; from 1 KiB on tiny platforms, extended to 512 KiB–1 MiB while the totals still fell) × 32–256 MiB groups (`assessment/tools/storage_eval_platform.py`, `assessment/data/storage-experiment-<platform>.json`; caps above the platform's unique data are measured once). Rule: the smallest total; among the configurations within 0.5% of it, the smallest block, then the smallest group (finer deduplication for later revisions, less decoding per read). Master System 128 KiB / 256 MiB: 62.61 MiB (ZIPs 177.42 MiB, per-file LZMA 105.80 MiB; 0.17% above the smallest); 32X 32 KiB / 256 MiB: 83.85 MiB (ZIPs 593.11 MiB, per-file LZMA 281.98 MiB; 0.32% above the smallest); WonderSwan 64 KiB / 256 MiB: 75.97 MiB (ZIPs 150.46 MiB, per-file LZMA 100.84 MiB; 0.45% above the smallest); WonderSwan Color 64 KiB / 128 MiB: 122.06 MiB (ZIPs 246.58 MiB, per-file LZMA 176.38 MiB; 0.23% above the smallest); NeoGeo Pocket 128 KiB / 32 MiB: 3.08 MiB (ZIPs 5.26 MiB, per-file LZMA 3.72 MiB; 0.36% above the smallest); NeoGeo Pocket Color 128 KiB / 256 MiB: 33.02 MiB (ZIPs 92.97 MiB, per-file LZMA 64.83 MiB; 0.25% above the smallest); Pokémon Mini 256 KiB / 32 MiB: 1.54 MiB (ZIPs 8.91 MiB, per-file LZMA 5.40 MiB; 0.33% above the smallest); Game Gear 32 KiB / 256 MiB: 63.83 MiB (ZIPs 254.16 MiB, per-file LZMA 139.89 MiB; the smallest); PC Engine 128 KiB / 256 MiB: 62.67 MiB (ZIPs 172.69 MiB, per-file LZMA 100.74 MiB; 0.23% above the smallest); SuperGrafx 128 KiB / 32 MiB: 2.20 MiB (ZIPs 6.59 MiB, per-file LZMA 2.77 MiB; 0.18% above the smallest); MSX 64 KiB / 64 MiB: 12.50 MiB (ZIPs 24.38 MiB, per-file LZMA 20.15 MiB; 0.21% above the smallest); MSX2 128 KiB / 128 MiB: 24.50 MiB (ZIPs 50.62 MiB, per-file LZMA 40.50 MiB; 0.22% above the smallest); Virtual Boy 256 KiB / 128 MiB: 21.87 MiB (ZIPs 76.45 MiB, per-file LZMA 33.69 MiB; 0.16% above the smallest); Game & Watch 4 KiB / 32 MiB: 0.13 MiB (ZIPs 0.15 MiB, per-file LZMA 0.14 MiB; the smallest); Super A'Can 64 KiB / 32 MiB: 9.44 MiB (ZIPs 11.72 MiB, per-file LZMA 9.67 MiB; 0.38% above the smallest).

## Storage v4 in brief

- ROM data is split into fixed-size blocks deduplicated by SHA256 and packed in No-Intro family order into `lzma2-solid` groups; block size, group cap and dictionary are stored in each database's `meta`.
- Each block keeps its ID, size and SHA256; objects are assembled from blocks and exports check the full CRC32/MD5/SHA1/SHA256 set.
- Reads decode a group only up to the bytes they need; every block is still checked against its SHA256. The decode cache holds two groups; an object whose blocks lie in several groups (for example a multicart) is read group by group, decoding each group once; audits and bulk exports raise the cache to at most 2 GiB (and at most the decoded size of all groups) and decode whole groups, so no partial decoder keeps its dictionary window.
- NES keeps 16-byte headers separate from bodies, headered and headerless dumps share one body, and 8 KiB blocks follow header/PRG/CHR boundaries.
- Source ZIPs are kept as checksums and regenerated from TorrentZip plans. The 23 databases hold 57,437 source ZIPs (No-Intro and RetroAchievements sets, all TorrentZips); 57,437 of them are checked to reproduce byte-for-byte (`v_file_checksums.exported_bytes_equal_source`).
- The format marker is `user_version=4`. The v3 engine refuses v4 files; the v4 engine reads v2, v3 and v4.

| Platform | Block | Group cap / dictionary | Groups | Unique block bytes → stored |
| --- | ---: | ---: | ---: | --- |
| NES | 8 KiB | 256 MiB | 9 | 1.35 GiB → 344.7 MiB |
| SNES | 64 KiB | 128 MiB | 57 | 5.38 GiB → 1.70 GiB |
| Mega Drive | 64 KiB | 256 MiB | 20 | 4.07 GiB → 940.5 MiB |
| Game Boy | 64 KiB | 256 MiB | 5 | 631.2 MiB → 139.5 MiB |
| Game Boy Color | 64 KiB | 256 MiB | 13 | 2.40 GiB → 469.2 MiB |
| Game Boy Advance | 1 MiB | 256 MiB | 123 | 27.43 GiB → 6.95 GiB |
| Famicom Disk System | 64 KiB | 128 MiB | 1 | 78.8 MiB → 10.2 MiB |
| Satellaview | 32 KiB | 256 MiB | 2 | 280.3 MiB → 102.0 MiB |
| Master System | 128 KiB | 256 MiB | 2 | 241.8 MiB → 64.2 MiB |
| 32X | 32 KiB | 256 MiB | 2 | 346.1 MiB → 80.4 MiB |
| WonderSwan | 64 KiB | 256 MiB | 1 | 208.5 MiB → 75.5 MiB |
| WonderSwan Color | 64 KiB | 128 MiB | 4 | 359.0 MiB → 120.3 MiB |
| NeoGeo Pocket | 128 KiB | 32 MiB | 1 | 10.7 MiB → 3.1 MiB |
| NeoGeo Pocket Color | 128 KiB | 256 MiB | 2 | 158.2 MiB → 32.9 MiB |
| Pokémon Mini | 256 KiB | 32 MiB | 1 | 23.1 MiB → 1.5 MiB |
| Game Gear | 32 KiB | 256 MiB | 2 | 240.8 MiB → 63.5 MiB |
| PC Engine | 128 KiB | 256 MiB | 2 | 193.5 MiB → 63.6 MiB |
| SuperGrafx | 128 KiB | 32 MiB | 1 | 4.3 MiB → 2.2 MiB |
| MSX | 64 KiB | 64 MiB | 2 | 41.7 MiB → 12.6 MiB |
| MSX2 | 128 KiB | 128 MiB | 2 | 85.3 MiB → 25.5 MiB |
| Virtual Boy | 256 KiB | 128 MiB | 2 | 127.1 MiB → 22.4 MiB |
| Game & Watch | 4 KiB | 32 MiB | 1 | 0.3 MiB → 0.1 MiB |
| Super A'Can | 64 KiB | 32 MiB | 1 | 20.8 MiB → 9.4 MiB |

## Contents

Source collections (`source_collections`, registered per folder; ZIP members carry their ZIP's path):

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No-Intro (ZIPs / size) | 21,792 / 4.12 GiB | 4,898 / 3.99 GiB | 5,281 / 3.93 GiB | 2,671 / 295.8 MiB | 3,006 / 1.06 GiB | 3,946 / 14.42 GiB | 720 / 32.4 MiB | 699 / 302.4 MiB |
| RetroAchievements sets (ZIPs / size) | 1,973 / 230.3 MiB | 1,836 / 2.07 GiB | 934 / 753.3 MiB | 720 / 105.3 MiB | 575 / 326.7 MiB | 1,206 / 6.78 GiB | 53 / 2.8 MiB | 40 / 21.7 MiB |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No-Intro (ZIPs / size) | 1,674 / 150.9 MiB | 375 / 528.8 MiB | 258 / 121.5 MiB | 265 / 195.6 MiB | 13 / 4.4 MiB | 130 / 62.0 MiB | 50 / 6.2 MiB | 1,319 / 227.0 MiB |
| RetroAchievements sets (ZIPs / size) | 201 / 26.5 MiB | 39 / 64.3 MiB | 29 / 29.0 MiB | 45 / 51.0 MiB | 1 / 0.8 MiB | 53 / 31.0 MiB | 51 / 2.7 MiB | 140 / 27.2 MiB |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No-Intro (ZIPs / size) | 651 / 133.7 MiB | 10 / 4.2 MiB | 959 / 21.5 MiB | 204 / 23.8 MiB | 127 / 60.8 MiB | 54 / 0.1 MiB | 12 / 11.7 MiB |
| RetroAchievements sets (ZIPs / size) | 174 / 39.0 MiB | 4 / 2.4 MiB | 111 / 2.9 MiB | 89 / 26.8 MiB | 49 / 15.6 MiB | — | — |

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Local ZIPs | 23,765 | 6,734 | 6,215 | 3,391 | 3,581 | 5,152 | 773 | 739 |
| ROM records | 18,414 | 5,239 | 3,959 | 2,538 | 2,784 | 4,143 | 703 | 602 |
| Games / releases | 3,477 / 7,385 | 1,996 / 4,329 | 1,581 / 3,503 | 1,419 / 2,299 | 1,576 / 2,622 | 1,901 / 3,750 | 307 / 408 | 606 / 609 |
| Local ROMs in no DAT | 2,849 | 978 | 561 | 306 | 279 | 467 | 9 | 34 |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Local ZIPs | 1,875 | 414 | 287 | 310 | 14 | 183 | 101 | 1,459 |
| ROM records | 1,230 | 228 | 265 | 268 | 13 | 160 | 83 | 927 |
| Games / releases | 774 / 1,238 | 61 / 227 | 228 / 257 | 217 / 253 | 12 / 13 | 76 / 128 | 22 / 46 | 474 / 928 |
| Local ROMs in no DAT | 39 | 9 | 8 | 15 | 0 | 32 | 37 | 22 |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Local ZIPs | 825 | 14 | 1,070 | 293 | 176 | 54 | 12 |
| ROM records | 545 | 7 | 1,008 | 295 | 97 | 53 | 13 |
| Games / releases | 363 / 509 | 6 / 6 | 622 / 952 | 157 / 201 | 53 / 80 | 51 / 53 | 12 / 12 |
| Local ROMs in no DAT | 36 | 1 | 56 | 94 | 19 | 0 | 0 |

Every local Parent-Clone DAT version is imported and scanned; `dat_changes` diffs each older version against the newest and older DAT entries join the newest DAT's release through that diff. Platforms with several DAT formats (NES headered/headerless, FDS FDS/QD) diff each format against its own older versions; the primary format (first in the list) creates games and releases, and entries of other formats join the primary release of the same name, else the game of their parent.

The RetroAchievements-curated ROM folders (`/mnt/MyShare/RetroAchievements/RA - <platform>`) are imported like the No-Intro folders: ROMs already stored only gain file records and a source link; new ROMs (hacks, translations, homebrew, versions No-Intro does not list) are stored with block deduplication. A ROM outside every DAT joins the family of the stored ROMs it shares the most blocks with (`object_families.basis='shared_blocks'`; most hacks land next to their original), else a title family. The RA NES folder also holds FDS disk images; the NES import skips and reports them and the FDS database imports them. Satellaview (BS-X, `.bs`) files in the RA SNES folder belong to a separate platform: the SNES import skips and reports them and the Satellaview database imports them. `.nes` files in the RA FDS folder (FDS cartridge conversions, pirate carts) belong to NES and are skipped by the FDS import (the NES database holds them). RA has one set each for WonderSwan + WonderSwan Color and for NeoGeo Pocket + NeoGeo Pocket Color: both databases import that folder and keep their own extension (`.ws` / `.wsc`, `.ngp` / `.ngc`); the other platform's files are skipped and reported. The RA TurboGrafx-16 folder holds PC Engine (`.pce`) and SuperGrafx (`.sgx`) files and is split the same way. The RA MSX folder mixes MSX and MSX2 games as well as disks, tapes and cartridges: it is split platform first, medium second (`tools/msx_route.py`); each ZIP goes to exactly one database by, in order, a member SHA1 in the MSX2 / MSX DATs, an `(MSX2` tag or `.mx2` member, the reviewed list `data/msx-routing.csv` (reference lists, public references such as MSX software databases and contest pages, manual knowledge; reviewed decisions override the heuristics that follow), a base title that only one platform's DATs name, and at least 10% of 8 KiB blocks shared with one platform's DAT ROMs (hacks, translations); anything still undecided goes to MSX (MSX2 machines run MSX software) flagged as unconfirmed. The basis is stored in `rom_annotations` (`kind='platform'`) and shown in `v_msx_headers.platform_evidence`; files routed to the other database are reported. Game & Watch and Super A'Can have no RA folder.

- **NES** (2 DATs): 20260713-141345: 7,100/7,288; 20261002-002752: 7,095/7,390
- **SNES** (2 DATs): 20260710-203222: 4,255/4,318; 20261003-140326: 4,261/4,331
- **Mega Drive** (2 DATs): 20260714-063411: 3,398/3,486; 20260927-122056: 3,398/3,504
- **Game Boy** (4 DATs): 20260602-070215: 2,225/2,276; 20260707-013717: 2,226/2,284; 20260814-115131: 2,230/2,292; 20261001-130150: 2,232/2,299
- **Game Boy Color** (5 DATs): 20260602-074724: 2,502/2,604; 20260713-134329: 2,503/2,612; 20260715-062319: 2,503/2,612; 20260814-104253: 2,503/2,614; 20261001-131920: 2,503/2,622
- **Game Boy Advance** (4 DATs): 20260531-074517: 3,676/3,745; 20260707-143610: 3,676/3,748; 20260812-060017: 3,676/3,749; 20260929-130236: 3,676/3,750
- **Famicom Disk System** (3 DATs): 20260517-061737: 405/407; 20260617-195332: 295/296; 20260930-033941: 294/295
- **Satellaview** (3 DATs): 20260619-093425: 569/603; 20260814-103513: 566/604; 20260919-025009: 562/610
- **Master System** (4 DATs): 20260527-203639: 1,191/1,215; 20260706-223420: 1,191/1,216; 20260809-210908: 1,191/1,240; 20260918-065535: 1,189/1,238
- **32X** (1 DATs): 20260317-140429: 219/227
- **WonderSwan** (1 DATs): 20260525-011654: 257/257
- **WonderSwan Color** (1 DATs): 20260525-011610: 253/253
- **NeoGeo Pocket** (1 DATs): 20250904-215533: 13/13
- **NeoGeo Pocket Color** (3 DATs): 20240506-123728: 128/128; 20260626-085623: 128/128; 20260919-122044: 128/128
- **Pokémon Mini** (1 DATs): 20260529-125415: 46/46
- **Game Gear** (3 DATs): 20260706-223743: 905/927; 20260725-204513: 905/928; 20260822-061808: 905/928
- **PC Engine** (1 DATs): 20260124-120557: 509/509
- **SuperGrafx** (1 DATs): 20250913-112105: 6/6
- **MSX** (1 DATs): 20260618-055428: 952/952
- **MSX2** (1 DATs): 20260124-112728: 201/201
- **Virtual Boy** (3 DATs): 20260428-015207: 78/78; 20260804-192036: 78/80; 20260805-170231: 78/80
- **Game & Watch** (2 DATs): 20260512-134045: 53/54; 20260512-134245: 53/54
- **Super A'Can** (2 DATs): 20240927-111000: 13/13; 20260913-064553: 10/12

## No-Intro DB Export and Dump Log

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Snapshot | 20261002-002752 | 20261003-140326 | 20260927-122056 | 20261001-130150 | 20261001-131920 | 20260929-130236 | 20260930-033941 | 20260919-025009 |
| Archives / file identities | 7,704 / 16,154 | 4,365 / 5,457 | 3,640 / 4,142 | 2,335 / 2,450 | 2,678 / 2,921 | 3,793 / 4,563 | 408 / 1,437 | 615 / 766 |
| Files with local payload | 14,885 | 4,276 | 3,537 | 2,248 | 2,514 | 3,713 | 701 | 590 |
| Documented hardware assertions | 6,412 | 5,399 | 2,017 | 2,810 | 2,830 | 3,188 | 8 | 6 |
| Dump Log: verified / trusted unverified / unverified | 2,794 / 3,814 / 1,028 | 1,871 / 1,708 / 736 | 868 / 2,085 / 615 | 719 / 1,118 / 490 | 448 / 1,521 / 703 | 770 / 1,703 / 1,307 | 7 / 262 / 136 | 7 / 445 / 137 |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Snapshot | 20260918-065535 | 20260317-140429 | 20260525-011654 | 20260525-011610 | 20250904-215533 | 20260919-122044 | 20260529-125415 | 20260822-061808 |
| Archives / file identities | 1,245 / 1,279 | 228 / 239 | 257 / 278 | 254 / 263 | 13 / 22 | 128 / 215 | 46 / 49 | 928 / 951 |
| Files with local payload | 1,192 | 221 | 257 | 253 | 13 | 129 | 49 | 905 |
| Documented hardware assertions | 367 | 35 | 318 | 263 | 11 | 215 | 20 | 354 |
| Dump Log: verified / trusted unverified / unverified | 435 / 791 / 15 | 23 / 175 / 29 | 58 / 199 / 0 | 53 / 191 / 9 | 8 / 4 / 1 | 81 / 35 / 12 | 9 / 9 / 28 | 443 / 473 / 11 |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Snapshot | 20260124-120557 | 20250913-112105 | 20260618-055428 | 20260124-112728 | 20260804-192036 | 20260512-134045 | 20260913-064553 |
| Archives / file identities | 510 / 714 | 7 / 7 | 952 / 961 | 201 / 204 | 81 / 81 | 53 / 54 | 12 / 15 |
| Files with local payload | 510 | 6 | 952 | 201 | 78 | 53 | 13 |
| Documented hardware assertions | 208 | 0 | 11 | 2 | 76 | 17 | 12 |
| Dump Log: verified / trusted unverified / unverified | 292 / 162 / 56 | 0 / 5 / 1 | 0 / 47 / 905 | 0 / 12 / 189 | 21 / 58 / 1 | 2 / 51 / 0 | 0 / 0 / 12 |

## RetroAchievements

RA public-API snapshots (`API_GetGameList`) are stored without credentials. Each ROM's RA hash follows rcheevos (NES: body MD5 without the 16-byte header; FDS: drop a 16-byte fwNES header when present; SNES: drop a 512-byte copier header when size % 8192 = 512; PC Engine / SuperGrafx: drop a 512-byte copier header when size % 131072 = 512; other platforms: whole-file MD5). Matching is exact. Console IDs: NES 7, SNES 3, MD 1, GB 4, GBC 6, GBA 5, FDS 81, Master System 11, 32X 10, WonderSwan (both) 53, NeoGeo Pocket (both) 14, Pokémon Mini 24, Game Gear 15, PC Engine and SuperGrafx (both) 8, MSX and MSX2 (both) 29, Virtual Boy 28; Game & Watch and Super A'Can have no RA console and get an empty report; RA has no Satellaview console, its games are listed under SNES (3) and hashed with the SNES method.

Cross-database links: some RA games have their ROM in a sibling platform's database (FDS-console cartridge conversions in NES, SNES-console BS games in Satellaview). The report looks these hashes up in the sibling databases (NES<->FDS, SNES<->Satellaview, WonderSwan<->WonderSwan Color, NeoGeo Pocket<->NeoGeo Pocket Color, PC Engine<->SuperGrafx, MSX<->MSX2) and marks them `local_other_platform` with the database in `other_platform_db`; they are not counted as gaps. Because Satellaview shares the SNES console, and WonderSwan / WonderSwan Color NeoGeo Pocket / NeoGeo Pocket Color, PC Engine / SuperGrafx and MSX / MSX2 each share one console, those reports cover only RA games tied to their own ROMs, DAT entries or DB Export files.

`v_ra_collection` lists every ROM file of an RA set with its RA game, No-Intro DAT entries and release, with status `in_nointro_dat`, `ra_only` or `ra_hash_unknown` (hash absent from the latest RA snapshot). The `local_sources` column of `reports/ra-<platform>-games.csv` names the source collections holding each game's local ROMs; `reports/ra-<platform>-collection-unknown.csv` lists the files with unknown hashes and `reports/ra-<platform>-missing.csv` the RA games still without a local ROM (gap list).

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RA games with achievements | 1,123 | 1,185 | 613 | 505 | 419 | 775 | 38 | 13 |
| With a local ROM | 1,110 | 1,089 | 606 | 492 | 402 | 750 | 34 | 13 |
| ROM in a sibling database | 0 | 6 | 0 | 0 | 0 | 0 | 1 | 0 |
| DAT only (ROM missing) | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| DB Export file only | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| No No-Intro counterpart (hacks) | 13 (9) | 90 (62) | 7 (5) | 13 (5) | 16 (3) | 23 (12) | 2 (1) | 0 (0) |
| Local ROMs with achievements | 3,385 | 1,845 | 942 | 725 | 584 | 1,230 | 47 | 44 |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RA games with achievements | 183 | 36 | 23 | 33 | 1 | 41 | 40 | 167 |
| With a local ROM | 181 | 35 | 23 | 33 | 1 | 41 | 39 | 165 |
| ROM in a sibling database | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DAT only (ROM missing) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DB Export file only | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| No No-Intro counterpart (hacks) | 2 (2) | 1 (0) | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 1 (0) | 2 (1) |
| Local ROMs with achievements | 235 | 39 | 30 | 44 | 1 | 54 | 51 | 192 |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RA games with achievements | 138 | 4 | 92 | 45 | 43 | 0 | 0 |
| With a local ROM | 138 | 4 | 92 | 45 | 41 | 0 | 0 |
| ROM in a sibling database | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DAT only (ROM missing) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DB Export file only | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| No No-Intro counterpart (hacks) | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 2 (0) | 0 (0) | 0 (0) |
| Local ROMs with achievements | 180 | 4 | 115 | 116 | 51 | 0 | 0 |

## Chinese names

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV rows / translated / unique Chinese names | 4,453 / 3,703 / 1,875 | 4,154 / 3,942 / 2,030 | 2,869 / 2,694 / 1,226 | 1,974 / 1,816 / 1,237 | 2,124 / 1,763 / 1,156 | 3,522 / 3,410 / 1,882 | 404 / 404 / 296 | 0 / 0 / 0 |
| Matched / ambiguous / unmatched | 4,420 / 22 / 11 | 4,099 / 10 / 45 | 2,715 / 58 / 96 | 1,956 / 0 / 18 | 1,945 / 7 / 172 | 3,444 / 26 / 52 | 403 / 1 / 0 | 0 / 0 / 0 |
| Releases with Chinese names (direct + inherited) | 3,698 + 389 | 3,864 + 73 | 2,550 + 117 | 1,803 + 59 | 1,590 + 110 | 3,315 + 47 | 402 + 4 | 0 + 0 |
| Local ROMs with Chinese names | 8,104 | 3,909 | 2,656 | 1,835 | 1,663 | 3,350 | 692 | 0 |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV rows / translated / unique Chinese names | 699 / 542 / 342 | 213 / 213 / 54 | 264 / 148 / 118 | 242 / 115 / 97 | 10 / 10 / 9 | 132 / 132 / 83 | 44 / 43 / 17 | 825 / 825 / 411 |
| Matched / ambiguous / unmatched | 697 / 1 / 1 | 204 / 6 / 3 | 257 / 0 / 7 | 242 / 0 / 0 | 10 / 0 / 0 | 128 / 0 / 4 | 44 / 0 / 0 | 818 / 5 / 2 |
| Releases with Chinese names (direct + inherited) | 542 + 30 | 203 + 1 | 141 + 0 | 115 + 0 | 10 + 0 | 128 + 0 | 43 + 0 | 824 + 1 |
| Local ROMs with Chinese names | 563 | 203 | 141 | 115 | 10 | 128 | 43 | 823 |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV rows / translated / unique Chinese names | 468 / 468 / 339 | 5 / 5 / 5 | 944 / 907 / 577 | 198 / 198 / 154 | 33 / 33 / 23 | 53 / 53 / 46 | 0 / 0 / 0 |
| Matched / ambiguous / unmatched | 460 / 1 / 7 | 5 / 0 / 0 | 944 / 0 / 0 | 198 / 0 / 0 | 32 / 0 / 1 | 53 / 0 / 0 | 0 / 0 / 0 |
| Releases with Chinese names (direct + inherited) | 460 + 0 | 5 + 0 | 907 + 0 | 198 + 0 | 32 + 0 | 53 + 0 | 0 + 0 |
| Local ROMs with Chinese names | 460 | 5 | 907 | 198 | 32 | 53 | 0 |

Satellaview has no Chinese name source yet, so its column is 0; once a name CSV (`Name EN,Name CN` or `EN Name,CN Name`) exists, place it at `data/Nintendo - Satellaview.csv` and run `tools/update_db.py RetroBoxDB.Satellaview.sqlite --names "data/Nintendo - Satellaview.csv"`.

## Information layers

`v_information_sources` lists every information source with its version: existing (DAT versions, ROM files, source collections), extended (No-Intro DB/Dump Log snapshots, RA snapshots, name sources, documented hardware assertions), provider tables (filled only in local databases; empty in the Catalog) and placeholders (Batocera media slots). Each source is imported as a versioned, idempotent snapshot; older snapshots are kept.

## Export and maintenance

`tools/export_set.py` combines DAT version (and the format: NES headered/headerless, FDS FDS/QD with `--dat-format`), set (all, parents, 1G1R with region priority and RA preference), RA filter and category, name include/exclude patterns, container (TorrentZip or plain ROM) and layout (flat, parent, RA category, region); every member is checked against all DAT hashes and `export-manifest.json` records the criteria and checksums. `tools/update_db.py` adds new DATs, DB/Dump Log snapshots, ROMs (No-Intro and RetroAchievements folders with `--discover`; files of another platform are skipped and reported), RA snapshots and name CSVs idempotently; new ROMs join their family's newest group when it has room. A new block whose SHA-256 is already stored is compared byte for byte when the stored block is loose or its group is already decoded; otherwise the SHA-256 identity stands (groups are verified when encoded and by every audit). The TorrentZip plan of a new ZIP is computed from the member bytes just imported. On NES this cut the import of the RA set (1,969 ZIPs) from 27 minutes to about 3.5 minutes, and DAT packaging no longer reads members back. `tools/retune_db.py` merges groups to a larger cap and `tools/migrate_v4.py` converts a v3 database; both keep block identities and run in one verified transaction.

The handling of the 2026-10-04 audit findings is recorded in [reports/audit-resolution-20261004.md](reports/audit-resolution-20261004.md). `engine.py` and the other `resources` entries are executable code; run them only from a database you built or a Release asset whose SHA256 you verified.

Populated-database audits: NES 19,069 objects / 9 groups / 25,368 archive plans; SNES 5,243 objects / 57 groups / 5,774 archive plans; Mega Drive 3,963 objects / 20 groups / 5,367 archive plans; Game Boy 2,546 objects / 5 groups / 2,776 archive plans; Game Boy Color 2,791 objects / 13 groups / 2,931 archive plans; Game Boy Advance 4,149 objects / 123 groups / 4,396 archive plans; Famicom Disk System 712 objects / 1 groups / 728 archive plans; Satellaview 607 objects / 2 groups / 923 archive plans; Master System 1,236 objects / 2 groups / 1,523 archive plans; 32X 231 objects / 2 groups / 387 archive plans; WonderSwan 268 objects / 1 groups / 269 archive plans; WonderSwan Color 271 objects / 4 groups / 278 archive plans; NeoGeo Pocket 16 objects / 1 groups / 16 archive plans; NeoGeo Pocket Color 165 objects / 2 groups / 171 archive plans; Pokémon Mini 86 objects / 1 groups / 88 archive plans; Game Gear 934 objects / 2 groups / 1,306 archive plans; PC Engine 548 objects / 2 groups / 684 archive plans; SuperGrafx 10 objects / 1 groups / 14 archive plans; MSX 1,011 objects / 2 groups / 1,023 archive plans; MSX2 306 objects / 2 groups / 277 archive plans; Virtual Boy 102 objects / 2 groups / 113 archive plans; Game & Watch 57 objects / 1 groups / 58 archive plans; Super A'Can 17 objects / 1 groups / 16 archive plans; all passed.
