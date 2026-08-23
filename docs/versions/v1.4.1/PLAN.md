# Resume Assistant V1.4.1 对外版本一致性与身份边界清理计划

> 文档角色：已完成的历史补丁版本执行计划
> 状态：ACCEPTED；T1–T5、N1–N4、最终源码验收与发布档案语义收口均已完成；发布 commit 由 annotated tag `v1.4.1` 标识
> 源码基线：公开仓库 commit `8ca7fffda2681a9dde8809460e032e630890bab6`；本 PLAN 的文档提交不改变该源码基线；既有发布标签 `v1.4` 保持不动
> 前置版本：[V1.4.0 RESULT](../v1.4.0/RESULT.md)
> 开发必读：[开发文档入口](../../README.md) → [当前状态](../../CURRENT_STATE.md) → 本 PLAN

## 1. 背景与问题

V1.4.0 发布后，验收 Agent 读取公开源码发现两项工程问题，文档 Agent 已复核：

1. `backend/main.py` 的 FastAPI `version` 和 `GET /` 返回值仍是 `1.3.0`，与公开版本 V1.4.0 不一致；
2. `resume_builder.py` 仍保留从经历文本正则提取姓名、手机和邮箱的 `_extract_profile_from_experiences()`，但主流程实际使用严格的 `ProfileResolver`，该函数未被调用且与 D-019 冲突。

继续检查后发现，`_v13_stub_e2e.py` 仍 patch 上述死函数，并期待“姓名为空 → `PROFILE_INCOMPLETE`”。这同样不符合当前已验收规则：身份字段只来自 request，缺失是合法状态，禁止从经历回填。

这些问题不代表当前主流程已经错误回填身份信息，但会造成公开元数据错误、测试契约过期，并留下未来误用死代码的风险。因此先完成 V1.4.1，再恢复 V1.5.0 架构规划。

## 2. 版本目标

V1.4.1 只做补丁收口：

- 统一公开版本元数据；
- 删除与身份事实边界冲突的死代码；
- 把过期测试改成当前正确的 Profile 来源测试；
- 保持 V1.4.0 的 API、数据、生成流程和运行数据边界不变；
- 修正文档中“README 分层等于隐藏 Agent 痕迹”的错误表达。

## 3. 明确不做

- 不实施 V1.5.0 的事实级检索或内容决策架构；
- 不改变 Experience、VectorIndexJob 或数据库表结构；
- 不改变 JD → RAG → Builder → DOCX 主链路；
- 不新增身份信息 fallback；
- 不要求姓名、电话、邮箱或所在地必须填写；
- 不删除仍被模板兼容路径使用的 `ProfileIncompleteError`；
- 不批量把源码中所有历史 `V1.3.0` 注释替换成 V1.4.1；
- 不移动或覆盖既有 `v1.4` tag。

## 4. 实施方案

本版本包含两项替换型变更，必须按全局规则完成正向、反向和回归验证：

| 变更 | 新状态 / 唯一真源 | 必须退出的旧状态 | 正向验证 | 反向与回归验证 |
|---|---|---|---|---|
| 当前版本元数据 | `backend/core/version.py` 的 `APP_VERSION` | 活动代码中各自维护的当前版本号 | FastAPI、OpenAPI、根接口、Stub 均读取同一值 | 搜索活动代码无另一份当前版本硬编码；历史说明与兼容语义不被误改 |
| 身份事实来源 | request-only `ProfileResolver` | 经历正则提取、DB/AI/模板 fallback、旧函数 patch 和“姓名缺失即失败”的旧测试契约 | request 提供什么就只保留什么，缺失允许为空 | 经历注入虚构身份信息仍不能回填；旧符号与旧 fallback 零残留；核心链路回归通过 |

### T1：版本元数据建立单一真源

新增最小版本常量模块，例如 `backend/core/version.py`：

- `APP_VERSION = "1.4.1"`；
- `main.py` 的 FastAPI `version` 与 `GET /` 响应必须引用同一常量；
- Stub Demo 对外版本显示也引用该常量，避免再次漂移；
- OpenAPI description 改成不易过期的当前能力描述。

以下历史语义必须保留，不做全局替换：

- 某能力在 V1.3.0 首次建立的源码注释；
- `/api/resume/generate` 自 1.3.0 起 deprecated 的兼容说明；
- V1.3.0 验收脚本和历史报告名称。

### T2：删除身份提取死代码

从 `resume_builder.py` 删除：

- `_extract_profile_from_experiences()`；
- `_PHONE_RE`、`_EMAIL_RE`、`_NAME_HINT_RE`；
- 删除后不再使用的 `re` import。

