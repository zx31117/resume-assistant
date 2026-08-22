# V1.4.2 RESULT：发布基线与开发档案收口

> 状态：需修正
> 分支：`version/v1.4.2`
> 基线 commit：`cbccdc8f40c9d4c2952c08504c14aa248fbfa29a`（`main` / `v1.4.1`）
> 首轮开发交付 commit：`ed4d3ac7da0463773d98c975c0af37e1b7dba9c3`；发布检查返工 commit：`bda3b351a510df36d32756b29062606a2ddf7348`
> 第一轮 T9 验收对象：`ca1f1b9cd053a56fe61b36484953b2ccf51639fc`（不通过）
> 功能验收：不通过；Stub 业务断言 20/20，但临时 runtime 资源未释放、目录未删除
> 结构变更验收：不通过；T9 发现测试生命周期未闭环及 RESULT 引用悬空 SHA

## 1. PLAN Task 对照

| Task | 状态 | 实际结果 |
|---|---|---|
| T0 固定基线与工作路径 | 完成 | canonical/current 从 `v1.4.1@cbccdc8...` 建立；current 为 `version/v1.4.2` |
| T1 一次性首发工具退出 | 完成 | 删除 `backend/_v14_t8_delivery.py`；新增只读 `backend/_v14_release_check.py` |
| T2 README、隐私和工作流 | 完成 | 根 README 使用真实公开 URL；工作流明确路径角色、commit 交接、发布责任和 fast-forward |
| T3 当前事实与历史归档 | 完成 | CURRENT_STATE 精简；V1.4.1 RESULT 追加发布后远端纠正记录 |
| T4 Markdown LF 规范 | 完成 | 新增 `.gitattributes`；24 份 Markdown 统一为 LF；DOCX/字体/图片声明为 binary |
| T5 Stub E2E runtime 隔离 | 需修正 | 独立路径和真实 runtime 不变已通过，但 SQLite/Chroma 连接未释放，临时目录每次残留，不能声明完成 |
| T6 V1.5.0 草稿同步 | 完成 | 补齐 SQLite 单一持久化、退出 Chroma/numpy+JSON 和内部 Provider 边界 |
| T7 版本元数据 | 完成 | `APP_VERSION="1.4.2"`；根 README 和对外运行入口同步 |
| T8 候选与开发验证 | 需修正 | 版本、LF、旧脚本退出和发布检查通过；T5 的“目录已删除”证据被 T9 否定，需形成新候选 |
| T9 独立源码验收 | 不通过 | `ca1f1b9...`：6 项通过，Stub 临时目录清理失败；RESULT 另引用不在谱系内的悬空 `838578...` |
| T10 文档收口与发布 | 未开始 | 需 T9 通过、文档最终同步和用户发布确认 |

## 2. 实际全局变化

| 类别 | 实际变化 |
|---|---|
| API | 无 |
| 数据表/模型 | 无 |
| 产品业务链路 | 无 |
| 模块职责 | 一次性单 commit 首发脚本退出；新增无写入、无发布能力的只读发布检查 |
| 测试 | Stub E2E 改为独立临时 runtime，不读取或清理用户真实 runtime |
| 配置/依赖 | 新增根 `.gitattributes`；无第三方依赖变化 |
| 版本 | `backend/core/version.py` 的 `APP_VERSION` 从 1.4.1 更新为 1.4.2 |
| 根 README | 当前版本、真实 clone URL 和补丁定位更新 |
| 开发文档 | 工作流、决策、当前状态、历史补录、索引和 V1.5.0 草稿同步 |

## 3. 替换型变更闭环

| 变更 | 新状态 | 旧状态退出 | 回归证据 |
|---|---|---|---|
| Git 发布方式 | 公开 main 上正常增量开发；发布前只读检查 | `_v14_t8_delivery.py` 删除，无常规 orphan/single-commit 重建入口 | 基线祖先关系成立；发布检查不含 push/commit/reset |
| Stub runtime | 每次运行使用临时 `RESUME_DATA_DIR` | 不再清理旧 `backend/data`，不接触真实 runtime | 部分完成：连续两次 20/20、真实 runtime 不变；临时目录删除失败，待返工 |
| Markdown 换行 | `*.md text eol=lf` | CRCRLF/混合换行退出 | `git check-attr` 和字节扫描通过 |
| 版本元数据 | `APP_VERSION=1.4.2` 单一真源 | 活动对外入口不保留 1.4.1 硬编码 | FastAPI/OpenAPI/健康检查/Stub Banner 一致性待 T9 独立复核 |

## 4. 开发 Agent 验证

| 验证 | 状态 | 开发侧证据 |
|---|---|---|
| 基线谱系 | 通过 | V1.4.1 基线是 V1.4.2 HEAD 的祖先 |
| 工作区 | 通过 | 交接时分支 `version/v1.4.2`、HEAD `ed4d3ac...`、status clean |
| Stub E2E | 失败 | 连续两次业务断言 20/20、真实 runtime 不变，但每次残留一个 `stub-e2e-runtime-*` 目录；清理自检发现失败仍退出 0 |
| 版本一致性 | 通过 | `APP_VERSION=1.4.2`，所有对外入口从该模块导入 |
| LF | 通过 | 24 份 Markdown 属性均为 `eol: lf`，无 CRCRLF/混合换行 |
| 一次性工具退出 | 通过 | 旧脚本删除；新检查只读 |
| 文档链接与隐私 | 通过 | 相对链接无缺失；本机绝对路径和真实凭据无命中 |
| 只读发布检查 | 通过 | 默认 Windows 控制台直接运行：Git 跟踪、隐私/PII、clean/历史和邮箱正反向自测全部 `[PASS]`，退出码 0 |
| 高性能源码验收 | 失败 | 第一轮 T9 绑定 `ca1f1b9...`；Git、工具只读、GBK/邮箱、版本、LF、目录契约、隐私和无产品变更通过，Stub 资源清理阻断 |
| 人工验收 | 未执行 | 本版本无新产品功能，最终由用户审核文档和发布结果 |

