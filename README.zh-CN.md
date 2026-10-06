# RetroBoxDB SNES

[English](README.md) | 中文

超级任天堂（SNES／Super Famicom）的单文件 SQLite 保存库。公开的 Catalog 只含元数据（校验值、DAT 与来源记录、头部字段、打包配方和程序），不含 ROM 数据，不能独立恢复文件；完整库保留在本地。

| 项目 | 数值 |
| --- | --- |
| 原始大小 | 源 ZIP 6,734 个，6.06 GiB（No-Intro 4,898 个，RetroAchievements 集合 1,836 个）；解压后 ROM 6,734 个，10.90 GiB |
| 入库后大小 | 完整库 1.77 GiB；公开 Catalog 54.1 MiB（不含 ROM 数据） |
| 比例 | 完整库为原 ZIP 的 29.1%，为解压后 ROM 总量的 16.2% |
| 使用的技术 | 存储 v4：64 KiB 块按 SHA256 去重，按 No-Intro 游戏族顺序装入最大 128 MiB 的 LZMA2 实体组（字典 128 MiB）；逐块 SHA256、逐对象 CRC32／MD5／SHA1／SHA256 校验；源 ZIP 由 TorrentZip 配方逐字节重建 |
| 导出性能 | Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz，空闲负载，Python 3.14.4，含全部校验。按最新 DAT 整套导出（`export_set.py`，4,261 个文件，逐个按 DAT 哈希校验）：28.0 MiB/s，平均 52 毫秒／个；单个文件冷缓存（每次清空缓存，需解压所在组的前段）：ROM 平均 1.094 秒，TorrentZip 平均 1.397 秒 |

## 下载与说明

| 文件／文档 | 内容 |
| --- | --- |
| [RetroBoxDB.SNES.Catalog.sqlite](https://github.com/rshi0212/RetroBoxDB-SNES/releases/latest/download/RetroBoxDB.SNES.Catalog.sqlite) | 公开 Catalog（Release 附件，附 `SHA256SUMS`） |
| [存储 v4 说明](RetroBoxDB.Storage-v4.zh-CN.md)／[English](RetroBoxDB.Storage-v4.en.md) | 各平台的存储评估、内容、RA、中文名与维护 |
| [Technical design](RetroBoxDB.Storage-v4.Technical-Design.en.md) | 存储格式、平台适配、增量更新、校验 |
| [RA 清单](reports/ra-snes-games.csv)／[汇总](reports/ra-snes.json)、[构建报告](reports/snes-build-report.json)、[审计处理](reports/audit-resolution-20261004.md) | 逐项数据 |

## 本平台的存储选择与特殊情况

真实全量数据（按族排序的前 16 个组，484 MiB）上相对 32 MiB 组的变化：64 MiB −0.24%，128 MiB −0.51%，256 MiB −0.78%；按规则采用 128 MiB。

- ROM 为 0.25–6 MiB；地区版和修订版相似但常有位移，NES v3 的对齐 XOR 差分收效有限，族排序数据上的大 LZMA2 字典更有效。
- 内部头部：在 LoROM 0x7FC0、HiROM 0xFFC0、ExLoROM、ExHiROM 四处按校验和互补、映射模式、标题、ROM 大小字节和复位向量打分选位置；分数不足的记为 `unclassified`（多为 Beta、原型、盗版卡和增强芯片固件）。保存映射模式、FastROM、芯片组与协处理器、SRAM、地区、厂商／游戏代码和两种校验和。
- 512 字节 copier 头（文件大小 %1024 = 512）会单独切成一块，使正文与无头版本去重，RA 哈希也在去头后计算；本地收藏中没有这类文件。
- 无 No-Intro 对应的 RA 游戏主要是 Hack、翻译补丁版（如 RA 的 Bahamut Lagoon、Rushing Beat 套装使用英译补丁 ROM）和 Subset。
- RetroAchievements SNES 目录中的 Satellaview（BS-X，`.bs`）文件属于独立平台：SNES 导入时跳过，由 [RetroBoxDB-Satellaview](https://github.com/rshi0212/RetroBoxDB-Satellaview) 收录；ROM 在该库中的 RA 游戏在报告里标为 `local_other_platform`。

## 内容

| 项目 | 数值 |
| --- | --- |
| ROM 记录／游戏组／发行版本 | 5,239／1,996／4,329 |
| 各版 DAT 覆盖 | 20260710-203222：4,255/4,318；20261003-140326：4,261/4,331 |
| 不在任何 DAT 的本地 ROM | 978 |
| RetroAchievements 集合中的 ROM 文件 | DAT 中有 889，仅 RA 收录 932，哈希不在最新 RA 快照 15（[清单](reports/ra-snes-collection-unknown.csv)）；仍缺本地 ROM 的 RA 游戏见 [缺口清单](reports/ra-snes-missing.csv) |
| No-Intro DB Export＋Dump Log 20261003-140326 | 4,365 个档案、5,457 个文件身份、5,399 条有文档的硬件声明；Dump Log Verified 1,871 |
| RetroAchievements（console 3） | 有成就的游戏 1,185 个：本地有 ROM 1,089（1,845 个 ROM），ROM 在兄弟库中 6，仅 DAT 有 0，仅 DB 文件 0，无 No-Intro 对应 90 |
| 中文名 | 4,154 条记录中 3,942 条有中文（2,030 个唯一名）；本地 ROM 3,909 个有中文名 |
| 完整库审计 | 5,243 个对象、57 个组、5,774 个 ZIP 配方，全部通过 |

源 ZIP 均可由 TorrentZip 配方逐字节重建（`v_file_checksums.exported_bytes_equal_source`）。

## 使用

```bash
# 用 Catalog 内嵌引擎做只读审计（stats、checksums FILE_ID、help 同理）
python3 -B -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); s=c.execute("SELECT content FROM resources WHERE name=?",("engine.py",)).fetchone()[0]; c.close(); exec(compile(s,"RetroBoxDB:engine.py","exec"))' ./RetroBoxDB.SNES.Catalog.sqlite audit
# 完整库：按 DAT 版本、1G1R、RA 成就、TorrentZip／裸 ROM 组合导出
python3 -B tools/export_set.py RetroBoxDB.SNES.sqlite OUT --set 1g1r --ra achievements --container torrentzip --layout ra-category
# 增量加入新 DAT、DB Export／Dump Log、ROM 与 RA 快照
python3 -B tools/update_db.py RetroBoxDB.SNES.sqlite --discover --ra --catalog RetroBoxDB.SNES.Catalog.sqlite
```

只需 Python 3.10+ 标准库。`resources` 中的 `engine.py` 等是可执行代码，只应从自己构建或 SHA256 已核对的 Release 附件中执行。发布由 `.github/workflows/publish-catalog.yml` 完成：工作流从 `release/catalog-release.json` 固定的基础 Catalog 出发，注入本仓库提交中的引擎与文档，核对全部数据表摘要、运行测试与审计后发布。
