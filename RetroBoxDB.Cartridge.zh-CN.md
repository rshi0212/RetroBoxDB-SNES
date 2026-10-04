# RetroBoxDB SNES／Mega Drive

[NES 中文说明](https://github.com/rshi0212/RetroBoxDB-NES/blob/main/README.zh-CN.md) | [Technical design (English)](RetroBoxDB.Cartridge.Technical-Design.en.md)

两个平台各自一个完整库（含 ROM 正文）和一个无载荷 Catalog，沿用 NES 库的表结构、校验、DAT 验证、TorrentZip 配方、No-Intro DB／Dumplog、中文名与 Batocera／ScreenScraper 占位，但**存储层按卡带平台实测重新选型**（存储格式 v4），并新增 RetroAchievements（RA）成就匹配。

| 文件 | 内容 |
| --- | --- |
| `RetroBoxDB.SNES.sqlite` | SNES 完整库：1.54 GiB（1,657,028,608 字节） |
| `RetroBoxDB.SNES.Catalog.sqlite` | SNES 无载荷目录库：48.2 MiB |
| `RetroBoxDB.MegaDrive.sqlite` | Mega Drive 完整库：0.95 GiB（1,019,019,264 字节） |
| `RetroBoxDB.MegaDrive.Catalog.sqlite` | Mega Drive 无载荷目录库：42.2 MiB |

Catalog 与 NES 相同：从新 SQLite 文件建立，`compression_groups`、`chunks`、`object_chunks` 为空，不含 ROM 正文、DAT／DB／Dumplog 原文件或压缩数据。

## 为什么不照搬 NES 存储

NES v3 用 8 KiB 块、XOR 差分和 2 MiB LZMA 分组，适合 NES 的小 ROM。SNES／MD 单个 ROM 1–8 MiB，同一游戏的地区版、修订版、Beta 之间大量相似但常有位移，2 MiB 组装不下一个完整 ROM，对齐块和 XOR 也抓不住位移。为此在两平台各随机抽 250 个 Parent／Clone 游戏族（约 10%）实测（单位 MiB，脚本与数据见 `assessment/tools/cart_storage_*.py`、`assessment/data/cart-storage-experiment.json`）：

| 策略 | SNES | MD |
| --- | ---: | ---: |
| 原 No-Intro ZIP | 443.2 | 408.2 |
| 逐文件 LZMA | 387.0 | 314.2 |
| 照搬 NES v3 引擎（实际运行，含库开销） | 238.9 | 216.9 |
| zstd 以母版为字典的差分 | 206.1 | 167.8 |
| 8 KiB 块 + 族排序 16 MiB 实体组（另有约 9 MiB 块元数据） | 189.1 | 146.7 |
| **64 KiB 块 + 族排序 32 MiB 实体组（采用）** | **189.8（+1.2）** | **144.5（+1.2）** |
| 整族一个实体流（上限参考） | 192.3 | 151.2 |

采用方案比照搬 NES v3 小约 20%（SNES）和 33%（MD）。64 MiB 组只再省 0.2–0.4%，却让单次读取解压量翻倍；LZMA 的 lc／lp／pb 调整差异小于 0.2%，保持 NES 的 lc3／lp0／pb0。zstd 需要 Python 3.14，且比采用方案大 8–16%，未采用。

**存储格式 v4**：ROM 按 64 KiB 切块并按 SHA256 去重；导入时按 No-Intro 游戏族（新 DAT 的 Parent／Clone，其次 DB Export 的母档案、旧 DAT，最后按去括号标题）排序，把新块装入不超过 32 MiB 的 `lzma2-solid` 实体组（32 MiB 字典）。每个块仍保留 ID、大小和 SHA256，对象仍按块拼接并核对完整 CRC32／MD5／SHA1／SHA256。读取一个 ROM 最多解压一个 32 MiB 组（96 MiB 解码缓存）。v3 引擎会拒绝 v4 库；v4 引擎仍可读 v2／v3（NES 原有 70 项测试在 v4 引擎下全部通过）。

全量结果：SNES 原 ZIP 3.99 GiB（4,288,077,842 字节），逻辑内容 6.11 GiB，64 KiB 去重后 4.25 GiB，145 个实体组压缩为 1.48 GiB，整库 1.54 GiB，为原 ZIP 的 38.6%；MD 原 ZIP 3.93 GiB（4,218,193,674 字节），逻辑内容 5.61 GiB，去重后 3.87 GiB，143 个实体组压缩为 0.90 GiB，整库 0.95 GiB，为原 ZIP 的 24.2%。

## 导入内容

| | SNES | Mega Drive |
| --- | ---: | ---: |
| 本地 ZIP（含 Aftermarket／Private 目录） | 4,898 | 5,281 |
| ROM 记录（去重后） | 4,293 | 3,687 |
| 旧 DAT 覆盖 | 4,255／4,318（20260710-203222） | 3,398／3,486（20260714-063411） |
| 新 DAT 覆盖 | 4,261／4,331（20261003-140326） | 3,398／3,504（20260927-122056） |
| 新旧 DAT 差异 | 未变 4,313、新增 13、改名 5 | 未变 3,474、新增 18、改名 11、大小写 1 |
| 不在任何 DAT 的本地 ROM | 32 | 289 |
| 游戏组／发行版本 | 1,996／4,329 | 1,581／3,503 |
| TorrentZip 配方（源 ZIP + DAT 打包） | 4,813 个，DAT 打包 8,516 | 5,044 个，DAT 打包 6,794 |

新旧 DAT 都完整导入、分别扫描；`dat_changes` 记录逐条差异，旧 DAT 条目通过差异关系挂到新 DAT 的同一发行版本（`release_dat_games`）。游戏组与发行版本取自最新 DAT 的 Parent／Clone，与 NES 相同，不猜测发行字段；DAT 的 `<release>` 元素保留在 `releases.metadata_json`。所有原始 ZIP 校验值作为历史身份保留，导出时按配方重新生成并核对。

```sql
SELECT dat_set_id,status,count(*) FROM v_dat_coverage GROUP BY 1,2;
SELECT classification,count(*) FROM dat_changes GROUP BY 1;
SELECT * FROM v_solid_groups LIMIT 5;          -- 实体组大小、压缩比、包含的游戏族（仅完整库；Catalog 中为空）
```

## 内部头部

不修改任何字节，只做描述性解析；头部声明不等于实物硬件证据。

- **SNES**（`snes_hardware`／`v_snes_headers`）：在 LoROM／HiROM／ExLoROM／ExHiROM 位置按校验和互补、映射模式、标题、大小、复位向量打分选位置；记录标题（ASCII／Shift-JIS 半角假名）、映射模式、FastROM、芯片组与协处理器（SuperFX 57、SA-1 51、DSP 45、CX4 15 等）、ROM／SRAM 声明大小、地区、扩展头部厂商与游戏代码、版本、声明与计算的校验和（非 2 的幂按镜像规则计算）。512 字节 copier 头会被识别并作为组件记录（本地收藏中没有）。3,463 个有效、629 个有警告（多为校验和不符）、201 个未找到合理头部（基本是 Beta／Proto／盗版／增强芯片固件）。
- **Mega Drive**（`md_hardware`／`v_md_headers`）：0x100 头部的系统类型、版权、日版／海外标题、序列号、设备支持、ROM／RAM 范围、SRAM、地区，以及按 0x200 至文件末尾计算的校验和。SMD 交错格式会被识别但不自动解交错（本地没有）。1,708 个声明校验和与计算不符：604 个是自制／原型等填 0，授权游戏 409 个确实不符；只有 41 个按头部声明的 ROM 结束地址计算才吻合，此字段仍按整文件计算。

## No-Intro DB Export 与 Dump Log

| | SNES 20261003-140326 | MD 20260927-122056 |
| --- | ---: | ---: |
| 档案／文件身份／来源 | 4,365／5,457／12,153 | 3,640／4,142／9,152 |
| 有本地正文的文件 | 4,276 | 3,537 |
| 有序列号的硬件声明（`hardware_assertions`） | 5,399 | 2,017 |
| Dump Log：Verified／Trusted 未验证／未验证／Bad | 1,871／1,708／736／18 | 868／2,085／615／8 |

导入器 `cart_nointro.py` 由 NES 版改写：SNES／MD 的 DB 文件都是 `Default` 格式，没有 16 字节头重建与有头／无头配对；部分文件缺 SHA256（SNES 38、MD 50）时保持为空并记为 `ni_anomalies`；DB 的 `header` 属性在这两个平台是内部头部序列号文本，原样保存在 `ni_files.attrs_json`。`v_nointro_archives` 提供 No-Intro 本地文字名称（`name_alt`，如日文原名）、类别、母档案等。

## RetroAchievements 成就匹配

`ra_snapshots`／`ra_games`／`ra_hashes` 保存 RA 官方公开 API（`API_GetGameList`，含无成就游戏）快照，原始响应存为 resource；API 密钥只在运行时从环境变量或 `~/Sync/API_TOKEN/retroachievements.md` 读取，不写入库、报告或日志。每个 ROM 在导入时按 rcheevos 规则计算 RA 哈希（`rom_ra_hashes`：SNES 若大小 %8192==512 先去掉 512 字节头；MD 整文件 MD5），只做精确哈希相等匹配。

| 有成就的 RA 游戏 | SNES（1,185） | MD（612） |
| --- | ---: | ---: |
| 本地有匹配 ROM | 673 | 520 |
| 仅 DAT 有（本地缺 ROM） | 0 | 0 |
| 仅 No-Intro DB 的坏 dump／其他来源 | 1 | 1 |
| 无任何 No-Intro 对应 | 511（Hack 440、Official 64） | 91（Hack 65、Official 14） |

本地有成就的 ROM：SNES 914 个，MD 673 个。凡是 No-Intro DAT 收录、且 RA 有成就的游戏，本地都有对应 ROM（“仅 DAT 有”为 0）。“无对应”主要是 Hack、翻译补丁版（例如 RA 的 Bahamut Lagoon、Rushing Beat 套装对应英译补丁 ROM）、Subset 和 No-Intro 未收录的版本；它们不会被自动关联。逐游戏清单见 `reports/ra-snes-games.csv`、`reports/ra-megadrive-games.csv`。

```sql
SELECT * FROM v_rom_ra_matches WHERE has_achievements;         -- 本地 ROM → RA 游戏
SELECT * FROM v_dat_ra_matches WHERE has_achievements AND NOT local_rom_available;  -- 缺的 ROM
SELECT * FROM v_nointro_ra_matches WHERE NOT in_dat;           -- 只在 DB Export 的文件
SELECT * FROM v_ra_unmatched_hashes WHERE num_achievements>0;  -- 待人工查看
```

刷新 RA 快照（新快照另存，旧快照保留）：`python3 -B tools/import_ra.py RetroBoxDB.SNES.sqlite`。按 RA 导出有成就的游戏（TorrentZip，导出后再核对 DAT 与 RA 哈希）：

```bash
python3 -B tools/export_nointro_parents.py RetroBoxDB.SNES.sqlite OUT_DIR report.json --ra-only --clone-fallback --ra-folders
```

## 中文名

与 NES 相同的 v4 名称扩展和匹配规则（`tools/import_game_names.py --platform snes|megadrive`），原始 CSV 文本保存在 `resources`。

| | SNES | MD |
| --- | ---: | ---: |
| CSV 记录／含中文／唯一中文名 | 4,154／3,942／2,030 | 2,869／2,694／1,226 |
| 已确认／待消歧／无候选 | 4,099／10／45 | 2,715／58／96 |
| 有中文名的发行版本（直接＋组内继承） | 3,864＋73 | 2,550＋117 |
| 有中文名的本地 ROM | 3,909 | 2,656 |
| 游戏组：唯一译名／多译名待审／无中文 | 1,539／230／227 | 872／161／548 |

```sql
SELECT * FROM v_release_effective_chinese_names WHERE name_cn LIKE '%恶魔城%';
SELECT * FROM v_game_chinese_name_status WHERE status='needs_review';
```

## 扩展与特殊案例

存储不是一次性固定的：新数据先安全入库，再按实际情况归并。

- **新增 ROM**：`update_cart_db.py` 跳过已入库的 ZIP（内容哈希＋路径），新 ROM 先按普通 64 KiB 块入库并记录游戏族（`object_families`：新 DAT → DB Export 母档案 → 旧 DAT → 去括号标题）。随后 `compact_solid` 按族归并：该族最新实体组还有空间就**解压原组、追加新块、重新编码**（新修订版与老版本共享同一 LZMA 字典），否则在族排序下新建实体组。块 ID／SHA256／对象拼接不变；在一个 savepoint 中完成，所有受影响块逐一校验，失败整体回滚；重复执行无副作用。
- **新 DAT**：导入（同内容重复导入为空操作）、扫描，与上一版最新 DAT 做差异；未变／改名／大小写／校验值变化的条目挂到原发行版本，新增条目按 Parent／Clone 链挂到已有游戏或新建游戏与发行版本；随后补 ROM↔发行版本关系和 TorrentZip 配方。发行版本标题保持创建时的 DAT 名，最新名称通过 `release_dat_games` 查询。
- **新 DB Export／Dump Log**：按两份输入的 SHA256 成对幂等导入为新快照，旧快照保留。
- **RA／中文名**：`--ra` 追加新的 RA 快照（视图总用最新快照）；新 CSV 按 SHA256 另存来源并刷新匹配。
- **SNES copier 头**：大小 %1024==512 的文件在 512 字节处切块，正文块与无头版本完全去重；RA 哈希按 rcheevos 去头计算。
- **MD SMD 交错格式**：识别并原样保存（当前收藏中没有）；如将来出现，可增加可逆解交错配方。
- **卡带 ROM 不再做 XOR 差分**：实体组已覆盖跨版本冗余，避免依赖链。
- **平台适配**：`CART_PLATFORMS` 为每个平台登记头部解析器、硬件表、扩展名和切块规则；块大小与实体组上限读库内 `meta`，新平台（如 GB／GBA）可按实测另行设定。
- **审计**：v4 引擎按实体组顺序遍历对象和 ZIP 配方、多线程重建 TorrentZip，每个组基本只解压一次。

```bash
# 自动发现并增量导入本平台新的 DAT、DB Export/Dump Log、ROM，追加 RA 快照，重建 Catalog
python3 -B tools/update_cart_db.py RetroBoxDB.SNES.sqlite --discover --ra --audit --catalog RetroBoxDB.SNES.Catalog.sqlite
# 只导入指定文件
python3 -B tools/update_cart_db.py RetroBoxDB.MegaDrive.sqlite --dat '新 DAT.zip' --roms '/路径/新ROM目录'
```

## 复现与维护

```bash
# 构建完整库与 Catalog（输入只读；拒绝覆盖已有输出）
python3 -B tools/build_cart_db.py snes RetroBoxDB.SNES.sqlite --catalog RetroBoxDB.SNES.Catalog.sqlite
python3 -B tools/build_cart_db.py megadrive RetroBoxDB.MegaDrive.sqlite --catalog RetroBoxDB.MegaDrive.Catalog.sqlite
# 刷新内嵌文档／工具与报告并重建 Catalog
python3 -B tools/finalize_cart_db.py RetroBoxDB.SNES.sqlite RetroBoxDB.SNES.Catalog.sqlite
# 测试（SNES／MD 合成数据测试）
python3 -B -m unittest tests/test_cart.py -v
# 内嵌引擎：统计、全量审计（解压全部对象并重新生成全部 ZIP 配方）、导出
python3 -B -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); s=c.execute("SELECT content FROM resources WHERE name=?",("engine.py",)).fetchone()[0]; c.close(); exec(compile(s,"RetroBoxDB:engine.py","exec"))' RetroBoxDB.SNES.sqlite audit-all
```

单个导入（`import-rom`）走普通 64 KiB 块，之后用 `update_cart_db.py`（或引擎的 `compact_solid`）归并进实体组。全量审计结果：SNES 4,297 个对象、145 个实体组、4,813 个 ZIP 配方全部通过（11 分钟）；MD 3,691 个对象、143 个实体组、5,044 个 ZIP 配方全部通过；SQLite 完整性与外键检查均无错误。两个 Catalog 完整性 ok、外键 0 错、载荷表为空。构建报告见 `reports/snes-build-report.json`、`reports/megadrive-build-report.json`，同时内嵌为 `build-report`。
