# Design Snapshot D-002

~~~yaml
Snapshot ID: D-002
Status: Approved / Immutable
Created: 2026-09-06 18:12 Asia/Shanghai
Approved By: Product Owner
Approval Evidence: 2026-09-06 17:00 起一轮演进（文案用户侧化/简历记录/经历主从/纸张缩放/流式细化），
  PO 于 18:05 指示「这个版本也做一个快照，验收完成」
Based On: D-001
Entry Point: prototype/index.html
Observed Product Version: APP_VERSION 2.0.2（backend/core/version.py）
Observed Source Commit: N/A（source 目录非 git 仓库）
Source Bundle Hash: N/A
Reference Browser: Google Chrome（headless=new，本地截图与 DOM 校验）
Primary Viewport: 1440x900
Secondary Viewports:
  - 1280x800
  - 1024x768
  - 390x844
  - 320x568
Device Scale Factor: 1
Approved Theme: A（克制的职业工作台）
Theme Approval Scope: single production theme
Manifest Hash: 见 `./CHECKSUMS.sha256`（创建时 `sha256sum -c` 全部 OK，见 §8 QA）
~~~

## 1. 批准结论

- Product Owner 明确批准内容：v1.3.0 全稿（D-001 后一轮），验收完成并指示生成快照；
- 最终主题决定：**A（克制的职业工作台）**，单一生产主题（延续 D-001）；
- 明确未批准内容：
  - 简历记录作为正式生产入口（仅侧栏脚注「后续版本功能」预览态，未进入任务持久化）；
  - 意图级修改、修订历史、回退与锁定（界面标注「即将上线 / 后续版本功能」）；
  - 真实 DOCX 下载与身份长期自动带入（标注「后续版本能力/本次生成使用」）；
  - 我还没有简历（对话补充）真实接通（欢迎页标注「即将上线」）。
- 本快照是可执行设计基线，不代表其中所有 Preview/Design-only 页面进入开发范围。

## 2. 文件清单

| 路径 | 用途 | 必需 |
|---|---|---|
| `prototype/index.html` | 唯一入口 | Yes |
| `prototype/README.md` | 启动与参数 | Yes |
| `SPEC.md` | 完整设计规范 | Yes |
| `previews/` | 参考截图（10 张，主题 A） | Yes |
| `CHECKSUMS.sha256` | 快照全部文件哈希 | Yes |

## 3. 页面和状态覆盖

| Page ID | 页面 | 覆盖 Scenario | 已批准 | 现实能力状态 |
|---|---|---|---|---|
| welcome | 欢迎 · 冷启动 | 空态双路径 | Yes | DESIGN_ONLY（对话补充）/ ACTIVE 语义（上传路径） |
| upload | 上传现有简历 | idle / parsing / error | Yes | DESIGN_ONLY（Mock 解析） |
| generate | 生成简历 | ready / blocked / conflict | Yes | DESIGN_ONLY（Mock） |
| processing | 生成中 | 阶段推进 / AI 流式 / 失败重试 | Yes | DESIGN_ONLY（Mock） |
| result | 结果预览 | 纸张缩放 / 依据 / 修改 / 导出 | Yes | PREVIEW + DESIGN_ONLY |
| experience | 我的经历 | 主从：列表 / 详情 / 筛选搜索 / CRUD | Yes | ACTIVE 语义（Mock fixture） |
| records | 简历记录 | empty / list（生成自动登记） | Yes | DESIGN_ONLY（Preview 语义） |
| privacy | 个人与隐私 | 数据边界 / 重置当前数据 | Yes | DESIGN_ONLY |
| dev | 开发者后台 | 配置 / 日志 / 运行链路（隐藏入口） | Yes | DESIGN_ONLY |

## 4. 版本实施建议，不构成 PLAN

| 页面/功能 | 快照状态 | 建议版本目标 | 数据源 | 建议生产可见性 | 依赖 |
|---|---|---|---|---|---|
| 我的经历事实库（主从） | approved design | Active | Real API（V2.0.2 experience CRUD） | 显示 | experience API 契约 |
| 上传 PDF → 解析 | approved design | Preview | Real API | 显示 | extract 服务 |
| 生成岗位简历 | approved design | Preview | Real API | 显示 | generate 流水线契约 |
| 结果预览与依据 | approved design | Preview | Real API | 显示 | resume/detail 契约 |
| 结果纸张缩放预览 | approved design | Active（前端） | 本地渲染 | 显示 | 无（纯前端 fitPaper） |
| 简历记录 | approved design（Preview） | 待任务持久化后实施 | Real API | 后续版本入口 | 记录存储 |
| 下载 DOCX | approved design | 待 Renderer 完成后接通 | Real API | 显示（接通前占位） | Renderer |
| AI 流式展示 | approved design | 待定 | 需 stream 事件契约 | Preview | LLM stream |
| 意图级修改/修订历史 | Preview 标注 | 不实施 | None | 隐藏 | 依赖模型改写能力 |
| 身份长期自动带入 | Preview 标注 | 不实施 | None | 隐藏 | 本地存储方案 |

