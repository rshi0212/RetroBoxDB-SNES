# RetroBoxDB 存储 v4：NES／SNES／Mega Drive／Game Boy／Game Boy Color／Game Boy Advance／Famicom Disk System

[English](RetroBoxDB.Storage-v4.en.md) | [Technical design](RetroBoxDB.Storage-v4.Technical-Design.en.md)

七个平台各有一个完整库（含 ROM 数据，只保存在本地）和一个公开 Catalog（只含元数据）。七个库使用同一份引擎和同一种存储格式（v4），各平台在块大小、组上限、头部解析和导入路径上的差异由库内 `meta` 参数和平台适配代码表达。原始大小包括 No-Intro 目录和 RetroAchievements 整理的 ROM 目录（见“导入内容”）。

| 平台 | 原始大小（ZIP／解压后 ROM） | 完整库 | 比例（相对 ZIP／ROM） | Catalog | 单个 ROM（冷缓存） | 单个 TorrentZip（冷缓存） | 按 DAT 整套导出 |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| NES | 4.35 GiB／11.18 GiB | 536.8 MiB | 12.1%／4.7% | 145.1 MiB | 2.325 s | 1.983 s | 71.7 MiB/s（7,090 个文件） |
| SNES | 6.06 GiB／10.90 GiB | 1.76 GiB | 29.1%／16.2% | 53.7 MiB | 1.094 s | 1.397 s | 28.0 MiB/s（4,261 个文件） |
| Mega Drive | 4.66 GiB／9.61 GiB | 998.5 MiB | 20.9%／10.2% | 44.7 MiB | 1.734 s | 2.087 s | 18.8 MiB/s（3,398 个文件） |
| Game Boy | 401.1 MiB／1.05 GiB | 177.7 MiB | 44.3%／16.5% | 35.5 MiB | 1.594 s | 1.812 s | 41.0 MiB/s（2,232 个文件） |
| Game Boy Color | 1.38 GiB／4.42 GiB | 522.2 MiB | 37.1%／11.5% | 45.5 MiB | 1.719 s | 1.857 s | 56.2 MiB/s（2,503 个文件） |
| Game Boy Advance | 21.20 GiB／44.24 GiB | 7.01 GiB | 33.1%／15.9% | 57.8 MiB | 2.413 s | 2.682 s | 25.1 MiB/s（3,676 个文件） |
| Famicom Disk System | 33.8 MiB／82.7 MiB | 21.1 MiB | 62.5%／25.6% | 9.5 MiB | 0.364 s | 0.334 s | 30.4 MiB/s（405 个文件） |

Catalog 从新的 SQLite 文件建立，`compression_groups`、`chunks`、`object_chunks` 三张表为空，不含 ROM 数据、DAT／DB／Dump Log 原文件或压缩数据。导出性能为本机（Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz，Python 3.14）在空闲负载下的实测，导出过程包含全部校验：

- **单个文件（冷缓存）**：固定种子随机抽取 100 个 ROM 和 50 个 TorrentZip，每次导出前清空引擎缓存。耗时主要来自解压所在实体组中该文件之前的部分，组越大耗时越长，这是选择大组换取压缩率的代价。
- **按 DAT 整套导出**：用 `tools/export_set.py` 把最新 DAT 的全部游戏导出为裸 ROM（NES 用有头 DAT，FDS 用 FDS 格式），按存储顺序读取、批量缓存（最多 2 GiB，整组解压），每个文件按 DAT 的全部哈希校验，哈希与写文件在线程池中进行，结束时统一落盘一次；计时含进程启动和筛选。单文件导出（`engine.py export`）则每个文件写完即 `fsync`。

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
| Famicom Disk System (全集) | 33.7 | — | 64 KiB / 128 MiB | 10.1 |

真实全量数据上，相对基准组的压缩后大小变化；最后一列为采用的组上限应用到整个库后的实测结果：

