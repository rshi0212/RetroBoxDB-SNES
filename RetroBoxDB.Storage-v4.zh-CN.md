# RetroBoxDB 存储 v4：NES／SNES／Mega Drive／Game Boy／Game Boy Color／Game Boy Advance／Famicom Disk System／Satellaview／Master System／32X／WonderSwan／WonderSwan Color／NeoGeo Pocket／NeoGeo Pocket Color／Pokémon Mini／Game Gear／PC Engine／SuperGrafx／MSX／MSX2／Virtual Boy／Game & Watch／Super A'Can

[English](RetroBoxDB.Storage-v4.en.md) | [Technical design](RetroBoxDB.Storage-v4.Technical-Design.en.md)

23 个平台各有一个完整库（含 ROM 数据，只保存在本地）和一个公开 Catalog（只含元数据）。这些库使用同一份引擎和同一种存储格式（v4），各平台在块大小、组上限、头部解析和导入路径上的差异由库内 `meta` 参数和平台适配代码表达。原始大小包括 No-Intro 目录和 RetroAchievements 整理的 ROM 目录（见“导入内容”）。

| 平台 | 原始大小（ZIP／解压后 ROM） | 完整库 | 比例（相对 ZIP／ROM） | Catalog | 单个 ROM（冷缓存） | 单个 TorrentZip（冷缓存） | 按 DAT 整套导出 |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| NES | 4.35 GiB／11.18 GiB | 530.1 MiB | 11.9%／4.6% | 145.5 MiB | 2.325 s | 1.983 s | 71.7 MiB/s（7,090 个文件） |
| SNES | 6.06 GiB／10.90 GiB | 1.77 GiB | 29.1%／16.2% | 54.1 MiB | 1.094 s | 1.397 s | 28.0 MiB/s（4,261 个文件） |
| Mega Drive | 4.66 GiB／9.61 GiB | 999.0 MiB | 20.9%／10.2% | 45.1 MiB | 1.734 s | 2.087 s | 18.8 MiB/s（3,398 个文件） |
| Game Boy | 401.1 MiB／1.05 GiB | 178.2 MiB | 44.4%／16.5% | 35.9 MiB | 1.594 s | 1.812 s | 41.0 MiB/s（2,232 个文件） |
| Game Boy Color | 1.38 GiB／4.42 GiB | 522.6 MiB | 37.1%／11.5% | 45.9 MiB | 1.719 s | 1.857 s | 56.2 MiB/s（2,503 个文件） |
| Game Boy Advance | 21.20 GiB／44.24 GiB | 7.01 GiB | 33.1%／15.9% | 58.2 MiB | 2.413 s | 2.682 s | 25.1 MiB/s（3,676 个文件） |
| Famicom Disk System | 35.2 MiB／85.7 MiB | 22.1 MiB | 62.7%／25.8% | 10.3 MiB | 0.364 s | 0.334 s | 30.4 MiB/s（405 个文件） |
| Satellaview | 324.1 MiB／703.6 MiB | 116.1 MiB | 35.8%／16.5% | 10.7 MiB | 2.78 s | 2.613 s | 61.6 MiB/s（561 个文件） |
| Master System | 177.4 MiB／392.5 MiB | 84.9 MiB | 47.9%／21.6% | 19.0 MiB | 1.783 s | 1.799 s | 43.9 MiB/s（1,189 个文件） |
| 32X | 593.1 MiB／1.09 GiB | 87.9 MiB | 14.8%／7.8% | 3.9 MiB | 1.524 s | 1.707 s | 69.9 MiB/s（219 个文件） |
| WonderSwan | 150.5 MiB／383.0 MiB | 81.4 MiB | 54.1%／21.3% | 4.0 MiB | 2.225 s | 2.433 s | 53.2 MiB/s（257 个文件） |
| WonderSwan Color | 246.6 MiB／659.1 MiB | 126.7 MiB | 51.4%／19.2% | 4.0 MiB | 1.226 s | 1.398 s | 54.2 MiB/s（253 个文件） |
| NeoGeo Pocket | 5.3 MiB／13.7 MiB | 6.3 MiB | 120.3%／46.2% | 1.8 MiB | 0.091 s | 0.186 s | 29.5 MiB/s（13 个文件） |
| NeoGeo Pocket Color | 93.0 MiB／261.8 MiB | 38.2 MiB | 41.1%／14.6% | 3.7 MiB | 0.943 s | 1.184 s | 52.5 MiB/s（128 个文件） |
| Pokémon Mini | 8.9 MiB／35.9 MiB | 5.1 MiB | 57.3%／14.2% | 2.2 MiB | 0.074 s | 0.118 s | 47.6 MiB/s（46 个文件） |
| Game Gear | 254.2 MiB／501.3 MiB | 80.0 MiB | 31.5%／16.0% | 13.7 MiB | 1.913 s | 1.784 s | 47.5 MiB/s（905 个文件） |
| PC Engine | 172.7 MiB／334.9 MiB | 71.7 MiB | 41.5%／21.4% | 6.5 MiB | 1.798 s | 1.8 s | 39.3 MiB/s（509 个文件） |
| SuperGrafx | 6.6 MiB／11.1 MiB | 5.5 MiB | 83.4%／49.4% | 1.9 MiB | 0.084 s | 0.122 s | 14.1 MiB/s（6 个文件） |
| MSX | 24.4 MiB／50.3 MiB | 22.2 MiB | 91.3%／44.2% | 8.0 MiB | 0.311 s | 0.326 s | 27.0 MiB/s（952 个文件） |
| MSX2 | 50.6 MiB／111.1 MiB | 30.5 MiB | 60.2%／27.4% | 3.5 MiB | 0.399 s | 0.473 s | 30.7 MiB/s（201 个文件） |
| Virtual Boy | 76.4 MiB／315.1 MiB | 26.5 MiB | 34.6%／8.4% | 2.7 MiB | 0.717 s | 0.99 s | 51.1 MiB/s（78 个文件） |
| Game & Watch | 0.1 MiB／0.2 MiB | 3.5 MiB | 2356.2%／2004.3% | 2.1 MiB | 0.01 s | 0.011 s | 1.1 MiB/s（52 个文件） |
| Super A'Can | 11.7 MiB／22.5 MiB | 12.5 MiB | 106.8%／55.6% | 1.7 MiB | 0.252 s | 0.412 s | 20.0 MiB/s（10 个文件） |

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
| Satellaview (全集) | 324.1 | — | 32 KiB / 256 MiB | 103.8 |
| Master System (全集) | 177.4 | — | 128 KiB / 256 MiB | 62.6 |
| 32X (全集) | 593.1 | — | 32 KiB / 256 MiB | 83.9 |
| WonderSwan (全集) | 150.5 | — | 64 KiB / 256 MiB | 76.0 |
| WonderSwan Color (全集) | 246.6 | — | 64 KiB / 128 MiB | 122.1 |
| NeoGeo Pocket (全集) | 5.3 | — | 128 KiB / 32 MiB | 3.1 |
| NeoGeo Pocket Color (全集) | 93.0 | — | 128 KiB / 256 MiB | 33.0 |
| Pokémon Mini (全集) | 8.9 | — | 256 KiB / 32 MiB | 1.5 |
| Game Gear (全集) | 254.2 | — | 32 KiB / 256 MiB | 63.8 |
| PC Engine (全集) | 172.7 | — | 128 KiB / 256 MiB | 62.7 |
| SuperGrafx (全集) | 6.6 | — | 128 KiB / 32 MiB | 2.2 |
| MSX (全集) | 24.4 | — | 64 KiB / 64 MiB | 12.5 |
| MSX2 (全集) | 50.6 | — | 128 KiB / 128 MiB | 24.5 |
| Virtual Boy (全集) | 76.5 | — | 256 KiB / 128 MiB | 21.9 |
| Game & Watch (全集) | 0.1 | — | 4 KiB / 32 MiB | 0.1 |
| Super A'Can (全集) | 11.7 | — | 64 KiB / 32 MiB | 9.4 |

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
| Satellaview | 全集，16 KiB 块，去重后 256 MiB | −1.28% | −3.33% | −6.32% | — | 256 MiB | — |

