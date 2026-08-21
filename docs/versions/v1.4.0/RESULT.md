# V1.4.0 版本 RESULT

**版本号**：V1.4.0（源码真源唯一，runtime 数据解耦版）
**日期**：2026-08-16（初版） / 2026-08-17（三轮修正与 MIG-3） / 2026-08-18（T10/T11 与 Public 首发）
**状态**：`已验收` —— T1–T11、T9 三轮、MIG-3、Private 干净 clone、Public 首发、`v1.4` annotated tag 与匿名 clone 复核全部完成。源码冻结 commit 为 `d99d1bc22a86c3c9b016dc266dac11353cdb3386`，T10 修正 commit 为 `e631531d93f23f0d4f3bc37f43aee2a0b982fc82`，`v1.4` 解引用到发布记录 commit `c5d9f6ebc54045a4553d9a113e0406584f4ac763`。

---

## 一、V1.4.0 目标回顾（对照 PLAN.md §6.1）

本版本解决 V1.3.0 的两个首发阻断性缺陷：

| # | V1.3.0 阻断项 | V1.4.0 解决方案 | 对应阶段 |
| - | --------- | ------------- | -------- |
| 1 | **源码兼作数据目录**：SQLite / Chroma / DOCX 输出默认写入 `backend/data/`、`backend/output/`，导致 `git status` 永远脏，无法 GitHub 发布。 | 引入跨平台 `RESUME_DATA_DIR`（默认在 `%LOCALAPPDATA%/ResumeAssistant` 等 Git 仓库外），所有可变路径由其派生；提供自动建目录 + 环境变量覆盖；`T2` 完成。 | T2 |
| 2 | **缺少"零 API Key 运行链路"**：开源用户下载后无 API Key 跑不通任何链路，GitHub 首发冷启动体验差。 | 新增 `run_stub_demo.py`：虚构 Demo 三件套 + 纯本地构建 ResumeDocument + 渲染 docx，证明"模板→事实→输出"全链路；`T5` 完成。 | T5 |
| 3 | **发布前缺少"源码真源 / 数据真源 / 交付真源"三重严格隔离**，导致验收 AGENT 容易在开发污染环境中误判通过。 | T8 产出全新独立 git 仓库一次性 worktree：main 分支，历史长度 1，零 runtime 数据/二进制/PII/绝对路径硬编码；验收 AGENT **仅允许**用此目录。 | T8 |

---

## 二、阶段产出总表（T1–T9）

> T0–T4 是前置基础，T5–T9 完成首发与独立复核。阶段文档已经收束进本 RESULT；版本目录只保留 PLAN 和 RESULT，实现脚本仍保留在 `backend/`。

| 阶段 | PLAN 条目 | 实现 / 证据位置 | 关键结论 | 状态 |
| ---- | --------- | --------------- | -------- | ---- |
| **T1 只读审计** | §6.5.1 | 本 RESULT §十五 | A/B/C/D 四类文件清单；数据读写路径解耦分析；`OUTPUT_DIR` 硬编码位置 2 处。 | ✅ 完成 |
| **T2 路径解耦** | §6.5.2 | `backend/core/config.py` (改) + `backend/api/routes/template.py` (改) + `.env.example` (改) | 引入 `RESUME_DATA_DIR`；所有可变路径派生自此根；默认位于源码仓库外；`mkdir parents=True exist_ok=True` 自动建 5 个子目录。 | ✅ 完成 |
| **T3 数据迁移** | §6.5.3 | `backend/_v14_t3_migrate.py` + 本 RESULT §四/§十/§十五 | SQL 层：表结构/记录数/ID 集完全一致（5 experiences / 1 user / 9 jobs）；V1.3.0 旧 DB `backend/data/app.db` **保留**（`OLD_DATA_NOT_DELETED = True`，回滚开关）；向量层重建 5/5。 | ✅ 完成 |
| **T4 D类脚本审查** | §6.5.4 | 本 RESULT §十五 | `_v14_t3_migrate.py` / `_v13_validation.py` / `run_stub_demo.py` 等 D 类脚本完成输出解耦、PII 与运行产物审查。 | ✅ 完成 |
| **T5 固化 V1.3.0** | §6.6 | `backend/run_stub_demo.py`（新）+ `input/demo_profile.json`（新）+ `input/demo_experiences.json`（新）+ `input/demo_jd.txt`（新）+ 根 `README.md` + `LICENSE` + `backend/.env.example` | 根三件（README/LICENSE/.env.example）齐全；Demo 三件套全虚构无 PII；`run_stub_demo.py` 零 API Key 成功生成 docx，且输出落盘至 `RESUME_DATA_DIR/output`（T6 git clean 证明不在源码树）。 | ✅ 完成 |
| **T6 安全审计** | §6.7 | 根 `.gitignore` + 本 RESULT §七/§十二/§十五 | Secret / PII / 二进制 / 元数据 / 硬编码绝对路径 / 许可证 6 项全扫；A 类源码无阻断性发现；运行后源码树干净。 | ✅ 完成 |
| **T7 干净回归** | §6.8（上半） | `backend/_v14_t7_regression.py` + 本 RESULT §四/§七 | 15 条自动化 case 覆盖 RUNTIME/CORE/V13/MIG；官方复验 12 PASS / 0 FAIL / 3 SUSPEND，挂起项均有明确原因。 | ✅ 官方复验通过 |
| **T8 干净首发包** | §6.8（下半） | `backend/_v14_t8_delivery.py` + `<delivery-root>/.t8-manifest.json` | 最终本地冻结为全新独立 Git 仓库，main 分支、历史 1 条、Git 跟踪 91 文件；必要模板已跟踪，validation artifacts、runtime 数据、PII 与 Agent 产物均排除。 | ✅ 完成；冻结 commit `d99d1bc` |
| **T9 发布前复核** | §6.9 | 本 RESULT §七至§十二 | 三轮完成：第一轮发现 B1/C1–C3，第二轮修复，第三轮确认 L1/L2/L3 与新增收口项全部解决；manifest 91/91、T7、Stub E2E 和安全五门通过。 | ✅ 本地复核与 MIG-3 均通过 |

