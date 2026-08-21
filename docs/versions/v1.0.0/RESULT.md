# AI Career Resume Assistant V1.0.0 实现结果存档

> 文档角色：V1.0.0 历史实施结果与验收证据  
> 状态：已验收  
> 对应计划：[PLAN.md](./PLAN.md)  
> 阅读提示：本文记录的是 V1.0.0 当时的实际状态，不是当前架构

> 版本：V1 实现结果
> 日期：2026-08-12
> 对应方案：[PLAN.md](./PLAN.md)
> 状态：✅ 端到端测试通过

---

## 1. 实现结果概览

V1 核心流程已跑通，端到端测试全部通过。以下为实测数据（测试 PDF：`真实用户简历PDF（已脱敏）`）：

| 步骤 | API | 耗时 | 结果 |
|------|-----|------|------|
| 健康检查 | `GET /` | - | ✅ 向量后端 = numpy |
| PDF 解析 | `POST /api/resume/upload` | - | ✅ 文本 1266 字符 |
| AI 经历提取 | `POST /api/experience/extract` | 201.5s | ✅ 提取 4 条经历 |
| 经历入库 | `POST /api/experience/` × 4 | - | ✅ 4/4 成功（SQL + 向量） |
| JD 分析 | `POST /api/jd/analyze` | 28.3s | ✅ 结构化岗位需求 |
| 检索+生成 | `POST /api/resume/generate` | 67.8s | ✅ 命中 3 条，简历 1574 字符 |

**生成简历质量**：基于真实经历（教育、产品经理实习、影像测评实习、语音交互项目），针对 Python 后端工程师岗位做了适配优化，突出可迁移能力（流程建模、需求规范、数据驱动问题定位），未编造 Python 开发经验。

---

## 2. 实际技术栈

| 层 | 方案计划 | 实际实现 | 是否一致 |
|---|---|---|---|
| Web 框架 | FastAPI + Uvicorn | FastAPI + Uvicorn | ✅ |
| SQL 数据库 | SQLite + SQLAlchemy | SQLite + SQLAlchemy | ✅ |
| 向量数据库 | Chroma（本地持久化） | Chroma 优先 + numpy 回退 | ⚠️ 见 4.1 |
| LLM | 豆包（火山方舟 Ark API） | 豆包（火山方舟 Ark API） | ✅ |
| LLM 模型 | `doubao-seed-evolving` | `doubao-seed-evolving` | ✅ |
| Embedding 模型 | `doubao-embedding-text-240715` | `doubao-embedding-vision-251215` | ⚠️ 见 4.2 |
| Embedding 调用方式 | LangChain `OpenAIEmbeddings` | 原生 HTTP（urllib） | ⚠️ 见 4.3 |
| PDF 解析 | pdfplumber | pdfplumber | ✅ |
| AI 编排 | LangChain（限 2 模块） | LangChain（限 1 模块） | ⚠️ 见 4.4 |

---

## 3. 模块实现清单

### 3.1 目录结构（与方案一致）

```
backend/
├── api/
│   ├── routes/
│   │   ├── resume.py          # ✅ PDF 上传/解析
│   │   ├── experience.py      # ✅ 经历 CRUD
│   │   ├── jd.py              # ✅ JD 分析
│   │   └── generate.py        # ✅ 简历生成
│   └── schemas.py             # ✅ Pydantic 模型（含字段校验器）
├── services/
│   ├── resume_parser.py       # ✅ PDF→文本（pdfplumber）
│   ├── experience_service.py  # ✅ 经历 CRUD + 向量库编排
│   ├── experience_extractor.py# ✅ 文本→结构化经历
│   ├── jd_analyzer.py         # ✅ JD→结构化需求
│   ├── rag_service.py         # ⚠️ 向量检索（改用原生 HTTP，非 LangChain）
│   ├── llm_service.py         # ✅ LLM 调用入口（LangChain）
│   └── resume_generator.py    # ✅ 生成 Markdown 简历
├── database/
│   ├── models.py              # ✅ ORM
│   ├── session.py             # ✅ DB session
│   └── init_db.py             # ✅ 建表
├── vectorstore/
│   └── chroma_store.py        # ⚠️ Chroma + numpy 回退
├── prompts/
│   ├── experience_extract.py  # ✅ 简化版 prompt
│   ├── jd_analyze.py          # ✅ 简化版 prompt
│   └── resume_generate.py     # ✅ prompt
├── core/
│   └── config.py              # ✅ 配置
├── data/                      # ✅ 运行时数据
├── main.py                    # ✅ FastAPI 入口
├── requirements.txt           # ⚠️ 版本锁定
└── .env / .env.example        # ✅ 配置
```