| 平台 | 测量数据 | 64 MiB | 128 MiB | 256 MiB | 512 MiB | 采用 | 全库实测（组数，大小变化） |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| NES | 按族排序的全部 43 个组，1,289 MiB | −1.40% | −2.59% | −5.66% | — | 256 MiB | 43 → 6，−5.66% |
| SNES | 按族排序的前 16 个组，484 MiB | −0.24% | −0.51% | −0.78% | — | 128 MiB | 145 → 37，−0.50% |
| Mega Drive | 按族排序的前 16 个组，472 MiB | −1.74% | −1.99% | −2.64% | — | 256 MiB | 143 → 17，−3.90% |
| Game Boy | 全部 18 个组，551 MiB | −1.31% | −2.36% | −3.73% | — | 256 MiB | 18 → 3，−3.73% |
| Game Boy Color | 按族排序的前 16 个组，487 MiB | −1.04% | −1.56% | −2.65% | — | 256 MiB | 77 → 10，−2.88% |
| Game Boy Advance | 按族排序的前 8 个组，956 MiB；512 MiB 超过 256 MiB 工程上限 | — | 基准 | −2.08% | −3.29% | 256 MiB | 210 → 104，−1.90% |
| Famicom Disk System | 全集，64 KiB 块，77 MiB（128 MiB 起为一个组） | −1.15% | −4.75% | −4.75% | — | 128 MiB | — |

基准组：NES、SNES、MD、GB、GBC、FDS 为 32 MiB，GBA 为 128 MiB。FDS 直接以 128 MiB 构建（全平台一个组），没有重打包。

其他实测结论：

- **BCJ 过滤器**：xz 提供的 ARM、ARM-Thumb 过滤器只适用于 GBA。在 6 个真实 128 MiB 组上，ARM-Thumb 使结果增大 2.35%，ARM 增大 0.73%，因此不用。其余平台的 CPU（6502、65816、68000、SM83）没有对应过滤器。
- **LZMA 参数**：lc／lp／pb 的各种组合差异小于 0.2%，统一使用 lc3／lp0／pb0、BT4、nice_len 273。
- **zstd**：以母版为字典的差分比 LZMA 方案大 8–16%，且标准库 `compression.zstd` 要求 Python 3.14，而工具以 Python 3.10+ 标准库为目标，未采用。
- **NES**：迁移到 v4：8 KiB 块（按头部、trainer、PRG、CHR 边界切分），256 MiB 组。全库实测，v3 载荷（489 个 lzma2-4m 组加 XOR 差分散块，382,082,581 字节）变为 344,223,238 字节（−9.91%）；真实数据曲线相对 32 MiB 组为 64 MiB −1.40%、128 MiB −2.59%、256 MiB −5.66%，较小的组都比 256 MiB 大 0.5% 以上，按规则取 256 MiB。
- **FDS**：64 KiB 块（每面一块），全平台一个 128 MiB 组：合计 10.055 MiB，原 ZIP 33.72 MiB，逐文件 LZMA 28.21 MiB。单组时各种块大小压缩后都约 9.9 MiB，块越小元数据越多；64 MiB 组会拆成两组（+3.8%）。按面切块不改变压缩大小，但能让有头、无头版本的同一面去重。

## 存储格式 v4

- ROM 数据切成固定大小的块并按 SHA256 去重，块按 No-Intro 游戏族顺序装入 `lzma2-solid` 实体组；块大小、组上限和字典大小记录在每个库的 `meta` 中。
- 每个块保留 ID、大小和 SHA256；对象按块拼接，导出时核对完整的 CRC32、MD5、SHA1、SHA256。
- 读取时只解压到所需位置，每个块仍单独核对 SHA256。解码缓存为两个组大小；块分布在多个组中的对象（如多合一卡带）按组读取，每组只解压一次；审计和批量导出时缓存放宽到不超过 2 GiB（且不超过全部组的解压后总量），并整组解压，不保留未完成解码器的字典窗口。
- NES 保留 16 字节头部与正文分开存储、有头和无头版本共用正文的结构，块按头部、PRG、CHR 边界对齐（8 KiB）。
- 源 ZIP 只保留原始校验值，导出时由 TorrentZip 配方重新生成。七个库共 49,581 个源 ZIP（No-Intro 与 RetroAchievements 集合，均为 TorrentZip），其中 49,581 个经核对可逐字节重建（`v_file_checksums.exported_bytes_equal_source`）。
- 格式标记为 `user_version=4`。v3 引擎无法打开 v4 库；v4 引擎可以读取 v2、v3、v4。

