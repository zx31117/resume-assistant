# AI Career Resume Assistant V1.1.0 技术优化需求文档

> 文档角色：V1.1.0 历史执行计划  
> 状态：已实施；实际结果见 [RESULT.md](./RESULT.md)  
> 基线：[V1.0.0 RESULT](../v1.0.0/RESULT.md)  
> 经验阅读：先确认 V1.0.0 RESULT，再理解本计划的 O1-O4，最后用本版 RESULT 对照实际结果  
> 当前全局上下文：[项目总览](../../README.md) · [当前状态](../../CURRENT_STATE.md)；本文本身保留 V1.1.0 当时语境

> 版本：V1.1.0
> 基于版本：V1
> 目标：优化 AI 流程质量与稳定性，不改变核心架构
> 原则：V1 快速验证，V1.1.0 提升效果，V2/V3 保持扩展能力

---

## 1. 文档目标

V1 已完成端到端流程验证：

```
PDF上传 → 文本解析 → AI经历提取 → 职业履历库存储 → JD分析 → RAG检索 → 针对岗位简历生成
```

核心功能已跑通，但实际测试暴露以下问题：

| 环节 | 实测耗时 | 问题 |
|------|---------|------|
| PDF 解析 | 即时 | 无 |
| AI 经历提取 | 201.5s | LLM 承担过多文本理解任务 |
| 经历入库 | 即时 | 无 |
| JD 分析 | 28.3s | 岗位信息维度不足 |
| 检索+生成 | 67.8s | 单纯语义匹配，缺少业务评分 |

V1.1.0 不重新设计架构，针对 AI 核心链路优化：

- 降低 LLM 无效工作量
- 提升经历提取稳定性
- 提升 JD 理解能力
- 提升 RAG 匹配准确度
- 降低 LLM 输出异常概率

---

## 2. V1.1.0 优化范围

### 2.1 纳入范围

| 编号 | 模块 | 优化内容 |
|------|------|---------|
| O1 | 经历提取 | 增加文本预处理和章节切分 |
| O2 | JD 分析 | 从 3 字段扩展到 7 字段 |
| O3 | RAG 检索 | 增加多因素评分机制 |
| O4 | LLM 调用 | 增加结构化输出和重试机制 |

### 2.2 不纳入范围

| 项目 | 原因 |
|------|------|
| Embedding 模型更换 | 当前火山方舟可用模型有限 |
| Chroma 迁移 | 当前 numpy 方案满足 V1 单用户场景 |
| PostgreSQL 迁移 | SQLite 满足验证需求 |
| Agent 化 | 当前流程属于固定 pipeline |
| 前端开发 | 当前重点是 AI 能力验证 |

---

## 3. O1：经历提取流程优化

### 3.1 当前流程

```
PDF文本 → LLM 整体理解 → 结构化经历 JSON
```

LLM 同时承担：文本清洗、章节识别、经历定位、信息抽取、JSON 生成。

导致：
- 输入越长，耗时越高
- 简历格式变化影响明显
- 大文本处理能力不足

### 3.2 新流程

```
PDF文本 → 文本预处理 → 章节切分 → 分段 LLM 提取 → 经历合并 → 去重
```

设计原则：**程序负责确定结构，AI 负责理解内容。**

### 3.3 新增模块

**文件**：`backend/services/text_preprocessor.py`（新增，纯业务/工具层，不调用 AI）

**功能**：

**1. 文本清洗**
- 处理多余空格、空行、特殊字符
- 保留时间、标题、公司名称等关键结构

**2. 简历章节识别**

| 章节类型 | 识别关键词 |
|---------|-----------|
| 教育 | 教育背景、教育经历、Education、Education Background |
| 工作 | 工作经历、实习经历、Professional Experience、Work Experience |
| 项目 | 项目经历、项目经验、Project Experience、Projects |
| 技能 | 技能、专业技能、技术栈、Skills、Technical Skills |

**3. 输出结构**

```json
{
  "cleaned_text": "清理后的完整文本",
  "sections": [
    { "type": "work", "title": "工作经历", "content": "..." },
    { "type": "project", "title": "项目经历", "content": "..." }
  ],
  "unmatched": "未被识别的自由文本"
}
```

### 3.4 experience_extractor 修改

原：全文 → LLM
改为：sections → 循环调用 LLM → 结构化经历 → 合并

**策略**：
- 每段文本独立处理，单次输入控制在 1000 字以内
- `section_type` 作为上下文传入 prompt
- 示例：`类型：项目经历，请从该项目经历片段提取：title, role, skills, achievement`

### 3.5 并发优化

多个 section 并行调用，例如：Worker1 处理教育背景，Worker2 处理工作经历，Worker3 处理项目经历。

