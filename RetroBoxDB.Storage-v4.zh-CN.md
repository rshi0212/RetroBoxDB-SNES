# RetroBoxDB 存储 v4：NES／SNES／Mega Drive／Game Boy／Game Boy Color／Game Boy Advance

[English](RetroBoxDB.Storage-v4.en.md) | [Technical design](RetroBoxDB.Storage-v4.Technical-Design.en.md)

六个平台各有一个完整库（含 ROM 数据，只保存在本地）和一个公开 Catalog（只含元数据）。六个库使用同一份引擎和同一种存储格式（v4），各平台在块大小、组上限、头部解析和导入路径上的差异由库内 `meta` 参数和平台适配代码表达。

| 平台 | 原始大小（ZIP／解压后 ROM） | 完整库 | 比例（相对 ZIP／ROM） | Catalog | 单个 ROM（冷缓存） | 单个 TorrentZip（冷缓存） | 全集合顺序导出 |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| NES | 4.12 GiB／10.69 GiB | 506.2 MiB | 12.0%／4.6% | 138.7 MiB | 2.339 s | 2.216 s | 54.1 MiB/s（22,943 个文件） |
| SNES | 3.99 GiB／6.97 GiB | 1.54 GiB | 38.5%／22.0% | 48.5 MiB | 1.099 s | 1.402 s | 20.6 MiB/s（4,898 个文件） |
| Mega Drive | 3.93 GiB／8.25 GiB | 936.4 MiB | 23.3%／11.1% | 42.5 MiB | 1.752 s | 1.986 s | 21.4 MiB/s（5,282 个文件） |
| Game Boy | 295.8 MiB／820.0 MiB | 164.4 MiB | 55.6%／20.0% | 33.6 MiB | 1.669 s | 1.537 s | 33.2 MiB/s（2,672 个文件） |
| Game Boy Color | 1.06 GiB／3.50 GiB | 504.1 MiB | 46.6%／14.1% | 44.2 MiB | 1.676 s | 1.923 s | 26.5 MiB/s（3,006 个文件） |
| Game Boy Advance | 14.42 GiB／30.92 GiB | 5.51 GiB | 38.2%／17.8% | 54.7 MiB | 2.374 s | 2.751 s | 22.2 MiB/s（3,946 个文件） |

Catalog 从新的 SQLite 文件建立，`compression_groups`、`chunks`、`object_chunks` 三张表为空，不含 ROM 数据、DAT／DB／Dump Log 原文件或压缩数据。导出性能为本机（Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz，Python 3.14）在空闲负载下的实测，导出过程包含全部校验：

- **单个文件（冷缓存）**：固定种子随机抽取 100 个 ROM 和 50 个 TorrentZip，每次导出前清空引擎缓存。耗时主要来自解压所在实体组中该文件之前的部分，组越大耗时越长，这是选择大组换取压缩率的代价。
- **全集合顺序导出**：按存储顺序把库中每个 ROM 文件各导出一次，使用批量缓存，每个组只解压一次；对应按 DAT 版本、RA、1G1R 等条件批量导出的场景。

## 存储方案的评估方法

每个平台单独评估，依据如下：

1. **抽样网格**：按 No-Intro Parent／Clone 游戏族随机抽样（种子 2026），比较块大小 × 组上限的组合，并原样运行 NES v3 引擎作对照。
2. **真实全量数据曲线**：把库中按游戏族排好的相邻组合并后重新压缩，测 32→256 MiB 各级组的收益。抽样会低估跨游戏族的相似内容（同一引擎、同一系列），所以以真实数据为准。
3. **选型规则**：取压缩后大小与 256 MiB 组相差不到 0.5% 的最小组；256 MiB 是工程上限（再大则每个编码进程约需 6 GB 内存，平均每次读取需解压约 256 MiB）。

抽样结果（MiB，含块元数据估算；组大小随后按真实数据曲线确定）：