基准组：NES、SNES、MD、GB、GBC、FDS、Satellaview 为 32 MiB，GBA 为 128 MiB。FDS 和 Satellaview 直接按选定参数构建，没有重打包。

其他实测结论：

- **BCJ 过滤器**：xz 提供的 ARM、ARM-Thumb 过滤器只适用于 GBA。在 6 个真实 128 MiB 组上，ARM-Thumb 使结果增大 2.35%，ARM 增大 0.73%，因此不用。其余平台的 CPU（6502、65816、68000、SM83）没有对应过滤器。
- **LZMA 参数**：lc／lp／pb 的各种组合差异小于 0.2%，统一使用 lc3／lp0／pb0、BT4、nice_len 273。
- **zstd**：以母版为字典的差分比 LZMA 方案大 8–16%，且标准库 `compression.zstd` 要求 Python 3.14，而工具以 Python 3.10+ 标准库为目标，未采用。
- **NES**：迁移到 v4：8 KiB 块（按头部、trainer、PRG、CHR 边界切分），256 MiB 组。全库实测，v3 载荷（489 个 lzma2-4m 组加 XOR 差分散块，382,082,581 字节）变为 344,223,238 字节（−9.91%）；真实数据曲线相对 32 MiB 组为 64 MiB −1.40%、128 MiB −2.59%、256 MiB −5.66%，较小的组都比 256 MiB 大 0.5% 以上，按规则取 256 MiB。
- **FDS**：64 KiB 块（每面一块），全平台一个 128 MiB 组：合计 10.055 MiB，原 ZIP 33.72 MiB，逐文件 LZMA 28.21 MiB。单组时各种块大小压缩后都约 9.9 MiB，块越小元数据越多；64 MiB 组会拆成两组（+3.8%）。按面切块不改变压缩大小，但能让有头、无头版本的同一面去重。
- **Satellaview**：32 KiB 块、256 MiB 组：合计 103.779 MiB，原 ZIP 324.15 MiB，逐文件 LZMA 240.46 MiB。块级去重去掉了大部分数据（BS 记忆卡之间共用填充和重复广播内容）：703.62 MiB 的文件按 32 KiB 去重后为 278.78 MiB。256 MiB 组下 8／16／32／64 KiB 块分别为 106.862／103.935／103.779／104.615 MiB；16 KiB 块时 128 MiB 组比 256 MiB 组大 3.18%，因此取 256 MiB 上限。
- **Master System、32X、WonderSwan、WonderSwan Color、NeoGeo Pocket、NeoGeo Pocket Color、Pokémon Mini，以及第三批 Game Gear、PC Engine、SuperGrafx、MSX、MSX2、Virtual Boy、Game & Watch、Super A'Can**（2026-10-06 新增）：用各平台的全部本地收藏（No-Intro 目录加 RA 目录中属于本平台的文件）测量块大小（一般 8–256 KiB，小平台从 1 KiB 起，曲线仍在下降时加测到 512 KiB–1 MiB）× 32–256 MiB 组（`assessment/tools/storage_eval_platform.py`，结果在 `assessment/data/storage-experiment-<平台>.json`；超过平台去重后数据量的组上限只测一次）。规则：取总大小最小值；与最小值相差 0.5% 以内的配置中选块最小、再选组最小的（以后加入新版本时去重更细，单次读取解码更少）。Master System 128 KiB / 256 MiB：62.61 MiB（ZIP 177.42 MiB，逐文件 LZMA 105.80 MiB；比最小值多 0.17%）；32X 32 KiB / 256 MiB：83.85 MiB（ZIP 593.11 MiB，逐文件 LZMA 281.98 MiB；比最小值多 0.32%）；WonderSwan 64 KiB / 256 MiB：75.97 MiB（ZIP 150.46 MiB，逐文件 LZMA 100.84 MiB；比最小值多 0.45%）；WonderSwan Color 64 KiB / 128 MiB：122.06 MiB（ZIP 246.58 MiB，逐文件 LZMA 176.38 MiB；比最小值多 0.23%）；NeoGeo Pocket 128 KiB / 32 MiB：3.08 MiB（ZIP 5.26 MiB，逐文件 LZMA 3.72 MiB；比最小值多 0.36%）；NeoGeo Pocket Color 128 KiB / 256 MiB：33.02 MiB（ZIP 92.97 MiB，逐文件 LZMA 64.83 MiB；比最小值多 0.25%）；Pokémon Mini 256 KiB / 32 MiB：1.54 MiB（ZIP 8.91 MiB，逐文件 LZMA 5.40 MiB；比最小值多 0.33%）；Game Gear 32 KiB / 256 MiB：63.83 MiB（ZIP 254.16 MiB，逐文件 LZMA 139.89 MiB；最小值）；PC Engine 128 KiB / 256 MiB：62.67 MiB（ZIP 172.69 MiB，逐文件 LZMA 100.74 MiB；比最小值多 0.23%）；SuperGrafx 128 KiB / 32 MiB：2.20 MiB（ZIP 6.59 MiB，逐文件 LZMA 2.77 MiB；比最小值多 0.18%）；MSX 64 KiB / 64 MiB：12.50 MiB（ZIP 24.38 MiB，逐文件 LZMA 20.15 MiB；比最小值多 0.21%）；MSX2 128 KiB / 128 MiB：24.50 MiB（ZIP 50.62 MiB，逐文件 LZMA 40.50 MiB；比最小值多 0.22%）；Virtual Boy 256 KiB / 128 MiB：21.87 MiB（ZIP 76.45 MiB，逐文件 LZMA 33.69 MiB；比最小值多 0.16%）；Game & Watch 4 KiB / 32 MiB：0.13 MiB（ZIP 0.15 MiB，逐文件 LZMA 0.14 MiB；最小值）；Super A'Can 64 KiB / 32 MiB：9.44 MiB（ZIP 11.72 MiB，逐文件 LZMA 9.67 MiB；比最小值多 0.38%）。