不得改动 `ProfileResolver` 的规则：

- `name/phone/email/location` 只取 `request_profile`；
- 缺失字段保持为空；
- `target_position` 只取当前 JD；
- `summary` 保持为空；
- 经历、DB、AI、模板都不能补齐身份字段。

### T3：修正过期测试

删除 `_v13_stub_e2e.py` 对死函数的 patch，并把旧的“姓名为空必须报错”场景改为身份来源边界测试：

1. 经历 `raw_text` 放入完全虚构的姓名、手机号和邮箱；
2. request 不提供对应字段时，最终 Profile 仍为空；
3. request 只提供电话或邮箱时，只保留明确提供的值；
4. 姓名缺失时核心流程允许成功，不返回 `PROFILE_INCOMPLETE`；
5. `profile_source` 只允许 `request` 或 `empty`。

测试必须同时覆盖 `ProfileResolver` 单元边界和一次 Builder / 核心链路调用，避免只测孤立函数。

### T4：公开 README 与开发档案自然分层

根 README 按正常开源项目方式介绍项目，并自然链接 `docs/` 下的完整开发历史。分层目的是服务不同读者，不是隐藏项目采用人机协作、PLAN/RESULT 或 Agent 验收的事实。

- 根 README 不把内部流程当作普通用户理解和运行项目的前置知识；
- 可以明确说明项目保留了完整人机协作开发档案，并把它作为架构学习和求职展示内容；
- `docs/` 继续完整保留版本计划、结果、决策依据、Agent 分工和验收记录；
- V1.4.1 最终发布时，根 README 的当前代码版本保持为 V1.4.1。

### T5：回归、独立验收与发布

开发 Agent 至少执行：

- `GET /` 与 OpenAPI `info.version` 一致且均为 `1.4.1`；
- `python backend/run_stub_demo.py`；
- 修正后的 `_v13_stub_e2e.py`；
- `python backend/_v14_t7_regression.py --report=<temp-dir>/v141-t7.json`；
- 运行后 `git status` 不出现 runtime 数据；
- 令牌、PII、绝对路径和必要模板跟踪状态复核。

> **高风险，必须安排可读取源码的验收 Agent。**
>
> 原因：T2/T3 涉及身份事实来源和 PII 边界。验收 Agent 必须从 D-019 和本 PLAN 独立推导反向场景，确认整个相关源码范围不存在其他经历/DB/AI/模板身份 fallback，测试确实覆盖“经历中含虚构联系方式也不能回填”的失败路径，并把简短结论和被验收 commit 写入同一份 V1.4.1 RESULT。

### N4：GitHub 版本档案三段式与发布链路同步（最终冻结前追加）

触发原因：GitHub 按名称展示版本目录时，两段式版本号会造成阅读与排序歧义；同时 V1.4.0 仍残留多份分项验收材料，不符合“正式版本只保留 PLAN + RESULT”的长期规则。此次变更不仅影响 Markdown 链接，也会影响忽略规则、交付脚本、脱敏脚本、验收输出位置和最终 manifest，因此必须作为完整替换型变更处理。

文档 Agent 已完成：

1. 历史与候选版本目录统一为三段式：`v1.0.0`、`v1.1.0`、`v1.2.0`、`v1.2.1`、`v1.3.0`、`v1.4.0`、`v1.4.1`、`v1.5.0`、`v3.0.0`；显示版本同步为 `Vx.y.z`。
2. V1.4.0 的审计、迁移、交付、复核、手动发布和 manifest 独有信息合并进 `v1.4.0/RESULT.md`，分项文件及 `validation-artifacts` 运行产物退出版本档案。
3. 两个版本索引、全局文档和根 README 的相对链接同步更新；已发布历史 tag `v1.4` 保持不动。

开发 Agent 必须完成以下源码同步，不得只修改文档或依赖 `.gitignore` 掩盖问题：

1. 全仓库搜索对旧目录 `docs/versions/v1.4/` 及其他被重命名版本目录的活动引用；把 `.gitignore`、交付脚本、路径脱敏脚本、测试与构建配置同步到 `docs/versions/v1.4.0/` 等新路径。历史叙述和已发布 tag 不做无差别替换。
2. 确认 T7 等验收报告默认写入临时目录或 runtime data root，不再创建 `docs/versions/<version>/validation-artifacts/`；删除旧目录后运行验收也不能把它重新生成。
3. 删除或替换对已退出分项文件的读取、写入和链接；Git 跟踪中正式版本目录只能有 `PLAN.md` 与 `RESULT.md`，草稿目录只能有 `DRAFT.md`。
4. 重新构建最终 T8 候选包。不得继续把首轮 `96` 个文件作为固定 PASS 值；以最终 `git ls-files`、manifest 记录数和逐文件 SHA256 三者相等为标准，并把新的实际文件数与 commit 写回 RESULT。
5. 从最终候选包复核必要模板仍被跟踪、runtime/Agent/validation 产物未跟踪、文档相对链接有效、运行 Stub/T7 后源码树不产生档案文件。

