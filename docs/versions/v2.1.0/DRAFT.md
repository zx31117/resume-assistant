# Resume Assistant V2.1.0 草稿：持续设计、冻结快照与整体界面重构

> 文档角色：下一阶段产品与协作草稿，供用户继续审核
> 状态：DRAFT，非开发指令；不创建开发分支，不改变 CURRENT_STATE
> 草稿日期：2026-09-05
> 当前产品基线：已发布 V2.0.2，annotated tag `v2.0.2` → `78bb909c18ca28e45b54406536aa326887caa1ca`
> 产品方向：重新设计整体界面，并建立“设计持续演进、开发按小版本冻结同步”的长期工作流

## 1. 核心判断

V2.1.0 不把设计工作绑定到单个开发版本，也不要求 Development Agent 实时跟随 Design Agent。设计与开发改为两条并行线：

~~~text
Design：HTML 工作稿 → 用户反馈 → 修改 → 用户确认 → 不可变 Design Snapshot
                           ↓
Development：版本启动时导入当时最新的已批准快照 → 本版本冻结实现
~~~

Design Agent 是设计执行者，不是设计决策者。它根据用户反馈持续生成和修改 HTML；用户负责真实的 UI/UX 判断，并通过明确要求“生成版本快照”完成 Design Approval。Documentation Agent 只负责冻结、导入、记录和发布，不替代用户判断设计好坏。

冻结快照是本版本的**可执行视觉规范**，不是方向性参考。Development Agent 可以自行设计 React 组件、状态管理、API Client 和文件结构，但最终可见布局、文案、交互流程和页面状态应一比一还原冻结 HTML；任何可见偏差必须登记并由用户决定。

## 2. 五方角色与权限

本项目采用“1 位 Product Owner + 4 个 Agent”：

| 角色 | 负责 | 不负责 |
|---|---|---|
| Product Owner（用户） | 产品方向、优先级、设计判断、快照批准、人工验收、发布批准 | 不要求亲自实现代码或维护状态文档 |
| Design Agent | 阅读项目现实，持续制作 HTML 原型，响应用户打回，生成设计快照与设计历史 | 不批准自己的设计，不修改生产源码或正式项目文档 |
| Documentation / Release Agent | 维护 canonical、导入已批准快照、冻结 PLAN 身份、维护 RESULT/CURRENT_STATE、执行批准后的发布 | 不自行设计界面，不修改生产源码，不代替源码验收 |
| Development Agent | 按冻结设计实现正式前后端、Mock/API Adapter、Feature Flag、测试和构建 | 不自行追随更新设计，不修改设计快照或已批准 PLAN |
| Review / Acceptance Agent | 只读检查设计还原、源码、状态真实性、隔离、回归和 Version Gate | 不参与被验收候选的实现或修复，不替代用户审美判断 |

## 3. Design Agent 的源码可见边界

Design Agent 必须理解实际产品，不能只根据抽象需求凭空设计。允许读取：

- `docs/README.md`、`CURRENT_STATE.md`、`DECISIONS.md`、需求池和适用版本文档；
- 正式前端的路由、组件、样式、状态管理、API 类型与构建边界；
- 与页面状态有关的后端 API 契约、领域错误、版本元数据和测试说明；
- 已发布产品和隔离测试环境中的界面表现。

Design Agent 只写独立 design workspace，包括 HTML 工作稿、虚构 Mock、设计快照与设计历史。禁止修改：

- 正式 `frontend/`、`backend/`、依赖、构建和打包配置；
- canonical 全局文档、版本 PLAN / RESULT、CURRENT_STATE 和正式决策；
- 真实 runtime、数据库、用户输出、`.env`、凭据或用户隐私数据。

发现源码限制、文档偏差或技术问题时，Design Agent 只在设计说明中登记事实与建议，由 Documentation Agent 或 Development Agent 按职责处理。读取现有实现用于避免脱离现实，不表示当前技术债永久限制未来设计；超前设计必须明确标为未来能力。

## 4. 设计工作稿与批准快照

### 4.1 持续工作稿

Design Agent 可以持续修改 `current/` HTML。工作稿允许不完整、被推翻或领先多个版本，不进入 CURRENT_STATE，也不自动成为 Development Agent 的任务。

### 4.2 用户批准

用户持续预览 HTML、提出修改并打回。只有用户明确要求“生成 Design Snapshot”时，当前阶段才视为批准。无需让 Design Agent 再次批准自己的输出。