### 3.2 API 接口（全部实现）

| 方法 | 路径 | 状态 |
|---|---|---|
| POST | `/api/resume/upload` | ✅ |
| POST | `/api/experience/extract` | ✅ |
| POST | `/api/experience/` | ✅ |
| GET | `/api/experience/` | ✅ |
| PUT | `/api/experience/{id}` | ✅ |
| DELETE | `/api/experience/{id}` | ✅ |
| POST | `/api/jd/analyze` | ✅ |
| POST | `/api/resume/generate` | ✅ |

### 3.3 数据模型（与方案一致）

- `users` 表：`id, name, email, created_at`
- `experiences` 表：`id(UUID), user_id, type, title, company, time, role, description, skills(JSON), achievements(JSON), raw_text, vector_id, created_at, updated_at`
- 向量库：`id = experience.id`，`document` = 拼接文本，`metadata = {user_id, type, title}`

---

## 4. 与 tech-plan.md 的偏离及原因

### 4.1 ⚠️ 向量数据库：Chroma → numpy 回退

**方案**：Chroma（本地持久化），LangChain 原生支持。

**实际**：Chroma 优先 + numpy 余弦检索 + JSON 持久化回退。

**原因**：当前 Windows 环境下 Chroma 的 Rust 扩展（`chromadb_rust_bindings`）DLL 加载失败，原因是缺少 VC++ 运行时或 MSVC 编译环境。为保证 V1 可跑通，在 [chroma_store.py](../../../backend/vectorstore/chroma_store.py) 中实现了自动回退机制：Chroma 初始化失败时，使用 numpy 进行余弦相似度检索 + JSON 文件持久化向量数据。

**影响**：
- 对外接口完全一致（`upsert / delete / query_by_embedding`），上层 `rag_service` 无感知。
- V1 单用户、经历数 < 50 条场景下，numpy 性能足够。
- 未来环境就绪后，移除回退分支即可纯用 Chroma，无需改动其它模块。

**符合 V1 原则**：V1 能快速跑通；V2/V3 不推倒重来（接口不变）。

---

### 4.2 ⚠️ Embedding 模型：text-240715 → vision-251215

**方案**：`doubao-embedding-text-240715`（文本向量化模型）。

**实际**：`doubao-embedding-vision-251215`（多模态向量化模型，支持纯文本输入）。

**原因**：方案中的 `doubao-embedding-text-240715` 在火山方舟平台**不存在**。经文档核实与 API 探测：
- `doubao-embedding-text-240515`（旧版文本模型）已下线，调用返回 404。
- `doubao-embedding-text-240715` 从未存在过。
- 当前平台可用的 embedding 模型为 `doubao-embedding-vision-251215`（多模态），需在控制台开通后使用。

**影响**：
- 向量维度从预期的（未指定）变为 2048。
- 多模态模型支持纯文本输入，V1 用例（简历经历文本）完全适用。
- 调用方式与文本模型不同（见 4.3）。

**符合 V1 原则**：模型名通过 `.env` 配置，V2 换模型只改配置，不改代码。

---

### 4.3 ⚠️ Embedding 调用方式：LangChain → 原生 HTTP

**方案**：`rag_service.py` 使用 LangChain `OpenAIEmbeddings` 调用豆包 embedding。

