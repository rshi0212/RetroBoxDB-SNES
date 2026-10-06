# RetroBoxDB storage v4 — technical design

[English guide](RetroBoxDB.Storage-v4.en.md) · [中文说明](RetroBoxDB.Storage-v4.zh-CN.md) · [NES v3 design (history)](https://github.com/rshi0212/RetroBoxDB-NES/blob/main/RetroBoxDB.NES.Technical-Design.en.md)

23 platforms (NES, SNES, Mega Drive, Game Boy, Game Boy Color, Game Boy Advance, Famicom Disk System, Satellaview, Master System, 32X, WonderSwan, WonderSwan Color, NeoGeo Pocket, NeoGeo Pocket Color, Pokémon Mini, Game Gear, PC Engine, SuperGrafx, MSX, MSX2, Virtual Boy, Game & Watch, Super A'Can) each have one populated SQLite file and one payload-free Catalog. The application schema is the NES v3 schema (objects, files, ROMs, DAT sets, validations, archive plans, No-Intro DB/Dump Log, frontend placeholders, names) plus `tools/schema_v4.sql`. Tables of other platforms exist and stay empty so shared views and the single engine work everywhere. `platforms.id=1` holds the platform code.

## Storage evaluation

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

Rule: the smallest group cap whose compressed size is within 0.5% of the 256 MiB result. FDS: 64 KiB blocks (one block per side) in a single 128 MiB group: 10.055 MiB in total against 33.72 MiB of ZIPs and 28.21 MiB with per-file LZMA. With one group the compressed size is about 9.9 MiB for every block size; smaller blocks only add metadata. 64 MiB groups split the platform into two groups (+3.8%). Side-aligned cuts do not change the compressed size but let headered and headerless copies of a side deduplicate. Satellaview: 32 KiB blocks and 256 MiB groups: 103.779 MiB in total against 324.15 MiB of ZIPs and 240.46 MiB with per-file LZMA. Block deduplication removes most of the data (BS memory packs share padding and repeated broadcasts): 703.62 MiB of files become 278.78 MiB of unique 32 KiB blocks. At 256 MiB groups 8, 16, 32 and 64 KiB blocks give 106.862, 103.935, 103.779 and 104.615 MiB; with 16 KiB blocks 128 MiB groups are 3.18% larger than 256 MiB groups, so the 256 MiB ceiling is used. The 256 MiB ceiling bounds encoder memory (about 12 × dictionary per process) and read amplification (a read decodes the group up to the bytes it needs). NES: migrated to v4 with 8 KiB blocks (cut at header/trainer/PRG/CHR boundaries) and 256 MiB groups. On the full database the v3 payload (489 lzma2-4m groups plus XOR-delta loose blocks, 382,082,581 bytes) became 344,223,238 bytes (−9.91%); the real-data curve was 64 MiB −1.40%, 128 MiB −2.59%, 256 MiB −5.66% against 32 MiB groups, smaller caps stay more than 0.5% above the 256 MiB result, so 256 MiB is used. Platforms added 2026-10-06 were measured on their whole local collections (8–256 KiB blocks × 32–256 MiB groups) and use the smallest total, or among configurations within 0.5% of it the smallest block, then the smallest group: Master System 128 KiB / 256 MiB: 62.61 MiB (ZIPs 177.42 MiB, per-file LZMA 105.80 MiB; 0.17% above the smallest); 32X 32 KiB / 256 MiB: 83.85 MiB (ZIPs 593.11 MiB, per-file LZMA 281.98 MiB; 0.32% above the smallest); WonderSwan 64 KiB / 256 MiB: 75.97 MiB (ZIPs 150.46 MiB, per-file LZMA 100.84 MiB; 0.45% above the smallest); WonderSwan Color 64 KiB / 128 MiB: 122.06 MiB (ZIPs 246.58 MiB, per-file LZMA 176.38 MiB; 0.23% above the smallest); NeoGeo Pocket 128 KiB / 32 MiB: 3.08 MiB (ZIPs 5.26 MiB, per-file LZMA 3.72 MiB; 0.36% above the smallest); NeoGeo Pocket Color 128 KiB / 256 MiB: 33.02 MiB (ZIPs 92.97 MiB, per-file LZMA 64.83 MiB; 0.25% above the smallest); Pokémon Mini 256 KiB / 32 MiB: 1.54 MiB (ZIPs 8.91 MiB, per-file LZMA 5.40 MiB; 0.33% above the smallest); Game Gear 32 KiB / 256 MiB: 63.83 MiB (ZIPs 254.16 MiB, per-file LZMA 139.89 MiB; the smallest); PC Engine 128 KiB / 256 MiB: 62.67 MiB (ZIPs 172.69 MiB, per-file LZMA 100.74 MiB; 0.23% above the smallest); SuperGrafx 128 KiB / 32 MiB: 2.20 MiB (ZIPs 6.59 MiB, per-file LZMA 2.77 MiB; 0.18% above the smallest); MSX 64 KiB / 64 MiB: 12.50 MiB (ZIPs 24.38 MiB, per-file LZMA 20.15 MiB; 0.21% above the smallest); MSX2 128 KiB / 128 MiB: 24.50 MiB (ZIPs 50.62 MiB, per-file LZMA 40.50 MiB; 0.22% above the smallest); Virtual Boy 256 KiB / 128 MiB: 21.87 MiB (ZIPs 76.45 MiB, per-file LZMA 33.69 MiB; 0.16% above the smallest); Game & Watch 4 KiB / 32 MiB: 0.13 MiB (ZIPs 0.15 MiB, per-file LZMA 0.14 MiB; the smallest); Super A'Can 64 KiB / 32 MiB: 9.44 MiB (ZIPs 11.72 MiB, per-file LZMA 9.67 MiB; 0.38% above the smallest).

BCJ (GBA only): ARM-Thumb +2.35%, ARM +0.73% on six real 128 MiB groups; not used. lc/lp/pb variations: < 0.2%.

## Format

- `PRAGMA user_version=4`. `compression_groups.codec` accepts `lzma2-4m` (v3 groups, ≤ 2 MiB) and `lzma2-solid` (≤ the platform cap in the table definition). Per-database parameters in `meta`: `rom_block_size` (4 KiB Game & Watch; 8 KiB NES; 32 KiB Satellaview/32X/Game Gear; 64 KiB SNES/MD/GB/GBC/FDS/WonderSwan/WonderSwan Color/MSX/Super A'Can; 128 KiB Master System/NeoGeo Pocket/NeoGeo Pocket Color/PC Engine/SuperGrafx/MSX2; 256 KiB Pokémon Mini/Virtual Boy; 1 MiB GBA; `nes_block_size` mirrors it for the shared code path), `solid_group_max_bytes`, `solid_group_dictionary_bytes` (≥ cap), `solid_group_cache_bytes` (max(96 MiB, 2 × cap)). `SOLID_MAX` = 256 MiB.
- Blocks are identified by SHA256 and deduplicated globally; grouped blocks store `(group_id, group_offset)` with an empty data BLOB. `solid_group_families` records each group's families; `object_families` records each payload object's family and its basis (newest DAT, older DAT, No-Intro DB parent archive, title).
- Encoding: raw LZMA2 with the platform dictionary, lc3 lp0 pb0, normal mode, BT4, nice_len 273, in a process pool whose workers load the engine from an explicit file; each group is round-trip decoded before insertion; plaintext and encoded SHA256 are stored.
- Reading verifies the encoded SHA256, then decodes incrementally up to the requested offset; each returned block is verified against its SHA256; a full decode additionally checks exact length, end of stream and the plaintext SHA256.
- Objects whose blocks lie in several groups (deduplication across families, e.g. NES multicarts) are read group by group in ascending order, each group decoded once up to the last byte needed, then assembled. `set_bulk_cache()` (audit, `export_set.py`) raises the cache to min(2 GiB, decoded size of all groups) and decodes whole groups, so no partially decoded group keeps its LZMA dictionary window (one dictionary per partial group is counted against the cache). On the NES database this changed the audit from re-decoding groups for each multicart to decoding each of the 6 groups once.

## Platform adapters and special cases

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

- NES: imported by the NES path (16-byte header recipe, body shared by headered and headerless dumps, 8 KiB blocks cut at header/trainer/PRG/CHR boundaries, XOR deltas for loose blocks), then packed into solid groups by `compact_solid`, which treats the body object behind a header recipe as the payload. DB Export imports use the NES importer (header reconstruction, pair checks).
- SNES: header scored at four locations; a 512-byte copier header is cut into its own block so the body deduplicates with headerless dumps.
- Mega Drive: SMD-interleaved files are detected and stored unchanged.
- GB/GBC: logo stored as SHA1 only; frontend sidecar text files are stored as `metadata` files.
- GBA: 1 MiB blocks; trailing 0xFF/0x00 padding recorded (padding blocks deduplicate); save-library IDs located with `bytes.find`.
- Satellaview: 32 KiB blocks, 256 MiB groups; `parse_bsx` locates the BS memory-pack header at 0x7FB0/0xFFB0 (fixed byte 0x33, map mode, checksum pair) and stores it in `bsx_hardware`; the BS-X base cartridge has a standard SNES header and goes through `parse_snes` into `snes_hardware` (a parser may name its table). RA hashes use the SNES method; the RA console is shared with SNES.
- FDS: images are FDS (65,500-byte sides), QD (65,536-byte sides with a CRC after each block) or BIOS (8 KiB), optionally behind a 16-byte fwNES header. Blocks (64 KiB, one per side) restart at the header and at every side, so a side shared by headered and headerless copies or by revisions is stored once. `fds_hardware.sides_json` keeps the disk information block of every side. Two DAT formats: FDS (primary) and QD (entries join the FDS release of the same name).
- Master System: `parse_sms` reads the `TMR SEGA` header (0x7FF0, else 0x3FF0/0x1FF0 with a warning), recomputes the checksum over the declared range (16 bytes before 0x8000 excluded) and records Codemasters and SDSC headers at 0x7FE0; Mark III cartridges without a header stay `unclassified`. Table `sms_hardware`.
- 32X: `parse_32x` uses the Mega Drive header (`md_hardware`); retail cartridges often say `SEGA MEGA DRIVE`/`SEGA GENESIS` and declare checksum 0, which is reported as 'no checksum declared' instead of a mismatch; the MARS block at 0x3C0 is checked. SMD-copier cuts as for Mega Drive.
- WonderSwan / WonderSwan Color: `parse_ws` reads the 16-byte footer (publisher, colour flag, game id, version, ROM size, save type and size, orientation, bus width, RTC, 16-bit checksum of all other bytes) into `ws_hardware`; WonderWitch homebrew carries a default footer with checksum 0. RA: one console (53) for both; the RA folder is shared and split by extension (`OTHER_PLATFORM_EXT`).
- NeoGeo Pocket / NeoGeo Pocket Color: `parse_ngp` reads the 64-byte header (licence string, start address, software id, sub code, colour mode, title) into `ngp_hardware`; BIOS images have no header. RA: one console (14) for both, shared RA folder split by extension.
- Pokémon Mini: `parse_pokemini` reads the header at 0x2100 (`MN`, `NINTENDO`, game code, title, `2P`) into `pokemini_hardware`.
- Game Gear: `parse_sms` (same `TMR SEGA` header as Master System, Game Gear region codes) into `sms_hardware`.
- PC Engine / SuperGrafx: HuCards have no internal header; `parse_pce` records a 512-byte copier header (size % 8192 = 512; cut into its own block like SNES), size, 8 KiB banks, partial-bank bytes and the reset vector at the end of the first bank into `pce_hardware`. RA hash drops the copier header when size % 131072 = 512 (rcheevos pce). The RA TurboGrafx-16 folder is shared and split by extension (`.pce` / `.sgx`).
- MSX / MSX2: `parse_msx` reads the cartridge `AB` header at 0x0000 or 0x4000 (INIT, STATEMENT, DEVICE, TEXT), recognises disk images by size and boot byte and tapes by the CAS block magic, into `msx_hardware` (`media`). The shared RA MSX folder is split by platform with `tools/msx_route.py` (DAT SHA1, `(MSX2`/`.mx2` tag, reviewed `data/msx-routing.csv`, single-platform title, ≥ 10% shared 8 KiB blocks, else MSX flagged unconfirmed); the basis goes to `rom_annotations(rom_id, kind='platform', value, source, created_at)`.
- Virtual Boy: `parse_vb` reads the game header 0x220 bytes before the end (title, maker code, game code, version) into `vb_hardware`.
- Game & Watch / Super A'Can: no internal header (`parse_plain`, `unclassified`); no RA console (empty report, `supported: false`).
- Loose blocks of adapter platforms skip XOR deltas; every platform's loose blocks are later packed by family.

## Incremental operation

- `update_db.py` reads only a ZIP's central directory to decide whether a stored archive changed (path, size, member names and CRC32). New ROMs are written as ordinary blocks with their family; `compact_solid` repacks a family's newest group when it has room, otherwise creates new groups; one savepoint, only the chunk-update and group-delete guards are lifted temporarily, every block of every touched group is re-verified.
- New DATs are diffed against the previous newest of the same format (`build_db.dat_format`: NES Headered/Headerless, FDS FDS/QD); in the primary format linked entries join existing releases and added entries join the parent's game or create one; other formats join releases by name (`build_db.link_format`). DB Export/Dump Log pairs are matched by their timestamp. RA and name imports add snapshots.
- Source collections: `update_db.register_collections` records every folder ROM ZIPs come from (`source_collections`: nointro, retroachievements, other); `v_collection_files` maps files to collections by path and `v_ra_collection` joins RA-set files to RA games, DAT validations and releases. `--discover` includes the platform's RA folder; files of another platform found there (`OTHER_PLATFORM_EXT`: FDS images in the RA NES folder go to the FDS database; Satellaview `.bs` files in the RA SNES folder go to the Satellaview database; `.nes` files in the RA FDS folder go to NES; `.wsc`/`.ws` and `.ngc`/`.ngp` in the shared RA WonderSwan and NeoGeo Pocket folders go to the matching database) are skipped and listed in the update report; both sides of each pair list the shared folder in `RA_FOLDERS`.
- Families for ROMs outside every DAT: `update_db.shared_block_family` picks the family of the stored objects sharing the most blocks (blocks referenced by more than 32 objects, such as padding, are ignored; at least 10% of the object's blocks must be shared), else a title family. The index `object_chunk_block` on `object_chunks(chunk_id)` serves this lookup.
- Deduplication check: a new block whose SHA-256 is stored is compared byte for byte when the stored block is loose or its group is already decoded in the cache; otherwise the SHA-256 identity is accepted, because decoding a solid group per hit made imports of mostly known ROMs very slow; groups are verified by the round-trip decode at encoding time and by every audit. New TorrentZip plans are computed from the member bytes just imported (`DB.plan` with the recent-object cache), and DAT packages compare immutable object checksums for every v4 database including NES.
- `retune_db.py` merges consecutive groups to a larger cap (relaxing, never tightening, the table's cap through `writable_schema`, followed by an integrity check). `migrate_v4.py` copies a v3 database, upgrades its schema, assigns families and RA hashes, decodes payload blocks in block-ID order and packs them in family order. Both keep block IDs, SHA256, sizes, object extents and all metadata.

## Verification

- The audit sweeps solid groups in storage order (`storage_positions()`: first block of each object; NES header recipes take their body's position): objects and archive plans whose first block is in a group are verified while it is cached, then the group's full decode is checked. The next group is decoded and fully verified in a separate thread meanwhile; object hashing and TorrentZip regeneration run in a thread pool (up to 8 threads), and plans reuse the object bytes read in the same step. Each group is decoded about once.
- Exports check every byte; `export_set.py` exports in storage order with the bulk cache, checks every member against all DAT hashes and TorrentZips against the registered archive plans (found through the members' immutable object checksums), hashes and writes in a thread pool and syncs once at the end; `engine.py export` fsyncs each file.
- Memory: a full audit of a database with 256 MiB groups peaks at about 4.2 GiB (2 GiB bulk cache, the next group decoded ahead, plans in flight); `compact_solid` keeps at most `workers` groups assembled or encoding at a time (GBA, two 256 MiB encoders: 7.4 GiB peak measured while repacking 66 groups; before this bound the whole backlog was held in memory).
- DAT packages compare members through immutable object checksums (computed from the bytes at import); member bytes are decoded only to encode a new plan.

## Catalog and release

`build_catalog.py` creates a fresh SQLite file without payload rows; the Catalog `engine.py` is query-only and reports `payloads_verified=false`. Releases follow one workflow in every repository: `release/catalog-release.json` pins a base Catalog by SHA256 and lists every data table's digest; `tools/build_catalog_release.py` injects the engine generated from `tools/` and the documents of the commit, checks the digests, integrity, foreign keys, resource checksums, the Catalog audit, the repository tests (and NES's embedded suite), vacuums to zero free pages and writes `SHA256SUMS`. The `resources` table holds executable code: run it only from a database you built or a Release asset whose SHA256 you verified. `files.source_path` keeps original local paths as provenance. Provider-information tables (`LOCAL_ONLY` in `tools/base/build_catalog.py`: `scrape_texts`, `scrape_blobs`, `provider_snapshots`, `provider_records`, `provider_snapshot_records`, `provider_record_values`, `provider_record_media`, `ss_record_roms`, `ss_lookups`, `scrape_checks`, `scraper_game_links`, `frontend_game_values`, `frontend_media_slots`, `scrape_records`, `media`) are created in the Catalog with the populated database's definitions and receive no rows; the build asserts they are empty.

## Post-audit engine changes (2026-10-04)

Naming decisions are written only when the validated object is the file itself; DAT `size` values are range-checked; raw `.dat/.xml` inputs obey `MAX_ROM`; `safe_name` rejects Unicode control and format characters; export checks the parent directory first; ZIP member CRC mismatches are rejected. Details: `reports/audit-resolution-20261004.md`.

Populated-database audits: NES 19,069 objects / 9 groups / 25,368 archive plans; SNES 5,243 objects / 57 groups / 5,774 archive plans; Mega Drive 3,963 objects / 20 groups / 5,367 archive plans; Game Boy 2,546 objects / 5 groups / 2,776 archive plans; Game Boy Color 2,791 objects / 13 groups / 2,931 archive plans; Game Boy Advance 4,149 objects / 123 groups / 4,396 archive plans; Famicom Disk System 712 objects / 1 groups / 728 archive plans; Satellaview 607 objects / 2 groups / 923 archive plans; Master System 1,236 objects / 2 groups / 1,523 archive plans; 32X 231 objects / 2 groups / 387 archive plans; WonderSwan 268 objects / 1 groups / 269 archive plans; WonderSwan Color 271 objects / 4 groups / 278 archive plans; NeoGeo Pocket 16 objects / 1 groups / 16 archive plans; NeoGeo Pocket Color 165 objects / 2 groups / 171 archive plans; Pokémon Mini 86 objects / 1 groups / 88 archive plans; Game Gear 934 objects / 2 groups / 1,306 archive plans; PC Engine 548 objects / 2 groups / 684 archive plans; SuperGrafx 10 objects / 1 groups / 14 archive plans; MSX 1,011 objects / 2 groups / 1,023 archive plans; MSX2 306 objects / 2 groups / 277 archive plans; Virtual Boy 102 objects / 2 groups / 113 archive plans; Game & Watch 57 objects / 1 groups / 58 archive plans; Super A'Can 17 objects / 1 groups / 16 archive plans; all passed.