## 存储格式 v4

- ROM 数据切成固定大小的块并按 SHA256 去重，块按 No-Intro 游戏族顺序装入 `lzma2-solid` 实体组；块大小、组上限和字典大小记录在每个库的 `meta` 中。
- 每个块保留 ID、大小和 SHA256；对象按块拼接，导出时核对完整的 CRC32、MD5、SHA1、SHA256。
- 读取时只解压到所需位置，每个块仍单独核对 SHA256。解码缓存为两个组大小；块分布在多个组中的对象（如多合一卡带）按组读取，每组只解压一次；审计和批量导出时缓存放宽到不超过 2 GiB（且不超过全部组的解压后总量），并整组解压，不保留未完成解码器的字典窗口。
- NES 保留 16 字节头部与正文分开存储、有头和无头版本共用正文的结构，块按头部、PRG、CHR 边界对齐（8 KiB）。
- 源 ZIP 只保留原始校验值，导出时由 TorrentZip 配方重新生成。23 个库共 57,437 个源 ZIP（No-Intro 与 RetroAchievements 集合，均为 TorrentZip），其中 57,437 个经核对可逐字节重建（`v_file_checksums.exported_bytes_equal_source`）。
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

## 导入内容

来源集合（`source_collections`，按目录登记；ZIP 成员继承所在 ZIP 的路径）：

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No-Intro（ZIP／大小） | 21,792／4.12 GiB | 4,898／3.99 GiB | 5,281／3.93 GiB | 2,671／295.8 MiB | 3,006／1.06 GiB | 3,946／14.42 GiB | 720／32.4 MiB | 699／302.4 MiB |
| RetroAchievements 集合（ZIP／大小） | 1,973／230.3 MiB | 1,836／2.07 GiB | 934／753.3 MiB | 720／105.3 MiB | 575／326.7 MiB | 1,206／6.78 GiB | 53／2.8 MiB | 40／21.7 MiB |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No-Intro（ZIP／大小） | 1,674／150.9 MiB | 375／528.8 MiB | 258／121.5 MiB | 265／195.6 MiB | 13／4.4 MiB | 130／62.0 MiB | 50／6.2 MiB | 1,319／227.0 MiB |
| RetroAchievements 集合（ZIP／大小） | 201／26.5 MiB | 39／64.3 MiB | 29／29.0 MiB | 45／51.0 MiB | 1／0.8 MiB | 53／31.0 MiB | 51／2.7 MiB | 140／27.2 MiB |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No-Intro（ZIP／大小） | 651／133.7 MiB | 10／4.2 MiB | 959／21.5 MiB | 204／23.8 MiB | 127／60.8 MiB | 54／0.1 MiB | 12／11.7 MiB |
| RetroAchievements 集合（ZIP／大小） | 174／39.0 MiB | 4／2.4 MiB | 111／2.9 MiB | 89／26.8 MiB | 49／15.6 MiB | — | — |

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 本地 ZIP | 23,765 | 6,734 | 6,215 | 3,391 | 3,581 | 5,152 | 773 | 739 |
| ROM 记录 | 18,414 | 5,239 | 3,959 | 2,538 | 2,784 | 4,143 | 703 | 602 |
| 游戏组／发行版本 | 3,477／7,385 | 1,996／4,329 | 1,581／3,503 | 1,419／2,299 | 1,576／2,622 | 1,901／3,750 | 307／408 | 606／609 |
| 不在任何 DAT 的本地 ROM | 2,849 | 978 | 561 | 306 | 279 | 467 | 9 | 34 |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 本地 ZIP | 1,875 | 414 | 287 | 310 | 14 | 183 | 101 | 1,459 |
| ROM 记录 | 1,230 | 228 | 265 | 268 | 13 | 160 | 83 | 927 |
| 游戏组／发行版本 | 774／1,238 | 61／227 | 228／257 | 217／253 | 12／13 | 76／128 | 22／46 | 474／928 |
| 不在任何 DAT 的本地 ROM | 39 | 9 | 8 | 15 | 0 | 32 | 37 | 22 |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 本地 ZIP | 825 | 14 | 1,070 | 293 | 176 | 54 | 12 |
| ROM 记录 | 545 | 7 | 1,008 | 295 | 97 | 53 | 13 |
| 游戏组／发行版本 | 363／509 | 6／6 | 622／952 | 157／201 | 53／80 | 51／53 | 12／12 |
| 不在任何 DAT 的本地 ROM | 36 | 1 | 56 | 94 | 19 | 0 | 0 |

