# V2.0.1 RESULT：本地流程可观测性与问题定位

> 当前状态：开发完成，待独立验收
> 当前阶段：T1-T7 已实现并自验，等待独立源码验收（T8）
> 计划与批准日期：2026-08-31
> 开发完成日期：2026-09-01
> 发布基线：`main@e914aaf4cf797048100e3b8e1e0f6ca408817241`，annotated tag `v2.0.0`
> 计划分支：`version/v2.0.1`
> 实现标识：工作区候选（尚未提交冻结 commit，HEAD 为 `7abc69e0fd7265b5295d5bc9d1655e553dc71de5`，即“docs: approve V2.0.1 observability plan”）；冻结 commit SHA 待提交后回填

## 1. 当前实际发生的事

用户已批准 [V2.0.1 PLAN](./PLAN.md)，目标是在现有三页界面和后端服务上增加真实操作阶段、分阶段耗时、资源类型、重试/退避、脱敏日志、刷新后复盘和近期耗时对比。开发 Agent 已按 `T1 → T2/T3 → T4 → T5 → T6 → T7` 完成实现与自验：

- 新增 `backend/core/operations.py` 作为唯一操作可观测性真源（OperationTracker / OperationRecord / StageEvent / 枚举 / 脱敏 / 轮转 / 启动收口 / 近期统计）；

- 生成链、Experience CRUD、提取、迁移、重建、重试全部收束到统一 `tracker.operation`，阶段与事务/回滚事件真实可见；

- 新增固定只读诊断 API 与 409 holder 证据；

- 前端三页接入操作状态轮询、阶段时间线、日志与近期对比；

- 版本元数据统一为 2.0.1，前端已构建通过，V1.5/V2.0 回归通过。

诊断能力贯穿整个 V2 且暂不区分普通用户和开发者（项目未正式上线）。是否在 V2 结束后长期保留，后续另行决定。

## 2. PLAN Task 实际状态

| Task                | 当前状态    | 实际结果                                                                                                                                                                         |
| ------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T1 统一操作、计时与日志机制     | 完成      | `core/operations.py`：OperationRecord/StageEvent/枚举、单调计时、脱敏 JSONL、轮转/启动收口、近期统计、诊断健康                                                                                           |
| T2 生成链打点收束          | 完成      | `resume_generation_service.generate_docx` 迁移检查/就绪/JD 分析/SQL 回读/两层选材/改写/构建/渲染/保存/组装 11 类真实阶段                                                                                  |
| T3 提取、CRUD 与维护写操作打点 | 完成      | `experience_service`（write/reconcile/commit/rollback/rollback 事件）、`migrations`（pre\_check/backup/apply/verify/release）、`embedding_service`（ready\_check/embed\_write/verify） |
| T4 诊断 API 与非阻塞读取    | 完成      | `system.py` 新增 5 个只读/清理接口；`concurrency.current_holder()` 提供 409 holder 证据；非阻塞读取不取门禁                                                                                          |
| T5 现有三页界面接入         | 完成      | `OperationTimeline.tsx`、`useOperation.ts`、types/endpoints/client 更新；三页接入轮询/时间线/日志/近期对比                                                                                       |
| T6 隐私、安全、容量与异常验证    | 完成（适用项） | `_v201_validation.py`：PASS=77 FAIL=0；LLM/Embedding 正向与失败注入需真实 Key 或 Stub，见验证表登记                                                                                              |
| T7 版本、回归、便携包与文档证据   | 部分完成    | 版本元数据、前端 build、V1.5/V2.0 回归、RESULT 均完成；便携包（PyInstaller）尚未构建                                                                                                                  |
| T8 独立源码验收与人工确认      | 未执行     | 尚无冻结候选 commit；需独立验收 Agent                                                                                                                                                    |

依赖主链已走完 `T1 → T2/T3 → T4 → T5 → T6 → T7`。T8 待冻结候选后交独立验收。

## 3. 当前实际全局变化

