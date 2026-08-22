# V1.4.1 版本 RESULT

**版本号**：V1.4.1（对外版本一致性 + 身份边界清理补丁）
**日期**：2026-08-19（核心补丁） / 2026-08-22（N4 最终验收）
**状态**：`已验收` — 高性能源码验收 Agent 已于 2026-08-22 完成 N4 后最终源码验收：候选 commit `317c5266` 的 manifest/SHA256/Git 三一致 88/88/88、T7 12 PASS / 0 FAIL、Stub E2E 干净环境 20/20、身份边界独立推导 10/10，源码与 runtime 安全门通过。首轮纯文档冻结候选 `2b6e8f9` 机械核对通过，但因包内仍保留“待最终冻结”状态文字，且文档复核另发现两处历史 GitHub 用户名未脱敏而退出发布；发布档案随后完成稳定语义和隐私收口，最终发布 commit 由 annotated tag `v1.4.1` 标识。遗留 1 项测试隔离缺陷（非阻断，见 §九末尾）。

源码基线公开仓库 commit 仍基于 V1.4.0；既有 v1.4 tag 保持不动。

前置版本：[V1.4.0 RESULT](../v1.4.0/RESULT.md)
本版本计划：[V1.4.1 PLAN.md](./PLAN.md)

---

## 一、V1.4.1 目标回顾（对照 PLAN.md §2）

本版本是补丁收口：V1.4.0 发布后 Work Buddy 发现公开源码存在版本漂移和死代码风险，不改变 V1.4.0 的 API、数据、生成流程和运行数据边界。

| # | V1.4.0 暴露的问题 | V1.4.1 解决方案 | 对应 T |
|---|----------------|---------------|--------|
| 1 | FastAPI `version` 与 `GET /` 返回 `1.3.0`，与公开版本 V1.4.0 不一致 | 新增 `backend/core/version.py` 中 `APP_VERSION="1.4.1"`，main.py / run_stub_demo.py / OpenAPI 三处统一读该常量 | T1 |
| 2 | `resume_builder.py` 仍保留 `_extract_profile_from_experiences()` + 三项正则常量，与 D-019 冲突（身份字段只取 request） | 删除该函数、三项正则和不再使用的 `import re`，保持 `ProfileResolver` 规则不变 | T2 |
| 3 | `_v13_stub_e2e.py` 仍 patch 旧函数并期待“姓名为空 → PROFILE_INCOMPLETE”，测试契约过期 | 删除旧 patch，替换为身份边界 A1–A4（ProfileResolver 单元）+ B1–B2（核心链路）六场景；修正 happy_path 中旧版 `BACKEND_ROOT/file_path` 路径错误 | T3 |
| 4 | 根 README 顶层版本号与“开发档案分层目的”表达待修正 | 版本号改为 V1.4.1；补充说明项目保留完整人机协作档案并把它作为架构学习/求职展示内容，分层服务不同读者不隐藏开发方式 | T4 |

---

## 二、实际变更文件清单（与 V1.4.0 基线对比）

开发 worktree 内与 V1.4.1 强相关的源码/文档差异：

| 文件 | 变更类型 | 作用 | 对应条目 |
|------|---------|------|---------|
| `backend/core/version.py` | 新增 | 单一版本常量真源：`APP_VERSION = "1.4.1"` | T1 |
| `backend/main.py` | 修改 | FastAPI `version` / OpenAPI `info.version` / `GET /` 三处都引用 `APP_VERSION`；OpenAPI description 改成不易过期的通用描述 | T1 |
| `backend/run_stub_demo.py` | 修改 | banner 从硬编码 V1.4.0 → `f"V{APP_VERSION}"` | T1 |
| `backend/services/resume_builder.py` | 修改 | 删除 `import re`、`_PHONE_RE/_EMAIL_RE/_NAME_HINT_RE`、`_extract_profile_from_experiences()`；保留 `ProfileResolver` 与 `ProfileIncompleteError` 导入 | T2 |
| `backend/_v13_stub_e2e.py` | 修改 | a) 增加 `APP_VERSION` / `_ProfileDoc` 头部 import；b) 用 `_run_profile_boundary()`（六场景）替换旧的 `_run_profile_error()`；c) happy_path 修正 DOCX 路径 (OUTPUT_DIR/resp.file_name) 和 UnboundLocalError；d) 显示文案从 5 scenarios 改为动态 | T3 |
| `README.md` | 修改 | 顶部版本号改为 **V1.4.1**；快速开始段落引用 V1.4.1；分层描述自然化 | T4 |
| `docs/versions/README.md` | — | 开发启动时该版本仍标记为待开发；最终已由文档 Agent 按 §六同步为实际结果 | §6 |