| 平台 | 块 | 组上限／字典 | 组数 | 去重后原始块 → 压缩后 |
| --- | ---: | ---: | ---: | --- |
| NES | 8 KiB | 256 MiB | 9 | 1.35 GiB → 344.7 MiB |
| SNES | 64 KiB | 128 MiB | 57 | 5.38 GiB → 1.70 GiB |
| Mega Drive | 64 KiB | 256 MiB | 20 | 4.07 GiB → 940.5 MiB |
| Game Boy | 64 KiB | 256 MiB | 5 | 631.2 MiB → 139.5 MiB |
| Game Boy Color | 64 KiB | 256 MiB | 13 | 2.40 GiB → 469.2 MiB |
| Game Boy Advance | 1 MiB | 256 MiB | 123 | 27.43 GiB → 6.95 GiB |
| Famicom Disk System | 64 KiB | 128 MiB | 1 | 78.8 MiB → 10.2 MiB |

## 导入内容

来源集合（`source_collections`，按目录登记；ZIP 成员继承所在 ZIP 的路径）：

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No-Intro（ZIP／大小） | 21,792／4.12 GiB | 4,898／3.99 GiB | 5,281／3.93 GiB | 2,671／295.8 MiB | 3,006／1.06 GiB | 3,946／14.42 GiB | 720／32.4 MiB |
| RetroAchievements 集合（ZIP／大小） | 1,969／229.8 MiB | 1,836／2.07 GiB | 934／753.3 MiB | 720／105.3 MiB | 575／326.7 MiB | 1,206／6.78 GiB | 27／1.4 MiB |

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 本地 ZIP | 23,761 | 6,734 | 6,215 | 3,391 | 3,581 | 5,152 | 747 |
| ROM 记录 | 18,414 | 5,239 | 3,959 | 2,538 | 2,784 | 4,143 | 703 |
| 游戏组／发行版本 | 3,477／7,385 | 1,996／4,329 | 1,581／3,503 | 1,419／2,299 | 1,576／2,622 | 1,901／3,750 | 307／408 |
| 不在任何 DAT 的本地 ROM | 2,849 | 978 | 561 | 306 | 279 | 467 | 9 |

每个平台本地现有的全部 Parent-Clone DAT 版本都导入并分别扫描；`dat_changes` 记录旧版本相对最新版的逐条差异，旧 DAT 条目通过差异关系挂到最新 DAT 的同一发行版本。

- **NES**（2 个 DAT）：20260713-141345：7,100/7,288；20261002-002752：7,095/7,390
- **SNES**（2 个 DAT）：20260710-203222：4,255/4,318；20261003-140326：4,261/4,331
- **Mega Drive**（2 个 DAT）：20260714-063411：3,398/3,486；20260927-122056：3,398/3,504
- **Game Boy**（4 个 DAT）：20260602-070215：2,225/2,276；20260707-013717：2,226/2,284；20260814-115131：2,230/2,292；20261001-130150：2,232/2,299
- **Game Boy Color**（5 个 DAT）：20260602-074724：2,502/2,604；20260713-134329：2,503/2,612；20260715-062319：2,503/2,612；20260814-104253：2,503/2,614；20261001-131920：2,503/2,622
- **Game Boy Advance**（4 个 DAT）：20260531-074517：3,676/3,745；20260707-143610：3,676/3,748；20260812-060017：3,676/3,749；20260929-130236：3,676/3,750
- **Famicom Disk System**（3 个 DAT）：20260517-061737：405/407；20260617-195332：295/296；20260930-033941：294/295

