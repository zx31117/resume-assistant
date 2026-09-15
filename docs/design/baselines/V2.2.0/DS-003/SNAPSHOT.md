# Design Snapshot D-003

~~~yaml
Snapshot ID: D-003
Status: Approved / Immutable
Created: 2026-09-15 07:58 Asia/Shanghai
Approved By: Product Owner
Approval Evidence: R-D003-12；Product Owner 明确指示“审批通过，按文档要求做下一步”
Based On: D-002
Entry Point: prototype/index.html
Observed Product Version: v2.1.0
Observed Source Commit: 5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd
Source Bundle Hash: 2e3a60368cd317a057582b70ccff63255a679c34f71ca532955543b3cd70a5bc（v2.1.0 DRAFT.md）
Reference Browser: Google Chrome 152.0.7977.84（Playwright）
Primary Viewport: 1440x900
Secondary Viewports:
  - 1920x1080
  - 1280x800
  - 1024x768
  - 720x450
  - 390x844
  - 320x568
Device Scale Factor: 1
Approved Theme: A
Theme Approval Scope: single production theme
Manifest Hash: 见 CHECKSUMS.sha256；创建后校验全部通过
~~~

## 1. 批准结论

- Product Owner 明确批准内容：D003-0.11 全稿，包括四步生成工作台、任务保存与恢复、阶段回看、事实与段落详情、自然语言修改入口、PDF 预览和 Word/PDF 下载，以及“我的经历”“我的简历”“个人与隐私”页面。
- 最终主题决定：主题 A，采用本轮批准的简约、克制视觉修订作为单一生产主题基线。
- 明确未批准内容：真实 AI 生成、真实任务持久化、随输入重新生成 DOCX/PDF、生产 Career Memory 读写及完整 WCAG 认证；这些能力在原型中仍是 Design-only 或固定样张。
- 本快照是可执行设计基线，不代表其中所有 Design-only 页面进入开发范围。

## 2. 文件清单

| 路径 | 用途 | 必需 |
|---|---|---|
| `prototype/index.html` | 唯一入口 | Yes |
| `prototype/server.cjs` | 本地任务模拟和静态服务 | Yes |
| `prototype/assets/` | 自包含脚本、样式、PDF.js、虚构数据和固定样张 | Yes |
| `prototype/README.md` | 启动、场景与能力边界 | Yes |
| `SPEC.md` | 完整设计规范 | Yes |
| `previews/` | 主题 A 的 10 张 1440×900 参考截图 | Yes |
| `DESIGN_QA.md` | 批准前设计检查 | Extra |
| `THEME_EVALUATION.md` | A/B/C 对照与主题结论 | Extra |
| `SCREENSHOT_MATRIX.md` | 全量截图证据索引 | Extra |
| `CHECKSUMS.sha256` | 快照全部文件哈希 | Yes |

## 3. 页面和状态覆盖

| Page ID | 页面 | 覆盖 Scenario | 已批准 | 现实能力状态 |
|---|---|---|---|---|
| workbench-input | 身份与目标 | empty / saving / saved / restored | Yes | DESIGN_ONLY |
| workbench-understand | 理解岗位 | p1 / history-p1 | Yes | DESIGN_ONLY |
| workbench-match | 匹配经历 | p2 / history-p2 / insufficient | Yes | DESIGN_ONLY |
| workbench-edit | 修改与下载 | p3 / p4 / failed / failed-p4 / success | Yes | PREVIEW + DESIGN_ONLY |
| experiences | 我的经历 | list / detail / edit | Yes | DESIGN_ONLY |
| records | 我的简历 | empty / generated record | Yes | DESIGN_ONLY |
| privacy | 个人与隐私 | explanation / clear confirmation | Yes | DESIGN_ONLY |

## 4. 版本实施建议，不构成 PLAN

| 页面/功能 | 快照状态 | 建议版本目标 | 数据源 | 建议生产可见性 | 依赖 |
|---|---|---|---|---|---|
| 四步工作台与阶段状态 | approved design | Active | Real API | 显示 | task status / generation contracts |
| 身份与 JD 保存恢复 | approved design | Active | Real API | 显示 | task persistence |
| 岗位理解与经历匹配回看 | approved design | Active | Real API | 显示 | structured analysis results |
| 事实与段落依据 | approved design | Preview | Real API | 显示 | evidence provenance |
| 自然语言修改 | approved design shell | Preview | Real API | 接通后显示 | rewrite service and revision state |
| PDF 预览与 Word/PDF 下载 | approved design | Active | Real API | 显示 | renderer artifact endpoints |
| 我的经历与简历记录 | approved design | Preview | Real API | 分阶段显示 | Career Memory / task records |