| 平台 | 样本 ZIP | NES v3 引擎原样 | v4 抽样最佳（块／组） | v4 大小 |
| --- | ---: | ---: | --- | ---: |
| NES | 652.6 | 91.8 | 8 KiB / 128 MiB | 81.9 |
| SNES | 443.2 | 238.9 | 64 KiB / 32 MiB | 191.0 |
| Mega Drive | 408.2 | 216.9 | 64 KiB / 32 MiB | 145.7 |
| Game Boy | 48.9 | 31.6 | 64 KiB / 32 MiB | 26.1 |
| Game Boy Color | 206.5 | 126.7 | 64 KiB / 32 MiB | 104.2 |
| Game Boy Advance | 602.8 | — | 1 MiB / 128 MiB | 228.0 |

真实全量数据上，相对基准组的压缩后大小变化；最后一列为采用的组上限应用到整个库后的实测结果：

| 平台 | 测量数据 | 64 MiB | 128 MiB | 256 MiB | 512 MiB | 采用 | 全库实测（组数，大小变化） |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| NES | 按族排序的全部 43 个组，1,289 MiB | −1.40% | −2.59% | −5.66% | — | 256 MiB | 43 → 6，−5.66% |
| SNES | 按族排序的前 16 个组，484 MiB | −0.24% | −0.51% | −0.78% | — | 128 MiB | 145 → 37，−0.50% |
| Mega Drive | 按族排序的前 16 个组，472 MiB | −1.74% | −1.99% | −2.64% | — | 256 MiB | 143 → 17，−3.90% |
| Game Boy | 全部 18 个组，551 MiB | −1.31% | −2.36% | −3.73% | — | 256 MiB | 18 → 3，−3.73% |
| Game Boy Color | 按族排序的前 16 个组，487 MiB | −1.04% | −1.56% | −2.65% | — | 256 MiB | 77 → 10，−2.88% |
| Game Boy Advance | 按族排序的前 8 个组，956 MiB；512 MiB 超过 256 MiB 工程上限 | — | 基准 | −2.08% | −3.29% | 256 MiB | 210 → 104，−1.90% |

基准组：NES、SNES、MD、GB、GBC 为 32 MiB，GBA 为 128 MiB。

其他实测结论：

- **BCJ 过滤器**：xz 提供的 ARM、ARM-Thumb 过滤器只适用于 GBA。在 6 个真实 128 MiB 组上，ARM-Thumb 使结果增大 2.35%，ARM 增大 0.73%，因此不用。其余平台的 CPU（6502、65816、68000、SM83）没有对应过滤器。
- **LZMA 参数**：lc／lp／pb 的各种组合差异小于 0.2%，统一使用 lc3／lp0／pb0、BT4、nice_len 273。
- **zstd**：以母版为字典的差分比 LZMA 方案大 8–16%，且标准库 `compression.zstd` 要求 Python 3.14，而工具以 Python 3.10+ 标准库为目标，未采用。
- **NES**：迁移到 v4：8 KiB 块（按头部、trainer、PRG、CHR 边界切分），256 MiB 组。全库实测，v3 载荷（489 个 lzma2-4m 组加 XOR 差分散块，382,082,581 字节）变为 344,223,238 字节（−9.91%）；真实数据曲线相对 32 MiB 组为 64 MiB −1.40%、128 MiB −2.59%、256 MiB −5.66%，较小的组都比 256 MiB 大 0.5% 以上，按规则取 256 MiB。

## 存储格式 v4

- ROM 数据切成固定大小的块并按 SHA256 去重，块按 No-Intro 游戏族顺序装入 `lzma2-solid` 实体组；块大小、组上限和字典大小记录在每个库的 `meta` 中。
- 每个块保留 ID、大小和 SHA256；对象按块拼接，导出时核对完整的 CRC32、MD5、SHA1、SHA256。
- 读取时只解压到所需位置，每个块仍单独核对 SHA256。解码缓存为两个组大小；块分布在多个组中的对象（如多合一卡带）按组读取，每组只解压一次；审计和批量导出时缓存放宽到不超过 2 GiB（且不超过全部组的解压后总量），并整组解压，不保留未完成解码器的字典窗口。
- NES 保留 16 字节头部与正文分开存储、有头和无头版本共用正文的结构，块按头部、PRG、CHR 边界对齐（8 KiB）。
- 源 ZIP 只保留原始校验值，导出时由 TorrentZip 配方重新生成。六个库的 41,594 个源 ZIP 全部能逐字节重建（`v_file_checksums.exported_bytes_equal_source`）。
- 格式标记为 `user_version=4`。v3 引擎无法打开 v4 库；v4 引擎可以读取 v2、v3、v4。