> **N4 涉及发布包清单和敏感验收产物边界，需由可读取源码的验收 Agent 做定向复核。**
>
> 验收 Agent 应确认：旧目录活动引用为 0；运行测试不会重建已删除档案目录；正式版本目录结构符合规则；最终 manifest=Git=SHA256；被验收 commit 与拟发布 `v1.4.1` tag 一致。结论写回本版本 RESULT，不创建第三份验收文档。

## 5. 验收标准

- [x] FastAPI `app.version`、OpenAPI `info.version`、`GET /` 和 Stub banner 均为 `1.4.1`；
- [x] 当前版本元数据只维护一处常量；
- [x] `_extract_profile_from_experiences` 和三项正则常量从源码及测试中消失；
- [x] `resume_builder.py` 不再需要 `re`；
- [x] 经历文本中的姓名、手机、邮箱无法进入最终 Profile；
- [x] request 缺失身份字段时保持为空且核心流程成功；
- [x] 求职意向仍只来自当前 JD；
- [x] 旧兼容接口和正确的历史版本说明未被误改；
- [x] Stub、身份边界测试、T7 回归全部通过；
- [x] T1–T3 源码验收结论为通过；
- [x] API、数据库、依赖、DOCX 内容和 runtime 数据隔离无回归；
- [x] 根 README 正常介绍项目并索引完整人机协作开发历史，没有“刻意隐藏开发方式”的表述；
- [x] T1–T3 的功能验收与结构变更验收分别为“通过”；替换型变更具有正向、反向和回归证据；
- [x] 开发验证、源码验收和最终源码实现绑定 commit `317c52660335a9dc35107d4627c25739c8eb4f9f`；验收后的变更仅为验收结论与全局文档回写；
- [x] 验收结论与全局文档已进入纯文档冻结候选 `2b6e8f9`，manifest/Git/SHA256 为 88/88/88；复核发现包内仍含“待冻结”状态文字和两处历史 GitHub 用户名，该候选不作为发布 tag 目标；
- [x] 根 README 已保持最终用户语义；开发档案已收口为稳定发布语义。最终包重新机械冻结并由 `v1.4.1` tag 标识，不再向 RESULT 回填候选自身 SHA；
- [x] 开发 Agent 已创建 `versions/v1.4.1/RESULT.md`，记录 branch、commit、实际变化和验证表；
- [x] 文档显示版本与目录统一为三段式，全部相对链接通过检查；历史 `v1.4` tag 未移动；
- [x] V1.4.0 版本档案只保留 `PLAN.md` 与 `RESULT.md`，分项独有证据已合并；
- [x] 源码、配置、测试和交付脚本中旧版本目录活动引用为 0；
- [x] 运行验收不会重新生成 `docs/versions/<version>/validation-artifacts/` 或其他第三份版本文档；
- [x] 最终 T8 使用新的实际文件数 88，manifest、`git ls-files` 和 SHA256 全部一致；
- [x] N4 源码定向复核通过，并绑定源码验收 commit `317c52660335a9dc35107d4627c25739c8eb4f9f`。

## 6. 文档与发布流程

1. 开发 Agent 按本 PLAN 修改源码和测试，提交待验收 commit，并创建同目录 `RESULT.md`；
2. 验收 Agent 对该 commit 独立复查身份事实边界，将结论和 commit 写入同一 RESULT；
3. 用户完成最小人工验证：Swagger/根接口版本、Stub Demo 和生成链路；
4. 验收后如有相关源码、测试、配置或公开元数据修改，受影响的验证必须针对新 commit 重跑；
5. 文档 Agent 完成 N4 文档收束；开发 Agent 同步源码路径、测试输出和交付清单；验收 Agent 对最终冻结候选做 N4 定向复核；
6. 文档 Agent 确认功能、结构、文档目录和实现标识一致后，更新 `CURRENT_STATE.md`、版本索引和根 README 当前版本；
7. 经用户明确授权后推送公开 `main`，确认最终 tag 可追溯到被验收 commit，再创建新的 annotated tag `v1.4.1`；
8. 不移动 `v1.4`；V1.5.0 草稿在 V1.4.1 最终发布收口后恢复。
