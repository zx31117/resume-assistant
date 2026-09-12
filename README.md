# Resume Assistant

一个本地运行的 AI 简历生成应用：保存用户的完整职业经历，再根据目标岗位 JD 检索相关事实、生成针对性表达，并输出可预览、可下载的 Word/PDF 简历。

当前版本为 **V2.1.0**。本版本完成核心用户界面整体重构：从简历上传、经历管理、JD 输入、四阶段生成到结果预览形成统一工作流；最终 DOCX 是排版真源，由 Microsoft Word 转换为 PDF，页面预览与 PDF 下载读取同一文件。

## 项目能做什么

```text
PDF 简历 → 文本解析 → 经历提取 → SQLite Experience / Fact 事实库
目标 JD → JD 分析 → 固定经历槽位 → 入选经历内事实选择 → 受约束改写
→ ResumeDocument（保留逐 bullet 来源）→ DOCX 模板渲染
→ Microsoft Word 转换 PDF → PDF.js 预览 / Word 与 PDF 下载
```

核心原则：

- SQLite 中的 Experience / Fact 是事实源，`fact_embeddings` 只是可重建的检索派生数据；
- AI 只能改写已经存在的经历事实，不能虚构公司、岗位、项目或时间；
- 姓名和联系方式只使用本次请求显式提供的信息，缺失时留空；
- 求职意向来自当前 JD，不写入长期职业经历库；
- 第一层规则冻结进入简历的经历，第二层只选择这些经历中的可用事实；
- 模板只负责结构和样式，不决定保留或删除哪些经历。

当前包含：

- PDF 文本解析和结构化经历提取；
- Experience / Fact 的 SQLite 持久化、revision/hash、失效和重建；
- SQLite BLOB 向量与内存精确检索，无第二持久化后端；
- JD 七字段分析、两层选材和带逐 bullet `fact_refs` 的受约束内容生成；
- `ResumeBuilder` 确定性装配、DOCX 模板渲染与 Word→PDF 单一排版链；
- 无需 API Key 的本地 Stub Demo；
- FastAPI 接口和 Swagger 文档；
- 仓库外的统一运行数据目录。
- React + TypeScript + Vite 用户界面，包括欢迎上传、经历库、生成工作台、四阶段进度和结果页；
- 连接测试、激活和脱敏状态显示，Windows 长期 Key 存入 Credential Manager；
- 状态、迁移、Embedding 重建和失败重试的图形维护入口；
- Windows x64 目录型便携启动器，支持单实例、端口选择、重开和退出释放。
- PDF.js 展示真实生成的 PDF artifact，支持逐条事实依据定位以及 Word/PDF 双下载；
- 运行活动、服务端四阶段实时耗时、近期同类耗时对比、脱敏后台日志和诊断摘要。

## 技术架构

当前发布版采用本地单用户、前后端同源的分层架构。浏览器界面只负责输入、状态展示、预览和结果下载，职业事实、检索、内容选择、生成与文件渲染统一由后端完成，不在前端建立第二套业务逻辑或数据真源。

```text
React + TypeScript + Vite
        │  同源 HTTP API
        ▼
FastAPI 路由与请求模型
        │
        ▼
应用服务层
├─ PDF 解析与经历提取
├─ Experience / Fact 生命周期管理
├─ JD 分析与两层事实选择
├─ 受约束改写与 ResumeBuilder 确定性装配
├─ DOCX 模板渲染与 Word→PDF 转换
└─ 配置、迁移、索引维护与操作诊断
        │
        ├─ SQLite / SQLAlchemy：Experience、Fact 与 Embedding
        ├─ 外部 LLM / Embedding Provider：内容理解、改写与向量生成
        └─ Runtime data root：输出文件、日志、缓存与版本化配置
```

架构中的关键边界：

- **事实真源**：Experience / Fact 保存在 SQLite；Embedding 是可以从 Fact 重建的派生索引，不能反向覆盖事实。
- **内容决策**：程序负责流程、约束、来源校验和结构装配，模型只在明确边界内理解或改写内容。
- **薄前端**：React 页面通过 typed API/状态模型消费后端结果，不直接访问数据库、持有长期 API Key 或实现另一套选材逻辑。
- **输出同源**：`ResumeBuilder` 生成 `ResumeDocument`，模板 Renderer 生成 DOCX；DOCX 经 Microsoft Word 转为 PDF，PDF.js 预览与 PDF 下载读取同一 artifact。
- **运行隔离**：数据库、输出、配置、日志和缓存统一位于仓库外的 `RESUME_DATA_DIR`；源码目录不承担运行数据持久化。
- **凭据边界**：Windows 便携版的长期 API Key 保存在 Credential Manager；浏览器和生成文件不保存密钥。
- **发行形态**：生产前端由 FastAPI 同源托管，Windows 发行采用 PyInstaller `onedir`，启动器负责 loopback 监听、单实例、端口选择和退出清理。
- **失败策略**：迁移、索引、模型调用、来源校验或渲染失败必须显式可见；已知失败不降级为伪成功或静默使用过期数据。