**明确未改**（符合 PLAN §3「明确不做」）：
- 数据库表结构、Experience/VectorIndexJob 模型、V1.4.0 路径解耦、JD→RAG→Builder→DOCX 主链路
- V1.3.0 首次建立的源码注释、`/api/resume/generate` 兼容说明、V1.3.0 历史验收脚本文件名
- `ProfileIncompleteError` 导出（保留 `from core.errors import ProfileIncompleteError  # noqa: F401` 兼容 template.py）
- 不覆盖 `v1.4` tag

---

## 三、验证矩阵（开发 AGENT 锚定结论）

> 开发侧锚定在本 worktree（非 T8 干净环境）执行，仅用于防止 V1.4.1 代码本身连开发侧都坏了；最终验收必须由高性能源码验收 AGENT 在 **T8 干净首发包 + 全新 venv** 中重跑，不得直接采信下表。

### 3.1 T1：版本元数据单一真源

| 验证项 | 开发侧结果 | 证据（开发 worktree，Python 3.10.11） |
|---|---|---|
| `core.version.APP_VERSION == "1.4.1"` | ✅ PASS | `from core.version import APP_VERSION` → `1.4.1` |
| FastAPI `app.version` | ✅ PASS | `from main import app; app.version` → `1.4.1` |
| OpenAPI `info.version` | ✅ PASS | `app.openapi()['info']['version']` → `1.4.1` |
| OpenAPI description 无 V1.3.0 字样 | ✅ PASS | 描述改为「核心生成：POST /api/resume/generate-docx ...」无过期版本名 |
| `GET /` 返回 version | ✅ PASS | TestClient `200`，body `version=1.4.1`，vector_backend=chroma |
| Stub Demo banner 显示 `V1.4.1` | ✅ PASS | 运行截图包含 `Resume Assistant V1.4.1 — Stub Demo` |
| 源码 grep 硬编码 `"1.3.0"`（排除 .venv） | ✅ PASS | 0 命中；仅 .venv 第三方包有历史版本号 |
| 死代码残留 grep（活动代码） | ✅ PASS | 无 `_extract_profile_from_experiences`、`_PHONE_RE`、`_EMAIL_RE`、`_NAME_HINT_RE` |
| `resume_builder.py` 无 `import re` | ✅ PASS | 0 命中 |

### 3.2 T3：身份边界测试（V1.4.1 新增六场景 + 旧 happy/error 回归）

`_v13_stub_e2e.py` 最终输出：`Happy Path: 10/10  错误分支: 10/10  总计: 20/20`。