Documentation Agent 编写 PLAN 时可以缩小范围，不得把本表自动视为获批开发任务。

## 5. 相对上一快照变化

| ID | 页面/组件 | 变化 | Product Owner 决定来源 | 影响 |
|---|---|---|---|---|
| CH-301 | 工作台 IA | 合并为连续任务工作台，并最终拆为身份、理解、匹配、修改下载四步 | R-D003-01 至 R-D003-11 | 核心流程与导航 |
| CH-302 | 阶段导航 | 当前阶段自动选中且不可点击；未来阶段降权；已完成阶段可回看 | R-D003-11 | 状态逻辑 |
| CH-303 | 完成预览 | 无主标题的 PDF 画布、可点击事实和整段内容、右侧详情与固定下载 | R-D003-06 至 R-D003-10 | 结果页布局与交互 |
| CH-304 | 修改入口 | 详情头部提供“开始编辑”，接受自然语言修改要求 | R-D003-09 | 修改流程入口 |
| CH-305 | 视觉语言 | 参考旧版恢复低饱和底色、轻边框阴影、克制绿色和更宽松留白 | R-D003-10 | 全局视觉层级 |
| CH-306 | 批注能力 | 任意组件可定位、保存、编辑和删除本地设计批注 | Product Owner 要求可批注界面 | 评审工具 |
| CH-307 | 任务连续性 | 本地设计服务模拟保存、刷新恢复、取消、局部失败与重试 | D-003 评审轮次 | 状态覆盖 |

## 6. 设计决策和废弃方向

- 保留：主题 A；四步流程；顶部“我的”与新任务；无标题 PDF 主预览；事实/段落详情；右栏固定下载；虚构数据边界。
- 废弃：三步合并“理解与匹配”；点击当前阶段跳入旧过程页；详情头部“已选中”和“返回完成摘要”；大面积绿色卡片底色。
- 进入后续工作稿：真实修改后重生成、跨进程任务恢复、完整记录管理、原生浏览器缩放和完整无障碍认证。

## 7. 已知限制与未决问题

| ID | 内容 | 是否影响实现 | Owner | 后续处理 |
|---|---|---|---|---|
| LIM-301 | 任务只保存在设计服务进程内存和当前标签引用中 | Yes | Development Agent | 接入正式任务持久化 |
| LIM-302 | DOCX/PDF 是固定虚构样张，不随输入或修改要求更新 | Yes | Development Agent | 接入 renderer 产物链 |
| LIM-303 | 经历与简历记录使用 fixture/内存，不访问生产 Career Memory | Yes | Development Agent | 按正式 API 契约集成 |
| LIM-304 | AI 解析、匹配和改写是演示节奏 | Yes | Development Agent | 接入结构化生成和流式事件 |
| LIM-305 | 720×450 代表 200% 等效 CSS viewport，未完成原生缩放认证 | No | QA / Accessibility | 实施阶段补充验证 |

## 8. QA 与证据

- Design QA：Pass，28 项核心检查，见 `DESIGN_QA.md` 和批准前 `qa/core-results.json` 记录。
- Supplemental review：Pass，13 项检查；Annotation QA：Pass，7 项检查；共 48 项。
- Screenshot Matrix：Pass，批准前生成 158 张跨主题、状态和 viewport 截图；快照收录主题 A 的 10 张关键截图。
- A/B/C Evaluation：主题 A 获批，见 `THEME_EVALUATION.md`。
- 外部依赖扫描：Pass；原型无 CDN 和在线素材，PDF.js 随快照提供。
- 真实数据扫描：Pass；全部为虚构 persona、JD、经历和样张。
- 键盘/焦点：Pass；菜单、对话框、阶段回看和交互控件完成自动检查。
- 对比度：Pass；主题 A/B/C 语义文本和控件样本通过自动检查。
- 响应式：Pass；覆盖 1920×1080 至 320×568，并包含 720×450 等效回流检查。

## 9. 完整性声明

- [x] Product Owner 已明确要求在批准后按文档执行下一步并生成本快照；
- [x] Snapshot ID D-003 创建前未被使用；
- [x] `prototype/` 与最终获批工作稿的可执行文件一致；
- [x] 不包含真实数据、凭据、runtime、依赖或缓存；
- [x] 所有文件已进入 `CHECKSUMS.sha256`；
- [x] 清单复核无缺失或 hash mismatch；
- [x] 本目录创建后不再修改。