| 平台 | 块 | 组上限／字典 | 组数 | 去重后原始块 → 压缩后 |
| --- | ---: | ---: | ---: | --- |
| NES | 8 KiB | 256 MiB | 6 | 1.28 GiB → 328.3 MiB |
| SNES | 64 KiB | 128 MiB | 37 | 4.25 GiB → 1.48 GiB |
| Mega Drive | 64 KiB | 256 MiB | 17 | 3.87 GiB → 882.3 MiB |
| Game Boy | 64 KiB | 256 MiB | 3 | 558.1 MiB → 128.3 MiB |
| Game Boy Color | 64 KiB | 256 MiB | 10 | 2.26 GiB → 453.3 MiB |
| Game Boy Advance | 1 MiB | 256 MiB | 104 | 23.72 GiB → 5.45 GiB |

## 导入内容

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 本地 ZIP | 21,792 | 4,898 | 5,281 | 2,671 | 3,006 | 3,946 |
| ROM 记录 | 17,726 | 4,293 | 3,687 | 2,315 | 2,605 | 3,734 |
| 游戏组／发行版本 | 3,477／7,385 | 1,996／4,329 | 1,581／3,503 | 1,419／2,299 | 1,576／2,622 | 1,901／3,750 |
| 不在任何 DAT 的本地 ROM | 2,194 | 32 | 289 | 91 | 137 | 58 |

每个平台本地现有的全部 Parent-Clone DAT 版本都导入并分别扫描；`dat_changes` 记录旧版本相对最新版的逐条差异，旧 DAT 条目通过差异关系挂到最新 DAT 的同一发行版本。

- **NES**（2 个 DAT）：20260713-141345：7,100/7,288；20261002-002752：7,094/7,390
- **SNES**（2 个 DAT）：20260710-203222：4,255/4,318；20261003-140326：4,261/4,331
- **Mega Drive**（2 个 DAT）：20260714-063411：3,398/3,486；20260927-122056：3,398/3,504
- **Game Boy**（4 个 DAT）：20260602-070215：2,218/2,276；20260707-013717：2,218/2,284；20260814-115131：2,222/2,292；20261001-130150：2,224/2,299
- **Game Boy Color**（5 个 DAT）：20260602-074724：2,467/2,604；20260713-134329：2,467/2,612；20260715-062319：2,467/2,612；20260814-104253：2,467/2,614；20261001-131920：2,466/2,622
- **Game Boy Advance**（4 个 DAT）：20260531-074517：3,676/3,745；20260707-143610：3,676/3,748；20260812-060017：3,676/3,749；20260929-130236：3,676/3,750

游戏组与发行版本取自最新 DAT 的 Parent／Clone，不推测发行字段。ROM 目录中的非 ZIP 文件（GB 目录中前端使用的 `metadata.txt`／`systeminfo.txt`）作为 `metadata` 文件保存。

## 内部头部

解析只作描述，不修改任何字节；头部声明不等同于实物硬件证据。解析结果：NES 有效 9,623／告警 28／未识别 8,075；SNES 有效 3,463／告警 629／未识别 201；Mega Drive 有效 1,883／告警 1,742／未识别 62；Game Boy 有效 2,115／告警 196／未识别 4；Game Boy Color 有效 2,296／告警 308／未识别 1；Game Boy Advance 有效 3,637／告警 86／未识别 11。