| 场景 | 结果 | 核心断言 |
|---|---|---|
| Profile边界A1: request空 → profile全空, source=empty | ✅ PASS | `name/phone/email/location` 全 `""`，`profile_source="empty"` |
| Profile边界A2: request空 + 经历注入虚构联系方式 → 全空, 不回填 | ✅ PASS | `欧阳不该出现在文档里 / 13999998888 / leaked-fake@should-not-appear.com` 都未进入 Profile |
| Profile边界A3: request仅提供 phone+email, 无 name → 仅保留显式值, 不经历补 name | ✅ PASS | `name=""`，`phone/email` = STUB_PROFILE 显式值，`profile_source="request"` |
| Profile边界A4: profile_source 只取值 request 或 empty | ✅ PASS | A1~A4 三个场景返回值 ∈ {request, empty} |
| Profile边界B1: name空但 phone+email 存在 → 核心链路成功（不再 PROFILE_INCOMPLETE） | ✅ PASS | `resp.ok=True`，所有 stages.status=done，无异常抛出 |
| Profile边界B2: 经历注入的虚构姓名/手机/邮箱不进入 DOCX | ✅ PASS | DOCX 全文本无三字符串泄露，也不出现 PROFILE_INCOMPLETE 字面量 |
| Happy Path 1~10（原 V1.3.0 十项不变） | ✅ 10/10 | 不变行为受 V1.3.0/V1.4.0 既有契约约束，这里不再展开 |
| 错误分支 JD/RAG/LLM/索引（原 V1.3.0 四项不变）| ✅ 4/4 | 同上 |

### 3.3 T7 回归（15 条）：开发 worktree 环境污染导致的两个 FAIL 的根因澄清

| Case | 开发 worktree 结果 | 根因与等价验证 |
|---|---|---|
| RUNTIME 1/2/3 | ✅ PASS | 全新 runtime root、settings 派生 5 子目录、路径互斥 |
| CORE 1/2/3/4 | ✅ PASS | 导入全部核心模块；BASE_DIR Path 指向 backend；init_db() 3 表；TemplateRenderer(pm_template) OK |
| V13 1/2 | ✅ PASS | 模板 JSON 无 PII；ProfileResolver request-only + JD-only 正确 |
| V13-3 | ❌ FAIL：OperationalError 沙箱拒写 `app.db-journal` | 等价夹具（全新 TEMP runtime）✅ PASS：fallback bullets 有 "下单/618零事故/TPS翻2倍"，fb_w 在 fallback_sql_experience_ids |
| V13-4/5 | ✅ PASS | 渲染不裁条目；Stub DOCX 输出落在 DOCX_OUTPUT_DIR |
| MIG-1 | ✅ PASS（兼容） | A/B 分类一致，旧 backend/data 不进首发 |
| MIG-2 | ❌ FAIL：实际 counts 24/1/24 ≠ V1.4.0 基线 5/1/9 | **开发 worktree 的 baseline 文件 `backend/data/app.db` 被历史 stub e2e 反复运行污染成 6 倍**（非代码回归）；等价夹具对比 old=new 的 SQL count=24/1/24（copy 正确性无问题）。**T8 干净首发包因排除 `backend/data/`，此文件不在首发范围。**高性能验收 AGENT 在 T8 环境不会遇到此文件。 |
| MIG-3 | ⏸ SUSPEND：需 ARK_API_KEY | V1.4.0 已在 MIG-3 通过，V1.4.1 不修改向量代码；如机器配置 API Key 可在 T8 环境补跑 |

### 3.4 运行时安全与干净性（5 项）

| 项 | 结果 | 说明 |
|---|---|---|
| Stub Demo 运行后源码树 git status（只看 A 类） | ✅ 干净 | 变化仅限当前 V1.4.1 代码文件（version.py / main.py / run_stub_demo.py / resume_builder.py / _v13_stub_e2e.py / README / docs 版本 / pm_template.docx），无 runtime 数据落到源码树 |
| 令牌扫描（源码 .py 无 ghp_/ark-xxxxx） | ✅ 干净 | 0 命中（`.env` 本机配置在 .gitignore） |
| PII 手机号扫描 | 仅 Demo 虚构值 | `13800000001`（STUB_PROFILE）与 `13999998888`（边界测试虚构泄露值）均为故意构造，无真实用户 PII |
| 绝对路径硬编码（源码 .py） | ✅ 干净 | backend/output/ JSON 产物、`_v14_t8_delivery.py:14`（D 类工具，T8 排除）非活动运行代码 |
| pm_template.docx 跟踪状态 | ✅ 跟踪 | `git ls-files backend/templates/pm_template.docx` → 存在 |

---

## 四、替换型变更的正向、反向与回归证据（PLAN §4 总表要求）