---

## 三、V1.4.0 核心架构变化

### 3.1 路径解耦总览（config.py 为唯一真源）

```
[跨平台默认] %LOCALAPPDATA%\ResumeAssistant           (Windows)
             ~/Library/Application Support/ResumeAssistant  (macOS)
             ~/.local/share/resume-assistant           (Linux)
        ↑ 也可用 env 变量 RESUME_DATA_DIR 覆盖
        │
        ├─ database/           ← settings.SQLITE_PATH = RESUME_DATA_DIR/database/app.db
        ├─ vectorstore/        ← settings.CHROMA_PATH = RESUME_DATA_DIR/vectorstore
        ├─ output/             ← settings.DOCX_OUTPUT_DIR   = RESUME_DATA_DIR/output
        ├─ logs/               ← 日志目录（自动建）
        └─ cache/              ← 临时文件（自动建）
```

源码树（`BASE_DIR = backend/`）保持 A 类干净，**永不**再写入可变数据。PLAN §6.5 "运行后 git 工作区 clean" 要求由此实现。

### 3.2 关键改动文件（验收 AGENT 建议按此顺序精读）

1. [backend/core/config.py](../../../backend/core/config.py) — `RESUME_DATA_DIR` + 5 个子目录派生；尾部 `assert` 保证路径互斥性；尾部 `_ensure_dirs()` 自动建目录。
2. [backend/api/routes/template.py](../../../backend/api/routes/template.py) — 移除硬编码 `OUTPUT_DIR`；下载接口路径校验兼容旧 `data/output/*` 格式（为 V1.3.0→V1.4.0 平滑切换兜底）。
3. [backend/_v14_t3_migrate.py](../../../backend/_v14_t3_migrate.py) — 迁移主逻辑；`OLD_DATA_NOT_DELETED` 标志；严格 SQL 一致性断言；向量重建 `--rebuild-vectors` 可选。
4. [backend/run_stub_demo.py](../../../backend/run_stub_demo.py) — T5 零 API Key 单条可运行入口；Demo Profile/Experiences/JD 全虚构；证明事实→渲染→落盘链路。
5. [backend/_v14_t7_regression.py](../../../backend/_v14_t7_regression.py) — 15 条 T7 自动化 case；V1.3.0 十 Case 覆盖关系和最终结果已合并在本 RESULT §四/§七。
6. [backend/_v14_t8_delivery.py](../../../backend/_v14_t8_delivery.py) — T8 构建脚本；四道安全屏障；交付 manifest JSON。

---

## 四、开发 AGENT 已锚定的"本环境实测结论"（供验收 AGENT 对照）

> ⚠️ 以下锚定都在**开发 worktree**（非 T8 干净包）里执行，仅用于防止开发侧关键路径失效；最终结论以 §七记录的 T8 独立复验为准。