游戏组与发行版本取自最新 DAT 的 Parent／Clone，不推测发行字段。同一平台有多种 DAT 格式时（NES 有头／无头，FDS 的 FDS／QD），各格式分别与本格式的旧版本做差异；主格式（列表第一个）建立游戏与发行版本，其他格式的条目挂到同名的主格式发行版本，没有同名的挂到其 Parent 所在游戏下。ROM 目录中的非 ZIP 文件（GB 目录中前端使用的 `metadata.txt`／`systeminfo.txt`）作为 `metadata` 文件保存。

RetroAchievements 整理的 ROM 目录（`/mnt/MyShare/RetroAchievements/RA - <平台>`）按与 No-Intro 目录相同的方式去重入库：已在库中的 ROM 只增加文件记录和来源关联，新 ROM（Hack、翻译版、自制游戏、No-Intro 未收录的版本等）按块去重后存入。不在任何 DAT 中的 ROM 归入与它共享块最多的已存 ROM 所在的游戏族（`object_families.basis='shared_blocks'`，多数 Hack 与原版同族，压缩时排在一起），没有共享块的按文件名标题归族。NES 的 RA 目录中混有 FDS 磁碟镜像，导入 NES 时跳过并列入报告，由 FDS 库导入；SNES 的 RA 目录中的 Satellaview（BS-X，`.bs`）文件属于独立平台，导入 SNES 时同样跳过并列入报告，留待以后单独建库。

## 内部头部

解析只作描述，不修改任何字节；头部声明不等同于实物硬件证据。解析结果：NES 有效 10,265／告警 64／未识别 8,083；SNES 有效 3,946／告警 1,089／未识别 204；Mega Drive 有效 2,055／告警 1,841／未识别 63；Game Boy 有效 2,278／告警 256／未识别 4；Game Boy Color 有效 2,425／告警 358／未识别 1；Game Boy Advance 有效 4,025／告警 104／未识别 14；Famicom Disk System 有效 671／告警 25／未识别 7。

- **NES**（`nes_hardware`、`nes_recipes`）：iNES／NES 2.0 头部字段；头部与正文分开保存，有头、无头版本共用正文。
- **SNES**（`snes_hardware`、`v_snes_headers`）：在 LoROM、HiROM、ExLoROM、ExHiROM 四处按校验和互补、映射模式、标题、ROM 大小字节、复位向量打分选择位置，分数不足的记为 `unclassified`；512 字节 copier 头单独切块。
- **Mega Drive**（`md_hardware`、`v_md_headers`）：0x100 头部与整文件校验和；识别 SMD 交错格式但原样保存。
- **Game Boy／Game Boy Color**（`gb_hardware`、`v_gb_headers`）：0x100–0x14F 卡带头，含 CGB／SGB 标志、MBC 类型、头部校验和与全局校验和；Nintendo Logo 只保存 SHA1。
- **Game Boy Advance**（`gba_hardware`、`v_gba_headers`）：0x00–0xBF 卡带头、补码校验、存档库标识、末尾填充长度。
- **Famicom Disk System**（`fds_hardware`、`v_fds_headers`）：识别 FDS（每面 65,500 字节）、QD（每面 65,536 字节，块后带 CRC）和 BIOS（8 KiB），以及可选的 16 字节 fwNES 头；逐面解析磁碟信息块（厂商代码、3 字符游戏代码、游戏类型、修订号、面号、盘号、BCD 制造日期、国家代码）和文件数量块，每面的值存于 `sides_json`。块在 fwNES 头和每面边界处重新起算，有头与无头版本、共用某一面的修订版可以按面去重。