开发提交自身涉及 12 个文件；从 V1.4.1 基线计算的完整版本 diff 还包含前一文档阶段提交和历史 Markdown 换行规范化，不能把“单个开发 commit 的 12 个文件”表述成“整个 V1.4.2 只改变 12 个文件”。

阶段性 manifest 已退出版本目录。正式版本长期只保留 PLAN 与 RESULT；文件数和校验结论写入 RESULT 或验收汇总，不建立第三个真源。

## 5. T9 交接

文档 Agent完成本节收口后创建 clean `<review-worktree>`，并在任务中给出其精确 HEAD。高性能源码验收 Agent只读取当前 PLAN、RESULT 和实际 diff，独立复核：

1. V1.4.1 → T9 HEAD 的父子谱系和实际文件范围；
2. 一次性首发脚本退出、只读检查无写入/发布副作用；
3. Stub E2E 连续两次 20/20，临时 runtime 清理且真实 runtime 不变；
4. Markdown LF、版本 1.4.2、隐私边界和正式版本仅 PLAN + RESULT；
5. 首轮开发交付 `ed4d3ac...` 到 T9 HEAD 的后续提交范围清楚；不得引用 amend 后已悬空的中间 SHA。

当前不能标记 V1.4.2 完成，也不能把 V1.4.2 写入 CURRENT_STATE 的已验收版本。

## 6. 发布检查脚本返工与修正（2026-08-22）

### 6.1 问题

文档 Agent 在 clean detached review worktree 运行 python backend/_v14_release_check.py --repo-root . 时发现：

1. Windows 默认 GBK 控制台在输出 Unicode 图标时抛出 UnicodeEncodeError，脚本未能完成；
2. 临时强制 UTF-8 只用于继续诊断，脚本随后把仓库已有的 example.com、should-not-appear.com 等明确虚构测试邮箱判为真实 PII，退出码为 2；
3. Git 跟踪规则、工作区 clean 和正常父提交检查本身通过。

### 6.2 修正内容

开发 Agent 作为新的正常增量 commit（不 amend 既有提交）完成以下修正：

1. **GBK 安全输出**：全部输出标记从 emoji 改为 ASCII（[PASS]/[FAIL]/[WARN]），在默认 Windows GBK 控制台直接运行不乱码。

2. **正确排除虚构域名**：按 RFC 2606 / RFC 6761 建立保留域名排除列表：
   - example.com、example.org、example.net、example.edu
   - .invalid、.test、.example、.localhost TLD
   - 旧测试域名 should-not-appear.com（向后兼容）

3. **测试邮箱改为明确保留域名**：_v13_stub_e2e.py 中 leaked-fake@should-not-appear.com 改为 leaked-fake@example.invalid（.invalid 是 RFC 2606 保留 TLD）。docs/versions/v1.4.1/RESULT.md 中引用同步修正。

4. **正反向自测**：发布检查脚本末尾新增 Self-test: email detection 节：
   - 正向（必须检出）：4 个非保留域名邮箱（gmail.com / company.cn / real-domain.org / university.edu）
   - 反向（必须排除）：8 个保留域名邮箱（example.com/.org/.net/.edu、.invalid、should-not-appear.com 等）
   - 自测自身不触发 PII 扫描（脚本自排除）

5. **clean 仓库退出 0**：工作区 clean 时无 [WARN]，所有检查 [PASS]，退出码 0。

### 6.3 验证

- Stub E2E 连续运行 20/20（邮箱改名后回归通过）；
- 发布检查脚本在 clean 仓库退出 0（仅工作区未提交时 [WARN]，退出码 1）；
- 自测节 4 正向 + 8 反向全部 [PASS]。

### 6.4 交接

不恢复 MANIFEST.txt，不操作公开 main/tag。文档 Agent 在本增量 commit 基础上重建 review worktree 执行 T9。

## 7. 第一轮 T9 源码验收（2026-08-22）

验收对象：`ca1f1b9cd053a56fe61b36484953b2ccf51639fc`，detached、clean；高性能源码验收 Agent未修改 review worktree。

通过项：正常增量 Git 谱系；旧首发脚本退出和新工具只读；默认 Windows GBK 与邮箱正反向检测；对外版本 1.4.2；Markdown LF 与 `.gitattributes`；正式版本只有 PLAN + RESULT；隐私、相对链接及无产品 API/数据模型变化。

阻断项：

1. Stub E2E 连续两次均为 20/20，真实 runtime 未变化，但 SQLite/Chroma 连接未关闭，`shutil.rmtree(ignore_errors=True)` 静默失败；每次运行残留一个含数据库和向量文件的临时目录。脚本已检测到“未删除”，却仍以 0 退出；
2. 本 RESULT 曾把 amend 后的悬空中间 commit `838578...` 写成开发实现，实际谱系内的首轮开发交付是 `ed4d3ac...`。本节已纠正，后续只记录已存在的前序 commit；当前验收对象由交接和验收回写记录，不向自身回填 SHA。

返工要求：开发 Agent在 current 工作树显式关闭数据库 engine、Chroma client 及其他文件句柄；目录删除不得 `ignore_errors=True` 后静默成功，需有限重试并在最终仍残留时非零退出。至少连续运行两次，证明 20/20、真实 runtime 不变、每次临时目录均删除；形成新的正常增量 commit 后重新 T9。