| 范围     | 当前实际变化                                                                                                                                                                                                                                                                                  |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API    | 新增 `GET /api/system/operations`、`GET /api/system/operations/{operation_id}`、`GET /api/system/logs`、`GET /api/system/diagnostics/{operation_id}`、`DELETE /api/system/logs`；`migrate`/`rebuild`/`retry`/提取/Experience CRUD/`generate-docx` 支持 `X-Operation-ID`（与 `X-Operation-Group-ID`）头 |
| 数据表/模型 | 无（诊断日志走独立 JSONL，不新增业务表）                                                                                                                                                                                                                                                                 |
| 后端模块职责 | 新增 `core/operations.py`（唯一可观测性真源）；`resume_generation_service`/`experience_service`/`migrations`/`embedding_service` 增加 recording 打点；`concurrency` 增加 holder 证据；`errors` 增加 DiagnosticsError 层级                                                                                          |
| 前端行为   | 三页接入操作状态轮询、阶段时间线、日志与近期对比；新增 OperationTimeline/useOperation；API client/types/endpoints 更新                                                                                                                                                                                                |
| 配置/依赖  | 新增 `core/config.py` 的 `DIAGNOSTICS_DIR`；无新增第三方依赖                                                                                                                                                                                                                                        |
| 版本元数据  | `core/version.py` APP\_VERSION=`2.0.1`；`frontend/package.json`/`package-lock.json` 版本 2.0.1                                                                                                                                                                                             |
| 文档     | 建立 V2.0.1 PLAN / RESULT，并同步两个版本索引                                                                                                                                                                                                                                                       |

## 4. 当前验证表

| 验证                 | 状态   | 证据/原因                                                                                                                                                                        |
| ------------------ | ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PLAN 与全局文档规则一致性    | 通过   | 三段式版本；版本目录仅 PLAN / RESULT；计划与实际分离                                                                                                                                            |
| 版本索引与相对链接          | 通过   | 文档建立时检查通过                                                                                                                                                                    |
| 源码实现验证 D1-D20      | 部分通过 | 见下方逐项登记；适用项全部通过，需真实 Key/Stub 项未执行                                                                                                                                            |
| V1.5.0 / V2.0.0 回归 | 通过   | `_v14_t7_regression.py` PASS=12 FAIL=0（SUSPEND=3 为需 ARK Key 的迁移/向量重建）；`_v15_r_rework.py` PASS=48 FAIL=0；`_v20_smoke.py` PASS=20 FAIL=0；`_v2_t5_crud_check.py` PASS=15 FAIL=0 |
| 前端 build           | 通过   | `npm run build`（tsc -b + vite build）成功，48 模块，产物 index-BQ8NVfq6.js 203.03 kB                                                                                                  |
| 便携包                | 未执行  | 尚未构建 PyInstaller 便携包                                                                                                                                                         |
| 隐私与日志反向扫描          | 通过   | `_v201_validation.py` A9：JSONL 无凭据/PII/绝对路径；U1 脱敏单元 8 项全过                                                                                                                    |
| 独立源码验收             | 未执行  | 尚无冻结候选 commit                                                                                                                                                                |

### 4.1 D1-D20 逐项证据（`_v201_validation.py`，PASS=77 FAIL=0）

