# RetroBoxDB SNES / Mega Drive — Storage v4 technical design

[中文说明](RetroBoxDB.Cartridge.zh-CN.md) · [NES design](https://github.com/rshi0212/RetroBoxDB-NES/blob/main/RetroBoxDB.NES.Technical-Design.en.md)

Each platform has one populated SQLite file (`RetroBoxDB.SNES.sqlite`, `RetroBoxDB.MegaDrive.sqlite`) and one payload-free Catalog. The application schema is the NES v3 schema (objects, files, ROMs, DAT sets, validations, archive plans, No-Intro DB/Dumplog, frontend placeholders, Chinese names) with a cartridge extension (`tools/cart_schema.sql`). NES-only tables (`nes_recipes`, `nes_hardware`) exist but stay empty so shared views and the shared engine keep working. Platform row `platforms.id=1` is `snes` or `megadrive`.

## Measured storage choice

A 10% random sample (250 No-Intro parent/clone families per platform, seed 2026) compared encodings on real data. Sizes in MiB (`assessment/data/cart-storage-experiment.json`):

| Strategy | SNES | MD |
| --- | ---: | ---: |
| Source No-Intro ZIPs | 443.2 | 408.2 |
| Per-file LZMA | 387.0 | 314.2 |
| NES v3 engine unchanged (8 KiB blocks, XOR deltas, 2 MiB groups; SQLite file) | 238.9 | 216.9 |
| zstd with the parent ROM as raw dictionary | 206.1 | 167.8 |
| 8 KiB blocks, family-ordered 16 MiB solid groups (+~9 MiB block metadata) | 189.1 | 146.7 |
| **64 KiB blocks, family-ordered 32 MiB solid groups (+1.2 MiB metadata)** | **189.8** | **144.5** |
| One solid stream per family (reference bound) | 192.3 | 151.2 |

SNES/MD ROMs are 0.5–8 MiB, so a 2 MiB group cannot hold one ROM, and revisions often shift data, defeating aligned blocks and XOR deltas. A 32 MiB LZMA2 dictionary over a family-ordered stream captures cross-revision redundancy. 64 MiB groups saved only 0.2–0.4% more while doubling worst-case decode work; lc/lp/pb variations changed size by less than 0.2%. zstd (stdlib only from Python 3.14) was 8–16% larger.

## Storage v4

- `PRAGMA user_version=4`. `compression_groups.codec` accepts `lzma2-4m` (v3, ≤2 MiB) and `lzma2-solid` (≤32 MiB). The v3 engine rejects v4 files; the v4 engine reads v2/v3/v4 and passes the NES 70-test suite unchanged.
- ROM bytes are split into 64 KiB blocks (`meta.nes_block_size`/`rom_block_size` = 65536), identified by SHA256 and deduplicated globally. Block rows keep ID, size and SHA256; grouped blocks store `(group_id, group_offset)` with an empty data BLOB, exactly like v3 group slices.
- The bulk importer orders ZIPs by family key: newest DAT parent/clone chain → DB Export parent archive (`clone` attribute) → older DAT → parenthesis-stripped title. New blocks of whole families are appended to a group until the next family would exceed 32 MiB (large families span several groups). `solid_group_families` records each group's family list (checked by trigger, not a foreign key, so the Catalog keeps it).
- Encoding: raw LZMA2, 32 MiB dictionary, lc3 lp0 pb0, normal mode, BT4, nice_len 273, executed in a process pool; each group is round-trip decoded before insertion. Group SHA256 of encoded and plaintext bytes is stored.
- Reading verifies encoded SHA256, bounded decompression with exact length and end-of-stream, plaintext SHA256, then each block's SHA256 and finally the object's full checksum set. A 96 MiB LRU cache holds decoded solid groups; worst-case read amplification is one 32 MiB group per ROM.
- Single-file imports through the CLI (`import-rom`) store ordinary per-block encodings; similarity indexing excludes grouped blocks so it never decodes all groups.

## Incremental growth and special cases

- `tools/update_cart_db.py` skips ZIPs already stored (content hash + path). New ROMs are stored as ordinary 64 KiB blocks and their family is recorded in `object_families` (newest DAT parent/clone → DB Export parent archive → older DAT → title). `DB.compact_solid()` then packs loose ROM blocks by family: if the family's newest solid group has room it is decoded, extended with the new blocks and re-encoded (the new revision shares the LZMA dictionary with its siblings); otherwise new family-ordered groups are created. Block identities and object extents never change; the operation runs in one savepoint, temporarily lifting only the chunk-update and group-delete guards, re-verifies every block of every touched group, and is idempotent.
- New DATs are imported idempotently and scanned; the previous newest DAT is diffed; linked entries join their existing release, added entries join the parent's game or create a new game/release; ROM/release links and TorrentZip packages are refreshed. Release titles keep the DAT name at creation; current names come through `release_dat_games`.
- New DB Export/Dumplog pairs become new snapshots (idempotent by both SHA256 values); RA and name imports add new snapshots/sources.
- SNES copier-headered files (`size % 1024 == 512`) are cut at 512 bytes so their body blocks deduplicate with headerless dumps. SMD-interleaved Mega Drive files are detected and stored unchanged (none exist locally). Cartridge ROM blocks skip XOR deltas. Platform adapters (`CART_PLATFORMS`) declare parser, hardware table, extensions and block cuts; block size and solid limit come from `meta`.
- The v4 audit visits objects and archive plans in solid-group order and regenerates TorrentZips in a thread pool, so each group is decoded about once.

## ROM records and internal headers

`roms.object_id = body_object_id` (no external header), `format` is `snes`/`snes_copier` or `md`/`smd_interleaved`. Parsing is descriptive and never alters stored bytes.

- `snes_hardware`: header location chosen among LoROM 0x7FC0, HiROM 0xFFC0, ExLoROM 0x407FC0, ExHiROM 0x40FFC0 by a score (checksum/complement, map mode, printable title, ROM-size byte, reset vector, developer ID); fields include title (ASCII/Shift-JIS), map mode, FastROM, chipset and coprocessor (custom subtype from the extended header), ROM/RAM declared sizes, region, maker/game codes, version, declared and computed checksums (non-power-of-two sizes mirrored). A 512-byte copier header is detected and recorded as a component.
- `md_hardware`: system type, copyright, domestic/overseas titles, serial, device support, ROM/RAM ranges, SRAM descriptor, modem, notes, regions; computed checksum is the 16-bit big-endian word sum from 0x200 to end of file (41 dumps match only over the declared ROM range; the field is not reinterpreted).

## DATs, No-Intro DB and Dumplog

Every local Parent-Clone DAT is imported and scanned (SNES 20260710-203222 and 20261003-140326; MD 20260714-063411 and 20260927-122056). `dat_changes` records the old→new diff with the NES rule (same casefold name, else identical full signature). Games and releases come from the newest DAT; older DAT games join the matching release through the diff. Source ZIP byte identities remain historical (`archive_manifest`), and TorrentZip plans (source ZIPs and DAT packages) are encoded once to register checksums; export regenerates and verifies them.

`cart_nointro.py` adapts the NES importer: all files are `Default` format, so header reconstruction and headered/headerless pairing are absent; a missing SHA256 stays NULL (`ni_files.sha256` is nullable in v4) and is logged as an anomaly; the `header` attribute is a serial string kept in `ni_files.attrs_json`. Serial-bearing sources become `documented` hardware assertions, as for NES.

## RetroAchievements

`tools/import_ra.py` stores a snapshot of `API_GetGameList` (all games of console 3 or 1, with hashes): `ra_snapshots` (response SHA256, resource name), `ra_games` (achievement/leaderboard counts, category from `~Tag~` prefixes) and `ra_hashes`. The API key is read at runtime and never persisted. `rom_ra_hashes` holds each ROM's RA hash computed at import (rcheevos rules: SNES drops a 512-byte header when `size % 8192 == 512`; Mega Drive hashes the full file). Views: `v_rom_ra_matches` (local bytes), `v_dat_ra_matches` (DAT MD5, no payload needed), `v_nointro_ra_matches` (DB Export files such as bad dumps), `v_ra_unmatched_hashes`. Matching is exact hash equality only. `tools/ra_report.py` classifies every RA game with achievements as local / dat_only / nointro_db_only / unmatched. `tools/export_nointro_parents.py` uses the stored snapshot for SNES/MD.

## Results

| | SNES | Mega Drive |
| --- | ---: | ---: |
| Source ZIPs | 4,898 files, 4,288,077,842 B | 5,281 files, 4,218,193,674 B |
| Unique 64 KiB block bytes → stored solid groups | 4.25 GiB → 1.48 GiB (145 groups) | 3.87 GiB → 0.90 GiB (143 groups) |
| Populated SQLite / Catalog | 1,657,028,608 B / 50,556,928 B | 1,019,019,264 B / 44,269,568 B |
| ROM records; newest-DAT coverage | 4,293; 4,261/4,331 | 3,687; 3,398/3,504 |
| RA games with achievements: local / DAT only / DB only / none | 673 / 0 / 1 / 511 | 520 / 0 / 1 / 91 |
| Audit (objects, groups, archive plans) | 4,297 / 145 / 4,813, no errors | 3,691 / 143 / 5,044, no errors |

The bulk build process was stopped during its original id-ordered archive audit (correct but cache-unfriendly); the v4 locality-ordered audit performed the same checks. The embedded `build-report` was assembled from the `events` table and records this.

## Catalog boundary and verification

`build_catalog.py` (unchanged from NES) creates a fresh SQLite file without rows in `compression_groups`, `chunks` and `object_chunks`; the Catalog `engine.py` is query-only and its audit reports `payloads_verified=false`. Internal-header fields (title, serial, checksums) are metadata.

Synthetic tests (`tests/test_cart.py`, embedded as `tests_cart.py`) cover both header parsers, copier/RA hashing, solid-group round trip, block deduplication, exact export of ROMs and TorrentZips, corruption detection, schema limits, v3 rejection of v4, DAT diff/catalog records, the No-Intro importer without SHA256, RA views and Catalog exclusion. The build ends with `audit(archives=True)`: SQLite integrity, foreign keys, every solid group, every stored object against its full checksum set, and every archive plan regenerated against its registered checksums.
