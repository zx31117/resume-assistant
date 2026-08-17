# V1.4 T9 — 发布前独立复核报告（三轮）

> 验收日期：2026-08-17  
> 验收对象：T8 一次性干净首发 worktree  
> 第一轮结论：**🔴 阻断（Block）**——存在 1 项首发功能完整性缺陷和 3 项发布前修正项。  
> 第二轮结论：**🟢 本地 T9 条件通过**——B1、C1、C2 已解决，C3 的文档路径已主要脱敏，核心回归和安全门通过；发布候选 HEAD 与脱敏脚本仍须完成最终收口，V1.4 整体仍处于 `待验收`。
> 第三轮结论：**🟢 本地 T9 通过**——第二轮遗留与文档 Agent 新增收口项全部解决；候选 commit `341512db...` 在报告写回前实现 manifest=Git=91、SHA256 91/91，核心回归、Stub E2E 和安全五门通过。MIG-3 后续已通过，见 §12。

## 1. 第一轮：交付清单与 SHA256

- 根 `.t8-manifest.json`：`copied_count=91`，91/91 文件 SHA256 和字节数一致，0 缺失、0 不一致；
- Git 实际跟踪 89 个文件；另外 2 个被忽略规则排除：`backend/templates/pm_template.docx`、`backend/pip_freeze_baseline.txt`；
- Git 内 `<delivery-root>/.t8-manifest.json` 是陈旧副本：记录 87 文件，11 个 hash 与实际不一致，并缺少后续文档；
- 根因是 delivery 流程在 `git add -A`/commit 后才更新 manifest，导致 Git 中保留上一轮快照。

## 2. 第一轮：T7 核心回归

- Python 3.10.11 全新 venv；`pip install -r requirements.txt` 成功；
- T7：`total=15, PASS=12, FAIL=0, SUSPEND=3`；
- RUNTIME、CORE、V13 全部通过；
- MIG-1/2：T8 干净包按设计不含 C 类旧数据库，因此显式跳过；
- MIG-3：需要有效 `ARK_API_KEY` 后手动执行向量重建；
- 机器可读证据写入本机临时目录，第三轮起不再进入 Git，避免验收运行污染发布工作区。

Stub E2E 在验收 worktree 成功生成约 38.5 KB 的 `demo_resume.docx`，输出位于仓库外 runtime；运行后源码树没有新增 DOCX、DB 或输出文件。

## 3. 第一轮 B1 阻断：必要模板未进入 Git

`backend/templates/pm_template.docx` 已被 T4/T6 判定为无 PII 的必要 B 类资产，delivery 脚本也将其复制进验收目录；但根 `.gitignore` 的 `backend/templates/*.docx` 规则使 `git add -A` 静默跳过该文件。

验收机磁盘上仍存在模板，所以 Stub E2E 可以通过；干净 Git clone 不包含模板，而 `run_stub_demo.py` 没有缺失时自动构建逻辑，将在 `TemplateRenderer → load_template_assets` 阶段因文件不存在而失败。

这违反 V1.4 PLAN 的“干净环境 Stub E2E 通过”以及 README 宣传的“零 API Key 可运行入口”。

修正后必须证明：

1. 最终 commit 跟踪必要模板，或干净 clone 能确定性自动构建；
2. 从新的干净 clone 直接按 README 运行 Stub Demo 成功；
3. 输出仍位于仓库外，运行后 Git 工作区保持干净。

## 4. 第一轮发布前修正项

### C1 `pip_freeze_baseline.txt` 分类不一致

该文件被忽略，但 T8 交付说明声称包含。应明确它是否属于公开依赖基线；如 `requirements.txt` 已是唯一依赖真源，应从交付清单删除，而不是为了匹配说明强行发布。

### C2 Git 内 manifest 陈旧

不应同时保留两个结论冲突的 manifest 真源。修正 delivery 顺序或简化清单方案后，必须用最终 Git 文件集合重新生成并复验。

### C3 文档包含本机绝对路径

共发现 67 处，全部位于文档；A 类 Python 源码没有硬编码本机路径。用户已确认公开完整版本档案，因此处理方式应是路径脱敏，而不是删除 V1.0–V1.3 历史文档。

## 5. 第一轮 T6 安全复核

