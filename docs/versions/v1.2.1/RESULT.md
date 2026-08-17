# V1.2.1 验收报告

> 文档角色：V1.2.1 历史实施结果与验收证据  
> 状态：已验收  
> 对应计划：[PLAN.md](./PLAN.md)  
> 阅读提示：本文保留了当时对下一版的 GitHub 发布设想，该设想后来被当前 V1.3 重新定义所替代

> 版本：V1.2.1（历史遗留清理版）
> 前序版本：V1.2.0 / V1.2（PDF 布局复刻完成，验收通过）
> 当时后续设想：V1.3（功能演进版，含 GitHub 发布计划）；当前 V1.3 已重新定义为核心链路收口
> 验收日期：2026-08-15
> Python 环境：3.10.11 + venv

---

## 1. Baseline 建立与回归对比

### Baseline（修改前）

| 指标 | 值 |
|------|-----|
| exit code | 0 |
| E2E 结果 | PASSED |
| sections_rendered | `["profile(1)", "education(2)", "work(2)", "projects(3)", "skills(5)", "awards(5)", "summary(1)"]` |
| page_count (estimate) | 1 |
| render_warnings | 0 |
| layout_optimizations | 0 |
| DOCX 文件大小 | 39.7 KB |

### 最终回归（所有 Task 完成后）

| 指标 | Baseline | 最终回归 | 一致性 |
|------|----------|----------|--------|
| exit code | 0 | 0 | PASS |
| sections_rendered | 7 章节 | 7 章节 | PASS |
| page_count | 1 | 1 | PASS |
| render_warnings | 0 | 0 | PASS |
| DOCX 大小 | 39.7 KB | 39.7 KB | PASS |

**结论：业务行为不变。**

---

## 2. Task 执行结果

### P0：安全与可发布性

#### T1：移除 fill_user_data.py 真实 PII

| 检查项 | 结果 |
|--------|------|
| fill_user_data.py 真实 PII 替换为 mock 数据 | PASS |
| 产物文件名 resume_user_mock.docx | PASS |
| 验收报告内容核对（21 项全 PASS） | PASS |
| Level 1 源码扫描 = 0 | PASS |
| Level 2 运行产物扫描 = 0 | PASS |
| Level 3 Git tracked files 扫描 = 0 | PASS |
| docs/ 文件 PII 脱敏 | PASS |

**修改文件：**
- `backend/fill_user_data.py`：真实 PII → 虚构 mock 数据（张示例）
- `backend/output/验收报告_用户数据填充.txt`：git rm --cached 取消跟踪
- `docs/` 下 7 个文件：PII 关键词脱敏

#### T2：重构并补全 Git 忽略规则