每个平台本地现有的全部 Parent-Clone DAT 版本都导入并分别扫描；`dat_changes` 记录旧版本相对最新版的逐条差异，旧 DAT 条目通过差异关系挂到最新 DAT 的同一发行版本。

- **NES**（2 个 DAT）：20260713-141345：7,100/7,288；20261002-002752：7,095/7,390
- **SNES**（2 个 DAT）：20260710-203222：4,255/4,318；20261003-140326：4,261/4,331
- **Mega Drive**（2 个 DAT）：20260714-063411：3,398/3,486；20260927-122056：3,398/3,504
- **Game Boy**（4 个 DAT）：20260602-070215：2,225/2,276；20260707-013717：2,226/2,284；20260814-115131：2,230/2,292；20261001-130150：2,232/2,299
- **Game Boy Color**（5 个 DAT）：20260602-074724：2,502/2,604；20260713-134329：2,503/2,612；20260715-062319：2,503/2,612；20260814-104253：2,503/2,614；20261001-131920：2,503/2,622
- **Game Boy Advance**（4 个 DAT）：20260531-074517：3,676/3,745；20260707-143610：3,676/3,748；20260812-060017：3,676/3,749；20260929-130236：3,676/3,750
- **Famicom Disk System**（3 个 DAT）：20260517-061737：405/407；20260617-195332：295/296；20260930-033941：294/295
- **Satellaview**（3 个 DAT）：20260619-093425：569/603；20260814-103513：566/604；20260919-025009：562/610
- **Master System**（4 个 DAT）：20260527-203639：1,191/1,215；20260706-223420：1,191/1,216；20260809-210908：1,191/1,240；20260918-065535：1,189/1,238
- **32X**（1 个 DAT）：20260317-140429：219/227
- **WonderSwan**（1 个 DAT）：20260525-011654：257/257
- **WonderSwan Color**（1 个 DAT）：20260525-011610：253/253
- **NeoGeo Pocket**（1 个 DAT）：20250904-215533：13/13
- **NeoGeo Pocket Color**（3 个 DAT）：20240506-123728：128/128；20260626-085623：128/128；20260919-122044：128/128
- **Pokémon Mini**（1 个 DAT）：20260529-125415：46/46
- **Game Gear**（3 个 DAT）：20260706-223743：905/927；20260725-204513：905/928；20260822-061808：905/928
- **PC Engine**（1 个 DAT）：20260124-120557：509/509
- **SuperGrafx**（1 个 DAT）：20250913-112105：6/6
- **MSX**（1 个 DAT）：20260618-055428：952/952
- **MSX2**（1 个 DAT）：20260124-112728：201/201
- **Virtual Boy**（3 个 DAT）：20260428-015207：78/78；20260804-192036：78/80；20260805-170231：78/80
- **Game & Watch**（2 个 DAT）：20260512-134045：53/54；20260512-134245：53/54
- **Super A'Can**（2 个 DAT）：20240927-111000：13/13；20260913-064553：10/12

游戏组与发行版本取自最新 DAT 的 Parent／Clone，不推测发行字段。同一平台有多种 DAT 格式时（NES 有头／无头，FDS 的 FDS／QD），各格式分别与本格式的旧版本做差异；主格式（列表第一个）建立游戏与发行版本，其他格式的条目挂到同名的主格式发行版本，没有同名的挂到其 Parent 所在游戏下。ROM 目录中的非 ZIP 文件（GB 目录中前端使用的 `metadata.txt`／`systeminfo.txt`）作为 `metadata` 文件保存。