| 变更 | 正向验证（新行为发生） | 反向验证（旧行为零残留） | 回归证据（V1.4.0 核心功能不坏） |
|---|---|---|---|
| 版本元数据单真源 | §3.1：FastAPI / OpenAPI / GET / Stub banner 全部=1.4.1 | 活动代码 grep `hardcoded "1.3.0"`=0；死 grep `_PHONE_RE ...`=0 | T7 V13 Stub(10/10)+Error(4/4) + Stub Demo + T7 RUNTIME/CORE/V13-1,2,4,5 全部通过 |
| 身份提取死代码删除 | §3.2：Profile边界 A1,A2,A3 单测证明 request-only | 死代码 grep 0；边界 A2,B2 证明虚构接触经历不回填；`import re` 从 resume_builder 消失 | Profile边界B1证明 name空=合法成功；V13 Stub happy(10/10) 证明主流程不坏 |
| 过期测试改为新契约 | §3.2：A1~A4, B1~B2 (6 PASS) | 旧 `_run_profile_error` 函数 + patch `_extract_profile_*` 代码已删除，grep 0 | Error 4 (JD/RAG/LLM/索引) + Happy 10 继续全数通过 |
| README 分层+版本 | 顶部版本号=V1.4.1；档案分层说明自然化 | 检查：无"刻意隐藏开发方式"类表述 | - |

---

## 五、结构变更验收（PLAN §2）

- [x] 源码目录结构未新增目录（`backend/core/version.py` 是新增单文件，不影响结构）
- [x] API 路由签名、请求响应模型、数据库 schema 未改变
- [x] `requirements.txt` 未修改、依赖版本一致
- [x] `RESUME_DATA_DIR`、路径解耦、DOCX 输出目录位置、自动建目录行为未改变
- [x] pm_template.docx 仍保持跟踪（T8 验收时复制进入首发包）

---

## 六、版本索引与后续文档接力

文档 Agent 已于 2026-08-19 完成：

1. `docs/versions/README.md` 和 `docs/README.md` 增加本 RESULT 与实际阶段结论；
2. `docs/CURRENT_STATE.md` 将已验收实现基线更新为 V1.4.1；
3. 根 README 已由开发侧统一为 V1.4.1，且对普通 GitHub 读者保持自包含；
4. 将高性能源码验收对象、结论和关键证据合并进本 RESULT §九，不保留独立验收文档；
5. 对全部拟公开 Markdown 执行本机路径、用户名和凭据写法扫描，完成 N2/N3；
6. `DECISIONS.md` 中既有 D-019 与 V1.4.1 流程复盘仍有效，本版本没有新增需要单独编号的架构决策。

---

## 七、源码 AGENT 复验 SOP（独立推导身份边界，防止开发 AGENT 测试自证）

> 开发 AGENT 写的测试不能代表验收结论。源码 AGENT 必须：
> 1) **独立写出** D-019 + V1.4.1 PLAN 推导的身份边界反向场景；
> 2) 在 **T8 干净首发包 + 全新 venv** 下重跑所有验证；
> 3) 不直接引用 §三 的测试代码和断言文字；
> 4) 把简短结论、被验收 commit SHA 和必要证据写入本 RESULT §九/§十，不创建独立验收报告。

源码 AGENT 最小必做清单：

