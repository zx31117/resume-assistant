# Resume Assistant

一个本地运行的 AI 简历生成后端：保存用户的完整职业经历，再根据目标岗位 JD 检索相关事实、生成针对性表达，并输出 DOCX 简历。

当前版本为 **V1.5.0**。本版本把职业素材收束为可追溯的 Experience / Fact，采用两层选材，并将向量持久化统一到 SQLite。

## 项目能做什么

```text
PDF 简历 → 文本解析 → 经历提取 → SQLite Experience / Fact 事实库
目标 JD → JD 分析 → 固定经历槽位 → 入选经历内事实选择 → 受约束改写
→ ResumeDocument（保留逐 bullet 来源）→ DOCX 模板渲染 → 本地文件
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
- `ResumeBuilder` 确定性装配与 DOCX 模板渲染；
- 无需 API Key 的本地 Stub Demo；
- FastAPI 接口和 Swagger 文档；
- 仓库外的统一运行数据目录。

## 快速开始

### 1. 获取源码并安装依赖

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

### 2. 运行零密钥 Demo

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

### 3. 启动真实 API

真实的 JD 分析、检索和内容生成需要豆包 / 火山方舟 API Key。

先在项目根目录复制配置样例：

```powershell
# Windows PowerShell
Copy-Item backend\.env.example backend\.env
```

```bash
# macOS / Linux
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，至少填写：

```dotenv
ARK_API_KEY=<your-ark-api-key>
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-evolving
EMBEDDING_MODEL=doubao-embedding-vision-251215
```

先初始化或升级数据库：

```bash
cd backend
python manage.py migrate
```

已有职业事实需要建立或修复向量时，可依次检查状态并按提示执行重建或重试：

```bash
python manage.py status
python manage.py rebuild
python manage.py retry
```

`migrate` 可以直接初始化不存在的全新 SQLite 文件；迁移既有数据库时会先备份并核对。`rebuild` 需要有效的 Embedding API Key，缺少 Key 或索引仍未就绪时生成接口会明确阻断。

然后在 `backend/` 目录启动服务：

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

- Swagger UI：<http://127.0.0.1:8000/docs>
- 健康检查：`GET http://127.0.0.1:8000/`
- 核心生成接口：`POST /api/resume/generate-docx`

## 主要 API

| 方法 | 路径 | 用途 |
|---|---|---|
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
├── docs/                 架构、决策和版本开发档案
├── LICENSE
└── README.md
```

## 当前边界

- 当前主要提供本地后端 API，没有完整图形界面；
- 面向单用户本地使用，尚未包含登录、多用户和服务器部署；
- 不保证简历严格控制在一页，排版精修属于后续体验版本；
- V1 不生成个人总结或自我评价；
- V1.5.0 验收固定槽位、事实边界和来源闭环，不代表相关性权重、召回质量、措辞或招聘效果已经优化；
- 真实生成依赖外部模型服务，其可用性和费用由对应服务商决定。

## 开发历程与设计文档

本项目保留了从 V1.0.0 开始的完整人机协作开发档案，包括每个版本的计划、实际结果、决策依据、验收记录和工作流。这些记录既用于后续维护，也用于展示项目如何逐步形成当前架构。

希望了解架构约束、技术决策或完整开发路径，可以从 [`docs/README.md`](docs/README.md) 开始；只想安装和使用项目则无需阅读这些档案。

## License

本项目使用 [MIT License](LICENSE)。