| 门 | 结果 |
|---|---|
| Secret | 0 个真实密钥；命中项为脱敏描述或扫描规则文本 |
| PII | 22 处均为虚构 Demo/测试姓名、测试号码或示例邮箱 |
| 二进制 | 仅必要模板 DOCX；该文件触发 B1 |
| 绝对路径 | A 类 Python 源码 0；文档路径见 C3 |
| 许可证 | MIT 完整；依赖许可证与 MIT 兼容 |
| C 类隔离 | DB、向量、输出、日志、缓存、`.env`、虚拟环境及真实输入均未进入 Git |

## 6. 第一轮结论

核心解耦链路、回归和安全门基本健康，但 B1 使公开仓库无法从干净 clone 执行 README 的核心 Demo，因此状态为 **Block**。

开发 Agent 修复 B1，并同轮处理 C1/C2/C3后，应重新构建 T8。高性能验收 Agent 必须针对新的最终 commit 复验 SHA256、实际 Git 清单、模板跟踪状态、干净 clone Stub E2E 和安全门，通过后才能进入 GitHub T10/T11。

## 7. 第二轮复验结果

第二轮针对修正后重建的 T8 仓库执行，分支为 `main`，历史长度为 1，候选 commit 为 `fadd7c2f189987aa0d391c296a2fb2ba17f3da4c`，Git 跟踪文件数为 92。

| 第一轮问题 | 第二轮处理 | 复验结论 |
|---|---|---|
| B1 必要模板未进 Git | `.gitignore` 明确放行 `backend/templates/pm_template.docx`，模板进入最终 commit | ✅ 已修复；blob 为 38,468 bytes，Stub E2E 可加载 |
| C1 依赖真源不一致 | 删除 `pip_freeze_baseline.txt`，确认 `requirements.txt` 为唯一依赖真源 | ✅ 已解决 |
| C2 manifest 真源冲突 | 删除 Git 内陈旧 `<delivery-root>/.t8-manifest.json（唯一 manifest 真源）`，根 `.t8-manifest.json` 为唯一交付清单 | ✅ 已解决；清单与 `git ls-files` 为 92=92 |
| C3 本机路径 | 新增路径脱敏脚本，当前开发者用户名路径替换为通用占位符 | ✅ 实质解决；旧版本无用户名盘符路径不构成个人识别信息 |

第二轮独立复验结果：

- 全新 Python 3.10.11 venv 安装依赖成功；
- T7：`total=15, PASS=12, FAIL=0, SUSPEND=3`；RUNTIME、CORE、V13 全部通过；
- MIG-1/2 因干净包不携带旧 C 类数据库而跳过；MIG-3 仍需有效 API Key；
- Stub E2E 通过，DOCX 输出位于仓库外 runtime，运行后未产生源码数据污染；
- Secret、PII、许可证、必要二进制和 C 类隔离复核通过。

因此，第一轮的功能性发布阻断已经解除，候选源码可以进入 T10 前的最终冻结。

## 8. 文档 Agent 对第二轮交付状态的补充核验

第二轮报告中的“SHA256 91/92”描述的是复验运行后、报告写回前的中间状态。报告写回后，验收仓库当前实际有以下变化：

- `RESULT.md`、`T9_REVIEW.md`、`validation-artifacts/t7-official.json` 共 3 个跟踪文件相对 commit 被修改；按当前工作区重算为 **89/92 一致**；
- `t7-official.json` 的重跑版本含本机绝对路径，不能直接提交；
- `.workbuddy/` 是未跟踪且未被 ignore 的 Agent 运行产物，不能进入公开仓库；
- `backend/_v14_c2c3_path_redact.py` 为实现 C3 直接写入了真实用户名和原始绝对路径规则；文档虽已脱敏，公开源码仍会暴露这些本机标识，必须改为参数或通用模式；
- 根 `.t8-manifest.json` 按设计未跟踪，但最终仍须针对冻结后的 Git 文件集合重新生成。

这不推翻第二轮核心回归结论，但表示 `fadd7c2f...` 加当前工作区尚不是可直接推送的最终状态。发布前必须先将需要留存的第二轮文档和脱敏证据纳入最终单提交 HEAD，明确排除 `.workbuddy/`，再生成 manifest 并从最终 HEAD 复验。

## 9. 第二轮后的门禁结论

T9 的核心功能、安全和源码—数据解耦复核记为**条件通过**。V1.4 不标记“已验收”，还需完成：