Documentation Agent 编写 PLAN 时可以缩小范围，不得把本表自动视为获批开发任务。

## 5. 相对上一快照变化（D-001 → D-002）

| ID | 页面/组件 | 变化 | Product Owner 决定来源 | 影响 |
|---|---|---|---|---|
| CH-101 | 全局文案 | 去除可见内部措辞（Preview/Design-only/演示/原型/深度思考/工作稿），换用户语言：实时预览/即将上线/AI 处理中/本地预览版；toast 与隐私/清除文案用户化 | 2026-09-06 17:00 指示 | 展示层全局 |
| CH-102 | records（新增） | 简历记录空态/列表双态；脚注入口标注后续版本；生成成功自动登记 | 2026-09-06 17:00 指示 | 新增视图 |
| CH-103 | experience | 列表+详情主从版式（360px 精简列 + 详情卡），选中高亮唯一，操作移入详情 | 2026-09-06 17:00 指示 | IA 层 |
| CH-104 | result | 纸张等比缩放适配 fitPaper（消除滚动），scale 下限 0.3 | 2026-09-06 17:00 指示 | 布局层 |
| CH-105 | processing/upload | AI 流式文案产物化，按 {n}/{target} 动态注入真实事实数与岗位 | 2026-09-06 17:00 指示 | 展示层 |

## 6. 设计决策和废弃方向

- 保留（延续 D-001）：V2.1.0 IA、主表达、上传即并入、AI 思考流式、控制台式 topbar、主题 A、
  结果右栏固定高卡、[hidden] 兜底、lock-scroll 锁整页滚动、导出常驻。
- 新增保留：用户侧文案基线（后续新增界面一律用用户语言）；records 登记钩子；fitPaper 缩放管线。
- 废弃（D-001 遗留内）：生成脚本中写死「5 条事实」与「输出 DOCX」表述；经历页内联长卡（改主从）。
- 进入后续工作稿：
  - records 正式持久化与详情；
  - 对话补充真实接通；
  - 意图级修改真实链路；
  - 纸张缩放极端视口复核与无障碍复核。

## 7. 已知限制与未决问题

| ID | 内容 | 是否影响实现 | Owner | 后续处理 |
|---|---|---|---|---|
| LIM-201 | 状态仅存单页内存，刷新回冷启动 | Yes | Design Agent | 接后端持久化 |
| LIM-202 | records 依赖生成动作登记，无独立删除/重命名 | No | Design Agent | 后续版本补齐 |
| LIM-203 | fitPaper scale 下限 0.3；390×844 以下未逐屏验证 | No | Design Agent | visual regression 接入 |
| LIM-204 | 主题 B/C token 残留无入口；单一主题 A | No | Design Agent | 快照只冻结 A |
| LIM-205 | e2e 依赖 jsdom | No | Design Agent | 接入 visual regression |

## 8. QA 与证据

- Design QA：Pass —— v1.3.0 十页截图人工复核（1440×900）
- Screenshot Matrix：Pass —— `previews/` 10 张主题 A（新增 records-empty / records-list）
- A/B/C Evaluation：已完成（D-001），延续批准 A
- 外部依赖扫描：Pass —— 单文件零外部资源
- 真实数据扫描：Pass —— 全部虚构（Persona 林澈 / 6 条经历 / 示例 JD）
- 键盘/焦点：Pass —— 经历行可聚焦回车选中、aria-pressed 同步
- 对比度：Pass —— A 主题语义 token ≥4.5:1
- 响应式：Pass（基本）—— ≤900 单列、主从 <980 回退单列

## 9. 完整性声明

- [x] Product Owner 已明确要求生成本快照（「这个版本也做一个快照，验收完成」）；
- [x] Snapshot ID D-002 未被使用；
- [x] `prototype/` 与最终获批工作稿一致（当前稿 index.html v1.3.0 原样复制）；
- [x] 不包含真实数据、凭据、runtime、依赖或缓存；
- [x] 所有文件已进入 `CHECKSUMS.sha256`；
- [x] 清单复核无缺失或 hash mismatch；
- [x] 本目录创建后不再修改。
