SNES Catalog, storage v4 (64 KiB blocks, 37 solid LZMA2 groups of up to 128 MiB). Metadata only: **no ROM payloads are published**; `compression_groups`, `chunks` and `object_chunks` are empty.

- Solid groups merged from 32 MiB to 128 MiB (measured on the full database; larger groups gave less than 0.5% more).
- Unified engine shared with NES, Mega Drive, Game Boy, Game Boy Color and Game Boy Advance.
- Source: 4,898 No-Intro ZIPs, 3.99 GiB (4,898 ROM files, 6.97 GiB uncompressed). Populated database: 1.54 GiB (38.5% of the ZIPs). All source ZIPs are reproduced byte-for-byte.
- Contents: 4,293 ROM records, 1,996 games, 4,329 releases; DAT versions: 20260710-203222, 20261003-140326.
- RetroAchievements: 673 of 1,185 games with achievements have a local ROM.
- Export (Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz, idle, all checks): whole set in storage order 20.6 MiB/s (4,898 ROM files); single file with a cold cache 1.099 s (ROM) / 1.402 s (TorrentZip) on average.
- Full audit of the populated database: 4,297 objects, 37 groups, 4,813 archive plans, no errors.

The release workflow starts from the base Catalog pinned by SHA256 in `release/catalog-release.json`, injects the engine and documents of the tagged commit, checks every data-table digest, SQLite integrity and foreign keys, runs the Catalog audit and the repository tests. Verify the download with `SHA256SUMS`.

[中文说明](https://github.com/rshi0212/RetroBoxDB-SNES/blob/main/README.zh-CN.md)