- **NES**（`nes_hardware`、`nes_recipes`）：iNES／NES 2.0 头部字段；头部与正文分开保存，有头、无头版本共用正文。
- **SNES**（`snes_hardware`、`v_snes_headers`）：在 LoROM、HiROM、ExLoROM、ExHiROM 四处按校验和互补、映射模式、标题、ROM 大小字节、复位向量打分选择位置，分数不足的记为 `unclassified`；512 字节 copier 头单独切块。
- **Mega Drive**（`md_hardware`、`v_md_headers`）：0x100 头部与整文件校验和；识别 SMD 交错格式但原样保存。
- **Game Boy／Game Boy Color**（`gb_hardware`、`v_gb_headers`）：0x100–0x14F 卡带头，含 CGB／SGB 标志、MBC 类型、头部校验和与全局校验和；Nintendo Logo 只保存 SHA1。
- **Game Boy Advance**（`gba_hardware`、`v_gba_headers`）：0x00–0xBF 卡带头、补码校验、存档库标识、末尾填充长度。

## No-Intro DB Export 与 Dump Log

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 快照 | 20261002-002752 | 20261003-140326 | 20260927-122056 | 20261001-130150 | 20261001-131920 | 20260929-130236 |
| 档案／文件身份 | 7,704／16,154 | 4,365／5,457 | 3,640／4,142 | 2,335／2,450 | 2,678／2,921 | 3,793／4,563 |
| 有本地正文的文件 | 14,885 | 4,276 | 3,537 | 2,248 | 2,514 | 3,713 |
| 有文档的硬件声明 | 6,412 | 5,399 | 2,017 | 2,810 | 2,830 | 3,188 |
| Dump Log：Verified／Trusted 未验证／未验证 | 2,794／3,814／1,028 | 1,871／1,708／736 | 868／2,085／615 | 719／1,118／490 | 448／1,521／703 | 770／1,703／1,307 |

NES 使用自己的导入器（重建 16 字节头、核对有头／无头配对）；其余五个平台的 DB 文件均为 `Default` 格式，使用 `nointro_db.py`。缺少 SHA256 的文件保持为空并记入 `ni_anomalies`。

## RetroAchievements 成就匹配

`ra_snapshots`、`ra_games`、`ra_hashes` 保存 RA 公开 API（`API_GetGameList`）的快照，原始响应存为 resource；API 密钥只在运行时读取，不写入库、报告或日志。每个 ROM 的 RA 哈希按 rcheevos 规则计算并保存在 `rom_ra_hashes`：NES 为去掉 16 字节头后的正文 MD5，SNES 在大小 %8192 = 512 时先去掉 512 字节头，其余平台为整文件 MD5。只做精确哈希匹配。主机 ID：NES 7、SNES 3、MD 1、GB 4、GBC 6、GBA 5。

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 有成就的 RA 游戏 | 1,123 | 1,185 | 612 | 505 | 419 | 774 |
| 本地有匹配 ROM | 933 | 673 | 520 | 394 | 327 | 581 |
| 仅 DAT 有（本地缺） | 1 | 0 | 0 | 2 | 8 | 2 |
| 仅 DB Export 文件 | 2 | 1 | 1 | 0 | 4 | 3 |
| 无 No-Intro 对应（其中 Hack） | 187 (133) | 511 (444) | 91 (67) | 109 (33) | 80 (20) | 188 (108) |
| 本地有成就的 ROM | 2,708 | 914 | 673 | 506 | 413 | 823 |

“无 No-Intro 对应”主要是 Hack、No-Intro 未收录的自制游戏、翻译补丁版和 Subset；“仅 DAT 有”是本地缺少的 ROM。逐游戏清单见 `reports/ra-<平台>-games.csv`。

## 中文名

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV 记录／含中文／唯一中文名 | 4,453／3,703／1,875 | 4,154／3,942／2,030 | 2,869／2,694／1,226 | 1,974／1,816／1,237 | 2,124／1,763／1,156 | 3,522／3,410／1,882 |
| 已确认／待消歧／无候选 | 4,420／22／11 | 4,099／10／45 | 2,715／58／96 | 1,956／0／18 | 1,945／7／172 | 3,444／26／52 |
| 有中文名的发行版本（直接＋继承） | 3,698 + 389 | 3,864 + 73 | 2,550 + 117 | 1,803 + 59 | 1,590 + 110 | 3,315 + 47 |
| 有中文名的本地 ROM | 8,100 | 3,909 | 2,656 | 1,829 | 1,639 | 3,350 |