| 锚定项 | 开发侧实测 | 验收重跑命令（T8 worktree） |
| ------ | ---------- | -------------------------- |
| 路径解耦默认生效 | config.py `_default_runtime_root()` 跨平台命中；`settings.DOCX_OUTPUT_DIR` 断言落在 runtime root | `python backend/_v14_t7_regression.py` RUNTIME-1/2/3 |
| 自动建目录 | 运行 settings 即建 5 子目录（mkdir parents=True exist_ok=True） | 同上 RUNTIME-2 |
| Stub E2E：run_stub_demo.py 零 API Key 生成 docx | ✅ 本工作区成功；T6 git clean 证明输出不在源码树 → 必然在 runtime root/output | `cd backend ; python run_stub_demo.py` |
| 迁移 SQL 一致性 | ✅ 表结构、记录数和 ID 集全相同（5/1/9），`OLD_DATA_NOT_DELETED=True` | `_v14_t7_regression.py` MIG-1/2；有 API Key 后补 `_v14_t3_migrate.py --rebuild-vectors`，结果见 §十 |
| 模板事实边界（不含用户姓名/公司） | ✅ `pm_template.json` 全为字段占位，无示例事实；安全审计通过 | T7 V13-1 + §七/§十五 |
| V1.3.0 核心类构造 / import | 日常调试 + T5 证明全部核心模块可 import / 可实例化 | T7 CORE-1/2/3/4 |
| ResumeBuilder.build 回退链路 | 代码级实现 + T3 5 条 SQL 记录基线 | T7 V13-3 |
| TemplateRenderer 条目不裁剪 | 源码审查 + T5 demo work/education 条目数无丢 | T7 V13-4 |

---

## 五、当时执行的独立验收 SOP

```
1. cd <delivery-root>
   确认：git rev-list --count HEAD = 1   &&   git branch --show-current = main

2. 建全新 venv + 安装 `backend/requirements.txt`

3. 跑 T7：
      cd backend
      python _v14_t7_regression.py --report=<temp-dir>/t7-official.json
   判定：fail=0。

4. Stub E2E：
      python run_stub_demo.py
   判定：屏幕显示 [STUB_DEMO_OK]，DOCX_OUTPUT_DIR 下产出 demo docx（>0KB）。

5. （如机器配 API Key）执行 `_v14_t3_migrate.py --rebuild-vectors` 补 MIG-3。

6. 按 PLAN §6.9 执行性能、安全和发布复核，把对象 commit、结果和问题直接写入本 RESULT。
```

---

## 六、状态

- **开发 AGENT 状态**：✅ T1–T8 全部完成；三轮修正（B1/C1/C2/C3 → L1/L2/L3 → §九-2/§九-3）全部完成；T8 重建并自测通过。
- **验收 AGENT 状态**：✅ 已完成三轮 T9；第三轮确认全部本地发布风险收口，结论“可发布”。
- **当前 RESULT 状态**：**`已验收`**。T9、MIG-3、T10 与 T11 全部通过；Public、tag、匿名访问和全局文档同步已完成。

## 七、T9 高性能源码验收结论

### 第一轮已通过部分

- 根 `.t8-manifest.json`：91/91 文件 SHA256 与字节数一致；
- 全新 Python 3.10.11 venv 安装依赖成功；
- T7：12 PASS / 0 FAIL / 3 SUSPEND；RUNTIME、CORE、V13 全部通过；
- MIG-1/2 因干净包按设计不含旧 C 类数据库而跳过，SQL 迁移证据仍以 T3 为准；
- Stub E2E 在零 API Key 下成功，DOCX 写入仓库外 runtime，运行后源码树干净；
- Secret、PII、许可证和 C 类数据隔离复核通过；A 类 Python 源码无本机绝对路径硬编码。

### 第一轮 B1 发布阻断

`backend/templates/pm_template.docx` 已被 T4/T6 判定为无 PII 的必要 B 类资产，delivery 脚本也将其复制到候选目录；但根 `.gitignore` 的 `backend/templates/*.docx` 使 `git add -A` 静默跳过该文件。验收机因为磁盘上仍有模板而能跑 Stub Demo，干净 Git clone 却没有该文件，必然在加载模板时失败。

复验通过标准：最终 commit 的 `git ls-files` 必须包含该模板，或者干净 clone 能在没有该文件时确定性自动构建；随后从全新 clone 直接按 README 跑通 Stub E2E。对于当前结构，给忽略规则增加该模板的明确例外并将已审计 DOCX 纳入 Git，是更简单的收口方式。

### 第一轮同轮修正项

| 编号 | 问题 | 收口要求 |
|---|---|---|
| C1 | `pip_freeze_baseline.txt` 被忽略，但 T8 交付说明声称包含 | 明确其最终分类：若 `requirements.txt` 已是唯一依赖真源，则从交付说明和 manifest 中删除该文件；如确需发布则显式纳入 Git |
| C2 | Git 内 `docs/versions/v1.4.0/T8_manifest.json` 是陈旧副本：87 文件、11 个 hash 错误；交付目录根 manifest 才是 91/91 | 取消两个互相冲突的 manifest 真源；保留一个可复验清单，或明确 in-repo manifest 不校验自身并在提交前生成；最终 T9 必须按实际 Git 清单复核 |
| C3 | 公开文档有 67 处开发者本机路径 | 用户已确认公开完整版本档案，因此不能通过删除 V1.0.0–V1.3.0 历史文档解决；应将机器、用户名和 worktree 路径替换为不损害开发经验的占位符 |