**实际**：`rag_service.py` 使用原生 `urllib.request` 调用豆包多模态向量化 API。

**原因**：两层问题叠加，LangChain `OpenAIEmbeddings` 无法直接用于豆包 vision embedding：

1. **tiktoken 编码冲突**：`langchain-openai` 的 `_get_len_safe_embeddings` 会用 tiktoken 把文本编码成 token ID 数组（如 `[82805, ...]`）再传给接口，但豆包 API 期望接收原始字符串，导致 `BadRequestError: expected a string, but got [82805]`。

2. **API endpoint 与格式不同**：豆包 vision embedding 使用专属 endpoint `/api/v3/embeddings/multimodal`（非标准 `/embeddings`），请求体为对象数组 `input: [{type: "text", text: "..."}]`，响应体 `data` 是 dict（`data.embedding`）而非 list（`data[0].embedding`）。OpenAI 原生客户端也不兼容此格式。

**实现细节**（见 [rag_service.py](../../../backend/services/rag_service.py)）：
```python
# 直接 HTTP 调用豆包多模态向量化 API
url = f"{settings.ARK_BASE_URL}/embeddings/multimodal"
payload = json.dumps({
    "model": settings.EMBEDDING_MODEL,
    "encoding_format": "float",
    "input": [{"type": "text", "text": text}],
})
# 响应：body["data"]["embedding"]  — data 是 dict
```

**影响**：
- `rag_service.py` 不再 import langchain，改为 import urllib。
- LangChain 专属层从 2 个文件缩减为 1 个（仅 `llm_service.py`）。
- 业务层接口不变（`index_experience / delete_experience / retrieve`）。

**符合 V1 原则**：AI 模块边界依然清晰。未来若豆包推出标准 `/embeddings` 接口的文本模型，只需改 `rag_service.py` 一个文件。

---

### 4.4 ⚠️ LangChain 专属层：2 个文件 → 1 个文件

**方案**：仅 `llm_service.py` 与 `rag_service.py` 两个文件 import langchain。

**实际**：仅 `llm_service.py` 一个文件 import langchain（`langchain_core.prompts` + `langchain_openai.ChatOpenAI`）。

**原因**：见 4.3，`rag_service.py` 因豆包 embedding API 不兼容 LangChain 封装，改用原生 HTTP。

**影响**：
- 边界约束更严格了（LangChain 依赖减少）。
- "换掉 LangChain 只动 1 个文件"比方案更优。

**符合 V1 原则**：AI 模块边界清晰，且优于方案。

---

### 4.5 ⚠️ 依赖版本锁定

**方案**：`requirements.txt` 未指定版本范围。

**实际**：明确锁定 AI 栈版本：
```
langchain>=0.3,<0.4
langchain-core>=0.3,<0.4
langchain-openai>=0.3,<0.4
openai>=1,<2
httpx>=0.27,<0.29
```

**原因**：`langchain-openai 1.4.3` 与 `openai 2.x` 存在 `httpx2`/`httpx` 版本冲突。`openai 2.x` 依赖 `httpx2`，而 `langchain-openai 1.4.3` 依赖 `httpx`，两者注入机制冲突导致 LLM 调用 `Connection error`。降级到 `langchain 0.3.x + openai 1.x` 栈，统一使用 `httpx 0.28.1`。

**影响**：依赖更稳定，避免上游版本漂移导致故障。

---

### 4.6 ⚠️ Prompt 模板简化

**方案**：未指定 prompt 具体内容。

**实际**：经历提取与 JD 分析的 prompt 去除了 JSON 示例模板，改用文字描述字段要求。

**原因**：包含复杂 JSON 示例的 prompt 导致 LLM 推理时间过长（经历提取曾超 300s）。简化后响应时间从 300s+ 降至 100-200s。

**影响**：响应速度提升，结果质量未下降。

---

### 4.7 ⚠️ Pydantic 字段校验器

**方案**：未提及。