1. `T6_AUDIT.md` 中真实 key 前缀完全脱敏，并把路径脱敏脚本改为不含真实用户名/原始路径的通用实现；
2. 将第二轮报告、RESULT 和脱敏后的机器可读证据纳入最终冻结 HEAD；`.workbuddy/` 必须排除；
3. 在干净最终 HEAD 上确认工作区无意外修改，manifest 与 Git 跟踪文件逐项 SHA256 全一致；
4. 按 PLAN 完成 MIG-3 向量全量重建，失败 ID 为 0；如要取消该门禁，必须由用户明确修改 PLAN，而不能把 `SUSPEND` 当作通过；
5. 完成 T10 Private clone 安装与 Stub E2E、T11 Public/tag、GitHub 页面与 clone 人工验收。

## 10. 第三轮针对性复验

第三轮针对第二轮遗留 L1/L2/L3，以及文档 Agent 追加的 Agent 产物排除和脱敏脚本自泄漏问题执行。候选环境为 `main`、单 commit、HEAD `341512db2dec29c4c99dbe1f21977a76d839496e`。

| 项目 | 第三轮实测 | 结论 |
|---|---|---|
| L1 Secret 描述 | 真实 key 前缀无命中 | ✅ 已解决 |
| L2 历史本机路径 | 用户目录与旧开发盘符字面量无命中；分支名按开发历史保留 | ✅ 已解决 |
| L3 验收 JSON 污染 | `validation-artifacts/` 移出首发包，报告改写到临时目录 | ✅ 已解决 |
| Agent 运行产物 | `.workbuddy/` 同时由 ignore 与 delivery 脚本排除，Git 跟踪为 0 | ✅ 已解决 |
| 脱敏脚本自身 | 不再包含原用户名、原绝对路径或真实 key 前缀 | ✅ 已解决 |

第三轮完整结果：

- Git 跟踪 91 个文件，manifest 与 `git ls-files` 双向一致，逐文件 SHA256 **91/91**；
- T7：`total=15, PASS=12, FAIL=0, SUSPEND=3`；RUNTIME、CORE、V13 全部通过；
- Stub E2E 通过，DOCX 写入仓库外 runtime；
- Secret、PII、必要二进制、绝对路径、许可证和 C 类隔离全部通过；
- 运行后 Git 状态仍只有预期未跟踪的根 `.t8-manifest.json`。

第三轮结论为：**本地 T9 通过；按 PLAN 完成 MIG-3 后进入 GitHub T10。**

## 11. 报告写回与最终冻结说明

上述 91/91 结论是在第三轮报告写回前针对候选 HEAD 得出。高性能 Agent 随后更新 `T9_REVIEW.md` 和 RESULT，使验收 worktree 当前出现两份文档修改，manifest 对当前工作区显示 89/91。

这两处变化只记录验收结论，不改变已验证源码、安全配置或运行行为。为避免“验收报告写回后再验收报告”的无限循环，第三轮是最后一次高性能验收。最终交付仅需：

1. 将最新 T9/RESULT 纳入 docs-only 最终冻结；
2. 重新生成 manifest 并做一次无副作用的机械 SHA256 校验；
3. 不再把机械冻结称作第四轮 T9，也不重跑完整回归。

V1.4 尚未整体验收：MIG-3 已于后续通过；T10 Private clone、T11 Public/tag 和用户人工验收仍待完成。

## 12. MIG-3 门禁通过记录（2026-08-17）

本节为门禁状态更新，**不构成第四轮 T9 复验**（按 §11 约定，第三轮为最后一次高性能验收）。

- 执行环境：开发 worktree，`ARK_API_KEY` 有效，`RESUME_DATA_DIR` 指向迁移后 runtime root；
- 执行入口：`python _v14_t3_migrate.py --rebuild-vectors`（user_id 从 SQL 首条用户自动获取，非 `settings.DEFAULT_USER_ID`）；
- 结果（见 [T3_MIGRATION.json](./T3_MIGRATION.json) §vector_rebuild_from_new_sql）：
  - `total_sql=5`，`upserted=5`，`deleted_stale=0`；
  - `failed_ids.count=0`，`errors=[]`；
  - `vector_rebuild_all_ok=true`；
- 脱敏：报告生成后由 `_v14_c2c3_path_redact.py` 重新处理，0 残留硬编码本机路径。

MIG-3 门禁由 `⏳ SUSPEND` 转为 `✅ PASS`。剩余门禁仅 T10/T11 与用户人工验收。