### 第二轮复验

开发 Agent 重建候选仓库后，高性能源码验收 Agent确认：

- B1：`pm_template.docx` 已进入 commit，干净来源不再缺模板；
- C1：删除 `pip_freeze_baseline.txt`，`requirements.txt` 为唯一依赖真源；
- C2：移除 Git 内陈旧 manifest，根 `.t8-manifest.json` 与 `git ls-files` 对齐为 92=92；
- C3：当前开发者用户名路径已占位符化；旧文档的无用户名盘符路径为低风险历史信息；
- 第二轮 T7 为 12 PASS / 0 FAIL / 3 SUSPEND，Stub E2E 通过，安全五门通过。

高性能 Agent 的第二轮结论“可发布（有条件）”在本 RESULT 中映射为工作流状态 `待验收`：T9 核心门已通过，但完整版本门禁尚未完成。

---

## 八、B1/C1/C2/C3 修正记录（2026-08-17）

### 修正概述

针对第一轮高性能复核指出的 B1 阻断和 C1–C3 同轮修正项，开发 Agent 完成以下工作并重建 T8 首发仓库。

### B1：pm_template.docx 进入 Git 跟踪

| 措施 | 实现 |
|---|---|
| `.gitignore` 例外 | 第 55 行 `!backend/templates/pm_template.docx`（已有，保留） |
| 开发仓库 `git add -f` | 在开发 worktree 显式 `git add -f backend/templates/pm_template.docx`，使其进入 `git ls-files` |
| T8 构建脚本加固 | `init_fresh_git()` 中 `git add -f` 强制纳入 + `git ls-files` 二次验证；manifest 阶段再核查 |
| 验证结果 | T8 worktree `git ls-files backend/templates/pm_template.docx` → ✅ 返回该文件 |

### C1：pip_freeze_baseline.txt 不进入首发

| 措施 | 实现 |
|---|---|
| 分类结论 | `requirements.txt`（23 行，含版本锁定说明）是唯一公开依赖真源；`pip_freeze_baseline.txt`（118 行传递依赖快照）属本地重现辅助，不公开维护 |
| T8 构建脚本排除 | `_FILE_ALWAYS_EXCLUDE_RELPATHS = {"backend/pip_freeze_baseline.txt"}`；`init_fresh_git()` 二次验证 `git ls-files` 不含该文件 |
| 文档清理 | 交付说明不再声称包含该文件；manifest 不记录该文件 |
| 验证结果 | T8 worktree `git ls-files backend/pip_freeze_baseline.txt` → ✅ 返回空 |

### C2：manifest 单真源

| 措施 | 实现 |
|---|---|
| 删除陈旧副本 | `docs/versions/v1.4.0/T8_manifest.json` 已删除（不再在 docs/ 下生成） |
| 唯一真源 | `<delivery-root>/.t8-manifest.json`（交付 worktree 根） |
| 生成时机 | `git commit` 完成后，基于 `git ls-files` 实际跟踪清单重算（`file_list_basis = "git-ls-files (post-commit, canonical)"`） |
| 不进入 Git | `.t8-manifest.json` 在 `_NAME_ALWAYS_EXCLUDE` 中，不会进入 git 跟踪 |
| 文档引用统一 | PLAN / RESULT 中所有 manifest 引用统一指向 `<delivery-root>/.t8-manifest.json` |
| 验证结果 | T8 worktree 仅 `.t8-manifest.json` 一份 manifest，内容与 `git ls-files` 92 文件一致 |

### C3：文档路径占位符化

| 措施 | 实现 |
|---|---|
| 脱敏脚本 | `backend/_v14_c2c3_path_redact.py` 扫描 `docs/**/*.md` 和 `docs/**/*.json` |
| 替换规则 | `<user-profile>\...` → `<repo-root>` / `<delivery-root>` / `<worktrees-root>` / `<user-profile>` / `<temp-dir>` 等占位符 |
| 覆盖范围 | V1.0.0–V1.4.0 完整历史文档保留；6 个文件修正，~105 处路径占位符化，~9 处 manifest 引用修正 |
| 残留检查 | 脚本自检 0 个真实本机路径残留 |

### T8 重建结果

