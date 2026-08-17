# V1.4 T8 交付 — 一次性干净首发 worktree 构建记录

> 构建脚本：[backend/_v14_t8_delivery.py](../../../backend/_v14_t8_delivery.py)
> 交付基准目录（三 Agent 统一根）：`<delivery-root>`
> 首发 Git 分支：`main`  |  历史长度 = 1（零旧历史污染）
> 首发 commit SHA 与文件清单以 `<delivery-root>/.t8-manifest.json` 为唯一真源（commit 后基于 `git ls-files` 生成）。

## 1. 交付资产清单（manifest 基准）

manifest JSON 唯一真源：

- `<delivery-root>/.t8-manifest.json`（交付 worktree 根，commit 完成后基于 `git ls-files` 生成）

> 历史上曾在 `<delivery-root>/.t8-manifest.json` 留有副本，因与 Git 实际跟踪清单冲突（C2），已删除；本版仅保留交付根一份。

核心字段（具体数值以构建后 manifest 为准）：

| 字段 | 值 |
|---|---|
| 首发包 Git 跟踪文件数（A 类 + 验收辅助 D 类） | 见 manifest `tracked_file_count` |
| Git 跟踪总字节数 | 见 manifest `tracked_total_bytes` |
| 跳过路径数（C/D/binary/敏感/疑似真实用户上传） | 见 manifest `skipped_count` |
| .git 全新初始化后干净状态（git status --short 为空） | ✅ |
| 开发 worktree .git 文件误拷贝进首发包 | ❌（未发生） |
| `backend/templates/pm_template.docx` 进入 Git 跟踪（B1 修正） | ✅（`git add -f` 强制 + `git ls-files` 二次验证） |
| `backend/pip_freeze_baseline.txt` 不进入首发 Git（C1 修正） | ✅（`requirements.txt` 已是唯一依赖真源） |
| manifest 真源唯一（C2 修正） | ✅（仅 `<delivery-root>/.t8-manifest.json`，基于 post-commit `git ls-files` 生成） |
| .env / .env.local / .env.user 敏感文件 | ❌（已排除） |
| `backend/data/app.db`（C 类 runtime 数据） | ❌（已排除，首发包不应携带任何用户真实数据） |
| `__t8_acceptance_worktree` 俄罗斯套娃目录递归拷贝 | ❌（`_NAME_ALWAYS_EXCLUDE` 拦截，嵌套数 = 0） |

## 2. 交付目录结构（根）

```text
<delivery-root>/
├── .git/                       # 全新 git 仓库，branch=main，commit 仅此一条
├── .t8-manifest.json           # 首发包内 manifest（post-commit 基于 git ls-files 生成）
├── backend/                    # 所有源码 + 验收辅助脚本（_v14_t7_regression / _v14_t3_migrate / run_stub_demo）
│   └── templates/
│       ├── pm_template.json
│       ├── pm_template.docx    # 已进入 Git 跟踪（B1：白名单 + git add -f + ls-files 二次验证）
│       └── _build_templates.py
├── docs/                       # V1.0~V1.4 文档（不含 docs/sources 历史遗留；路径已脱敏 C3）
│   └── versions/v1.4/          # PLAN / RESULT / T1~T9（manifest 真源在交付根 .t8-manifest.json）
├── input/                      # 仅 demo_profile.json / demo_experiences.json / demo_jd.txt（白名单）
├── .gitignore
├── LICENSE
└── README.md
```

## 3. 三 Agent 挂载指令

文档 Agent / 源码验收 Agent / 开发 Agent，三者基准目录统一为：

```text
<delivery-root>
```

> 说明：开发 worktree（`<repo-root>`）仍为开发专用，它本身携带 C 类数据、D 类未归档脚本、.git 真源，任何涉及「版本边界 / 安全审计 / 性能验收 / 发布真源」的复核工作，必须改挂载到上面的交付基准目录。

## 4. 构建脚本已加固的陷阱（打回后的修复项）

1. ✅ `.docx` 误全局排除 → 改为仅排除 `.doc/.pdf/.potx`，并在 `_WHITELIST_RELPATHS` 显式加入 `backend/templates/pm_template.docx`；`init_fresh_git` 中再以 `git add -f` 强制纳入，并用 `git ls-files` 二次验证（B1）。
2. ✅ `__t8_acceptance_worktree` 嵌套递归拷贝（俄罗斯套娃）→ `_NAME_ALWAYS_EXCLUDE` 硬拦截 basename；同时 manifest 中追加 `dest_inside_source_root` 注释字段，提示调用方把 dest 放到开发 worktree 外部最佳。
3. ✅ 前置 `templates/_build_templates.py` 自动执行：若 `pm_template.docx` 缺失则自动构建，保证交付产物永远和 `pm_template.json` 版本一致，避免交付包缺模板导致 T7 CORE-4 红。
4. ✅ `pip_freeze_baseline.txt` 不再打包（C1）：`_FILE_ALWAYS_EXCLUDE_RELPATHS` 显式排除；`init_fresh_git` 中二次验证 `git ls-files` 不含该文件；`requirements.txt` 是唯一公开依赖真源。
5. ✅ manifest 单真源（C2）：删除 `<delivery-root>/.t8-manifest.json`；manifest 在 `git commit` 完成后基于 `git ls-files` 重算，仅写入 `<delivery-root>/.t8-manifest.json`，不再在 `docs/` 下留副本。
6. ✅ 文档路径脱敏（C3）：`backend/_v14_c2c3_path_redact.py` 扫描 `docs/**/*.md` 与 `docs/**/*.json`，将本机路径替换为 `<repo-root>` / `<delivery-root>` / `<worktrees-root>` / `<user-profile>` / `<temp-dir>` / `<old-dev-root>` 等占位符，保留 V1.0–V1.4 完整历史文档；第三轮已将脚本自身改为通用匹配并复验无原用户名/路径字面量。
7. ✅ Agent 与验收产物隔离：`.workbuddy/`、`validation-artifacts/` 同时由 ignore 与 delivery 规则排除；T7 机器可读报告写入临时目录，不污染首发仓库。
