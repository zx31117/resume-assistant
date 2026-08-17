# V1.4 T4 审查：D 类脚本 / 模板资产 / 测试输出解耦

> 对应 T1_AUDIT.md 的 D 类（隔离审查）+ B 类（整理后公开）+ T2 数据解耦（防止测试/验收脚本又把 output 写回源码树）。
>
> 结论先说：**未发现密钥 / 真实 PII / 本地绝对路径硬编码**。D 类脚本与模板资产都通过审查；测试 & 验收脚本已统一使用 `settings.DOCX_OUTPUT_DIR`，不再写 `backend/output/`。

---

## 1. D 类脚本清单（`backend/_*.py` + `fill_user_data.py`）

| 文件 | 用途 | 是否含密钥 | 是否含真实 PII | 是否硬编码本地路径 | V1.4 修改 |
|---|---|:---:|:---:|:---:|---|
| `_diag_docx.py` | 诊断 DOCX 排版（读 DOCX 打印段落/分页信息） | ❌ 否 | ❌ 否 | 原硬编码 `output/<file>` → 改走 `settings.DOCX_OUTPUT_DIR`，支持 CLI arg | ✅ 已解耦 |
| `_e2e_v12_p0.py` | V1.2 P0 离线 E2E（无外部 API） | ❌ 否 | ❌ 否（全部数据脚本内构造） | 原 `BACKEND_ROOT/output` → `settings.DOCX_OUTPUT_DIR` | ✅ 已解耦 |
| `_e2e_v13_full.py` | V1.3 完整流程（PDF→落库→生成 DOCX） | ❌ 否（ARK_API_KEY 读 env） | ❌ 否（读 input/ 目录，数据归属用户） | 原 `BACKEND_ROOT/output` → `settings.DOCX_OUTPUT_DIR` | ✅ 已解耦 |
| `_v13_stub_e2e.py` | V1.3 Stub E2E（LLM/Embedding 打桩） | ❌ 否 | ❌ 否 | 原 `BACKEND_ROOT/output` → `settings.DOCX_OUTPUT_DIR` | ✅ 已解耦 |
| `_v13_validation.py` | V1.3 §8.2 必测独立验证 | ❌ 否 | ❌ 否 | 原 `BACKEND_ROOT/output` → `settings.DOCX_OUTPUT_DIR`；**清理函数不再删 backend/data（历史真源永不删除）** | ✅ 已解耦 |
| `fill_user_data.py` | 虚构"张示例"mock 数据验收 DOCX | ❌ 否 | ❌ 否（姓名手机号均为示例，见脚本 docstring 声明） | 原 `BACKEND_ROOT/output` → `settings.DOCX_OUTPUT_DIR` | ✅ 已解耦 |
| `_v14_t3_migrate.py` | **本次新增** V1.4 T3 一次性迁移脚本 | ❌ 否 | ❌ 否（只做文件复制 + vector 重建） | 专门屏蔽 env 污染强制走 runtime root；运行完 **不删除源码树内脚本**（供后续本地机器有 API key 时重跑 vector 重建） | ✅ 新增即合规 |
| `_v14_t3_redo_vector.py` | **本次新增** T3 补救脚本（sandbox 缺 API key 时补跑 rebuild，不通过 core.config 初始化触发 mkdir 限制） | ❌ 否 | ❌ 否 | 专门不触发 core.config 的目录创建，直接构造 SimpleNamespace settings | ✅ 新增即合规 |

**处置**：全部留在 `backend/`（D 类允许进源码树，仅需审查不含敏感内容），无删除项。

---

## 2. 模板资产审查（B 类 → 可公开）

| 文件 | 类型 | 审查点 | 结果 |
|---|---|---|---|
| `backend/templates/pm_template.docx` | Word 模板（A 类资产） | 模板示例文案（占位符"示例姓名 / XXX 科技有限公司"等）、字体、样式、封面样式、页眉页脚 | ✅ 无 PII，纯模板框架占位文本（非真实个人信息） |
| `backend/templates/pm_template.json` | 模板→JSON 映射（A 类资产） | 样式锚点 / 书签 / 段落定位 | ✅ 仅 style/bookmark 名，无 PII |
| `backend/templates/_build_templates.py` | 模板构建脚本（A 类构建工具） | 是否写死本地绝对路径 / 密钥 / PII | ✅ 仅用 python-docx 在源码树内重新构建 docx；不读外部数据；可在任意机器幂等运行 |
| `backend/config/template_mapping.json` | 模板 ID → 文件映射 | 仅字符串字段 | ✅ 无 PII |

**处置**：保持 B 类，无需归档移动；`_build_templates.py` 仍属于 A 类工具，任何人都能重建 pm_template.docx。

---

## 3. 测试 / 验收输出解耦

### 3.1 之前的违规模式

- 所有 D 类验收脚本都写：
  ```python
  OUTPUT_DIR = BACKEND_ROOT / "output"
  OUTPUT_DIR.mkdir(exist_ok=True)
  ```
- `_v13_validation.py._cleanup()` 还会：
  ```python
  shutil.rmtree(BACKEND_ROOT / "data")   # ← 破坏历史真源！！
  ```

### 3.2 V1.4 修复

- **所有 D 类脚本**统一改为：
  ```python
  from core.config import settings
  OUTPUT_DIR = Path(settings.DOCX_OUTPUT_DIR)  # 即 ${RESUME_DATA_DIR}/output
  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  ```
- `_v13_validation.py._cleanup()` **不再删 backend/data**：
  - 仅清理 `OUTPUT_DIR` 下 `resume_*.docx`；
  - runtime DB / Chroma 不做暴力删除（干净环境请切 RESUME_DATA_DIR）；
  - backend/data/app.db 是历史真源 → 永不主动删。

### 3.3 .gitignore 加固

新增 `backend/.gitignore` 条目防止 **迁移回滚期本地仍保留 backend/data 或 backend/output 时** 被误提交：

- `data/`, `output/`, `*.db`, `*.sqlite*`, `chroma/`, `chroma.sqlite3`
- `*.bad-dir-*`（迁移脚本为错误创建的目录留的备份文件后缀）

---

## 4. T4 结论

| 维度 | 状态 |
|---|---|
| D 类脚本通过敏感内容审查 | ✅ 全部通过（无密钥、无真实 PII、无硬编码绝对路径） |
| 模板资产通过 B 类审查 | ✅ 全部通过；`_build_templates.py` 仍幂等可重构建 |
| 所有验收脚本解耦到 runtime output | ✅ 6/6 修复；**不再写 backend/output/** |
| _cleanup 保护历史真源 backend/data/app.db | ✅ 已移除 rmtree(data_dir)；永不主动删除 |
| .gitignore 补充防误提交 | ✅ 已补 |
