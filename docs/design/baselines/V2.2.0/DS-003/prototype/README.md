# ResumeAssistant V2.2.0 D-003 设计工作稿

> 状态：Approved，工作稿 D003-0.11；Product Owner 于 2026-09-15 审批通过，冻结为 Design Snapshot D-003。
> 入口：`index.html`；最近更新：2026-09-15 Asia/Shanghai。
> 研究基线：V2.1.0 Design Strategy；导航和任务连续性以本轮明确需求为准。
> 现实产品基线：`v2.1.0` / `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`。
> 文档观察 commit：`d75b692c73ebeea91435f1daae996dde974fbf31`。
> Based On D-002；批准基线：Design Snapshot D-003。

聚焦生成工作台通过四步完成身份/JD、理解匹配、润色、预览导出。右上角“我的”菜单提供经历、简历记录和隐私入口。全部数据为虚构资料，任务 API 是本地设计模拟。

## 1. 启动

在本 `current` 目录运行唯一启动命令（需要 Node.js）：

```powershell
node server.cjs
```

访问：<http://127.0.0.1:8763/?scenario=empty>。仅监听 `127.0.0.1`。

必须通过此服务打开；双击 HTML 或普通静态服务器不支持保存/恢复演示。若端口已占用，先检查该地址是否已是本稿。运行原型无需 npm 安装、CDN、生产 API、真实 runtime 或目录外素材。PDF.js 位于 `assets/vendor/`；字体用系统 fallback。

## 2. 评审控制

| 控制 | 参数/入口 | 可选值 | 默认值 |
|---|---|---|---|
| 主题 | `?theme=` / 底部评审工具 | A / B / C | A，延续 D-002 方向 |
| 页面 | URL hash | workbench / experiences / records / privacy | workbench |
| Scenario | `?scenario=`，兼容 `sc` | 见下表 | empty |
| 创建新示例任务 | `&fresh=任意新值` | 换值新建 | 不填时刷新恢复原任务 |
| 打开评审工具 | `&review=1` | 场景、主题、演示推进、下一阶段、填入示例 | 收起 |
| 界面批注 | 底部“批注模式” | 开启后点击任意组件，填写、编辑或删除意见 | 关闭 |
| viewport | 浏览器 | 1280×720、1440×900、1920×1080；另测1280×800、1024×768、390×844、320×568、720×450 | 1440×900 |

| 场景 | 含义 |
|---|---|
| empty / saving / saved | 新任务、保存中、已保存 |
| restored | 恢复中的生成任务 |
| p1 / p2 / p3 / p4 | 岗位理解、经历匹配、润色及理由、文件准备 |
| history-p1 / history-p2 | 已完成业务结果回看 |
| cancel / cancelled | 取消确认、取消完成 |
| failed / failed-p4 | 经历失败、PDF 转换失败 |
| success | PDF 与 Word/PDF 下载 |
| menu / insufficient | 头像菜单、事实不足 |
| experiences / records / privacy | 三个二级页面 |

深链生成状态停在代表性时刻；底部“评审场景 → 演示推进 / 暂停”可继续。“下一阶段”快速推进。空态填写后点击生成则自动推进。切换主题不清空输入；切换场景有意创建新的示例任务。评审控制不属于正式产品功能。

### 批注第二轮修改

1. 点击底部“批注模式”；按钮变为“退出批注”。
2. 鼠标经过组件会出现橙色轮廓；点击后只选择组件，不触发原来的按钮或链接。
3. 在右侧面板写意见并保存。保存后面板自动收起，可继续点下一个组件。
4. 橙色编号表示已有批注；点击编号可查看、定位、编辑或删除。面板中的“复制全部”用于临时分享。
5. 批注写入 `review-annotations.json`，记录页面、场景、主题、viewport和组件定位；刷新与服务重启后保留。请只写设计反馈，不填写真实姓名、简历或联系方式。

在其他场景添加批注时，先退出批注模式，再用评审工具切换场景，之后重新开启。这样可避免误触发场景切换。

## 3. 页面清单

| Page ID | 用户名称 | 入口 | 核心任务 | 状态 |
|---|---|---|---|---|
| workbench | 生成工作台 | 默认 / 品牌 / 返回任务 | 四步生成、回看、取消、恢复、导出 | Draft |
| experiences | 我的经历 | 头像 / 材料不足 / 依据旁 | 选择经历、补充纠正、确认保存 | Draft |
| records | 我的简历 | 头像 / 完成页 | 虚构完成记录与文件 | Draft |
| privacy | 个人与隐私 | 头像 | 数据边界、确认清除草稿 | Draft |

## 4. 现实能力边界

| 展示能力 | 原型状态 | 当前产品状态 | 数据源 | 说明 |
|---|---|---|---|---|
| 聚焦导航与四步新布局 | 可操作 | DESIGN_ONLY | Mock | V2.2.0 PLAN Revision 1 尚未授权生产可见设计集成 |
| 保存、取消、局部重试、恢复 | 可操作 | DESIGN_ONLY | `/design/tasks` 内存模拟 | 不证明生产持久化、Provider、Word worker 已实现 |
| PDF 和双下载 | 固定样张 | 产品 V2.1.0 同源产物链 ACTIVE；本稿 DESIGN_ONLY | `assets/sample-resume.*` | 修改输入不会制作新样张 |
| 经历及记录 | 局部可操作 | 本稿 DESIGN_ONLY | fixture/内存 | 不读写生产 Career Memory |

## 5. 虚构数据

- Persona：林澈，计算机本科生；fixture ID `linche-d003-fictional`。
- JD：澄川实验室（虚构），后端开发实习生。
- 经历：一段实习、两个项目；入选两段、五条事实。
- 缺口：到岗安排未确认；第三项目因重复未采用；可切换事实不足/失败状态。
- 姓名、学校、公司、联系方式、业务指标完全虚构：Yes。

## 6. 已知限制

- Node 进程内存保存任务，sessionStorage 保存当前标签任务引用。同标签刷新/页面切换可恢复；关闭标签后的重新发现、后端重启/关机续跑未实现。
- 下载是固定 Word/PDF 样张；不随输入和经历编辑变化。服务重启后内存任务/记录消失，样张文件仍在。
- 经历编辑保存补充文字与确认状态，不驱动真实选材和文件生成。
- 上传/提取、无简历对话、经历删除、意图修订、长期偏好、开发后台的新实现不属于本轮；旧稿保存在 `drafts/v1.3-d002-reference/`。
- 200%回流采用720×450 CSS viewport等效验证，未声称原生缩放/完整WCAG认证。
- D-003 已获 Product Owner 明确批准并进入 Design Snapshot；快照仍不代表生产开发完成。
- 批注是本地设计评审资料，不会进入产品数据或修改被批注组件；组件结构大幅变化后，旧批注可能无法自动定位，但记录和文字仍会保留。

## 7. 关联文件

- [SPEC.md](SPEC.md)：布局、交互和能力边界。
- [REVIEW_NOTES.md](REVIEW_NOTES.md)：反馈与修复。
- [THEME_EVALUATION.md](THEME_EVALUATION.md)：主题对照。
- [SCREENSHOT_MATRIX.md](SCREENSHOT_MATRIX.md)：实际截图索引。
- [DESIGN_QA.md](DESIGN_QA.md)：检查结果和限制。
- `qa/check-design.cjs`、`qa/check-review.cjs`：设计验证脚本，需本地 Playwright/Chromium；原型运行不需要测试依赖。