RetroAchievements 整理的 ROM 目录（`/mnt/MyShare/RetroAchievements/RA - <平台>`）按与 No-Intro 目录相同的方式去重入库：已在库中的 ROM 只增加文件记录和来源关联，新 ROM（Hack、翻译版、自制游戏、No-Intro 未收录的版本等）按块去重后存入。不在任何 DAT 中的 ROM 归入与它共享块最多的已存 ROM 所在的游戏族（`object_families.basis='shared_blocks'`，多数 Hack 与原版同族，压缩时排在一起），没有共享块的按文件名标题归族。NES 的 RA 目录中混有 FDS 磁碟镜像，导入 NES 时跳过并列入报告，由 FDS 库导入；SNES 的 RA 目录中的 Satellaview（BS-X，`.bs`）文件属于独立平台，导入 SNES 时跳过并列入报告，由 Satellaview 库导入；RA 的 FDS 目录中的 `.nes` 文件（FDS 卡带转换版、盗版卡带）属于 NES，导入 FDS 时跳过，由 NES 库导入。RA 的 WonderSwan 与 WonderSwan Color、NeoGeo Pocket 与 NeoGeo Pocket Color 各共用一个目录：两边的库都导入该目录，各自只收本平台扩展名（`.ws`／`.wsc`、`.ngp`／`.ngc`），另一平台的文件跳过并列入报告。RA 的 TurboGrafx-16 目录同时含 PC Engine（`.pce`）和 SuperGrafx（`.sgx`）文件，同样按扩展名分到两个库。RA 的 MSX 目录同时含 MSX 和 MSX2 游戏，且磁碟、磁带、卡带混在一起：按“平台优先、介质其次”分库（`tools/msx_route.py`），每个 ZIP 只进一个库，依次看成员 SHA1 是否在 MSX2／MSX 的 DAT 中、文件名是否标 `(MSX2` 或有 `.mx2` 成员，再查复核表 `data/msx-routing.csv`（参考名单、公开资料（MSX 软件数据库、开发比赛页面）、人工判断；复核结论优先于后面的推断），然后看去掉括号后的标题是否只出现在一个平台的 DAT 中、与某一平台 DAT ROM 共享的 8 KiB 块是否达到 10%（Hack、翻译版）；都不能判定的归 MSX（MSX2 机器兼容 MSX 软件）并标为未确认。依据写入 `rom_annotations`（`kind='platform'`），在 `v_msx_headers.platform_evidence` 中可见；分到另一库的文件列入报告。Game & Watch 和 Super A'Can 没有 RA 目录。

## 内部头部

解析只作描述，不修改任何字节；头部声明不等同于实物硬件证据。解析结果：NES 有效 10,265／告警 64／未识别 8,083；SNES 有效 3,946／告警 1,089／未识别 204；Mega Drive 有效 2,055／告警 1,841／未识别 63；Game Boy 有效 2,278／告警 256／未识别 4；Game Boy Color 有效 2,425／告警 358／未识别 1；Game Boy Advance 有效 4,025／告警 104／未识别 14；Famicom Disk System 有效 671／告警 25／未识别 7；Satellaview 有效 564／告警 16／未识别 22；Master System 有效 888／告警 130／未识别 212；32X 有效 101／告警 123／未识别 4；WonderSwan 有效 110／告警 154／未识别 1；WonderSwan Color 有效 108／告警 158／未识别 2；NeoGeo Pocket 有效 10／告警 0／未识别 3；NeoGeo Pocket Color 有效 159／告警 0／未识别 1；Pokémon Mini 有效 82／告警 0／未识别 1；Game Gear 有效 816／告警 86／未识别 25；PC Engine 有效 539／告警 6／未识别 0；SuperGrafx 有效 7／告警 0／未识别 0；MSX 有效 1,002／告警 0／未识别 6；MSX2 有效 291／告警 0／未识别 4；Virtual Boy 有效 96／告警 1／未识别 0；Game & Watch 有效 0／告警 0／未识别 53；Super A'Can 有效 0／告警 0／未识别 13。