### 4.3 不可变快照

快照使用递增身份，例如 `D-001`、`D-002`。已生成快照不得原地修改；任何后续变化产生新编号。一个快照可以被多个开发小版本引用，但每个 PLAN 必须另行限定实际实施范围。

建议 design workspace：

~~~text
design-workspace/
├── current/
│   ├── index.html
│   └── assets/
├── snapshots/
│   ├── D-001/
│   └── D-002/
└── DESIGN_HISTORY.md
~~~

`DESIGN_HISTORY.md` 只记录用户已经做出的设计选择、方案变化和废弃方向。影响长期产品规则、架构或多版本协作的决策，由 Documentation Agent 整理进入 canonical `DECISIONS.md`。

## 5. 每份 Design Snapshot 的最低内容

~~~text
D-005/
├── SNAPSHOT.md
├── prototype/
│   ├── index.html
│   └── assets/
├── SPEC.md
├── previews/
│   ├── page-default.png
│   ├── page-loading.png
│   └── page-error.png
└── CHECKSUMS.sha256
~~~

### 5.1 身份与现实基线

`SNAPSHOT.md` 至少记录：

~~~yaml
Snapshot ID: D-005
Status: Approved / Immutable
Created: 2026-09-05
Approved By: Product Owner
Based On: D-004
Entry Point: prototype/index.html
Observed Product Version: v2.0.2
Observed Source Commit: 78bb909c18ca28e45b54406536aa326887caa1ca
Reference Browser: Chromium
Primary Viewport: 1440x900
Secondary Viewports:
  - 1280x720
  - 390x844
Device Scale Factor: 1
Theme: Light
~~~

同时列出覆盖页面、相对上一快照的变化、未来设计、已知限制和未决问题。

### 5.2 可执行 HTML 原型

- HTML、CSS、JavaScript、图标、字体和图片资源自包含，不依赖 Design Agent 工作目录外的临时路径；
- 可以本地直接打开，或提供唯一、最小的启动方式；
- 使用正常 DOM、Flex/Grid、真实表单和交互组件，不用整页截图、Canvas 或大量绝对定位伪造界面；
- Mock 数据完全虚构，不调用生产 API、不读取真实 runtime；
- 主要导航、弹窗、抽屉、表单、保存、取消和删除确认可以实际演示；
- 通过页面内 Scenario 面板或固定 URL 参数切换 Default、Empty、Loading、Success、Error、Disabled、Partial Data、Preview 等适用状态。

### 5.3 设计说明

`SPEC.md` 记录 HTML 无法完整表达的规则：

- 信息架构、页面层级和导航关系；
- 核心流程的入口、用户动作、系统反馈、成功终点和失败恢复；
- 焦点、键盘、滚动、刷新恢复、长任务、弹窗和破坏性操作规则；
- 每个页面和功能是已确认设计、Preview、未来设计还是未完成；
- 字体、图标、fallback、目标 viewport 和响应式规则；
- 与现有 API、未来 API、Mock 和 Feature Flag 的设计假设。

### 5.4 视觉证据与完整性

`previews/` 保存核心页面及关键状态的参考截图；HTML 是交互真源，截图是视觉比较基准。`CHECKSUMS.sha256` 覆盖快照全部文件，用于证明 PLAN 导入内容与用户批准快照一致。

快照不得包含 `node_modules`、构建缓存、真实简历、真实个人信息、数据库、用户输出、密钥、Cookie、`.env`、正式产品源码或无关运行日志。

## 6. 版本启动时导入与冻结

Documentation Agent 编写小版本 PLAN 时，只选择当时最新的**用户已批准快照**，不读取 Design Agent 尚未批准的工作稿。建议导入位置：

~~~text
docs/design/baselines/V2.1.0/D-005/
~~~

保持 `docs/versions/v2.1.0/` 在正式开发阶段仍只含 PLAN 和 RESULT。PLAN 至少记录：

~~~yaml
Design Snapshot: D-005
Imported Baseline: docs/design/baselines/V2.1.0/D-005
Snapshot Manifest Hash: <hash>
Design Approval: Product Owner
Status: Frozen for V2.1.0
~~~

导入后必须验证文件清单与 hash。用户批准 PLAN 后，本版本不再同步 `current/` 或更新快照；Design Agent 可以继续产生 D-006、D-007，默认供后续小版本选择。

## 7. Design Snapshot 不等于开发范围