## 信息分层与扩展

`v_information_sources` 视图列出每个库的全部信息来源及版本：

- **已有信息**：No-Intro DAT 各版本、ROM 文件；
- **扩展信息**：No-Intro DB Export／Dump Log 快照、RA 快照、中英文名称来源、有文档的硬件声明；
- **未来信息**：Batocera／ScreenScraper 前端字段、媒体槽位、刮削记录，目前为占位。

每类信息都以带来源、版本和时间戳的快照导入，重复导入不产生重复记录，新版本作为新快照追加，旧快照保留。

## 导出

`tools/export_set.py` 可以从完整库按以下维度组合导出：

- **DAT 版本**：任一已导入版本，NES 另选有头／无头；
- **集合**：全部、仅母版、1G1R（可指定地区优先级，并优先选有 RA 成就的版本）；
- **RA 筛选**：不限、仅有成就、仅无成就，并可按 RA 分类筛选；
- **名称**：按正则包含或排除；
- **容器**：TorrentZip 或裸 ROM；
- **目录结构**：平铺、按母版、按 RA 分类、按地区。

每个成员按 DAT 的全部哈希核对，TorrentZip 与库中登记的配方核对，`export-manifest.json` 记录筛选条件和每个文件的校验值。

## 增量维护

- **新 ROM**：`update_db.py` 只读 ZIP 中央目录判断文件是否已入库；新 ROM 先按普通块写入并记录游戏族，再由 `compact_solid` 合入该族最新的实体组（组内有空间时解压、追加、重新编码），否则新建族排序实体组。NES 使用其有头／无头导入路径。
- **新 DAT、DB Export／Dump Log、RA 快照、名称 CSV**：均可重复导入；新 DAT 与上一最新版做差异，新增条目挂到已有游戏或新建发行版本。
- **调整组大小**：`retune_db.py` 把相邻组合并到更大的上限并重新编码，块身份不变；`migrate_v4.py` 把 v3 库迁移到 v4。
- 所有修改在单个事务内完成，受影响的块逐一复核，失败整体回滚。

## 审计处理

2026-10-04 独立审计的处理结论见 [reports/audit-resolution-20261004.md](reports/audit-resolution-20261004.md)。

## 复现

只需 Python 3.10+ 标准库。

```bash
# 测试
python3 -B -m unittest tests/test_v4.py tests/test_game_names.py
# 用 Catalog 内嵌引擎做只读审计
python3 -B -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); s=c.execute("SELECT content FROM resources WHERE name=?",("engine.py",)).fetchone()[0]; c.close(); exec(compile(s,"RetroBoxDB:engine.py","exec"))' RetroBoxDB.GBA.Catalog.sqlite audit
# 从本地 No-Intro 输入构建（SNES、MD、GB、GBC、GBA）；NES 由迁移得到
python3 -B tools/build_db.py gba RetroBoxDB.GBA.sqlite --catalog RetroBoxDB.GBA.Catalog.sqlite
```

`resources` 中的 `engine.py` 等是可执行代码，只应从自己构建或 SHA256 已核对的 Release 附件中执行。公开 Catalog 保留文件的原始路径（`files.source_path`）作为溯源信息。全量审计：NES 17,734 个对象／6 个组／24,487 个 ZIP 配方；SNES 4,297 个对象／37 个组／4,813 个 ZIP 配方；Mega Drive 3,691 个对象／17 个组／5,044 个 ZIP 配方；Game Boy 2,323 个对象／3 个组／2,491 个 ZIP 配方；Game Boy Color 2,612 个对象／10 个组／2,679 个 ZIP 配方；Game Boy Advance 3,740 个对象／104 个组／3,940 个 ZIP 配方，全部通过。
