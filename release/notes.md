SNES Catalog, storage v4 (64 KiB blocks, 57 solid LZMA2 groups of up to 128 MiB). Metadata only: **no ROM payloads are published**; `compression_groups`, `chunks` and `object_chunks` are empty.

- RetroAchievements ROM set imported: 1,836 ZIPs; 889 ROM files are also in a No-Intro DAT, 932 are only in the RA set, 15 have a hash absent from the latest RA snapshot. RA games with achievements that have a local ROM: 673 → 1,089.
- Source collections (`source_collections`, `v_collection_files`) and RetroAchievements links per file (`v_ra_collection`).
- ROMs outside every DAT join the family of the stored ROMs they share the most blocks with (hacks next to their original).
- Imports and DAT packaging no longer decode solid groups for already stored blocks; DAT formats (e.g. FDS/QD, NES headered/headerless) are handled separately.
- Source: 6,734 ZIPs (nointro 4,898, retroachievements 1,836), 6.06 GiB (6,734 ROM files, 10.90 GiB uncompressed). Populated database: 1.76 GiB (29.1% of the ZIPs). All source ZIPs are reproduced byte-for-byte.
- Contents: 5,239 ROM records, 1,996 games, 4,329 releases; DAT versions: 20260710-203222, 20261003-140326.
- RetroAchievements: 1,089 of 1,185 games with achievements have a local ROM.
- Export (Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz, idle, all checks): whole newest-DAT set with export_set.py 28.0 MiB/s (4,261 files); single file with a cold cache 1.094 s (ROM) / 1.397 s (TorrentZip) on average.
- Full audit of the populated database: 5,243 objects, 57 groups, 5,774 archive plans, no errors.

The release workflow starts from the base Catalog pinned by SHA256 in `release/catalog-release.json`, injects the engine and documents of the tagged commit, checks every data-table digest, SQLite integrity and foreign keys, runs the Catalog audit and the repository tests. Verify the download with `SHA256SUMS`.

[中文说明](https://github.com/rshi0212/RetroBoxDB-SNES/blob/main/README.zh-CN.md)
