# RetroBoxDB SNES

[English](README.md) | 中文

超级任天堂（SNES／Super Famicom）保存库：精确 ROM 身份、去重存储、跨 No-Intro 快照的 DAT 验证、Dump 来源、内部头部元数据、RetroAchievements 哈希匹配、中英文名和带校验的 TorrentZip 配方。与 [RetroBoxDB-NES](https://github.com/rshi0212/RetroBoxDB-NES) 同一架构。

**公开的 Catalog 不含 ROM 正文、DAT／DB／Dumplog 原文件、压缩数据或媒体。** 完整库只保留在本地；Catalog 只有元数据、预期校验值、头部字段、打包配方、来源与程序代码，不能独立恢复文件。

| 下载／文档 | 用途 |
| --- | --- |
| [RetroBoxDB.SNES.Catalog.sqlite](https://github.com/rshi0212/RetroBoxDB-SNES/releases/latest/download/RetroBoxDB.SNES.Catalog.sqlite) | 无载荷 SQLite（48 MiB），GitHub Release 附件 |
| [中文说明](RetroBoxDB.Cartridge.zh-CN.md) | SNES／Mega Drive 完整中文说明 |
| [Technical design](RetroBoxDB.Cartridge.Technical-Design.en.md) | 存储 v4、平台适配、增量更新、RA、校验 |
| [RA 覆盖清单](reports/ra-snes-games.csv)／[汇总](reports/ra-snes.json) | 每个有成就的 RA 游戏及匹配状态 |
| [构建报告](reports/snes-build-report.json) | 导入、扫描、差异、No-Intro、打包、中文名与审计结果 |

## 收藏概况

| | |
| --- | --- |
| 本地 No-Intro ZIP（含 Aftermarket／Private） | 4,898 个，3.99 GiB |
| 完整库 | 1.54 GiB（原 ZIP 的 38.6%） |
| ROM 记录／游戏组／发行版本 | 4,293／1,996／4,329 |
| 旧 DAT 20260710-203222 覆盖 | 4,255/4,318 |
| 新 DAT 20261003-140326 覆盖 | 4,261/4,331 |
| 新旧 DAT 差异 | 未变 4,313、新增 13、改名 5 |
| No-Intro DB Export＋Dump Log 20261003-140326 | 4,365 个档案、5,457 个文件身份、12,153 条来源、5,399 条有文档的硬件声明；Dump Log 中 Verified 1,871 |

## 存储经实测选型

没有照搬 NES 的 8 KiB 块＋XOR＋2 MiB 组。随机抽取 10% 游戏族比较 7 种方案后，采用存储 v4：64 KiB 块按 SHA256 去重，按 No-Intro 游戏族（母版与各克隆版在一起）排序装入最大 32 MiB 的 LZMA2 实体组。本库 4.25 GiB 去重块存为 1.48 GiB（145 个组）。每个块保留 SHA256，每个对象核对 CRC32／MD5／SHA1／SHA256；v3 引擎会拒绝 v4 文件。实验数据见 [cart-storage-experiment.json](assessment/data/cart-storage-experiment.json)。

## RetroAchievements

保存 RA 公开 API（console 3）快照，不保存任何凭据；每个 ROM 按 rcheevos 规则计算 RA 哈希。1,185 个有成就的 RA 游戏中，**673 个本地有匹配 ROM**（共 914 个 ROM），No-Intro 收录的有成就游戏本地无一缺失；1 个只对应 No-Intro DB 中的坏 dump；无 No-Intro 对应的 511（Hack 440；Official 64，多为翻译补丁版或 Subset）。

## 中文名

4,154 条记录中 3,942 条有中文（2,030 个唯一中文名）；直接匹配 3,864 个发行版本，组内继承 73 个；本地 ROM 3,909 个。

## 使用与扩展

只需 Python 3.10+ 标准库。用库内引擎审计 Catalog：

```bash
python3 -B -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); s=c.execute("SELECT content FROM resources WHERE name=?",("engine.py",)).fetchone()[0]; c.close(); exec(compile(s,"RetroBoxDB:engine.py","exec"))' ./RetroBoxDB.SNES.Catalog.sqlite audit
```

`tools/build_cart_db.py` 从本地 No-Intro 输入构建完整库与 Catalog；`tools/update_cart_db.py --discover --ra` 增量加入新 DAT、DB Export／Dump Log 与 ROM（幂等），新修订版会重打包进同族实体组。完整库审计：4,297 objects, 145 solid groups, 4,813 archive plans，全部通过。