- **NES**（`nes_hardware`、`nes_recipes`）：iNES／NES 2.0 头部字段；头部与正文分开保存，有头、无头版本共用正文。
- **SNES**（`snes_hardware`、`v_snes_headers`）：在 LoROM、HiROM、ExLoROM、ExHiROM 四处按校验和互补、映射模式、标题、ROM 大小字节、复位向量打分选择位置，分数不足的记为 `unclassified`；512 字节 copier 头单独切块。
- **Mega Drive**（`md_hardware`、`v_md_headers`）：0x100 头部与整文件校验和；识别 SMD 交错格式但原样保存。
- **Game Boy／Game Boy Color**（`gb_hardware`、`v_gb_headers`）：0x100–0x14F 卡带头，含 CGB／SGB 标志、MBC 类型、头部校验和与全局校验和；Nintendo Logo 只保存 SHA1。
- **Game Boy Advance**（`gba_hardware`、`v_gba_headers`）：0x00–0xBF 卡带头、补码校验、存档库标识、末尾填充长度。
- **Satellaview**（`bsx_hardware`、`v_bsx_headers`）：BS 记忆卡头位于 0x7FB0（LoROM）或 0xFFB0（HiROM），以固定字节 0x33、映射模式和校验和补码打分定位；保存厂商代码、程序类型、Shift-JIS 标题、块分配位、剩余启动次数、广播月日、映射模式、执行类型、版本和校验和。没有 BS 头的文件（数据包等）记为 `unclassified`；BS-X 本体卡带（`.sfc`）是标准 SNES 头，由 SNES 解析器写入 `snes_hardware`。
- **Master System／Mark III**（`sms_hardware`、`v_sms_headers`）：0x7FF0（或 0x3FF0、0x1FF0）的 `TMR SEGA` 头：校验和、产品码、版本、地区、声明容量，按声明范围重算校验和；0x7FE0 的 Codemasters 头和 SDSC 自制软件头。日版 Mark III 卡带大多没有这个头，记为 `unclassified`。
- **32X**（`md_hardware`、`v_md_headers`）：与 Mega Drive 相同的 0x100 头部；许多正式版卡带的系统字符串是 `SEGA MEGA DRIVE`／`SEGA GENESIS`，声明校验和为 0 时记为“未声明”而不是不一致；检查 0x3C0 的 MARS 安全头。
- **WonderSwan／WonderSwan Color**（`ws_hardware`、`v_ws_headers`）：文件末尾 16 字节：发行商、彩色标志、游戏 ID、版本、容量、存档类型（SRAM／EEPROM 及大小）、方向、总线宽度、RTC 和 16 位校验和。WonderWitch 自制软件的页尾是默认值（校验和为 0），因此带告警。
- **NeoGeo Pocket／NeoGeo Pocket Color**（`ngp_hardware`、`v_ngp_headers`）：开头 64 字节卡带头：`COPYRIGHT／LICENSED BY SNK CORPORATION`、启动地址、软件 ID、子版本、彩色模式、标题。BIOS 没有卡带头，记为 `unclassified`。
- **Pokémon Mini**（`pokemini_hardware`、`v_pokemini_headers`）：0x2100 的 `MN` 头、`NINTENDO`、4 字符游戏代码（末字符为地区）、标题和 `2P` 标志。
- **Game Gear**（`sms_hardware`、`v_sms_headers`）：与 Master System 相同的 `TMR SEGA` 头（地区代码为 Game Gear 日版／海外／国际）；没有头的卡带记为 `unclassified`。
- **PC Engine／SuperGrafx**（`pce_hardware`、`v_pce_headers`）：HuCard 没有内部头，只记录镜像事实：是否有 512 字节 copier 头（大小 %8192 = 512，单独切块，使正文与无头版本去重）、容量、8 KiB bank 数和不足一个 bank 的字节数、第一个 bank 末尾的复位向量。
- **MSX／MSX2**（`msx_hardware`、`v_msx_headers`）：卡带在 0x0000 或 0x4000 的 `AB` 头（INIT、STATEMENT、DEVICE、TEXT 地址）；按大小和引导扇区识别磁碟镜像（`.dsk`），按 CAS 块标记识别磁带（`.cas`）。机型（MSX／MSX2）不在数据中，见 `rom_annotations`；mapper 需要外部证据，不推测。
- **Virtual Boy**（`vb_hardware`、`v_vb_headers`）：文件末尾前 0x220 字节处的游戏头：20 字节 Shift-JIS 标题、厂商代码、4 字符游戏代码、版本。
- **Game & Watch／Super A'Can**：没有定义内部头部，只记录文件，记为 `unclassified`。
- **Famicom Disk System**（`fds_hardware`、`v_fds_headers`）：识别 FDS（每面 65,500 字节）、QD（每面 65,536 字节，块后带 CRC）和 BIOS（8 KiB），以及可选的 16 字节 fwNES 头；逐面解析磁碟信息块（厂商代码、3 字符游戏代码、游戏类型、修订号、面号、盘号、BCD 制造日期、国家代码）和文件数量块，每面的值存于 `sides_json`。块在 fwNES 头和每面边界处重新起算，有头与无头版本、共用某一面的修订版可以按面去重。

## No-Intro DB Export 与 Dump Log

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 快照 | 20261002-002752 | 20261003-140326 | 20260927-122056 | 20261001-130150 | 20261001-131920 | 20260929-130236 | 20260930-033941 | 20260919-025009 |
| 档案／文件身份 | 7,704／16,154 | 4,365／5,457 | 3,640／4,142 | 2,335／2,450 | 2,678／2,921 | 3,793／4,563 | 408／1,437 | 615／766 |
| 有本地正文的文件 | 14,885 | 4,276 | 3,537 | 2,248 | 2,514 | 3,713 | 701 | 590 |
| 有文档的硬件声明 | 6,412 | 5,399 | 2,017 | 2,810 | 2,830 | 3,188 | 8 | 6 |
| Dump Log：Verified／Trusted 未验证／未验证 | 2,794／3,814／1,028 | 1,871／1,708／736 | 868／2,085／615 | 719／1,118／490 | 448／1,521／703 | 770／1,703／1,307 | 7／262／136 | 7／445／137 |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 快照 | 20260918-065535 | 20260317-140429 | 20260525-011654 | 20260525-011610 | 20250904-215533 | 20260919-122044 | 20260529-125415 | 20260822-061808 |
| 档案／文件身份 | 1,245／1,279 | 228／239 | 257／278 | 254／263 | 13／22 | 128／215 | 46／49 | 928／951 |
| 有本地正文的文件 | 1,192 | 221 | 257 | 253 | 13 | 129 | 49 | 905 |
| 有文档的硬件声明 | 367 | 35 | 318 | 263 | 11 | 215 | 20 | 354 |
| Dump Log：Verified／Trusted 未验证／未验证 | 435／791／15 | 23／175／29 | 58／199／0 | 53／191／9 | 8／4／1 | 81／35／12 | 9／9／28 | 443／473／11 |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 快照 | 20260124-120557 | 20250913-112105 | 20260618-055428 | 20260124-112728 | 20260804-192036 | 20260512-134045 | 20260913-064553 |
| 档案／文件身份 | 510／714 | 7／7 | 952／961 | 201／204 | 81／81 | 53／54 | 12／15 |
| 有本地正文的文件 | 510 | 6 | 952 | 201 | 78 | 53 | 13 |
| 有文档的硬件声明 | 208 | 0 | 11 | 2 | 76 | 17 | 12 |
| Dump Log：Verified／Trusted 未验证／未验证 | 292／162／56 | 0／5／1 | 0／47／905 | 0／12／189 | 21／58／1 | 2／51／0 | 0／0／12 |

