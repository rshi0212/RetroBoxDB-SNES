# RetroBoxDB storage v4 — technical design

[English guide](RetroBoxDB.Storage-v4.en.md) · [中文说明](RetroBoxDB.Storage-v4.zh-CN.md) · [NES v3 design (history)](https://github.com/rshi0212/RetroBoxDB-NES/blob/main/RetroBoxDB.NES.Technical-Design.en.md)

Six platforms (NES, SNES, Mega Drive, Game Boy, Game Boy Color, Game Boy Advance) each have one populated SQLite file and one payload-free Catalog. The application schema is the NES v3 schema (objects, files, ROMs, DAT sets, validations, archive plans, No-Intro DB/Dump Log, frontend placeholders, names) plus `tools/schema_v4.sql`. Tables of other platforms exist and stay empty so shared views and the single engine work everywhere. `platforms.id=1` holds the platform code.

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

Rule: the smallest group cap whose compressed size is within 0.5% of the 256 MiB result. The 256 MiB ceiling bounds encoder memory (about 12 × dictionary per process) and read amplification (a read decodes the group up to the bytes it needs). NES: migrated to v4 with 8 KiB blocks (cut at header/trainer/PRG/CHR boundaries) and 256 MiB groups. On the full database the v3 payload (489 lzma2-4m groups plus XOR-delta loose blocks, 382,082,581 bytes) became 344,223,238 bytes (−9.91%); the real-data curve was 64 MiB −1.40%, 128 MiB −2.59%, 256 MiB −5.66% against 32 MiB groups, smaller caps stay more than 0.5% above the 256 MiB result, so 256 MiB is used.

BCJ (GBA only): ARM-Thumb +2.35%, ARM +0.73% on six real 128 MiB groups; not used. lc/lp/pb variations: < 0.2%.

## Format

- `PRAGMA user_version=4`. `compression_groups.codec` accepts `lzma2-4m` (v3 groups, ≤ 2 MiB) and `lzma2-solid` (≤ the platform cap in the table definition). Per-database parameters in `meta`: `rom_block_size` (8 KiB NES, 64 KiB SNES/MD/GB/GBC, 1 MiB GBA; `nes_block_size` mirrors it for the shared code path), `solid_group_max_bytes`, `solid_group_dictionary_bytes` (≥ cap), `solid_group_cache_bytes` (max(96 MiB, 2 × cap)). `SOLID_MAX` = 256 MiB.
- Blocks are identified by SHA256 and deduplicated globally; grouped blocks store `(group_id, group_offset)` with an empty data BLOB. `solid_group_families` records each group's families; `object_families` records each payload object's family and its basis (newest DAT, older DAT, No-Intro DB parent archive, title).
- Encoding: raw LZMA2 with the platform dictionary, lc3 lp0 pb0, normal mode, BT4, nice_len 273, in a process pool whose workers load the engine from an explicit file; each group is round-trip decoded before insertion; plaintext and encoded SHA256 are stored.
- Reading verifies the encoded SHA256, then decodes incrementally up to the requested offset; each returned block is verified against its SHA256; a full decode additionally checks exact length, end of stream and the plaintext SHA256.
- Objects whose blocks lie in several groups (deduplication across families, e.g. NES multicarts) are read group by group in ascending order, each group decoded once up to the last byte needed, then assembled. `set_bulk_cache()` (audit, `export_set.py`) raises the cache to min(2 GiB, decoded size of all groups) and decodes whole groups, so no partially decoded group keeps its LZMA dictionary window (one dictionary per partial group is counted against the cache). On the NES database this changed the audit from re-decoding groups for each multicart to decoding each of the 6 groups once.

## Platform adapters and special cases

| Platform | Block | Group cap / dictionary | Groups | Unique block bytes → stored |
| --- | ---: | ---: | ---: | --- |
| NES | 8 KiB | 256 MiB | 6 | 1.28 GiB → 328.3 MiB |
| SNES | 64 KiB | 128 MiB | 37 | 4.25 GiB → 1.48 GiB |
| Mega Drive | 64 KiB | 256 MiB | 17 | 3.87 GiB → 882.3 MiB |
| Game Boy | 64 KiB | 256 MiB | 3 | 558.1 MiB → 128.3 MiB |
| Game Boy Color | 64 KiB | 256 MiB | 10 | 2.26 GiB → 453.3 MiB |
| Game Boy Advance | 1 MiB | 256 MiB | 104 | 23.72 GiB → 5.45 GiB |

- NES: imported by the NES path (16-byte header recipe, body shared by headered and headerless dumps, 8 KiB blocks cut at header/trainer/PRG/CHR boundaries, XOR deltas for loose blocks), then packed into solid groups by `compact_solid`, which treats the body object behind a header recipe as the payload. DB Export imports use the NES importer (header reconstruction, pair checks).
- SNES: header scored at four locations; a 512-byte copier header is cut into its own block so the body deduplicates with headerless dumps.
- Mega Drive: SMD-interleaved files are detected and stored unchanged.
- GB/GBC: logo stored as SHA1 only; frontend sidecar text files are stored as `metadata` files.
- GBA: 1 MiB blocks; trailing 0xFF/0x00 padding recorded (padding blocks deduplicate); save-library IDs located with `bytes.find`.
- Loose blocks of adapter platforms skip XOR deltas; every platform's loose blocks are later packed by family.

## Incremental operation

- `update_db.py` reads only a ZIP's central directory to decide whether a stored archive changed (path, size, member names and CRC32). New ROMs are written as ordinary blocks with their family; `compact_solid` repacks a family's newest group when it has room, otherwise creates new groups; one savepoint, only the chunk-update and group-delete guards are lifted temporarily, every block of every touched group is re-verified.
- New DATs are diffed against the previous newest; linked entries join existing releases, added entries join the parent's game or create one. DB Export/Dump Log pairs are matched by their timestamp. RA and name imports add snapshots.
- `retune_db.py` merges consecutive groups to a larger cap (relaxing, never tightening, the table's cap through `writable_schema`, followed by an integrity check). `migrate_v4.py` copies a v3 database, upgrades its schema, assigns families and RA hashes, decodes payload blocks in block-ID order and packs them in family order. Both keep block IDs, SHA256, sizes, object extents and all metadata.

## Verification

- The audit sweeps solid groups in storage order (`storage_positions()`: first block of each object; NES header recipes take their body's position): objects and archive plans whose first block is in a group are verified while it is cached, then the group's full decode is checked. The next group is decoded and fully verified in a separate thread meanwhile; object hashing and TorrentZip regeneration run in a thread pool (up to 8 threads), and plans reuse the object bytes read in the same step. Each group is decoded about once.
- Exports check every byte; `export_set.py` exports in storage order and also compares TorrentZips with the registered archive plans.
- DAT packages compare members through immutable object checksums (computed from the bytes at import); member bytes are decoded only to encode a new plan.

## Catalog and release

`build_catalog.py` creates a fresh SQLite file without payload rows; the Catalog `engine.py` is query-only and reports `payloads_verified=false`. Releases follow one workflow in every repository: `release/catalog-release.json` pins a base Catalog by SHA256 and lists every data table's digest; `tools/build_catalog_release.py` injects the engine generated from `tools/` and the documents of the commit, checks the digests, integrity, foreign keys, resource checksums, the Catalog audit, the repository tests (and NES's embedded suite), vacuums to zero free pages and writes `SHA256SUMS`. The `resources` table holds executable code: run it only from a database you built or a Release asset whose SHA256 you verified. `files.source_path` keeps original local paths as provenance.

## Post-audit engine changes (2026-10-04)

Naming decisions are written only when the validated object is the file itself; DAT `size` values are range-checked; raw `.dat/.xml` inputs obey `MAX_ROM`; `safe_name` rejects Unicode control and format characters; export checks the parent directory first; ZIP member CRC mismatches are rejected. Details: `reports/audit-resolution-20261004.md`.

Populated-database audits: NES 17,734 objects / 6 groups / 24,487 archive plans; SNES 4,297 objects / 37 groups / 4,813 archive plans; Mega Drive 3,691 objects / 17 groups / 5,044 archive plans; Game Boy 2,323 objects / 3 groups / 2,491 archive plans; Game Boy Color 2,612 objects / 10 groups / 2,679 archive plans; Game Boy Advance 3,740 objects / 104 groups / 3,940 archive plans; all passed.