一个快照可以包含当前页面、未来 Preview 和纯设计探索。PLAN 必须另列交付矩阵：

| 页面/功能 | 快照状态 | 本版本目标 | 数据源 | 生产可见性 |
|---|---|---|---|---|
| 履历库 | 已批准 | Active | Real API | 显示 |
| 生成工作台 | 已批准 | Active | Real API | 显示 |
| 项目知识库 | 已批准未来设计 | Preview | Mock Adapter | Preview 标记或开发环境显示 |
| 模型管理 | Design-only | 不实施 | 无 | 隐藏 |

未进入该表实施范围的快照内容不是 Development Agent 的任务。

## 8. 一比一还原契约

冻结 HTML 是规范性设计基线。Development Agent 必须还原：

- 信息层级、页面结构、尺寸、间距、对齐和留白；
- 色彩、边框、圆角、阴影、字体、字号、字重和行高；
- 图标、静态资源和可见文案；
- Default、Empty、Loading、Success、Error、Blocked、Preview 等适用状态；
- 弹窗、抽屉、菜单、悬浮、选择、保存、取消和页面跳转；
- PLAN 指定 viewport 下的响应式结果。

Development Agent 可以自行决定组件拆分、状态管理、CSS 技术、API Client 和文件结构。验收比较的是可见和可操作结果，不要求生产 DOM 或 React 代码复制原型。

若技术原因无法一致还原，Development Agent 不得自行“优化”：必须在 RESULT 记录差异、原因和影响，由用户选择接受、返工或进入下一快照。

## 9. 设计状态与产品能力状态

两套状态不得混用。

设计稿状态：

~~~text
Draft → User Approved → Frozen for Version
~~~

产品能力状态：

| 状态 | 含义 | CURRENT_STATE 规则 |
|---|---|---|
| Absent | 正式产品中不存在 | 不登记为能力 |
| Preview | Development Agent 已在正式前端实现，但使用 Mock 或尚未接真实能力 | 单列为 Preview，不宣称正式支持 |
| Integrated | 已连接真实前后端，但未完成最终验收 | 记录“已接通、待验收”，不写成 Active |
| Active | 已完成源码、人工和文档验收 | 可以作为正式能力声明 |

Design Agent 的 HTML 即使完整可用，仍是设计产物，不自动构成产品 Preview。

## 10. 正式 Preview、Mock 与 Feature Flag

正式产品中的提前页面必须由 Development Agent 实现：

~~~text
Page / Component
        ↓
Typed Frontend Service Interface
        ↓
Mock Adapter | Real API Adapter
~~~

强制边界：

- 页面不感知 Mock/API 的具体实现，禁止把假数据散落写死在组件中；
- Mock 数据完全虚构，不调用真实写接口、不修改真实 runtime；
- Mock 与 API Adapter 遵循同一 typed contract，并有适用的 contract test；
- 未上线功能的生产默认值为隐藏或明确标注 Preview / Coming Soon；
- Feature Flag 只控制可见性和服务绑定，不作为能力已上线的证据；
- 每个 Flag 记录 owner、默认值、当前阶段、转 Active 条件和最迟清理版本；
- 功能转为 Active 后删除失去意义的 Mock 分支和过期 Flag，避免形成永久双实现。

## 11. 版本内 Design Freeze 与例外

普通视觉、非阻塞交互和文案优化进入下个小版本。只有以下问题允许打破冻结：

- P0：安全、数据损坏或核心流程完全不可用；
- P1：核心流程无法正确完成且没有合理绕行方式。

解冻流程：

~~~text
发现 P0/P1
→ Design Agent 提供修订 HTML
→ Product Owner 批准并要求新快照
→ Documentation Agent 导入新快照并追加 PLAN
→ 形成新的批准 commit/blob
→ Development Agent 同步
→ 受影响的开发验证、源码验收和人工验收重新执行
~~~

不得原地修改已冻结快照，也不得用 RESULT 反向改变设计基线。

## 12. 三类验收 Gate

### 12.1 Design Fidelity Gate

- 在快照规定的 Chromium、viewport、主题、字体和固定 Scenario 下生成正式前端截图；
- 与快照截图进行叠加或视觉差异比较；
- Review Agent 检查布局、状态、交互和响应式规则；
- 自动视觉差异只负责发现问题，用户拥有最终视觉判断权。

### 12.2 Integration Gate