```
1. 在本机 CMD 构建 T8 干净首发包（见 §八）
2. 进入 <delivery-root>：确认 `git rev-list --count HEAD = 1`；记录 `git ls-files` 的最终实际数量，不再使用首轮 96 作为固定值
3. 全新 venv + pip install -r requirements.txt
4. 重跑 T7（backend/_v14_t7_regression.py）→ fail = 0
   ⚠️ T8 干净首发包中 backend/data/app.db 不存在，MIG-2 会按 PLAN.A/B 兼容规则 PASS（不需 baseline DB）
5. Stub E2E: backend/_v13_stub_e2e.py → 20/20
6. Stub Demo: backend/run_stub_demo.py → [STUB_DEMO_OK]
7. 独立验证身份边界（开发 AGENT 不允许代做）：
   a. ProfileResolver.resolve(None, "PM") → name/phone/email == ""，profile_source="empty"
   b. 构造 experiences，把 raw_text 里塞入真实手机号/邮箱/姓名，调用 ProfileResolver → Profile 里完全不出现
   c. 在 generate_docx 流程中，name 为空但 phone/email 有值 → 流程不应 PROFILE_INCOMPLETE
   d. grep -r "_extract_profile_from_experiences" 全仓库 → 空（除已删除文件外）
8. 版本一致性独立核验：FastAPI version、GET /、run_stub_demo banner 三处全为 1.4.1
9. 模板跟踪 / manifest 核对：同 V1.4.0 T9
```

---

## 八、T8 干净首发包构建记录

由于跨 worktree 写入限制，开发侧先把候选包构建到临时目录，再由用户在本机把临时产物移入干净验收目录。下列命令使用语义路径，不保留具体电脑目录：

```powershell
$DevelopmentRoot = '<development-root>'
$TempBuild = Join-Path $env:TEMP 'V1-t8-build'
$DeliveryRoot = '<delivery-root>'

Set-Location (Join-Path $DevelopmentRoot 'backend')
python _v14_t8_delivery.py --dest $TempBuild

Remove-Item -Recurse -Force $DeliveryRoot -ErrorAction SilentlyContinue
Move-Item $TempBuild $DeliveryRoot

git -C $DeliveryRoot rev-list --count HEAD
git -C $DeliveryRoot branch --show-current
git -C $DeliveryRoot ls-files
```

首轮构建成功标志：
- `manifest['tracked_file_count']` = 96
- `manifest['git']['b1_template_tracked']` = True
- `manifest['git']['status_after_commit_clean']` = True

实测为 `commit=1`、`branch=main`、`tracked_file_count=96`、`version.py` 已跟踪、身份提取死代码 0 命中。N1 和最终文档收口发生在首轮构建之后，因此最终发布包必须重新生成清单和 SHA。

---

## 九、高性能源码验收结论

```
首轮验收 commit SHA：da1754f1e0c4d8ce1cfe69c8ae04366cd8db6bdd
被验收 branch     ：main
tracked_file_count：96
version.py APP_VERSION 验证：PASS
死代码 _extract_profile_from_experiences 残留：无
身份边界独立反向推导：20 / 20 PASS
T7：12 PASS / 0 FAIL / 3 SUSPEND（预期挂起）
Stub E2E：首轮发现 N1；修复后二次验收 20 / 20 PASS（无真实 Key）
Stub Demo：[STUB_DEMO_OK]
manifest / SHA256 / git ls-files：96 / 96 / 96 PASS
简短结论：核心结构和事实边界通过；N1 已定向修复并复验，N2/N3 由文档 Agent 完成公开化收口。

验收 AGENT 签名 / 日期：高性能源码验收 Agent / 2026-08-19
```

### 最终验收（N4 后，2026-08-22）

N4 源码侧 5 项定向复核全部通过，源码验收 T8 包（HEAD `317c5266`）复验结论：