NES 使用自己的导入器（重建 16 字节头、核对有头／无头配对）；其余平台使用 `nointro_db.py`。FDS 的 DB Export 同时含 FDS 和 QD 文件，Dump Log 只有 FDS 格式。缺少 SHA256 的文件保持为空并记入 `ni_anomalies`。

## RetroAchievements 成就匹配

`ra_snapshots`、`ra_games`、`ra_hashes` 保存 RA 公开 API（`API_GetGameList`）的快照，原始响应存为 resource；API 密钥只在运行时读取，不写入库、报告或日志。每个 ROM 的 RA 哈希按 rcheevos 规则计算并保存在 `rom_ra_hashes`：NES 为去掉 16 字节头后的正文 MD5，FDS 在有 fwNES 头时去掉 16 字节头，SNES 在大小 %8192 = 512 时先去掉 512 字节头，PC Engine／SuperGrafx 在大小 %131072 = 512 时先去掉 512 字节头，其余平台为整文件 MD5。只做精确哈希匹配。主机 ID：NES 7、SNES 3、MD 1、GB 4、GBC 6、GBA 5、FDS 81、Master System 11、32X 10、WonderSwan（两者共用）53、NeoGeo Pocket（两者共用）14、Pokémon Mini 24、Game Gear 15、PC Engine 与 SuperGrafx（共用）8、MSX 与 MSX2（共用）29、Virtual Boy 28；Game & Watch 和 Super A'Can 没有 RA 主机，报告为空；RA 没有 Satellaview 主机，Satellaview 游戏在 SNES 主机（3）下，哈希按 SNES 规则计算。

跨库关联：有些 RA 游戏的 ROM 在兄弟平台的库中（FDS 主机下的 FDS 卡带转换版 `.nes` 在 NES 库，SNES 主机下的 BS 游戏在 Satellaview 库）。报告会到兄弟库（NES↔FDS、SNES↔Satellaview、WonderSwan↔WonderSwan Color、NeoGeo Pocket↔NeoGeo Pocket Color、PC Engine↔SuperGrafx、MSX↔MSX2）查找这些哈希，找到的标为 `local_other_platform`，并在 `other_platform_db` 列注明所在库，不计入缺口。Satellaview 与 SNES 共用 RA 主机，WonderSwan、NeoGeo Pocket、PC Engine／SuperGrafx、MSX／MSX2 也各是两个平台共用一个主机，因此这些平台的报告只统计与本库 ROM、DAT 或 DB Export 有关的 RA 游戏。

`v_ra_collection` 列出 RA 集合中每个 ROM 文件对应的 RA 游戏、No-Intro DAT 条目和发行版本，状态分为 `in_nointro_dat`（DAT 中有）、`ra_only`（只有 RA 收录）和 `ra_hash_unknown`（最新 RA 快照中没有该哈希）。`reports/ra-<平台>-games.csv` 的 `local_sources` 列给出每个 RA 游戏的本地 ROM 来自哪些来源集合，`reports/ra-<平台>-collection-unknown.csv` 列出哈希未知的文件，`reports/ra-<平台>-missing.csv` 列出仍没有本地 ROM 的 RA 游戏（缺口清单）。

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 有成就的 RA 游戏 | 1,123 | 1,185 | 613 | 505 | 419 | 775 | 38 | 13 |
| 本地有匹配 ROM | 1,110 | 1,089 | 606 | 492 | 402 | 750 | 34 | 13 |
| ROM 在兄弟库中 | 0 | 6 | 0 | 0 | 0 | 0 | 1 | 0 |
| 仅 DAT 有（本地缺） | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| 仅 DB Export 文件 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| 无 No-Intro 对应（其中 Hack） | 13 (9) | 90 (62) | 7 (5) | 13 (5) | 16 (3) | 23 (12) | 2 (1) | 0 (0) |
| 本地有成就的 ROM | 3,385 | 1,845 | 942 | 725 | 584 | 1,230 | 47 | 44 |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 有成就的 RA 游戏 | 183 | 36 | 23 | 33 | 1 | 41 | 40 | 167 |
| 本地有匹配 ROM | 181 | 35 | 23 | 33 | 1 | 41 | 39 | 165 |
| ROM 在兄弟库中 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 仅 DAT 有（本地缺） | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 仅 DB Export 文件 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 无 No-Intro 对应（其中 Hack） | 2 (2) | 1 (0) | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 1 (0) | 2 (1) |
| 本地有成就的 ROM | 235 | 39 | 30 | 44 | 1 | 54 | 51 | 192 |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 有成就的 RA 游戏 | 138 | 4 | 92 | 45 | 43 | 0 | 0 |
| 本地有匹配 ROM | 138 | 4 | 92 | 45 | 41 | 0 | 0 |
| ROM 在兄弟库中 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 仅 DAT 有（本地缺） | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 仅 DB Export 文件 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 无 No-Intro 对应（其中 Hack） | 0 (0) | 0 (0) | 0 (0) | 0 (0) | 2 (0) | 0 (0) | 0 (0) |
| 本地有成就的 ROM | 180 | 4 | 115 | 116 | 51 | 0 | 0 |

“无 No-Intro 对应”指 RA 游戏的哈希既不对应本地 ROM 也不对应 DAT 条目，主要是 Hack、翻译补丁版、Subset 和 No-Intro 未收录的版本；导入 RA 集合后其中大部分已由本地 ROM 覆盖，剩余的是本地没有文件的游戏。“仅 DAT 有”是 DAT 中有但本地缺少的 ROM。逐游戏清单见 `reports/ra-<平台>-games.csv`。

## 中文名