**实际**：在 [schemas.py](../../../backend/api/schemas.py) 的 `ExperienceItem` 中添加 `field_validator`：
- `skills / achievements`：非列表字段自动转为列表（LLM 偶尔返回字符串）。
- 字符串字段：`null` 自动转为空字符串（LLM 偶尔返回 null）。

**原因**：LLM 返回的数据格式不稳定，未加校验器时频繁触发 `ResponseValidationError`（500 错误）。

**影响**：系统稳定性提升，避免 LLM 输出波动导致的接口失败。

---

## 5. 边界自检清单（对照方案第 14 节）

| 检查项 | 方案要求 | 实际 | 说明 |
|---|---|---|---|
| LangChain import 范围 | 仅 `llm_service.py` 与 `rag_service.py` | ✅ 仅 `llm_service.py` | 见 4.4，比方案更严格 |
| 业务层不调 LLM | `experience_service` / `resume_parser` / `database` / `vectorstore` 不调 LLM | ✅ | 严格遵守 |
| API 层不直接调 LLM | `api/routes` 只调 services | ✅ | 严格遵守 |
| `chroma_store` 不依赖 LangChain | 用 chromadb 原生客户端 | ✅ | 用 chromadb 原生 + numpy 回退 |
| 数据模型按"经历是资产"设计 | 简历仅作为生成输出 | ✅ | 经历持久化存储，简历每次实时生成 |

---

## 6. 运行方式（实测）

```bash
cd <old-dev-root>\backend
# 虚拟环境已就绪
.venv\Scripts\activate
# 配置 .env（ARK_API_KEY / EMBEDDING_MODEL=doubao-embedding-vision-251215）
# 启动
uvicorn main:app --host 127.0.0.1 --port 8000
```

健康检查返回示例：
```json
{
  "status": "ok",
  "service": "AI Career Resume Assistant V1",
  "vector_backend": "numpy"
}
```

---

## 7. V2 改进建议

基于 V1 实现中发现的偏离点，V2 可考虑：

1. **向量数据库**：补装 VC++ 运行时 / MSVC，启用 Chroma 原生后端（移除 numpy 回退分支）。或直接评估换用 FAISS / Milvus。
2. **Embedding 模型**：关注火山方舟是否推出标准 `/embeddings` 接口的纯文本模型，届时可恢复 LangChain `OpenAIEmbeddings` 封装。
3. **LLM 响应速度**：经历提取 200s+ 偏慢，可评估切到 `doubao-seed-2-0-lite` 等更快的模型，或拆分为多次调用。
4. **Prompt 工程优化**：当前 prompt 已去除 JSON 示例，可进一步探索 few-shot 与结构化输出（`response_format`）的平衡。
5. **依赖升级**：关注 langchain 1.x / openai 2.x 的 httpx2 兼容性进展，条件成熟后升级。

---

## 8. V1 验收对照（对照方案第 13 节）

| 验收项 | 实现模块 | 状态 |
|---|---|---|
| 上传 PDF | `resume_parser` + `/api/resume/upload` | ✅ |
| AI 提取经历 | `experience_extractor` + `llm_service` | ✅ |
| 建立履历库 | `experience_service` + `database` + `chroma_store` | ✅ |
| 输入 JD | `jd_analyzer` + `llm_service` | ✅ |
| 检索相关经历 | `rag_service` | ✅ |
| 生成针对岗位简历 | `resume_generator` + `llm_service` | ✅ |
| 无明显编造 | Prompt 约束（保留 raw_text，禁止虚构） | ✅ |

---

## 9. 结论

V1 已达成核心目标：
- ✅ **快速跑通**：端到端测试全部通过，5 个核心步骤均返回 200。
- ✅ **V2/V3 不推倒重来**：所有偏离点均通过接口隔离（`.env` 配置、统一向量库接口、业务层不感知 LangChain），后续升级不影响业务模块。
- ✅ **AI 模块边界清晰**：LangChain 依赖缩减为 1 个文件（`llm_service.py`），优于方案的 2 个文件。

偏离点均为环境兼容性或平台 API 差异导致的必要调整，未破坏架构设计原则。