这里描述的是当前发布架构。设计理由、历史替代方案和版本级变更记录见 [开发文档入口](docs/README.md)、[架构与产品决策](docs/DECISIONS.md) 和 [当前实现状态](docs/CURRENT_STATE.md)。

## 快速开始

### Windows 便携版（推荐）

V2.1.0 提供 Windows x64 目录型便携发行包。获得完整 `ResumeAssistant` 目录后：

1. 双击 `ResumeAssistant.exe`；
2. 浏览器自动打开本地界面；
3. 从左下角进入开发者后台，完成连接测试/激活、数据库迁移和索引维护；
4. 上传已有 PDF 简历，或在“我的经历”中维护 Experience；
5. 在生成工作台确认身份信息、粘贴目标 JD 并一键生成；
6. 在结果页核对事实依据，下载 Word 或 PDF。

便携运行不要求安装 Python、Node.js、打开终端、使用 Swagger 或编辑 `.env`。生成 PDF 与页面预览需要本机安装 Microsoft Word；若转换不可用，系统会明确显示 PDF 不可用且保留 Word 下载，不会回退到另一套近似排版。API Key 不写入浏览器长期存储或便携目录；运行数据仍位于 `%LOCALAPPDATA%\ResumeAssistant`。

### 从源码运行

#### 1. 获取源码并安装依赖

要求 Python 3.10 或更高版本。当前发布基线的干净环境验证使用 Python 3.10.11。

```bash
git clone https://github.com/ZX31117/resume-assistant.git
cd resume-assistant
python -m venv backend/.venv
```

Windows PowerShell：

```powershell
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

macOS / Linux：

```bash
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

#### 2. 运行零密钥 Demo

```bash
python backend/run_stub_demo.py
```

Demo 使用仓库内的完全虚构数据，不调用外部模型。成功时控制台会显示 `[STUB_DEMO_OK]`，并在默认运行目录的 `output/` 下生成 `demo_resume.docx`。

默认运行数据目录：

| 系统 | 路径 |
|---|---|
| Windows | `%LOCALAPPDATA%\ResumeAssistant` |
| macOS | `~/Library/Application Support/ResumeAssistant` |
| Linux | `~/.local/share/resume-assistant` |

#### 3. 构建图形界面并启动真实服务

真实的 JD 分析、检索和内容生成需要豆包 / 火山方舟 API Key。Windows 用户可以在服务启动后通过“本地系统”页测试并激活配置；`.env` 继续作为源码开发、自动化和故障恢复入口。

如需使用 `.env`，在项目根目录复制配置样例：

```powershell
# Windows PowerShell
Copy-Item backend\.env.example backend\.env
```

```bash
# macOS / Linux
cp backend/.env.example backend/.env
```

按需编辑 `backend/.env`：

```dotenv
ARK_API_KEY=<your-ark-api-key>
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-evolving
EMBEDDING_MODEL=doubao-embedding-vision-251215
```

构建前端并启动同源服务：

```bash
cd frontend
npm ci
npm run build
cd ../backend
python manage.py migrate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

打开 <http://127.0.0.1:8000/> 即可使用图形界面。数据库或索引未就绪时，应用仍允许进入开发者后台维护，但会阻断生成。

CLI 维护入口继续保留：

```bash
cd backend
python manage.py migrate
python manage.py status
python manage.py rebuild
python manage.py retry
```

`migrate` 可以直接初始化不存在的全新 SQLite 文件；迁移既有数据库时会先备份并核对。`rebuild` 需要有效的 Embedding API Key，缺少 Key 或索引仍未就绪时生成接口会明确阻断。

- Swagger UI：<http://127.0.0.1:8000/docs>
- 健康检查：`GET http://127.0.0.1:8000/api/health`
- 核心生成接口：`POST /api/resume/generate-docx`