| 指标 | 值 |
|---|---|
| 交付目录 | `<delivery-root>` |
| Git 跟踪文件数 | 92（比首轮 91 多 1，即 `pm_template.docx`） |
| Git 跟踪总字节数 | 815,029 |
| 首发 commit SHA | `fadd7c2f189987aa0d391c296a2fb2ba17f3da4c` |
| 分支 / 历史长度 | `main` / 1 |
| `git status --short` | clean（仅 `.t8-manifest.json` untracked，符合设计） |
| B1 `git ls-files` 含模板 | ✅ |
| C1 `git ls-files` 不含 freeze | ✅ |
| C2 manifest 单真源 | ✅ |
| C3 文档路径脱敏 | ✅ 0 残留 |
| T7 回归 | 12 PASS / 0 FAIL / 3 SUSPEND |
| Stub E2E | ✅ 成功生成 38.5 KB demo_resume.docx，输出在仓库外 runtime |
| 运行后源码树 | clean（无 runtime 数据污染） |

### 交付给高性能验收 Agent 的复验要点

1. `cd <delivery-root>`；确认 `git rev-list --count HEAD = 1` 且 `git branch --show-current = main`；
2. `git ls-files backend/templates/pm_template.docx` 必须返回该文件（B1）；
3. `git ls-files backend/pip_freeze_baseline.txt` 必须返回空（C1）；
4. 确认 Git 跟踪清单中不存在 `docs/versions/v1.4.0/T8_manifest.json`；manifest 唯一真源为 `<delivery-root>/.t8-manifest.json`（C2）；
5. 扫描 `docs/`，确认无真实用户目录等硬编码本机路径（C3）；
6. 跑 T7（`python _v14_t7_regression.py`）确认 12 PASS / 0 FAIL / 3 SUSPEND；
7. 跑 Stub E2E（`python run_stub_demo.py`）确认零 API Key 成功；
8. 按 V1.4.0 PLAN §6.9 执行安全/迁移/发布三件套复核。

---

## 九、第三轮后剩余门禁

第三轮已经完成本地发布风险收口，不需要第四轮完整高性能验收。各门禁状态如下：

1. ✅ **第三轮候选冻结**：候选 commit `341512db...` 为单提交、91 个跟踪文件；validation artifacts 改写入临时目录，不进入 Git。
2. ✅ **清理 Agent 产物**：`.workbuddy/` 已同时由 `.gitignore` 和 T8 构建脚本排除。
3. ✅ **完全脱敏**：Secret、旧路径和脚本自身硬编码均已清零，高性能 Agent 第三轮复验通过。
4. ✅ **最终清单复验**：第三轮在报告写回前确认 manifest=Git=91，SHA256 91/91，运行后源码树干净。
5. ✅ **MIG-3**：在有效 API Key 环境从迁移后 SQL 全量重建向量，`total_sql=5 / upserted=5 / deleted_stale=0 / failed_ids.count=0 / errors=[] / vector_rebuild_all_ok=true`；user_id 从 SQL 首条用户自动获取，非 settings 默认值。
6. ✅ **T10/T11**：Private 干净 clone、依赖安装、修正后的 Stub E2E、Public、annotated tag `v1.4` 和匿名 clone 全部通过。

第三轮验证完成后，高性能 Agent 将验收结论写回工作区，当时因此出现文档修改、manifest 对当前工作区暂时为 89/91。这是记录动作，不是源码回退；随后完成 docs-only 冻结、重新生成 manifest 并机械核对，未再启动第四轮完整验收。

V1.4.0 全部门禁已完成；本 RESULT、`CURRENT_STATE.md`、入口索引与全局决策状态已同步。

---

## 十、MIG-3 完成与最终机械冻结（2026-08-17）

### MIG-3 向量重建

- 执行入口：`python _v14_t3_migrate.py --rebuild-vectors`；
- user_id 来源：从迁移后 SQL 首条用户自动获取（`sql_first_user`），非 `settings.DEFAULT_USER_ID`；
- 结果：
  - `total_sql=5 / upserted=5 / deleted_stale=0`；
  - `failed_ids.count=0 / errors=[]`；
  - `vector_rebuild_all_ok=true`；
- 脱敏：报告生成后由 `_v14_c2c3_path_redact.py` 重新处理，0 残留硬编码本机路径。

### 最终机械冻结

按第三轮验收结论，MIG-3 完成后只做无副作用的机械冻结，不重跑完整回归。

- 重建命令：`python _v14_t8_delivery.py --dest <delivery-root>`；
- 冻结结果：
  - Git：`main` 分支，单 commit，HEAD `d99d1bc22a86c3c9b016dc266dac11353cdb3386`；
  - 文件数：manifest=Git=`git ls-files`=**91**；
  - SHA256：逐文件 **91/91** 一致，0 mismatch；
  - B1：`git ls-files backend/templates/pm_template.docx` 返回该文件 ✅；
  - C1：`git ls-files backend/pip_freeze_baseline.txt` 返回空 ✅；
  - manifest 唯一真源：`<delivery-root>/.t8-manifest.json`（docs/versions/v1.4.0/T8_manifest.json 不再生成）；
  - 工作区 `git status --short` 干净。