| 指标 | V1 | V1.1.0 |
|------|----|------|
| 耗时 | 200s | 60-80s |
| 处理能力 | 3000 字 | 5000 字以上 |

### 3.6 Prompt 调整

**文件**：`backend/prompts/experience_extract.py`

```python
USER_TEMPLATE = """从下面简历片段中提取职业经历，输出 JSON 数组。
片段类型：{section_type}
每个经历包含字段：type(project/work/education), title, company, time, role, description, skills, achievements, raw_text。
严格基于原文，不编造。raw_text 必须是原文真实片段。只输出 JSON 数组，不要解释。

简历片段：
{section_content}
"""
```

---

## 4. O2：JD 分析增强

### 4.1 当前问题

V1 输出 `{ position: "", requirements: "", keywords: "" }`，信息不足，无法区分硬性要求、加分技能、岗位职责、岗位偏好。

### 4.2 新结构

```json
{
  "position": "",
  "industry": "",
  "required_skills": [],
  "preferred_skills": [],
  "responsibilities": [],
  "keywords": [],
  "experience_preferences": []
}
```

| 字段 | 作用 | 示例 |
|------|------|------|
| `position` | 岗位名称 | AI 产品经理 |
| `industry` | 行业 | 互联网/AI |
| `required_skills` | 硬性要求 | ["需求分析", "PRD"] |
| `preferred_skills` | 加分项 | ["RAG", "大模型"] |
| `responsibilities` | 岗位职责 | ["产品规划", "需求分析"] |
| `keywords` | 检索关键词 | ["AI应用", "B端产品"] |
| `experience_preferences` | 指导经历选择 | ["优先展示 AI 项目"] |

### 4.3 检索阶段利用

| 字段 | 检索用途 |
|------|---------|
| `required_skills` | 精确匹配打分（技能命中数） |
| `preferred_skills` | 加权匹配（加分但不硬性要求） |
| `keywords` + `responsibilities` | 语义检索 query 拼接 |
| `experience_preferences` | 结果重排序指导 |

### 4.4 Prompt 调整

**文件**：`backend/prompts/jd_analyze.py`

重写为 7 字段模板，明确区分 required_skills、preferred_skills、responsibilities 等字段。

---

## 5. O3：RAG 检索优化

### 5.1 当前流程

```
JD embedding → 向量搜索 → TopK 经历
```

问题：语义相似 ≠ 岗位匹配。例如岗位"AI 产品经理"可能找到普通产品经历，但遗漏 AI 项目经历。

### 5.2 新评分模型

```
Final = Semantic × 0.5 + Skill × 0.3 + Role × 0.2
```

**评分维度**：

| 维度 | 权重 | 算法 |
|------|------|------|
| 语义匹配 | 0.5 | Embedding cosine similarity |
| 技能匹配 | 0.3 | Jaccard similarity（经历 skills ∩ JD required_skills） |
| 岗位相关性 | 0.2 | 经历标题/描述与 JD 关键词重合度 |

**技能匹配示例**：
JD skills = {AI, Python, RAG}，经历 skills = {AI, Python} → 匹配度 2/3

### 5.3 输出：匹配分 + 匹配原因

```json
{
  "id": "...",
  "text": "产品经理（实习）-真实公司A（已脱敏）...",
  "metadata": { "user_id": "demo-user", "type": "work" },
  "scores": {
    "semantic": 0.85,
    "skill": 0.67,
    "role": 0.80,
    "final": 0.79
  },
  "reason": "该经历包含 AI 应用开发和需求分析，与岗位要求高度相关"
}
```

### 5.4 匹配原因生成规则

- 语义分 ≥ 0.8 → "语义高度匹配"
- 语义分 ≥ 0.6 → "语义较为相关"
- 技能匹配百分比直接显示
- 岗位相关性 ≥ 0.8 → "岗位高度匹配"

组合为自然语言：`语义高度匹配，技能匹配 67%，岗位高度匹配。`

### 5.5 修改文件

- `backend/services/rag_service.py` — 新增多因素评分逻辑 + 匹配原因生成
- `backend/api/schemas.py` — `MatchedExperience` 增加 `scores` 和 `reason` 字段
- `backend/api/routes/generate.py` — 透传 scores 和 reason 给客户端

---

## 6. O4：LLM 输出稳定性优化

### 6.1 当前问题

```
LLM 输出 → Pydantic 修正
```

属于事后处理，异常输出概率仍较高。

### 6.2 优化方案

```
LLM → Structured Output → Pydantic → 业务
```

**三层防护**：