```
最终验收 commit SHA：317c52660335a9dc35107d4627c25739c8eb4f9f
被验收 branch     ：main
tracked_file_count：88（N4 文档收束后实际值，已替代首轮 96）
N4 源码侧复核      ：通过（.gitignore 通配符 / 交付脚本不再生成旧 manifest / 脱敏脚本无旧版本目录 / 验收脚本 --report 默认 None / 文件数改实际值）
version.py APP_VERSION 验证：PASS（1.4.1，四处一致，活动代码无硬编码 1.3.0）
死代码残留          ：无（_extract_profile_from_experiences / 三正则 / import re 全 0 命中）
身份边界独立反向推导：10 / 10 PASS（request-only、注入虚构联系方式不回填、缺身份合法、target_position 只取 JD）
T7 回归             ：12 PASS / 0 FAIL / 3 SUSPEND（预期挂起）
Stub E2E            ：干净 runtime 下 20 / 20 PASS（无真实 Key；见下方测试隔离缺陷说明）
Stub Demo           ：[STUB_DEMO_OK]（banner=V1.4.1，落盘仓库外 runtime）
manifest / SHA256 / git ls-files 三一致：88 / 88 / 88 PASS
安全扫描            ：源码与 runtime 范围 Secret 0、PII 全虚构测试号段、本机绝对路径 0；公开 Markdown 的 GitHub 用户名扫描有两处漏项，后由文档 Agent 在发布档案收口时修正（见 §十三）
C 类隔离 / 许可证    ：通过（无 data/output/logs/cache/.venv/.db/.env；MIT）
运行后源码树        ：干净（仅 .t8-manifest.json 未跟踪）
简短结论：N4 源码收束与最终 T8 复验全部通过，V1.4.1 满足发布条件。遗留 1 项测试隔离缺陷（非阻断，见下）。

验收 AGENT 签名 / 日期：高性能源码验收 Agent / 2026-08-22
```

### 遗留：测试隔离缺陷（非阻断，建议后续修复）

`_v13_stub_e2e.py` 的 `_cleanup()` 清理的是 `BACKEND_ROOT/data`（V1.4.0 前路径），但 V1.4.0 起数据在 runtime root，导致 `stub-user` 经历在 runtime 数据库累积（本轮实测 97 条）。在污染 runtime 下 Stub E2E 会波动到 19/20（`5_bullets_missing_sql_fallback` 因 `pids` 超载而失败）；在干净 runtime 下稳定 20/20。该问题属于测试脚本隔离缺陷，不影响产品代码，也不阻断 V1.4.1 发布；后续应让 `_cleanup()` 清理 runtime 的 `stub-user` 数据，或让测试强制使用独立临时 `RESUME_DATA_DIR`，以兑现“CI 可重复”。

---

## 十、实现与发布标识

```
开发 worktree 工作分支 ：feat-generate-code-wiki-qOQiu7
开发 worktree 实现基线 ：e4cf9d7028036ac1be3ccff14027da4708de51dd（非最终发布标识）
首轮 T8 验收根目录     ：<delivery-root>
首轮 T8 HEAD (40位)   ：da1754f1e0c4d8ce1cfe69c8ae04366cd8db6bdd
T8 commit count        ：1
最终 T8 tracked files ：88（N4 文档收束后）
N1 二次验收文件 SHA256：67EEE4643480D4D7C3DDD4ADA582978ED30FB553A8A21D180C15F13E97D156D0（开发目录逻辑内容一致；最终以新 manifest 为准）
B1 pm_template.docx tracked ：✅
最终 manifest 三一致  ：git = manifest = SHA256：88 / 88 / 88
N4 源码验收 commit     ：317c52660335a9dc35107d4627c25739c8eb4f9f（高性能验收对象）
首轮纯文档冻结候选    ：2b6e8f9ad69ca8ee481c824e38461bb698f671e7（机械核对通过；档案状态未收口，不发布）
最终发布标识          ：annotated tag `v1.4.1` 的目标 commit；不在 commit 自身文档中回填自身 SHA
对外发布归档          ：以远端 `v1.4.1^{commit}` 为核验真源
```

`da1754f...` 是核心验收基线，不包含后来通过二次验收的 N1 补丁和最终文档修改，不能直接作为 `v1.4.1` 发布 tag。最终构建只需做定向一致性复核，无需重新进行人工核心链路 E2E。

---

## 十一、状态