### 剩余门禁

无。T10/T11、用户授权、Public、tag、匿名访问复核与最终状态同步均已完成。

---

## 十一、T10 Private 预发布与干净 Clone（2026-08-18）

### Private push

- Remote：`https://github.com/<github-owner>/resume-assistant.git`；
- Visibility：Private；
- Branch：`main`；
- 本地冻结 commit `d99d1bc22a86c3c9b016dc266dac11353cdb3386` 已成功推送；
- Git 认证使用 Git Credential Manager 浏览器授权，remote URL 不含 Token；Clash/Mihomo 仓库级代理端口为本机配置，不写入项目文档。

### 干净 Clone 与安装

- 从 Private remote 重新 clone 到 `<temp-dir>/v14-t10-clean-clone`；
- Clone 初始 HEAD=`d99d1bc...`、branch=`main`、Git 跟踪 91 文件、必要模板存在、依赖快照未跟踪、工作区干净；
- Python 3.10.11 全新 venv；`pip install -r backend/requirements.txt` 成功。

### T10 新发现与修正

首次按 README 在 Windows 默认 GBK 控制台运行 Stub：DOCX 已成功生成并写入仓库外 runtime，但结尾打印 emoji 时触发 `UnicodeEncodeError`，导致进程退出码为 1。该问题未影响生成结果，却违反 README 的零密钥入口应以成功码完成的要求。

修正：

- `backend/run_stub_demo.py` 将警告 emoji 改为 ASCII `[WARN]`；
- 成功结束标记改为 ASCII `[STUB_DEMO_OK]`；
- 复验结果：Stub exit code=0、DOCX 38.5 KB、输出位于仓库外 runtime；
- 同轮修正根 README 中仍停留在第二轮“需修正”的版本状态。

上述改动属于 T10 跨环境兼容性与文档收口，不改变 V1.4.0 核心架构，也不触发第四轮 T9。修正已作为 commit `e631531d93f23f0d4f3bc37f43aee2a0b982fc82` 推送；本地 HEAD 与 `origin/main` 一致，最终 Stub 退出码为 0，工作区干净。T10 通过。

---

## 十二、T11 Public 发布（2026-08-18）

- 仓库：`https://github.com/<github-owner>/resume-assistant`
- 默认分支：`main`
- 最终可见性：Public（GitHub API 200，`private=false`）
- 源码冻结 commit：`d99d1bc22a86c3c9b016dc266dac11353cdb3386`
- T10 跨环境修正 commit：`e631531d93f23f0d4f3bc37f43aee2a0b982fc82`
- 发布记录 commit：`c5d9f6ebc54045a4553d9a113e0406584f4ac763`
- 发布标签：`v1.4`（annotated tag）；tag object `30175b22b52d659dfe7d7693475609f91b8270e7`，解引用到 `c5d9f6ebc54045a4553d9a113e0406584f4ac763`
- 用户授权：2026-08-18 已确认旧令牌撤销，并明确授权转 Public
- 匿名访问：关闭 Git 凭据助手并禁止交互后，`ls-remote` 成功读取 `main`、tag object 与解引用 commit
- 匿名 clone：从 `v1.4` 全新 clone 成功；HEAD `c5d9f6e`，91 个跟踪文件，必要模板已跟踪，冗余 `pip_freeze_baseline.txt` 未跟踪，工作区干净
- 发布结论：PASS；V1.4.0 转为 `已验收`
- 说明：tag 固定发布代码与发布前记录；tag 后只追加最终验收状态文档，不移动或覆盖既有标签

---

## 十三、第三轮修正记录（L1/L2/L3 + §九-2/§九-3）

### 修正概述

针对 T9 第二轮遗留的 3 项弱风险（L1/L2/L3）和文档 Agent §九 收口清单中的第 2、3 项，开发 Agent 完成以下修正并重建 T8 首发仓库。

### L1：API Key 前缀脱敏

| 措施 | 实现 |
|---|---|
| 安全审计记录修正 | 真实 key 前缀（ark-[hex]）→ `ark-********`（文档真源已改） |
| 脱敏脚本集成 | `_v14_c2c3_path_redact.py` 中 `_ARK_PATTERN = r"ark-[a-f0-9]{8,}"` 自动匹配并替换为 `ark-********` |
| 残留检查 | T8 HEAD `git grep` 真实前缀 → 0 匹配（仅脱敏脚本检测模式中有通配符） |

### L2：旧盘符路径脱敏