## No-Intro DB Export 与 Dump Log

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 快照 | 20261002-002752 | 20261003-140326 | 20260927-122056 | 20261001-130150 | 20261001-131920 | 20260929-130236 | 20260930-033941 |
| 档案／文件身份 | 7,704／16,154 | 4,365／5,457 | 3,640／4,142 | 2,335／2,450 | 2,678／2,921 | 3,793／4,563 | 408／1,437 |
| 有本地正文的文件 | 14,885 | 4,276 | 3,537 | 2,248 | 2,514 | 3,713 | 701 |
| 有文档的硬件声明 | 6,412 | 5,399 | 2,017 | 2,810 | 2,830 | 3,188 | 8 |
| Dump Log：Verified／Trusted 未验证／未验证 | 2,794／3,814／1,028 | 1,871／1,708／736 | 868／2,085／615 | 719／1,118／490 | 448／1,521／703 | 770／1,703／1,307 | 7／262／136 |

NES 使用自己的导入器（重建 16 字节头、核对有头／无头配对）；其余平台使用 `nointro_db.py`。FDS 的 DB Export 同时含 FDS 和 QD 文件，Dump Log 只有 FDS 格式。缺少 SHA256 的文件保持为空并记入 `ni_anomalies`。

## RetroAchievements 成就匹配

`ra_snapshots`、`ra_games`、`ra_hashes` 保存 RA 公开 API（`API_GetGameList`）的快照，原始响应存为 resource；API 密钥只在运行时读取，不写入库、报告或日志。每个 ROM 的 RA 哈希按 rcheevos 规则计算并保存在 `rom_ra_hashes`：NES 为去掉 16 字节头后的正文 MD5，FDS 在有 fwNES 头时去掉 16 字节头，SNES 在大小 %8192 = 512 时先去掉 512 字节头，其余平台为整文件 MD5。只做精确哈希匹配。主机 ID：NES 7、SNES 3、MD 1、GB 4、GBC 6、GBA 5、FDS 81。

`v_ra_collection` 列出 RA 集合中每个 ROM 文件对应的 RA 游戏、No-Intro DAT 条目和发行版本，状态分为 `in_nointro_dat`（DAT 中有）、`ra_only`（只有 RA 收录）和 `ra_hash_unknown`（最新 RA 快照中没有该哈希）。`reports/ra-<平台>-games.csv` 的 `local_sources` 列给出每个 RA 游戏的本地 ROM 来自哪些来源集合，`reports/ra-<平台>-collection-unknown.csv` 列出哈希未知的文件，`reports/ra-<平台>-missing.csv` 列出仍没有本地 ROM 的 RA 游戏（缺口清单）。

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 有成就的 RA 游戏 | 1,123 | 1,185 | 613 | 505 | 419 | 775 | 38 |
| 本地有匹配 ROM | 1,110 | 1,089 | 606 | 492 | 402 | 750 | 34 |
| 仅 DAT 有（本地缺） | 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| 仅 DB Export 文件 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| 无 No-Intro 对应（其中 Hack） | 13 (9) | 96 (62) | 7 (5) | 13 (5) | 16 (3) | 23 (12) | 3 (1) |
| 本地有成就的 ROM | 3,385 | 1,845 | 942 | 725 | 584 | 1,230 | 47 |

“无 No-Intro 对应”指 RA 游戏的哈希既不对应本地 ROM 也不对应 DAT 条目，主要是 Hack、翻译补丁版、Subset 和 No-Intro 未收录的版本；导入 RA 集合后其中大部分已由本地 ROM 覆盖，剩余的是本地没有文件的游戏。“仅 DAT 有”是 DAT 中有但本地缺少的 ROM。逐游戏清单见 `reports/ra-<平台>-games.csv`。