| #   | 场景                                    | 状态  | 证据                                                                                                      |
| --- | ------------------------------------- | --- | ------------------------------------------------------------------------------------------------------- |
| D1  | 正常生成逐阶段受控慢速 Stub                      | 未执行 | 生成正向需真实 ARK\_API\_KEY 或注入受控 Stub；本轮无 Key 环境未覆盖                                                          |
| D2  | 生成关键阶段注入失败                            | 部分  | A3 提取 fail-closed 负向通过（空文本 422、FAILED、停在 input\_validate）；生成链各阶段注入失败待 Stub                              |
| D3  | LLM/Embedding 慢响应/重试/耗尽               | 未执行 | 需真实 Key 或受控延迟 Stub                                                                                      |
| D4  | Experience create/update/delete 成功    | 部分  | A1 create（experience\_write/tx\_commit 阶段、SUCCEEDED）、A2 delete 通过；update 未单列打点断言                        |
| D5  | reconciliation/失效/commit 分别失败         | 未执行 | 事务语义回归由 `_v15_r_rework.py` 覆盖（PASS=48），但不含 V2.0.1 打点断言                                                  |
| D6  | 批量导入部分失败                              | 未执行 | group 字段（X-Operation-Group-ID）已就绪，本版本无批量导入入口断言                                                          |
| D7  | migrate 正常/备份失败/迁移失败/释放失败             | 部分  | A4 migrate 正常五阶段（pre\_check/backup/apply\_migration/verify/release）通过；备份/释放失败注入待补                       |
| D8  | rebuild/retry 正常/维度/模型超时/部分写入         | 部分  | A5 无 Key 分支 skipped\_no\_key 通过；向量写入正向/失败注入待 Stub                                                       |
| D9  | 长操作占用门禁并并发只读查询                        | 部分  | A8 门禁占用中 `GET /operations` 仍 200；A6 诊断 API 正常；未做真实长 LLM 期间的定时响应测量                                       |
| D10 | 第二个受门禁操作被 409                         | 通过  | A8：409 + OPERATION\_IN\_PROGRESS + holder\_operation\_id + holder + holder\_elapsed\_ms；被拒请求不成为 RUNNING |
| D11 | 刷新/断连/后端继续完成                          | 部分  | U6 从 JSONL 重建脱敏摘要；页面轮询组件实现，浏览器级断连未自动化                                                                   |
| D12 | 阶段中退出并重启收口                            | 通过  | U3：遗留 RUNNING 收口为 INTERRUPTED，seq 恢复递增                                                                  |
| D13 | 系统时间/输入乱序                             | 通过  | A1 阶段 seq 严格递增、耗时非负                                                                                     |
| D14 | 日志 7 天/10 MiB 轮转                      | 通过  | U4：过期旧行被裁剪，保留未过期行                                                                                       |
| D15 | 隐私反向扫描                                | 通过  | U1 脱敏 8 项 + A9 JSONL 反向扫描无凭据/PII/绝对路径                                                                   |
| D16 | 日志目录只读/磁盘满/序列化失败                      | 未执行 | 需文件系统失败注入                                                                                               |
| D17 | 近期同类统计 0/1/20/>20                     | 部分  | U5：样本数 4、中位数 25、最大值 40、不串样本、空返回 0/None；20+ 边界未覆盖                                                        |
| D18 | 诊断非法 UUID/超大 limit/未知筛选/路径穿越          | 通过  | A7：非法 UUID→400、非法 status→400、非法 operation\_type→400、不存在→404；路径穿越由严格 UUID 校验拦截                           |
| D19 | 打点性能开销对照                              | 未执行 | 需同 Stub 下 10 次对照基准                                                                                      |
| D20 | V1.5 全矩阵/V2.0 冒烟/CRUD/安全/前端 build/便携包 | 部分  | 回归四项全过 + 前端 build 通过；便携包未构建，V1.5 需 Key 的迁移/向量重建 SUSPEND                                                 |

## 5. 验收结论

- **功能验收（开发侧自验）：通过。** 统一可观测性、生成链打点、CRUD/维护写操作打点、诊断 API、前端三页接入均已实现并自验通过；`_v201_validation.py` PASS=77 FAIL=0，V1.5/V2.0 回归与前端 build 通过。

- **结构变更验收（开发侧自验）：已完成但不等于独立验收。** tracker 唯一真源、诊断非阻塞读取、并发 holder 证据、事务/回滚语义、版本一致、隐私反向扫描已由开发脚本覆盖；需独立验收 Agent 复核后出具结论。

- **需真实 Key/Stub 的适用项**（D1/D3/D4 全量/D5/D6/D7 负向/D8 正向/D16/D19）在 RESULT 验证表中登记为未执行，未把它们写成已通过。

本版本的当前状态属于“开发完成待独立验收”，开发侧结论不得替代 T8 独立验收。开发完成后按 `§6` 交给未参与实现、自测或修复的独立验收 Agent 执行 T8，再进入人工确认、文档收口和发布决定。

## 6. 下一步交接

1. 提交冻结候选 commit（更新本文“实现标识”）并保持工作区干净；
2. 由独立验收 Agent 执行 T8（PLAN §10 九项复核），分别出具功能验收与结构变更验收结论；
3. 通过后进行人工确认、便携包构建、文档收口和发布决定。