- **开发 Agent 状态**：✅ T1–T5、N1 与 N4 源码侧同步全部完成。
- **源码验收 Agent 状态**：✅ 已完成最终验收（N4 后）：manifest/SHA256 三一致 88/88/88、T7 12 PASS / 0 FAIL、Stub E2E 干净环境 20/20、身份边界独立推导 10/10，源码与 runtime 安全门通过；公开 Markdown 用户名漏项由文档 Agent 后续修正。
- **文档 Agent 状态**：✅ N2/N3 与 N4 文档收束已完成。
- **发布档案状态**：✅ 入包文档已完成稳定语义收口；最终机械冻结与 annotated tag `v1.4.1` 只产生 Git 发布元数据，不再反向修改本 RESULT。
- **当前 RESULT 状态**：**`已验收`**（遗留 1 项测试隔离缺陷，非阻断，见 §九末尾）。

---

## 十二、N4 GitHub 版本档案与发布链路收束（2026-08-21）

### 12.1 文档侧已完成

| 项目 | 结果 |
|---|---|
| 版本目录 | 统一为三段式 `v<major>.<minor>.<patch>`；V1.2.1、V1.4.1 等补丁版本排序语义明确 |
| 显示版本 | 索引、标题、交叉引用统一使用 `V<major>.<minor>.<patch>` |
| 历史发布标识 | 已发布 Git tag `v1.4` 原样保留，不移动、不重建 |
| V1.4.0 档案 | 原 T1/T3/T4/T6/T7/T8/T9/T10 分项独有证据合并进 V1.4.0 RESULT；分项文档和陈旧 in-repo manifest 退出长期档案 |
| 运行产物 | `validation-artifacts/t7-official.json` 不作为文档真源；结论已在 RESULT 留存，机读报告应由测试写入临时目录 |
| 目录契约 | 正式版本只保留 PLAN + RESULT；候选草稿只保留 DRAFT |
| 文档校验 | 两段式旧版本目录链接、已删除分项文件链接和拟公开敏感路径均完成文档侧扫描；相对链接待源码同步完成后再做最终复验 |

### 12.2 源码侧（2026-08-22 验收复核：已完成）

| # | 项 | 复核结果 |
|---|---|---|
| 1 | 根忽略规则 `docs/versions/v1.4/validation-artifacts/` | ✅ 已改为 `docs/versions/*/validation-artifacts/`（通配符） |
| 2 | T8 交付脚本旧 `docs/versions/v1.4/` 与旧 manifest 路径 | ✅ 不再生成 `T8_manifest.json`，`_DIR_EXCLUDE` 含 `validation-artifacts` |
| 3 | C2/C3 脱敏脚本旧版本目录范围与旧 manifest 路径 | ✅ 无 `v1.4` / `versions/v1.` 旧路径残留 |
| 4 | 验收脚本报告输出位置 | ✅ `--report` 默认 `None`，不重建 `validation-artifacts` |
| 5 | 固定文件数 96 → 实际值 | ✅ 最终 manifest/Git/SHA256 = 88/88/88 |

### 12.3 验收影响

- 功能验收：T1–T3、N1 对应的版本元数据、身份事实边界和无 Key Stub 结论仍有效；N4 不改变业务 API、数据库或生成内容。
- 结构变更验收：N4 文档侧与源码侧均已完成并复验通过。
- 最终源码验收：T8 HEAD `317c5266`，manifest/Git/SHA256 = 88/88/88，已通过。
- 发布档案冻结：首轮纯文档候选 `2b6e8f9` 已完成单 commit、`main`、88 个文件、864,358 bytes、manifest/Git 文件列表与 SHA256 全量一致；开发侧安全断言报告为通过，但文档 Agent 复核另发现 V1.4.0 RESULT 中两处真实 GitHub 用户名，且候选包仍保留“待最终冻结”语义，因此不作为最终 tag 目标。两处用户名现已替换为 `<github-owner>`。最终发布包从已收口文档重新机械冻结；只要不混入源码、测试或配置变化，就不重跑功能 E2E 或高性能源码验收。

---

## 十三、验收回写后的发布档案冻结

高性能 Agent 的验收对象是 commit `317c52660335a9dc35107d4627c25739c8eb4f9f`。验收完成后，验收结论写入本 RESULT，文档 Agent同时同步了 PLAN 状态、CURRENT_STATE、两个版本索引和 V1.5.0 草稿状态。这些都是必要的公开档案变更，但不包含产品源码、测试逻辑或配置变化。