## 中文名

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV 记录／含中文／唯一中文名 | 4,453／3,703／1,875 | 4,154／3,942／2,030 | 2,869／2,694／1,226 | 1,974／1,816／1,237 | 2,124／1,763／1,156 | 3,522／3,410／1,882 | 404／404／296 |
| 已确认／待消歧／无候选 | 4,420／22／11 | 4,099／10／45 | 2,715／58／96 | 1,956／0／18 | 1,945／7／172 | 3,444／26／52 | 403／1／0 |
| 有中文名的发行版本（直接＋继承） | 3,698 + 389 | 3,864 + 73 | 2,550 + 117 | 1,803 + 59 | 1,590 + 110 | 3,315 + 47 | 402 + 4 |
| 有中文名的本地 ROM | 8,104 | 3,909 | 2,656 | 1,835 | 1,663 | 3,350 | 692 |

## 信息分层与扩展

`v_information_sources` 视图列出每个库的全部信息来源及版本：

- **已有信息**：No-Intro DAT 各版本、ROM 文件、来源集合（No-Intro、RetroAchievements）；
- **扩展信息**：No-Intro DB Export／Dump Log 快照、RA 快照、中英文名称来源、有文档的硬件声明；
- **未来信息**：Batocera／ScreenScraper 前端字段、媒体槽位、刮削记录，目前为占位。

每类信息都以带来源、版本和时间戳的快照导入，重复导入不产生重复记录，新版本作为新快照追加，旧快照保留。

## 导出

`tools/export_set.py` 可以从完整库按以下维度组合导出：

- **DAT 版本**：任一已导入版本；NES 另选有头／无头，FDS 另选 FDS／QD 格式（`--dat-format`）；
- **集合**：全部、仅母版、1G1R（可指定地区优先级，并优先选有 RA 成就的版本）；
- **RA 筛选**：不限、仅有成就、仅无成就，并可按 RA 分类筛选；
- **名称**：按正则包含或排除；
- **容器**：TorrentZip 或裸 ROM；
- **目录结构**：平铺、按母版、按 RA 分类、按地区。

每个成员按 DAT 的全部哈希核对，TorrentZip 与库中登记的配方核对，`export-manifest.json` 记录筛选条件和每个文件的校验值。

## 增量维护

- **新 ROM**：`update_db.py --discover` 扫描 No-Intro 与 RetroAchievements 目录，只读 ZIP 中央目录判断文件是否已入库；属于其他平台的文件（如 NES 目录中的 FDS 镜像）跳过并列入报告。新 ROM 先按普通块写入并记录游戏族，再由 `compact_solid` 合入该族最新的实体组（组内有空间时解压、追加、重新编码），否则新建族排序实体组。NES 在 No-Intro 有头／无头目录按目录声明导入，其他目录逐文件识别。
- **去重校验**：新块与已存块 SHA-256 相同时，若已存块是散块或其所在组已在缓存中解压，则逐字节比较；否则以 SHA-256 为身份，组的完整性由打包时的往返解码和每次审计保证。新 ZIP 的 TorrentZip 配方由刚导入的成员字节计算，不再从实体组回读。在 NES 上这使 RA 集合（1,969 个 ZIP）的导入从 27 分钟降到约 3.5 分钟，DAT 打包也不再回读成员。
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

`resources` 中的 `engine.py` 等是可执行代码，只应从自己构建或 SHA256 已核对的 Release 附件中执行。公开 Catalog 保留文件的原始路径（`files.source_path`）作为溯源信息。全量审计：NES 19,069 个对象／9 个组／25,368 个 ZIP 配方；SNES 5,243 个对象／57 个组／5,774 个 ZIP 配方；Mega Drive 3,963 个对象／20 个组／5,367 个 ZIP 配方；Game Boy 2,546 个对象／5 个组／2,776 个 ZIP 配方；Game Boy Color 2,791 个对象／13 个组／2,931 个 ZIP 配方；Game Boy Advance 4,149 个对象／123 个组／4,396 个 ZIP 配方；Famicom Disk System 712 个对象／1 个组／728 个 ZIP 配方，全部通过。
