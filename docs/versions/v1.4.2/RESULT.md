# V1.4.2 RESULT：发布基线与开发档案收口

> 状态：需修正
> 分支：`version/v1.4.2`
> 基线 commit：`cbccdc8f40c9d4c2952c08504c14aa248fbfa29a`（`main` / `v1.4.1`）
> 开发实现 commit：`8385787676ae985e64c5b79cbb44fe6970d2acd8`；开发 Agent 交接 HEAD `ed4d3ac7da0463773d98c975c0af37e1b7dba9c3` 仅继续修改本 RESULT 与已退出的 manifest
> T9 验收对象：以文档 Agent创建 review worktree 时提供的 clean HEAD 为准；不在该 commit 内回填自身 SHA
> 功能验收：开发 Agent验证通过；T9 前只读发布检查自身不可用，修复后才能送独立验收
> 结构变更验收：待高性能源码验收 Agent复核

## 1. PLAN Task 对照

| Task | 状态 | 实际结果 |
|---|---|---|
| T0 固定基线与工作路径 | 完成 | canonical/current 从 `v1.4.1@cbccdc8...` 建立；current 为 `version/v1.4.2` |
| T1 一次性首发工具退出 | 完成 | 删除 `backend/_v14_t8_delivery.py`；新增只读 `backend/_v14_release_check.py` |
| T2 README、隐私和工作流 | 完成 | 根 README 使用真实公开 URL；工作流明确路径角色、commit 交接、发布责任和 fast-forward |
| T3 当前事实与历史归档 | 完成 | CURRENT_STATE 精简；V1.4.1 RESULT 追加发布后远端纠正记录 |
| T4 Markdown LF 规范 | 完成 | 新增 `.gitattributes`；24 份 Markdown 统一为 LF；DOCX/字体/图片声明为 binary |
| T5 Stub E2E runtime 隔离 | 完成 | 使用临时 `RESUME_DATA_DIR` 并覆盖三个派生路径；连续两次 20/20；退出时删除临时目录 |
| T6 V1.5.0 草稿同步 | 完成 | 补齐 SQLite 单一持久化、退出 Chroma/numpy+JSON 和内部 Provider 边界 |
| T7 版本元数据 | 完成 | `APP_VERSION="1.4.2"`；根 README 和对外运行入口同步 |
| T8 候选与开发验证 | 完成 | 开发实现 commit `838578...`；版本、LF、旧脚本退出、两次 Stub 和只读发布检查均由开发侧验证 |
| T9 独立源码验收 | 阻断前置检查 | review 已建立，但新发布检查在默认 Windows 编码崩溃，并把仓库既有虚构邮箱误报为真实 PII；尚未交给高性能验收 Agent |
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
| Stub runtime | 每次运行使用临时 `RESUME_DATA_DIR` | 不再清理旧 `backend/data`，不接触真实 runtime | 连续两次 20/20；临时目录退出后删除 |
| Markdown 换行 | `*.md text eol=lf` | CRCRLF/混合换行退出 | `git check-attr` 和字节扫描通过 |
| 版本元数据 | `APP_VERSION=1.4.2` 单一真源 | 活动对外入口不保留 1.4.1 硬编码 | FastAPI/OpenAPI/健康检查/Stub Banner 一致性待 T9 独立复核 |

## 4. 开发 Agent 验证

| 验证 | 状态 | 开发侧证据 |
|---|---|---|
| 基线谱系 | 通过 | V1.4.1 基线是 V1.4.2 HEAD 的祖先 |
| 工作区 | 通过 | 交接时分支 `version/v1.4.2`、HEAD `ed4d3ac...`、status clean |
| Stub E2E | 通过 | 连续两次均 20/20；输出位于临时目录，不接触真实 runtime |
| 版本一致性 | 通过 | `APP_VERSION=1.4.2`，所有对外入口从该模块导入 |
| LF | 通过 | 24 份 Markdown 属性均为 `eol: lf`，无 CRCRLF/混合换行 |
| 一次性工具退出 | 通过 | 旧脚本删除；新检查只读 |
| 文档链接与隐私 | 通过 | 相对链接无缺失；本机绝对路径和真实凭据无命中 |
| 只读发布检查 | 失败 | 默认 Windows GBK 输出 `✅` 时触发 `UnicodeEncodeError`；强制 UTF-8 后又把 `example.com` 等既有虚构 fixture 误报为真实 PII，clean 仓库退出码 2 |
| 高性能源码验收 | 未执行 | 发布检查工具需先返工；本次预检不能算 T9 |
| 人工验收 | 未执行 | 本版本无新产品功能，最终由用户审核文档和发布结果 |

开发提交自身涉及 12 个文件；从 V1.4.1 基线计算的完整版本 diff 还包含前一文档阶段提交和历史 Markdown 换行规范化，不能把“单个开发 commit 的 12 个文件”表述成“整个 V1.4.2 只改变 12 个文件”。

阶段性 manifest 已退出版本目录。正式版本长期只保留 PLAN 与 RESULT；文件数和校验结论写入 RESULT 或验收汇总，不建立第三个真源。

## 5. T9 交接

文档 Agent完成本节收口后创建 clean `<review-worktree>`，并在任务中给出其精确 HEAD。高性能源码验收 Agent只读取当前 PLAN、RESULT 和实际 diff，独立复核：

1. V1.4.1 → T9 HEAD 的父子谱系和实际文件范围；
2. 一次性首发脚本退出、只读检查无写入/发布副作用；
3. Stub E2E 连续两次 20/20，临时 runtime 清理且真实 runtime 不变；
4. Markdown LF、版本 1.4.2、隐私边界和正式版本仅 PLAN + RESULT；
5. 开发实现 `838578...` 到 T9 HEAD 之间只有文档交接收口，没有未复验的源码变化。

当前不能标记 V1.4.2 完成，也不能把 V1.4.2 写入 CURRENT_STATE 的已验收版本。

## 6. T9 前预检返工（2026-08-22）

文档 Agent在 clean detached review worktree 运行 `python backend/_v14_release_check.py --repo-root .`：

1. Windows 默认 GBK 控制台在输出 Unicode 图标时抛出 `UnicodeEncodeError`，脚本未能完成；
2. 临时强制 UTF-8 只用于继续诊断，脚本随后把仓库已有的 `example.com`、`should-not-appear.com` 等明确虚构测试邮箱判为真实 PII，退出码为 2；
3. Git 跟踪规则、工作区 clean 和正常父提交检查本身通过。

开发 Agent需修正发布检查自身：默认 Windows 控制台可运行；测试/演示中的明确虚构邮箱不会阻断；真实邮箱检测能力仍保留，并增加正反向自测。修复必须作为新的正常增量 commit，不 amend 或覆盖既有提交。RESULT 更新后再由文档 Agent重建 review worktree。
