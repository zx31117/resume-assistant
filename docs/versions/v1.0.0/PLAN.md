# AI Career Resume Assistant V1.0.0 技术方案存档

> 文档角色：V1.0.0 历史执行计划  
> 状态：已实施；实际结果见 [RESULT.md](./RESULT.md)  
> 基线：无，项目初始版本  
> 经验阅读：先读本 PLAN 理解当时目标，再读 RESULT 对照实际偏差；可执行性用于检验记录完整度  
> 当前全局上下文：[项目总览](../../README.md) · [当前状态](../../CURRENT_STATE.md)；本文本身保留 V1.0.0 当时语境

> 版本：V1 技术方案（确认稿）
> 日期：2026-08-12
> 目标：V1 快速跑通；V2/V3 不推倒重来；AI 模块边界清晰。

---

## 1. 产品定位

- **产品名称（暂定）**：AI Career Resume Assistant
- **产品目标**：基于用户已有职业经历，根据目标岗位 JD 自动生成针对性简历内容。
- **核心价值**：把用户已有经历转化为符合目标岗位需求的表达，而非简单润色文字。
- **关键设计原则**：真正的资产是"用户职业经历知识库"，简历文件只是该知识库的一个输出渠道。后续加模板、投递、面试辅导均不破坏核心架构。

---

## 2. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| Web 框架 | FastAPI + Uvicorn | 路由、请求调度 |
| SQL 数据库 | SQLite + SQLAlchemy ORM | V1 零配置；V2 换 PostgreSQL 只改连接串 |
| 向量数据库 | Chroma（本地持久化） | LangChain 原生支持 |
| LLM | 豆包（火山方舟 Ark API） | 兼容 OpenAI SDK，LangChain 直接接入 |
| LLM 模型 | `doubao-seed-evolving` | 由 `.env` 配置 |
| Embedding | 豆包 embedding 模型（默认 `doubao-embedding-text-240715`） | 可在 `.env` 修改 |
| PDF 解析 | pdfplumber | 纯文本提取，保留段落，无 AI |
| AI 编排 | LangChain（**仅限 2 个模块**） | 见第 4 节边界 |

---

## 3. 目录结构

```
backend/
├── api/
│   ├── routes/
│   │   ├── resume.py          # PDF 上传/解析
│   │   ├── experience.py      # 经历 CRUD
│   │   ├── jd.py              # JD 分析
│   │   └── generate.py        # 简历生成
│   └── schemas.py             # Pydantic 请求/响应模型
├── services/                  # 业务 + AI 编排层
│   ├── resume_parser.py       # 【无AI】PDF→文本
│   ├── experience_service.py  # 【无AI】经历 CRUD + 向量库读写编排
│   ├── experience_extractor.py# 【调 llm_service】文本→结构化经历
│   ├── jd_analyzer.py         # 【调 llm_service】JD→结构化需求
│   ├── rag_service.py         # 【LangChain】检索 Retriever
│   ├── llm_service.py         # 【LangChain】LLM 调用唯一入口
│   └── resume_generator.py    # 【调 llm_service】生成 Markdown 简历
├── database/
│   ├── models.py              # SQLAlchemy ORM
│   ├── session.py             # DB session
│   └── init_db.py             # 建表
├── vectorstore/
│   └── chroma_store.py        # Chroma 封装（无 LangChain 依赖）
├── prompts/                   # Prompt 模板（纯文本，非 LangChain 强绑定）
│   ├── experience_extract.py
│   ├── jd_analyze.py
│   └── resume_generate.py
├── core/
│   └── config.py              # 配置（env 读取）
├── data/                      # 运行时数据（SQLite + Chroma 持久化）
├── main.py                    # FastAPI 入口
├── requirements.txt
└── .env.example
```

---

## 4. 模块边界（核心，严格遵守）

按"是否触达 AI"分三类，**任何模块不得越界**：

### A. 纯业务/工具层（无 AI，不依赖 LangChain）
- `api/routes/*` — HTTP 路由
- `services/resume_parser.py` — PDF→文本（pdfplumber）
- `services/experience_service.py` — 经历 CRUD，编排 SQL 写入 + 向量库写入，**自己不调 LLM**
- `database/*` — ORM
- `vectorstore/chroma_store.py` — Chroma 原生封装（增删查），**不引入 LangChain**
- `core/config.py` — 配置

### B. AI 调用方（业务编排，通过 llm_service 间接用 AI）
- `services/experience_extractor.py` — 加载 prompts/，调 `llm_service` 提取结构化经历
- `services/jd_analyzer.py` — 加载 prompts/，调 `llm_service` 分析 JD
- `services/resume_generator.py` — 加载 prompts/，调 `llm_service` 生成简历

### C. LangChain 专属层（**只有这 2 个文件 import langchain**）
- `services/llm_service.py` — 封装 `ChatOpenAI`（指向豆包），暴露 `chat(prompt, vars)` / `chat_json(prompt, vars)` 等纯函数接口。Prompt 模板在这里加载并渲染。
- `services/rag_service.py` — 封装 Chroma Retriever，暴露 `retrieve(jd_analysis, k)`。

> **设计收益**：未来若要换掉 LangChain，只动这 2 个文件；业务模块、数据库、API 全部不动。这是"V2/V3 不推倒重来"的根基。

---

## 5. 数据模型

