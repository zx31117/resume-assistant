# 简历助手 · V2.1.0 HTML 工作稿（Design Snapshot D-002）

> 状态：Frozen（Immutable）
> 入口：`index.html`
> 最近更新：2026-09-06 18:10 Asia/Shanghai
> 对应研究基线：V2.1.0 Design Strategy
> 现实产品基线：APP_VERSION 2.0.2（`source/full-repository/backend/core/version.py`）
> 原型稿版本：v1.3.0（演进记录见 `../SNAPSHOT.md` §5，Based On D-001）

## 1. 启动

唯一启动方式：

~~~text
直接打开 index.html（零依赖单文件，样式与图标全部内联）
~~~

访问地址：本地 `file://` 直接打开。

禁止依赖：Design Workspace 外的临时路径、生产 API、真实 runtime、真实用户数据、未声明的 CDN、
仅作者机器可用的字体。

## 2. 评审控制

| 控制 | 参数/入口 | 可选值 | 默认值 |
|---|---|---|---|
| 主题 | `?theme=`（仅 URL 深链，无界面元素） | A | A |
| Scenario | `?sc=`（仅 URL 深链，无界面元素） | welcome / upload-idle / generate-ready / generate-blocked / processing / result / experience / records-empty / records-list / privacy / dev | 真实产品状态（空态 → 欢迎） |
| viewport | 浏览器 | 1440×900（基准） | 1440×900 |

评审深链属于设计工具，不是已批准的正式产品功能；界面上不存在任何评审切换元素。

## 3. 页面清单

| Page ID | 用户名称 | 入口 | 核心任务 | 当前设计状态 |
|---|---|---|---|---|
| welcome | 欢迎 · 冷启动 | 首启空态 | 双路径：上传现有简历 / 我还没有简历（即将上线） | Approved |
| upload | 上传现有简历 | 欢迎页路径卡 | 本机解析 PDF → 静默并入经历库；右侧 AI 解析过程流式 | Approved |
| generate | 生成简历 | 侧栏 / 上传完成 | 身份摘要 + JD 输入 + 生成前检查 + 主操作（控制台式顶栏） | Approved |
| processing | 生成中 | 点「生成岗位简历」 | 4 阶段 + AI 思考流式（产物化文案，按真实事实数/岗位动态注入） | Approved |
| result | 结果预览 | 生成完成 | 纸张整页缩放适配；依据 / 修改固定高卡；导出常驻 | Approved |
| experience | 我的经历 | 侧栏 | 主从版式：360px 列表 + 详情卡（摘要/事实/操作） | Approved |
| records | 简历记录 | 侧栏脚注（后续版本预览） | 生成记录空态 / 列表两态 | Approved（Preview 语义） |
| privacy | 个人与隐私 | 侧栏 | 数据边界 / 可见性 / 重置当前数据 | Approved |
| dev | 开发者后台 | 个人与隐私下隐藏入口 | 运行链路 / 配置 / 日志 | Approved（隐藏入口） |

## 4. 现实能力边界

| 展示能力 | 原型状态 | 当前产品状态 | 数据源 | 说明 |
|---|---|---|---|---|
| 上传 PDF 并解析 | 视觉演示 | DESIGN_ONLY | Mock | 解析为模拟节奏，界面文案已用户化 |
| AI 流式（上传 / 生成 / JD） | 可操作演示 | DESIGN_ONLY | Mock 脚本 | 产物化文案，非真实 LLM 输出 |
| 简历生成与渲染 | 可操作演示 | DESIGN_ONLY | Mock | 无真实 DOCX |
| 下载 DOCX | 按钮演示 | PREVIEW | None | 文案标注「后续版本能力」 |
| 我的经历 CRUD | 可操作 | ACTIVE 语义对齐源码 V2.0.2 | Mock fixture | 主从版式 |
| 简历记录 | 双态演示 | DESIGN_ONLY | 生成时登记 | 侧栏脚注「后续版本功能」 |
| 身份长期自动带入 | 标注本次生成 | DESIGN_ONLY | None | 文案已用户化 |
| 意图级修改 / 修订历史 | 标注即将上线 | DESIGN_ONLY | None | 未实现 |

## 5. 虚构数据

- Persona：林澈（蓝港示范大学 · 软件工程 · 后端开发实习生）
- JD：澄川科技 · 后端开发实习生（Java / Spring Boot / MySQL）
- 经历：6 条虚构经历（教育 / 实习 / 项目×3 / 活动），覆盖 confirmed / needsReview / deferred
- 记录：生成成功后自动产生（records-list 深链含 2 条示例）
- 所有姓名、学校、公司、联系方式和业务指标均为虚构：Yes

## 6. 已知限制

- 状态仅存单页内存，刷新回冷启动（同 D-001）
- 经历库 6 条为 MEMORY_SEED；records 依赖生成动作登记，不持久化
- 纸张缩放 scale 下限 0.3；超高/超窄视口需人工复核
- e2e 冒烟依赖 jsdom；真机以人工截图复核为主

## 7. 关联文件

- `SPEC.md`
- `../SNAPSHOT.md`
- `../previews/`（10 张主题 A 状态截图）
- `../CHECKSUMS.sha256`
