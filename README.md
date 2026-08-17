# Resume Assistant — AI 简历生成助手

> **当前版本**：V1.4（源码/运行数据解耦 + 可公开首发版）  
> **文档中心**：[docs/README.md](docs/README.md) · [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) · [版本索引](docs/versions/README.md) · [V1.4 PLAN](docs/versions/v1.4/PLAN.md)

基于用户积累的**职业经历知识库**，针对目标岗位 JD 生成**有边界的、不虚构事实的**定向简历 DOCX。真正的长期资产是用户职业经历库，简历只是一次输出。

- ✅ **单用户桌面端，纯本地 Python 3.10+**
- ✅ **FastAPI + uvicorn HTTP API**（可直接接入前端或 IDE 插件）
- ✅ **SQLite（真源）+ Chroma（向量索引，可全量从 SQL 重建）**
- ✅ **源码 / 运行数据物理解耦**：可变数据默认放到用户级目录（不进仓库）
- ✅ **内置一份完全虚构的 Demo 数据集**，无需任何密钥即可跑通 Stub Demo

## 1. 目录结构（源码树 A/B 类，不包含 C 类运行数据）

```
.
├── backend/                 # A 类：后端源码（可公开）
│   ├── api/routes/          #   路由：experience / generate / jd / resume / template
│   ├── core/                #   配置 + 错误（V1.4 统一 RESUME_DATA_DIR）
│   ├── database/            #   SQLAlchemy 模型 / 会话 / 初始化
│   ├── services/            #   经验抽取 / JD 分析 / 生成 / RAG / DOCX 写入
│   ├── prompts/             #   LLM prompt
│   ├── templates/           # B 类：DOCX 模板资产（可公开，经 V1.4 审查无 PII）
│   ├── config/              #   模板映射 JSON
│   ├── vectorstore/         #   Chroma 封装
│   ├── _v14_t3_migrate.py   # D 类：V1.4 一次性迁移脚本
│   ├── _v13_*.py / _e2e_*.py / fill_user_data.py / _diag_docx.py  # D 类：验收 / 诊断
│   ├── requirements.txt
│   ├── main.py
│   ├── .env.example
│   └── .gitignore
├── docs/                    # A 类：版本化文档（README / CURRENT_STATE / PLAN / RESULT / 审计）
├── input/                   # B 类：虚构 Demo 数据（demo_profile / demo_experiences / demo_jd）
├── LICENSE                  # MIT
└── README.md
```

> 🧱 运行时数据目录（C 类）——默认**不在仓库内**：
> - Windows: `%LOCALAPPDATA%\ResumeAssistant`
> - macOS: `~/Library/Application Support/ResumeAssistant`
> - Linux: `~/.local/share/resume-assistant`
>
> 所有可变数据（`database/app.db`、`vectorstore/chroma/`、`output/*.docx`、`logs/`、真实用户 PDF/DOCX/JD）都在该目录下，源码树保持干净，可直接上 GitHub 发布。

## 2. 快速开始

### 2.1 安装（干净 venv）

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate
pip install -r requirements.txt
```

### 2.2 跑单条可运行演示（Stub 模式，**零 API Key**）

> 目标：证明代码链路能跑通 → 直接在 `output/` 下生成 `demo_resume.docx`。

```bash
cd backend
python run_stub_demo.py
```

完成后会在 **V1.4 默认 runtime 输出目录**（或 `RESUME_DATA_DIR` / `DOCX_OUTPUT_DIR`）下看到生成的 DOCX。

### 2.3 接入真实大模型（可选）

1. 复制配置模板：
   ```bash
   cp backend/.env.example backend/.env
   ```
2. 在 `.env` 中填入你自己的 `ARK_API_KEY` 等变量；不需要改路径项——默认会放到用户级 runtime root 下。
3. 启动 API：
   ```bash
   cd backend
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

启动后：
- Swagger UI：http://127.0.0.1:8000/docs
- 健康检查：`GET /health`

### 2.4 V1.4 旧数据回滚开关（紧急时用）

如果迁移后运行异常，想切回 V1.3.x 的旧路径（`backend/data/app.db` / `backend/data/chroma` / `backend/output`），在 `.env` 里打开三行：

```dotenv
SQLITE_PATH=./data/app.db
CHROMA_PATH=./data/chroma
DOCX_OUTPUT_DIR=./output
```

重启应用即回到 1.3.x 行为。

## 3. 版本索引 & 文档

- [项目总览 / 产品目标 / 版本边界](docs/README.md)
- [当前实现事实](docs/CURRENT_STATE.md)
- [版本索引（每版一份 PLAN + RESULT）](docs/versions/README.md)
  - **V1.4**：[PLAN](docs/versions/v1.4/PLAN.md) · [RESULT](docs/versions/v1.4/RESULT.md) = `待验收`（T9 与 MIG-3 已通过，T10 Private 验证中）

## 4. 安全 & 可公开保证（V1.4 新增）

- **源码与运行数据物理分离**：数据库、向量库、生成的 DOCX、真实 PDF/DOCX/JD 默认不在 Git 工作区。
- **输入目录零真实用户文件**：`input/` 下只保留虚构 `demo_*` 样本。
- **`.env` 强忽略**：敏感密钥不放仓库，`.env.example` 仅占位。
- **D 类验收脚本解耦**：`_v13_*` / `_e2e_*` / `fill_user_data.py` 全部使用 `RESUME_DATA_DIR`，不会往 `backend/data/` 或 `backend/output/` 写数据。
- **T6/T9 双门安全审计**：开发侧 T6 先扫，高性能验收 Agent 在 T8 干净首发 worktree 上独立复核 T9。

## 5. License

MIT，见 [LICENSE](LICENSE)。