| 检查项 | 结果 |
|--------|------|
| 根 .gitignore 从 Node 模板改为 Python 模板 | PASS |
| backend/.gitignore 精简 | PASS |
| 覆盖规则：output/、data/、*.db、.env、templates/*.docx、IDE、cache | PASS |

**修改文件：**
- `.gitignore`：完全重写为 Python 项目模板
- `backend/.gitignore`：精简为仅 backend 特有规则

#### T3：锁定 requirements.txt 已验证环境版本

| 检查项 | 结果 |
|--------|------|
| pip freeze 获取实际版本 | PASS |
| 所有依赖锁定精确版本（==） | PASS |
| 干净 venv 安装成功 | PASS |
| E2E 通过 | PASS |

**锁定版本：**
```
langchain==0.3.30          langchain-core==0.3.86
langchain-openai==0.3.35    openai==1.109.1
httpx==0.28.1               fastapi==0.141.1
uvicorn[standard]==0.52.3   sqlalchemy==2.0.52
pydantic==2.13.4            python-multipart==0.0.32
pdfplumber==0.11.10         chromadb==1.5.9
numpy==2.2.6                python-dotenv==1.2.2
python-docx==1.2.0
```

### P0 回归

| 检查项 | 结果 |
|--------|------|
| E2E PASSED | PASS |
| 三层 PII 扫描 = 0 | PASS |
| Baseline 对比一致 | PASS |

---

### P1：API 正确性

#### T4：修复 download_url 路径错误

| 检查项 | 结果 |
|--------|------|
| 旧路径 `/api/file/download` 搜索 = 0 | PASS |
| 新路径 `/api/template/download` 正确 | PASS |
| POST generate-docx → ok: True | PASS |
| download_url 返回正确路径 | PASS |
| GET download_url → HTTP 200 | PASS |
| Content-Type: application/vnd.openxmlformats... | PASS |
| 文件大小 > 2KB（38433 bytes） | PASS |

**修改文件：**
- `backend/api/routes/template.py`：download_url 从 `/api/file/download` 修正为 `/api/template/download`，同步更新注释

### P1 回归

| 检查项 | 结果 |
|--------|------|
| E2E PASSED | PASS |
| Baseline 对比一致 | PASS |

---

### P2：代码卫生

#### T5：清理 docx_writer.py 死代码

| 检查项 | 结果 |
|--------|------|
| 全仓库文本搜索无调用方 | PASS |
| import 搜索无引用 | PASS |
| 静态分析（import 验证） | PASS |
| E2E 回归 | PASS |

**删除项：**
- `estimate_page_count` 函数（无调用方，LayoutOptimizer.estimate_pages 替代）
- `apply_keyword_bold` 函数（无调用方）
- `_r_set_text` / `_r_set_bold` 辅助函数（仅被 apply_keyword_bold 调用）
- `from docx.oxml import OxmlElement` import（删除上述函数后无引用）

#### T6：清理 template_schema.py 旧路线死类

| 检查项 | 结果 |
|--------|------|
| `TemplateSection` 全仓库 0 命中（含注释） | PASS |
| `StyleInfo` 全仓库 0 命中（含注释） | PASS |
| `TemplateSchema` 全仓库 0 命中（含注释） | PASS |
| E2E 回归 | PASS |

**删除项：**
- `StyleInfo` 类
- `TemplateSection` 类
- `TemplateSchema` 类
- 未使用的 `Any` import
- `backend/models/__init__.py` 中三个类的 import 和 `__all__` 导出

#### T7：清理无效 import / 无调用兼容代码

| 检查项 | 结果 |
|--------|------|
| 全仓库文本搜索无调用方 | PASS |
| import 搜索无引用 | PASS |
| 静态分析（import 验证） | PASS |
| E2E 回归 | PASS |

**删除项：**
- `resume_document.py`：未使用的 `field_validator` import、`selected_education`/`selected_work`/`selected_projects` 兼容方法
- `template_renderer.py`：未使用的 `TemplateSpec` import、过期注释
- `api/routes/template.py`：未使用的 `shutil`/`uuid`/`datetime`/`Path` import、`_USER_ID` 变量
- `_e2e_v12_p0.py`：引用已删除 `apply_keyword_bold` 的过期注释

### P2+：鲁棒性修复（Chroma 专项）

#### T8：正式切回 Chroma PersistentClient 原生 + 修复初始化崩溃隐患 + 运维迁移接口

> **历史背景回应**（对应用户指出的 V1.0/V1.1 报告中那条「向量库 Chroma PersistentClient → numpy+JSON 文件 补装 VC++ 即切回 ❌ 未切」）：
>
> V1.0 时因 Windows 环境缺 VC++ 运行库 / onnxruntime DLL 加载失败，导致 Chroma 默认 embedding 路径无法使用，只能回退 numpy 余弦 + `vectors.json`。本次 V1.2.1 明确验证：**环境已就绪，已切回 Chroma 原生后端**，且通过「全部显式传 embeddings / query_embeddings」完全绕开 Chroma 默认 onnx embedding 路径，从根因上避免了 DLL 崩溃；同时提供了 numpy→chroma 迁移运维接口，对已存在的 `vectors.json` 历史数据可一键安全迁移。

| 检查项 | 结果 |
|--------|------|
| **A. 已切回 Chroma 原生后端** | |
| `get_backend_stats()["backend"]` = `"chroma"` | ✅ PASS |
| `get_backend_stats()["chroma_client_ok"]` = True | ✅ PASS |
| V1.0 「❌ 未切」状态 → V1.2.1 「✅ 已切回」 | ✅ 已更新 |
| **B. onnxruntime DLL 崩溃链路已彻底绕开（关键）** | |
| collection.embedding_function = None（无默认 embedding） | ✅ PASS |
| `get_backend_stats()["default_embedding_disabled"]` = True | ✅ PASS |
| upsert 始终显式传 `embeddings=`（不触发默认 embedding） | ✅ PASS |
| query 始终显式传 `query_embeddings=`（不调用 query_texts） | ✅ PASS |
| 完整 CRUD 流程无 process crash / exit code 异常 | ✅ PASS |
| **C. 初始化鲁棒性修复（崩溃 → 可回退）** | |
| `os.makedirs` 已移入 try/except 之内（目录权限失败时可回退 numpy） | ✅ PASS |
| except 分支内二次保证 numpy 回退目录可写 | ✅ PASS |
| `_NP_FILE` 唯一不重复定义 | ✅ PASS |
| **D. 运维接口：numpy → chroma 迁移已就绪** | |
| `migration_available()`：有 vectors.json 且 backend=chroma → True | ✅ PASS |
| `migration_available()`：无 vectors.json → False | ✅ PASS |
| `migrate_numpy_to_chroma(overwrite=False)`：源 3 条 → migrated=3，errors=0 | ✅ PASS |
| 二次迁移 overwrite=False → skipped_existing=3（幂等） | ✅ PASS |
| 三次迁移 overwrite=True → migrated=3（覆盖成功） | ✅ PASS |
| 迁移后余弦排序：emb=[0.1]*256 Top1 = "migrate-a1" | ✅ PASS |
| `get_backend_stats()` 快照：backend/path/count/禁用默认embedding全字段 | ✅ PASS |
| **E. 可发布性：忽略 + 版本锁定 + 链路无异常** | |
| `.gitignore:data/` 覆盖 chroma.sqlite3 → PASS | ✅ PASS |
| `.gitignore:data/` 覆盖 {uuid}/data_level0.bin / header.bin / length.bin / link_lists.bin → 5/5 | ✅ PASS |
| `.gitignore:data/` 覆盖 vectors.json（numpy 回退） | ✅ PASS |
| `git ls-files --cached backend/data/` = 0（缓存无遗留） | ✅ PASS |
| `chromadb==1.5.9` 在 requirements.txt 中精确锁定 | ✅ PASS |
| experience_service → rag_service → chroma_store 调用链 import 无异常 | ✅ PASS |
| **F. CRUD 验证** | |
| upsert 2 条 → count = 2 | ✅ PASS |
| query_by_embedding + where 过滤 → 正确返回 TopK | ✅ PASS |
| delete 2 条 → count = 0 | ✅ PASS |

**修改文件：**
- `backend/vectorstore/chroma_store.py`：
  1. `os.makedirs(settings.CHROMA_PATH)` 从 try 外移入 try 内；except 分支增加回退路径目录创建的保底；
  2. `_NP_FILE` 定义提前并删除重复赋值；
  3. 新增运维接口 `migration_available()` / `migrate_numpy_to_chroma(overwrite=False)` / `get_backend_stats()`；
- `docs/tech-plan-v1.2.1.md`：0.2 节「Chroma → numpy 回退未切回」标记为 ✅ 已处理并修正描述；0.4 节新增 P2+/T8 Chroma 专项条目；
- `docs/test-report-v1.2.1.md`：本条 T8 验收表；质量门新增切回 + 默认 embedding 禁用项。

### P2 最终回归

| 检查项 | 结果 |
|--------|------|
| E2E PASSED | PASS |
| 三层 PII 扫描 = 0 | PASS |
| Baseline 对比一致 | PASS |
| `TemplateSection`/`StyleInfo`/`TemplateSchema` 全仓库 0 命中 | PASS |

---

## 3. V1.2.1 质量门

```
V1.2.1 PASS
[x] 版本边界正确（前序 V1.2.0/V1.2，后续 V1.3）
[x] Baseline 已建立
[x] PII 源码 = 0
[x] PII 运行产物 = 0
[x] PII Git tracked files = 0
[x] .gitignore 正确（Python 模板 + backend 精简）
[x] requirements 可安装（干净 venv + E2E 通过）
[x] download_url 真正可访问（HTTP 200 + Content-Type 正确）
[x] 死代码无调用方（四层验证）
[x] 无意外 API 变化
[x] Chroma 原生后端已切回（backend=chroma，非 numpy 回退；V1.0 ❌未切 → V1.2.1 ✅已切回）
[x] Chroma 默认 onnx embedding 已禁用（embedding_function=None，显式传 embeddings/query_embeddings，无 DLL 崩溃风险）
[x] Chroma 初始化鲁棒（os.makedirs 包裹在 try/except 内）
[x] Chroma 运维接口就绪（numpy→chroma 迁移幂等 + 状态快照）
[x] Chroma 持久化产物全部被 .gitignore 覆盖（sqlite3 + *.bin + vectors.json）
[x] E2E PASS
[x] 修改前后核心业务行为一致（Baseline 对比）
[x] 每个 Task 可独立回滚
```

---

## 4. 修改文件清单

| 文件 | Task | 变更类型 |
|------|------|----------|
| `backend/fill_user_data.py` | T1 | 重写：真实 PII → mock 数据 |
| `.gitignore` | T2 | 重写：Node → Python 模板 |
| `backend/.gitignore` | T2 | 精简 |
| `backend/requirements.txt` | T3 | 重写：范围约束 → 精确锁定 |
| `backend/api/routes/template.py` | T4 | 修复：download_url 路径 + 清理 import |
| `backend/services/docx_writer.py` | T5 | 删除死代码 |
| `backend/models/template_schema.py` | T6 | 删除旧路线死类 |
| `backend/models/__init__.py` | T6 | 清理 import/export |
| `backend/models/resume_document.py` | T7 | 删除未使用 import + 兼容方法 |
| `backend/services/template_renderer.py` | T7 | 删除未使用 import + 过期注释 |
| `backend/_e2e_v12_p0.py` | T7 | 更新过期注释 |
| `backend/vectorstore/chroma_store.py` | T8 | 修复：os.makedirs 移入 try/except + numpy 回退保底 |
| `docs/tech-plan-v1.2.1.md` | T1 / T8 | PII 脱敏 + Chroma 状态修正 + 新增 T8 |
| `docs/tech-plan-v1.1.md` | T1 | PII 脱敏 |
| `docs/tech-plan-v1.2.md` | T1 | PII 脱敏 |
| `docs/test-report-v1.0.md` | T1 | PII 脱敏 |
| `docs/test-report-v1.1.md` | T1 | PII 脱敏 |
| `docs/test-report-v1.2.md` | T1 | PII 脱敏 |
| `docs/test-report-v1.2.1.md` | T8 | 新增 T8 Chroma 专项验收 + 质量门扩展 |

---

## 5. 当时计划的后续衔接（已被当前 V1.3 重新定义）

> 以下五项是 V1.2.1 验收当时记录的下一步设想，作为历史保留。当前活动计划以 [../v1.3/PLAN.md](../v1.3/PLAN.md) 为准。

V1.2.1 已完成所有 8 个 Task（T1-T8），满足 V1.3 前序条件：
- T1 PII 清理 → V1.3 G1/G2 历史层 PII 清理的基础
- T2 .gitignore 重构 → V1.3 G2 Index 层清理的基础（已验证 Chroma 全部产物被忽略）
- T3 requirements 锁定 → V1.3 G3 干净 venv 可移植性验证的基础（含 chromadb==1.5.9）
- T4-T7 代码清理 → V1.3 无需再处理代码层问题
- T8 Chroma 专项 → V1.3 可确认向量库状态、忽略覆盖、初始化鲁棒性全部就绪