- Preview/Mock/Real API 状态与 PLAN 一致；
- 页面状态、错误恢复、真实数据、副作用、Adapter contract 和 Feature Flag 通过验证；
- “页面存在”不能替代后端、事务、安全和失败路径验收。

### 12.3 Release Gate

- Preview、Integrated、Active 状态声明真实；
- 独立源码验收、用户人工验收和文档验收完成；
- CURRENT_STATE 只把 Active 写入正式能力，Preview 与 Integrated 单独标记；
- 发布仍由用户单独批准，Documentation Agent 负责最终 commit/tag/remote 核对。

## 13. 从成熟产品团队选择性借鉴

本项目借鉴大团队的身份、状态、质量门禁和反馈闭环，不复制其会议、多人审批和流程开销。

| 成熟实践 | V2.1.0 采用方式 |
|---|---|
| 设计/验证与构建双轨并行 | Design Agent 持续领先，Development Agent 按小版本只同步一次冻结快照 |
| 明确的 Ready for Development | 用户批准快照 + Documentation Agent 导入并冻结 PLAN 后才进入开发 |
| Design System / design tokens | 从颜色、字体、间距、圆角、阴影、层级和组件状态建立轻量 tokens，不先建设庞大平台 |
| Experiment/Beta/GA | 映射为 Preview/Integrated/Active，并为每次状态迁移设置退出条件 |
| Feature Flag 生命周期 | 记录 owner、生产默认值、启用条件和清理版本，不让 Flag 永久化 |
| 独立代码评审 | Review Agent 不参与候选实现，分别检查设计符合度、集成真实性和版本门禁 |
| 发布后反馈 | RESULT 记录用户体验、主要摩擦和下一设计输入，进入 Design Agent 后续工作稿 |
| Accessibility by design | HTML 阶段即覆盖键盘、焦点、label、错误表达、对比度和可预测交互 |

参考公开流程：

- [GitLab Product Development Flow](https://handbook.gitlab.com/handbook/product-development/how-we-work/product-development-flow/)：Validation 与 Build 双轨、阶段状态、Experiment/Beta/GA 和退出标准；
- [Google Code Review Standard](https://google.github.io/eng-practices/review/reviewer/standard.html)：代码健康持续改善、阻断问题与非阻断建议分离；
- [Microsoft Azure Feature Flags](https://learn.microsoft.com/en-us/azure/azure-app-configuration/manage-feature-flags) 与 [Safe Deployment Practices](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/safe-deployments)：开关、灰度、实验、健康检查与失败停止；
- [Atlassian Design Tokens](https://atlassian.design/tokens/design-tokens)：以语义 token 统一设计与实现；
- [W3C WCAG 2 Overview](https://www.w3.org/WAI/standards-guidelines/wcag/)：可感知、可操作、可理解、健壮及可测试成功标准。

## 14. V2.1.0 候选工作方向

以下只表示待设计和拆分的候选，不是已批准开发范围：

1. 重新设计全局信息架构、导航和三个现有页面；
2. 重新安排 V2.0.1 运行活动、阶段耗时和诊断信息的展示位置，但不无替代删除问题定位能力；
3. 建立首版轻量 design tokens 和组件状态规范；
4. 建立 Design Snapshot 导入、hash、视觉基线和设计符合度验收；
5. 根据用户批准的 HTML 快照决定是否提前实现未来功能 Preview；
6. 对进入正式前端的 Preview 建立 Mock/API Adapter 与 Feature Flag 生命周期。

## 15. 正式 PLAN 前待确认

1. Design workspace 的固定位置、仓库权限和快照编号规则；
2. 第一份用户批准 Design Snapshot 的编号、文件清单与现实基线；
3. V2.1.0 实际覆盖哪些页面，哪些进入 Preview，哪些只保留 Design-only；
4. 主参考浏览器、viewport、字体和视觉差异判定方式；
5. 首版 design tokens 的范围及现有组件复用边界；
6. Preview 在正式便携包中隐藏、显式展示还是仅开发环境可见；
7. Mock/API typed contract 和 Feature Flag 的具体落点；
8. Accessibility 的最低验收级别与自动/人工检查组合；
9. V2.1.0 是否只建立设计工作流和首批页面，还是同时实现完整整体界面重构；
10. 设计快照、开发候选和最终发布的独立验收安排。

在上述事项及实际 Design Snapshot 未经用户确认前，不将本文改名为 PLAN，不启动 V2.1.0 开发，也不把任何设计或 Preview 写入 CURRENT_STATE。