### 5.1 SQL 表（SQLite，JSON 字段存数组）

```
users
  id (PK), name, email, created_at

experiences
  id (PK, UUID)
  user_id (FK)
  type            # project | work | education
  title
  company
  time
  role
  description     # TEXT
  skills          # JSON 数组
  achievements    # JSON 数组
  raw_text        # TEXT 原始描述
  vector_id       # 关联 Chroma 中的文档 id
  created_at, updated_at
```

### 5.2 向量库（Chroma collection: `experiences`）
- 每条文档：`id = experience.id`
- `document` = 拼接文本（title + role + description + skills + achievements）
- `metadata` = `{user_id, type, title}`

### 5.3 UserExperience 数据结构（对外契约）

```json
{
  "id": "",
  "type": "project",
  "title": "AI错题本项目",
  "company": "",
  "time": "",
  "role": "产品经理",
  "description": "负责需求分析和PRD设计",
  "skills": ["AI应用", "产品设计", "需求分析"],
  "achievements": ["优化产品流程"],
  "raw_text": "原始描述"
}
```

> 字段由 AI 初步提取，用户后续可修改。

---

## 6. API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/resume/upload` | 上传 PDF → 返回解析后的原始文本 |
| POST | `/api/experience/extract` | 原始文本 → 结构化经历列表（AI） |
| POST | `/api/experience/` | 保存经历（写 SQL + Chroma） |
| GET | `/api/experience/` | 列出用户所有经历 |
| PUT | `/api/experience/{id}` | 修改经历（用户编辑，同步更新向量） |
| DELETE | `/api/experience/{id}` | 删除经历（同步删向量） |
| POST | `/api/jd/analyze` | JD 文本 → 结构化岗位需求（AI） |
| POST | `/api/resume/generate` | JD分析结果 → 检索 TopK + 生成 Markdown 简历 |

---

## 7. 核心流程串联

```
1. 上传 PDF
   route → resume_parser(PDF→文本)

2. 提取经历
   route → experience_extractor → llm_service(LLM) → 结构化经历

3. 入库
   route → experience_service(SQL写 + chroma_store写向量)

4. 分析 JD
   route → jd_analyzer → llm_service(LLM) → 结构化需求

5. 检索 + 生成
   route → rag_service(Chroma retriever, TopK)
        → resume_generator → llm_service(LLM) → Markdown 简历
```

---

## 8. 豆包（火山方舟）接入

兼容 OpenAI API，LangChain 直接用 `ChatOpenAI` / `OpenAIEmbeddings` 指向 Ark endpoint：

```python
# 仅在 llm_service.py / rag_service.py 内
ChatOpenAI(
    model=LLM_MODEL,                      # doubao-seed-evolving
    api_key=ARK_API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    temperature=0.3,
)
OpenAIEmbeddings(
    model=EMBEDDING_MODEL,                # doubao-embedding-text-240715
    api_key=ARK_API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)
```

---

## 9. 配置项（.env）

> 注意：真实 API Key 仅写入本地 `.env`（已 gitignore），不进入本文档与代码仓库。

```
# 豆包 / 火山方舟
ARK_API_KEY=<your-ark-********pi-key>
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=doubao-seed-evolving
EMBEDDING_MODEL=doubao-embedding-text-240715

# 存储
SQLITE_PATH=./data/app.db
CHROMA_PATH=./data/chroma

# 应用
APP_HOST=127.0.0.1
APP_PORT=8000
```

---

## 10. 依赖清单

```
fastapi
uvicorn[standard]
sqlalchemy
pydantic
python-multipart
pdfplumber
langchain
langchain-openai
langchain-chroma
chromadb
python-dotenv
```

---

## 11. 运行方式（V1 验收）

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
copy .env.example .env            # 填入 ARK_API_KEY
python init_db.py                 # 建表
uvicorn main:app --reload         # 启动
```

---

## 12. V2/V3/V4 扩展点（验证架构不被推翻）

- **V2 文档生成**：新增 `services/doc_exporter.py`（Markdown→Word/PDF），核心流程零改动。
- **V3 长期 Memory**：复用 `experience_service` 增加写入入口；新增 `services/profile_service.py` 做能力画像，不动现有模块。
- **V4 Agent**：把现有 services 包成 LangChain Tools，Agent 层在上面调度，services 内部不改。

---

## 13. V1 验收对照

| 验收项 | 实现模块 |
|---|---|
| 上传 PDF | resume_parser + /api/resume/upload |
| AI 提取经历 | experience_extractor + llm_service |
| 建立履历库 | experience_service + database + chroma_store |
| 输入 JD | jd_analyzer + llm_service |
| 检索相关经历 | rag_service |
| 生成针对岗位简历 | resume_generator + llm_service |
| 无明显编造 | Prompt 约束（保留 raw_text，禁止虚构） |

---

## 14. 边界自检清单（写代码时逐条对照）

- [ ] 全仓库仅 `services/llm_service.py` 与 `services/rag_service.py` 两个文件 `import langchain`
- [ ] `experience_service` / `resume_parser` / `database` / `vectorstore` 不出现任何 LLM 调用
- [ ] `api/routes` 不直接调 LLM，只调 services
- [ ] `vectorstore/chroma_store.py` 不依赖 LangChain（用 chromadb 原生客户端）
- [ ] 数据模型按"经历是资产"设计，简历仅作为生成输出