## 主要 API

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/health` | 健康检查与版本信息 |
| `GET` | `/api/config` | 获取连接配置脱敏快照 |
| `POST` | `/api/config/test` | 测试候选连接配置 |
| `POST` | `/api/config/activate` | 激活连接配置 |
| `GET` | `/api/system/status` | 获取数据库、索引和就绪状态 |
| `POST` | `/api/system/migrate` | 初始化或迁移数据库 |
| `POST` | `/api/system/rebuild` | 全量重建 Embedding |
| `POST` | `/api/system/retry` | 重试失败 Embedding 项 |
| `GET` | `/api/system/operations` | 查询活动与最近操作 |
| `GET` | `/api/system/operations/{operation_id}` | 查询单次操作及阶段时间线 |
| `GET` | `/api/system/logs` | 增量读取脱敏结构化日志 |
| `GET` | `/api/system/diagnostics/{operation_id}` | 获取单次操作的脱敏诊断摘要 |
| `DELETE` | `/api/system/logs` | 清理历史诊断日志 |
| `POST` | `/api/resume/upload` | 上传并解析 PDF |
| `POST` | `/api/experience/extract` | 从文本提取结构化经历 |
| `POST/GET` | `/api/experience/` | 创建或查询经历 |
| `PUT/DELETE` | `/api/experience/{id}` | 更新或删除经历并同步索引 |
| `POST` | `/api/jd/analyze` | 分析目标岗位 JD |
| `POST` | `/api/resume/generate-docx` | 根据 JD 生成 DOCX 简历 |
| `POST` | `/api/resume/generate` | 旧 Markdown 接口已退出，返回 410 |
| `GET` | `/api/template/list` | 查询内置模板 |
| `GET` | `/api/template/download` | 下载生成的 DOCX |

请求结构和实时接口说明以 Swagger UI 为准。

## 数据与隐私

源码仓库只保存代码、内置模板、配置样例和虚构 Demo 数据。以下内容默认写入 Git checkout 之外，不会出现在仓库中：

- SQLite 数据库；
- SQLite Fact 与向量派生数据；
- 生成的 DOCX；
- 日志与缓存；
- 用户真实 PDF、JD 和其他输入；
- `.env` 与 API Key。

正常 API 运行时可以通过 `RESUME_DATA_DIR` 修改统一数据根目录，也可以用 `SQLITE_PATH` 和 `DOCX_OUTPUT_DIR` 分别覆盖数据库与输出目录。配置说明见 [`backend/.env.example`](backend/.env.example)。

不要把真实简历、联系方式、API Key 或运行目录内容提交到 GitHub Issue 或 Pull Request。

## 项目结构

```text
resume-assistant/
├── backend/
│   ├── api/              FastAPI 路由与请求模型
│   ├── core/             配置和领域错误
│   ├── database/         SQLite / SQLAlchemy、Fact 与迁移
│   ├── services/         解析、两层选材、生成、装配和渲染
│   ├── templates/        内置 DOCX 模板
│   ├── manage.py         迁移、状态、重建和重试入口
│   ├── main.py           API 入口
│   └── run_stub_demo.py  零密钥演示入口
├── input/                完全虚构的 Demo 输入
├── frontend/             React + TypeScript + Vite 前端
├── packaging/            Windows 便携启动器与 PyInstaller 打包配置
├── docs/                 架构、决策和版本开发档案
├── LICENSE
└── README.md
```

## 当前边界

- V2.1.0 已完成欢迎上传、经历库、JD 输入、四阶段生成和结果预览的整体界面重构；
- 诊断数据仅用于本地问题定位，按容量和保留期轮转，不是业务事实源、生产 APM 或云端遥测；
- 面向单用户本地使用，尚未包含登录、多用户和服务器部署；
- Windows x64 是当前便携发行范围；macOS/Linux 便携、Firefox 发布验收和完整移动端适配尚未覆盖；
- 当前使用固定模板；不包含 Draft/Revision、差异回退、局部重新生成或手工覆盖选材结果；
- 工作台状态尚未在跨页面切换后保留，该项已进入 V2.1.1；
- 不保证简历严格控制在一页，不生成个人总结或自我评价；
- 固定槽位、事实边界和来源闭环已验收，不代表相关性权重、召回质量、措辞或招聘效果已经优化；
- 当前用户界面左下角仍保留开发者后台入口，尚未形成面向上线环境的权限隔离；
- 当前只图形化豆包 / 火山方舟配置，不包含多 Provider、Token/费用统计或质量评测后台；
- 真实生成依赖外部模型服务，其可用性和费用由对应服务商决定。

## 开发历程与设计文档

本项目保留了从 V1.0.0 开始的完整人机协作开发档案，包括每个版本的计划、实际结果、决策依据、验收记录和工作流。这些记录既用于后续维护，也用于展示项目如何逐步形成当前架构。

希望了解架构约束、技术决策或完整开发路径，可以从 [`docs/README.md`](docs/README.md) 开始；只想安装和使用项目则无需阅读这些档案。

## License

本项目使用 [MIT License](LICENSE)。