首轮纯文档冻结候选结果：

| 项目 | 结果 |
|---|---|
| 候选 HEAD | `2b6e8f9ad69ca8ee481c824e38461bb698f671e7` |
| 分支 / commit count | `main` / 1 |
| 工作区 | clean；仅 `.t8-manifest.json` 未跟踪，符合设计 |
| 文件数 / 总字节数 | 88 / 864,358 |
| manifest / `git ls-files` / SHA256 | 88 / 88 / 88，全量一致 |
| 安全断言 | 开发侧报告模板跟踪、依赖真源、runtime 与敏感文件排除、9 个版本目录结构通过；文档 Agent 随后发现两处历史 GitHub 用户名，候选退出发布并已脱敏 |

该候选在文件与哈希层面通过，但包内 PLAN、RESULT、CURRENT_STATE 和版本索引仍写着“待最终冻结”，并有两处历史 GitHub 用户名未被开发侧扫描识别，所以不能作为最终公开档案。根 README 已是稳定的用户介绍，不涉及该内部状态。问题不在产品代码，而在冻结前没有先完成开发档案的状态语义与隐私收口。

最终处理规则：

1. `317c5266` 继续作为 V1.4.1 最终源码验收 commit；功能、结构以及源码/runtime 安全结论有效；公开 Markdown 隐私收口以本节后续修正为准。
2. PLAN、RESULT、CURRENT_STATE、版本索引已收口为最终公开语义；根 README 原本已是稳定的 V1.4.1 用户介绍，不需要额外状态文字。
3. 最终候选从上述已收口内容重新运行 T8，只做单 commit、`main`、正式版本目录、manifest=`git ls-files`=SHA256、安全扫描和工作区状态核对；没有源码、测试或配置变化时不重跑功能及高性能验收。
4. RESULT 不再要求把最终发布 commit SHA 回填进该 commit 自身，否则写入 SHA 会再次改变 commit，形成无限冻结循环。
5. 机械核对通过后直接创建 annotated tag `v1.4.1`；最终发布 commit 由该 tag 的目标 commit 唯一标识。tag 创建与远端核验结果留在 Git/GitHub 发布记录，不再修改本版本入包文档。

本节完成后，入包文档不再包含需要冻结后回填的状态字段；T8 与 tag 是对既定内容的发布操作，不产生新的文档同步任务。

---

## 十四、发布后补录：远端 main/tag 纠正（2026-08-22）

> 本节由 V1.4.2 分支在发布后追加，不属于 `v1.4.1` tag 内的原始文档，也不因此移动或重建该 tag。

开发侧最后一次汇总曾记录：全新单 commit 候选 `cbccdc8f40c9d4c2952c08504c14aa248fbfa29a` 已推送为远端 `main` 和 annotated tag `v1.4.1`。文档 Agent随后独立读取 GitHub 远端引用，发现实际状态与汇总不一致：远端 `main` 仍指向旧发布 commit，`v1.4.1` 则指向开发基线，而不是已核对的最终候选。

在用户授权下，文档 Agent 以读取到的旧 SHA 为精确保护条件完成一次发布事故纠正，并再次从远端核验：

| 远端引用 | 纠正后的目标 |
|---|---|
| `refs/heads/main` | `cbccdc8f40c9d4c2952c08504c14aa248fbfa29a` |
| annotated tag `v1.4.1^{commit}` | `cbccdc8f40c9d4c2952c08504c14aa248fbfa29a` |

这次纠正说明，候选文件验收通过并不能替代远端引用核验；开发 Agent 的“已推送”汇总也不能直接作为发布事实。V1.4.2 因此把以下规则设为长期约束：V1.4.0 的单 commit 首发只执行一次；后续从公开 main 正常增量开发；开发 Agent不发布正式 main/tag；文档 Agent在用户确认后执行远端 preflight 和最终发布；正常发布只允许 fast-forward，force 仅作为单独授权并留痕的事故处置。