| 措施 | 实现 |
|---|---|
| 脱敏规则扩展 | `_v14_c2c3_path_redact.py` 新增 `[dD]:\\V1` / `[eE]:\\V1` → `<old-dev-root>` 替换规则 |
| 覆盖范围 | V1.0.0–V1.3.0 RESULT 中的 `cd <old-dev-root>\backend`、`<old-dev-root>\output\`、`<old-dev-root>\V1` 等 9 处旧盘符路径全部替换 |
| 残留检查 | T8 HEAD `git grep -E "[dDeE]:[\\\\/]V1"` → 仅脱敏脚本注释（非文档泄露） |

### L3：验收产物排除出 Git

| 措施 | 实现 |
|---|---|
| .gitignore | 新增 `docs/versions/v1.4.0/validation-artifacts/` 排除规则 |
| T8 构建脚本 | `_DIR_EXCLUDE` 新增 `"validation-artifacts"`，构建时不拷贝该目录 |
| 效果 | T8 HEAD `git ls-files docs/versions/v1.4.0/validation-artifacts/` → 空；验收 Agent 跑 T7 时的报告写到 `%TEMP%`，不再污染源码树 |

### §九-2：Agent 产物排除

| 措施 | 实现 |
|---|---|
| .gitignore | 新增 `.workbuddy/` 排除规则 |
| T8 构建脚本 | `_DIR_EXCLUDE` 新增 `".workbuddy"`，构建时不拷贝该目录 |

### §九-3：脱敏脚本不硬编码 PII

| 措施 | 实现 |
|---|---|
| 用户名通配符 | 原数字用户名硬编码 → `\d+`（`_UN` 变量），匹配任意数字用户名 |
| 通用兜底 | 新增 `[^\s\\/]+`（`_UN_G` 变量），匹配非数字用户名 |
| API Key 前缀 | 真实前缀（ark-[hex]）→ `ark-[a-f0-9]{8,}`（`_ARK_PATTERN` 变量，通配符匹配） |
| 文档注释 | 移除所有真实路径示例，改为占位符说明 |
| 验证 | `grep` 真实用户名/前缀 → 0 匹配 |

### T8 重建结果（第三轮）

| 指标 | 值 |
|---|---|
| 交付目录 | `<delivery-root>` |
| Git 跟踪文件数 | 91（排除 validation-artifacts/t7-official.json） |
| 首发 commit SHA | `341512db2dec29c4c99dbe1f21977a76d839496e` |
| 分支 / 历史长度 | `main` / 1 |
| `git status --short` | clean（仅 `.t8-manifest.json` untracked） |
| L1 key 前缀 | ✅ `ark-********` |
| L2 旧盘符路径 | ✅ 0 残留 |
| L3 validation-artifacts | ✅ 不在 Git 跟踪中 |
| §九-2 .workbuddy | ✅ 排除 |
| §九-3 脚本无 PII | ✅ 0 硬编码 |
| T7 回归 | 12 PASS / 0 FAIL / 3 SUSPEND |
| 运行后源码树 | clean |

### 交付给高性能验收 Agent 的第三轮复验要点

1. `cd <delivery-root>`；确认 `git rev-list --count HEAD = 1` 且 `git branch --show-current = main`；
2. `git grep -E "ark-[a-f0-9]{8,}" -- docs/` → 应返回空（真实 key 前缀不应出现在文档中）；
3. `git grep -E "[dDeE]:[\\\\/]V1" -- docs/` → 应返回空（旧盘符路径已脱敏）；
4. `git ls-files docs/versions/v1.4.0/validation-artifacts/` → 应返回空（L3）；
5. `git ls-files .workbuddy/` → 应返回空（§九-2）；
6. 扫描 `backend/_v14_c2c3_path_redact.py`，确认不含原用户名或原本机路径字面量（§九-3）；
7. 跑 T7（`python _v14_t7_regression.py --report=$TEMP/t7.json`）确认 12 PASS / 0 FAIL / 3 SUSPEND；
8. 跑 Stub E2E（`python run_stub_demo.py`）确认零 API Key 成功；
9. 按 V1.4.0 PLAN §6.9 执行安全/迁移/发布三件套复核。

---

## 十四、发布后 README 受众分层修正（2026-08-18）

### 发现的问题

V1.4.0 PLAN §5.3 和 T1 审计已明确采用“精简根 README + `docs/` 完整版本档案”，但公开后的根 README 同时承担项目介绍、文件分类和内部版本状态入口，普通 GitHub 用户难以先抓住项目用途与使用方式。

### 修正

- 根 `README.md` 改为自包含的 GitHub 用户入口：项目用途、核心流程、能力、安装、零密钥 Demo、真实 API、主要接口、运行数据、隐私、目录结构、当前边界和 License；
- 根 README 不再把 Task、审计分类和版本状态流水账作为首页主叙事，同时保留清晰的开发档案入口；
- `docs/README.md` 明确为开发者与 Agent 的总入口；
- `HUMAN_AI_WORKFLOW.md` 将所有开发角色的默认入口明确为 `docs/README.md`；
- 新增决策 D-021，防止后续版本再次把公开说明与开发状态混在同一入口。

后续用户补充澄清：上述分层用于形成正常的 GitHub 项目介绍，不是隐藏 Agent 驱动开发痕迹。完整人机协作开发历史继续公开保留，并作为架构学习、项目复用和求职展示内容；D-021 已按该含义修正。

### 影响与验证

- 源码、API、数据模型、配置和依赖：无变化；
- 根 README 的命令、路径和 API 已对照 V1.4.0 公开源码核验；
- 相对链接、敏感信息扫描和 Markdown diff 检查必须通过后再推送；
- 本修正只纠正 V1.4.0 公开文档交付偏差，不重写 V1.0.0–V1.3.0 的历史过程记录，也不移动既有 `v1.4` tag。

---

## 十五、原分项证据收束

V1.4.0 开发期间曾按 T 编号生成多份审计、迁移、交付、验收和手动发布文件。为遵守“每个版本只保留 PLAN + RESULT”的全局规则，以下独有信息已合并到本 RESULT，原分项文件不再作为长期真源。

| 阶段 | 合并后保留的事实 | 主要经验 |
|---|---|---|
| T1 框架审计 | A 类为可直接公开的源码、配置示例和通用文档；B 类为需确认无 PII/许可证后公开的模板与二进制资产；C 类为数据库、向量索引、用户输入、输出、日志、缓存和凭据；D 类为迁移、验证、交付等开发辅助脚本 | 先按“是否随用户和运行变化”划边界，再决定目录；不能靠每次发布前人工挑文件 |
| T2 路径解耦 | `RESUME_DATA_DIR` 是运行数据根；SQLite、Chroma、DOCX、日志和缓存均从其派生并自动建目录 | 源码位置负责不可变资产，runtime root 负责可变数据，二者不能互相回退 |
| T3 迁移 | 初次迁移验证时 users=1、experiences=5、vector jobs=9；表结构、记录数和 ID 集一致；旧 DB 保留用于回滚；MIG-3 后 5/5 向量重建成功、0 failed | 数据迁移必须同时证明新数据正确、旧数据仍可回滚、向量可从 SQL 重建；原始机读快照含临时路径和大量 ID，不作为公开长期文档 |
| T4 辅助脚本与模板 | 迁移、验证、Stub、交付脚本不写源码树 runtime；`pm_template.docx` 经 PII 审计后属于必须发布的 B 类资产 | D 类脚本可以进入源码，但产物必须写到 runtime 或临时目录；二进制模板不能只存在于工作区而未进入 Git |
| T6 安全审计 | 真实 Secret 0；PII 命中均为虚构 Demo/测试数据；公开二进制仅必要模板；许可证为 MIT；A 类源码绝对路径 0；C 类运行数据未进入首发包 | `.gitignore` 只是最后防线，发布前仍需按 Secret、PII、二进制、路径、许可证和数据隔离六门复扫 |
| T7 回归 | 全新 Python 3.10.11 venv 安装成功；12 PASS / 0 FAIL / 3 SUSPEND；挂起项为干净包没有旧数据库或需要真实 API Key；零 Key Stub 成功且输出在源码树外 | 开发环境锚定不能替代干净包复验；测试报告应写临时目录，不能反向污染候选仓库 |
| T8 交付 | 新 Git 仓库、`main`、单提交；最终清单 91 文件；manifest 与 Git、SHA256 91/91；必要模板跟踪，依赖快照、runtime、验收产物和 Agent 目录排除 | manifest 必须在 commit 后按 `git ls-files` 生成，并且不校验或跟踪自身，避免双真源和生成时序错误 |
| T9 三轮复核 | 第一轮发现模板未跟踪及依赖快照/manifest/路径问题；第二轮确认核心修复；第三轮清零 Key 前缀、旧盘符路径、验收产物、Agent 产物和脱敏脚本自身 PII | 功能测试通过不等于干净 clone 可运行；必须从 Git blob、清单和真实 clone 视角验证发布物 |
| T10/T11 发布 | Private push、干净 clone、全新安装、Stub exit code 0、转 Public、annotated `v1.4` tag、匿名 `ls-remote` 与匿名 clone 均通过 | 首次公开采用干净历史；认证不把 Token 写入 URL；Windows 默认控制台也属于真实用户环境，输出字符必须兼容 |

分项文件删除后，阶段目标仍以 PLAN 为准，实际过程、偏差、三轮问题、修正措施、commit、tag 和验收数据全部以本 RESULT 为准。