| 优先级 | 方案 | 说明 |
|--------|------|------|
| 1 | Structured Output | 要求模型按 Schema 返回 |
| 2 | Prompt 约束 JSON 格式 | 追加 JSON Schema 描述到 prompt |
| 3 | Pydantic 校验 | 保留现有 field_validator 兜底 |

### 6.3 实现策略

**文件**：`backend/services/llm_service.py`

新增 `chat_structured` 方法，优先调用豆包 Structured Output 能力；若不可用则回退到普通 chat + Pydantic 校验。

增加重试逻辑：校验失败时降低 temperature 重试，最多 2 次，仍失败则返回默认值 + 警告日志。

### 6.4 影响范围

- `backend/services/llm_service.py` — 新增 `chat_structured` + 重试逻辑
- `backend/services/experience_extractor.py` — 改用 `chat_structured`
- `backend/services/jd_analyzer.py` — 改用 `chat_structured`

---

## 7. 数据模型调整

### 7.1 新增 JDAnalysisOut

```python
class JDAnalysisOut(BaseModel):
    position: str = ""
    industry: str = ""
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    responsibilities: List[str] = []
    keywords: List[str] = []
    experience_preferences: List[str] = []
```

### 7.2 新增 MatchScores

```python
class MatchScores(BaseModel):
    semantic: float = 0.0
    skill: float = 0.0
    role: float = 0.0
    final: float = 0.0
```

### 7.3 MatchedExperience 扩展

```python
class MatchedExperience(BaseModel):
    id: str
    text: str
    metadata: dict
    distance: Optional[float] = None
    scores: Optional[MatchScores] = None   # 新增
    reason: str = ""                        # 新增
```

---

## 8. API 调整

### 8.1 JD 分析接口

`POST /api/jd/analyze` — 响应新增 4 字段：`industry`、`preferred_skills`、`responsibilities`、`experience_preferences`。

兼容性：前端需适配新字段。

### 8.2 简历生成接口

`POST /api/resume/generate` — `matched_experiences` 新增 `scores` 和 `reason` 字段。

兼容性：新增字段，旧客户端可忽略。

---

## 9. 修改文件列表

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/services/text_preprocessor.py` | 新增 | 文本预处理 + 章节切分 |
| `backend/services/experience_extractor.py` | 修改 | 章节处理 + 结构化输出 |
| `backend/services/jd_analyzer.py` | 修改 | 7 字段输出 + 结构化输出 |
| `backend/services/rag_service.py` | 修改 | 多因素评分 + 匹配原因 |
| `backend/services/llm_service.py` | 修改 | Structured Output + 重试逻辑 |
| `backend/api/schemas.py` | 修改 | 新增 JDAnalysisOut、MatchScores 模型 |
| `backend/prompts/experience_extract.py` | 修改 | 新增 section_type 上下文 |
| `backend/prompts/jd_analyze.py` | 修改 | 重写为 7 字段模板 |
| `backend/api/routes/generate.py` | 修改 | 透传 scores 和 reason |

---

## 10. V1 → V1.1.0 影响

| 模块 | V1 | V1.1.0 |
|------|----|------|
| PDF 解析 | pdfplumber | pdfplumber + text_preprocessor |
| 经历提取 | 全文 LLM | 分段 LLM + 合并 |
| JD 分析 | 3 字段 | 7 字段 |
| RAG | 语义搜索 | 综合评分 |
| LLM 输出 | JSON + 校验 | 结构化输出 + 校验 |
| Embedding | vision 模型 | 不变 |
| 数据库 | SQLite | 不变 |
| 向量库 | Chroma/numpy | 不变 |

---

## 11. V1.1.0 验收标准

### 11.1 性能

| 指标 | 目标 |
|------|------|
| 经历提取 | ≤ 80s |
| JD 分析 | ≤ 30s |
| 简历生成 | ≤ 70s |

### 11.2 稳定性

- LLM 异常格式明显下降
- JSON 解析失败自动恢复
- 不影响端到端流程

### 11.3 效果

- 岗位相关经历排序提升
- 输出匹配原因
- 保持不虚构经历

### 11.4 回归测试

V1.1.0 改造后，必须重新跑通 V1 的端到端测试，确保未引入回归问题。

---

## 12. V2 预留

V1.1.0 完成后：

- 存储升级：SQLite → PostgreSQL
- 向量升级：numpy → Chroma/Milvus
- 产品升级：用户系统、云部署、Word 导出、简历模板、面试辅助、职业画像

---

## 总结

**V1** 解决：能不能根据 JD 生成针对性简历。
**V1.1.0** 解决：如何让 AI 更准确理解经历、更合理匹配岗位、更稳定生成结果。

核心资产仍然保持：

```
用户职业经历库 → 岗位理解 → 经历检索 → 简历生成
```

不改变产品方向。