| | NES | SNES | Mega Drive | Game Boy | Game Boy Color | Game Boy Advance | Famicom Disk System | Satellaview |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV 记录／含中文／唯一中文名 | 4,453／3,703／1,875 | 4,154／3,942／2,030 | 2,869／2,694／1,226 | 1,974／1,816／1,237 | 2,124／1,763／1,156 | 3,522／3,410／1,882 | 404／404／296 | 0／0／0 |
| 已确认／待消歧／无候选 | 4,420／22／11 | 4,099／10／45 | 2,715／58／96 | 1,956／0／18 | 1,945／7／172 | 3,444／26／52 | 403／1／0 | 0／0／0 |
| 有中文名的发行版本（直接＋继承） | 3,698 + 389 | 3,864 + 73 | 2,550 + 117 | 1,803 + 59 | 1,590 + 110 | 3,315 + 47 | 402 + 4 | 0 + 0 |
| 有中文名的本地 ROM | 8,104 | 3,909 | 2,656 | 1,835 | 1,663 | 3,350 | 692 | 0 |

| | Master System | 32X | WonderSwan | WonderSwan Color | NeoGeo Pocket | NeoGeo Pocket Color | Pokémon Mini | Game Gear |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV 记录／含中文／唯一中文名 | 699／542／342 | 213／213／54 | 264／148／118 | 242／115／97 | 10／10／9 | 132／132／83 | 44／43／17 | 825／825／411 |
| 已确认／待消歧／无候选 | 697／1／1 | 204／6／3 | 257／0／7 | 242／0／0 | 10／0／0 | 128／0／4 | 44／0／0 | 818／5／2 |
| 有中文名的发行版本（直接＋继承） | 542 + 30 | 203 + 1 | 141 + 0 | 115 + 0 | 10 + 0 | 128 + 0 | 43 + 0 | 824 + 1 |
| 有中文名的本地 ROM | 563 | 203 | 141 | 115 | 10 | 128 | 43 | 823 |

| | PC Engine | SuperGrafx | MSX | MSX2 | Virtual Boy | Game & Watch | Super A'Can |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CSV 记录／含中文／唯一中文名 | 468／468／339 | 5／5／5 | 944／907／577 | 198／198／154 | 33／33／23 | 53／53／46 | 0／0／0 |
| 已确认／待消歧／无候选 | 460／1／7 | 5／0／0 | 944／0／0 | 198／0／0 | 32／0／1 | 53／0／0 | 0／0／0 |
| 有中文名的发行版本（直接＋继承） | 460 + 0 | 5 + 0 | 907 + 0 | 198 + 0 | 32 + 0 | 53 + 0 | 0 + 0 |
| 有中文名的本地 ROM | 460 | 5 | 907 | 198 | 32 | 53 | 0 |

Satellaview 目前没有中文名来源，表中为 0；取得名称 CSV（`Name EN,Name CN` 或 `EN Name,CN Name` 两列）后，放到 `data/Nintendo - Satellaview.csv`，运行 `tools/update_db.py RetroBoxDB.Satellaview.sqlite --names data/Nintendo - Satellaview.csv` 即可增量导入。

## 信息分层与扩展

`v_information_sources` 视图列出每个库的全部信息来源及版本：

- **已有信息**：No-Intro DAT 各版本、ROM 文件、来源集合（No-Intro、RetroAchievements）；
- **扩展信息**：No-Intro DB Export／Dump Log 快照、RA 快照、中英文名称来源、有文档的硬件声明；
- **提供者信息表**：只在本地完整库中填充，Catalog 中为空表；
- **占位**：Batocera 媒体槽位等。

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

`resources` 中的 `engine.py` 等是可执行代码，只应从自己构建或 SHA256 已核对的 Release 附件中执行。公开 Catalog 保留文件的原始路径（`files.source_path`）作为溯源信息。全量审计：NES 19,069 个对象／9 个组／25,368 个 ZIP 配方；SNES 5,243 个对象／57 个组／5,774 个 ZIP 配方；Mega Drive 3,963 个对象／20 个组／5,367 个 ZIP 配方；Game Boy 2,546 个对象／5 个组／2,776 个 ZIP 配方；Game Boy Color 2,791 个对象／13 个组／2,931 个 ZIP 配方；Game Boy Advance 4,149 个对象／123 个组／4,396 个 ZIP 配方；Famicom Disk System 712 个对象／1 个组／728 个 ZIP 配方；Satellaview 607 个对象／2 个组／923 个 ZIP 配方；Master System 1,236 个对象／2 个组／1,523 个 ZIP 配方；32X 231 个对象／2 个组／387 个 ZIP 配方；WonderSwan 268 个对象／1 个组／269 个 ZIP 配方；WonderSwan Color 271 个对象／4 个组／278 个 ZIP 配方；NeoGeo Pocket 16 个对象／1 个组／16 个 ZIP 配方；NeoGeo Pocket Color 165 个对象／2 个组／171 个 ZIP 配方；Pokémon Mini 86 个对象／1 个组／88 个 ZIP 配方；Game Gear 934 个对象／2 个组／1,306 个 ZIP 配方；PC Engine 548 个对象／2 个组／684 个 ZIP 配方；SuperGrafx 10 个对象／1 个组／14 个 ZIP 配方；MSX 1,011 个对象／2 个组／1,023 个 ZIP 配方；MSX2 306 个对象／2 个组／277 个 ZIP 配方；Virtual Boy 102 个对象／2 个组／113 个 ZIP 配方；Game & Watch 57 个对象／1 个组／58 个 ZIP 配方；Super A'Can 17 个对象／1 个组／16 个 ZIP 配方，全部通过。
