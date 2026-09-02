# V2.0.1 RESULT：本地流程可观测性与问题定位

> 当前状态：**T8 独立源码验收已通过（2026-09-02），待人工界面确认与发布决定**
> 当前阶段：T1-T7 实现与自验完成；T8 独立源码验收通过，绑定 `9319782`（见 §7）
> 计划与批准日期：2026-08-31
> 开发完成日期：2026-09-01
> 发布基线：`main@e914aaf4cf797048100e3b8e1e0f6ca408817241`，annotated tag `v2.0.0`
> 计划分支：`version/v2.0.1`
> 实现标识：冻结候选 `9319782d5f1a8d5f543e6795f2f024143fa9dbc7`（2026-09-02 20:13:43 +0800，`V2.0.1 T1-T7: implement unified operation observability and diagnostics`）；便携包 `dist/ResumeAssistant/ResumeAssistant.exe`（15,900,563 字节，2026-09-02 20:18，SHA-256 `27aa923dc2489e7b788e87141c577a01c41e9331fc4e11baa6c184a0f793570a`）

## 1. 当前实际发生的事

用户已批准 [V2.0.1 PLAN](./PLAN.md)，目标是在现有三页界面和后端服务上增加真实操作阶段、分阶段耗时、资源类型、重试/退避、脱敏日志、刷新后复盘和近期耗时对比。开发 Agent 已按 `T1 → T2/T3 → T4 → T5 → T6 → T7` 完成实现与自验：

- 新增 `backend/core/operations.py` 作为唯一操作可观测性真源（OperationTracker / OperationRecord / StageEvent / 枚举 / 脱敏 / 轮转 / 启动收口 / 近期统计）；

- 生成链、Experience CRUD、提取、迁移、重建、重试全部收束到统一 `tracker.operation`，阶段与事务/回滚事件真实可见；

- 新增固定只读诊断 API 与 409 holder 证据；

- 前端三页接入操作状态轮询、阶段时间线、日志与近期对比；

- 版本元数据统一为 2.0.1，前端已构建通过，V1.5/V2.0 回归通过。

诊断能力贯穿整个 V2 且暂不区分普通用户和开发者（项目未正式上线）。是否在 V2 结束后长期保留，后续另行决定。

## 2. PLAN Task 实际状态

| Task                | 当前状态      | 实际结果                                                                                                                                                                         |
| ------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T1 统一操作、计时与日志机制     | 完成        | `core/operations.py`：OperationRecord/StageEvent/枚举、单调计时、脱敏 JSONL、轮转/启动收口、近期统计、诊断健康                                                                                           |
| T2 生成链打点收束          | 完成        | `resume_generation_service.generate_docx` 迁移检查/就绪/JD 分析/SQL 回读/两层选材/改写/构建/渲染/保存/组装 11 类真实阶段                                                                                  |
| T3 提取、CRUD 与维护写操作打点 | 完成        | `experience_service`（write/reconcile/commit/rollback/rollback 事件）、`migrations`（pre\_check/backup/apply/verify/release）、`embedding_service`（ready\_check/embed\_write/verify） |
| T4 诊断 API 与非阻塞读取    | 完成        | `system.py` 新增 5 个只读/清理接口；`concurrency.current_holder()` 提供 409 holder 证据；非阻塞读取不取门禁                                                                                          |
| T5 现有三页界面接入         | 完成        | `OperationTimeline.tsx`、`useOperation.ts`、types/endpoints/client 更新；三页接入轮询/时间线/日志/近期对比                                                                                       |
| T6 隐私、安全、容量与异常验证    | 完成（适用项）   | `_v201_validation.py`：PASS=77 FAIL=0；LLM/Embedding 正向与失败注入需真实 Key 或 Stub，见验证表登记                                                                                              |
| T7 版本、回归、便携包与文档证据   | 已完成       | 版本元数据、前端 build（48 模块）、V1.5/V2.0 回归、RESULT 均完成；便携包已于 2026-09-02 20:18 从冻结候选构建（SHA-256 `27aa923d…`，见 §7）                                                                       |
| T8 独立源码验收与人工确认      | 已完成（源码部分） | 独立验收通过并绑定 `9319782`（§7）；人工界面确认待开展                                                                                                                                            |

依赖主链已走完 `T1 → T2/T3 → T4 → T5 → T6 → T7 → T8`。T8 源码部分已由独立验收 Agent 完成并绑定冻结候选。

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

- **结构变更验收（开发侧自验）：已完成但不等于独立验收。** tracker 唯一真源、诊断非阻塞读取、并发 holder 证据、事务/回滚语义、版本一致、隐私反向扫描已由开发脚本覆盖；正式结论见 §7（独立验收 Agent）。

- **需真实 Key/Stub 的适用项**（D1/D3 生成正向、D11 浏览器级断连、D19 性能开销对照）在验证表中登记为未执行/部分，待人工界面确认阶段按需补充；未写成已通过。

## 6. 下一步交接

1. 冻结候选 commit 已提交：`9319782`（更新于本文“实现标识”）；
2. T8 独立源码验收已由独立验收 Agent 完成（§7），功能与结构变更验收结论分别出具；
3. 通过后进行人工界面确认、文档收口和发布决定。

## 7. T8 独立源码验收（验收 Agent）

> 执行角色：验收 Agent；未参与 V2.0.1 候选实现、自测或修复，只读检查
> 绑定对象：`9319782d5f1a8d5f543e6795f2f024143fa9dbc7`（`V2.0.1 T1-T7: implement unified operation observability and diagnostics`，2026-09-02 20:13:43 +0800）
> 验收日期：2026-09-02
> 工作树：新 detached clean 工作树 `resume-assistant-v201-review` @ `9319782`；公开基线 `e914aaf…`（v2.0.0 发布链）是其祖先

### 7.1 PLAN §10 九项复核

| # | 复核项                                                          | 结论                                                                                                                       |
| - | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| 1 | tracker/计时/JSONL 单一机制，无生成与系统双轨                               | ✅ 唯一 `core/operations.py`；生成/提取/CRUD/迁移/重建/重试全部经 `tracker.operation`；响应阶段由 recording 投影，无第二事实源                           |
| 2 | 诊断读取在真实同步长请求期间可响应                                            | ✅ 门禁占用 + 慢操作线程下 `GET /operations` 5ms 响应（独立探针 P4）；内存/文件锁分离，诊断 GET 不取门禁                                                   |
| 3 | Experience commit/rollback、迁移 fail-closed、Embedding 失败未因打点改变 | ✅ 注入 reconciliation 失败 → op FAILED + ROLLED\_BACK + 业务异常传播（不空成功）；migrations 用 finally 补收口不吞异常；回归 48/0                    |
| 4 | 日志写失败不破坏业务、不伪称诊断健康                                           | ✅ 底层文件写失败（IsADirectoryError）→ 业务仍成功 + health DEGRADED（独立探针 P5）                                                           |
| 5 | 日志/API/前端/测试/包无凭据、正文、PII、绝对路径、原始堆栈                           | ✅ `_sanitize_message` 写前白名单（marker→redacted、email/path/phone 替换、500 上限）；`_v201_validation` A9/U1 与独立 JSONL 扫描通过；源码/包扫描干净 |
| 6 | 读取/清理 API 无任意文件、SQL、命令或安全绕过                                  | ✅ 诊断 API 仅 tracker 投影 + UUID/枚举白名单 + limit 上限；DELETE /logs 走统一写安全校验；无路径参数                                                |
| 7 | 刷新、断连、重启、轮转、清理失败、409 冲突负向证据                                  | ✅ 启动收口 INTERRUPTED+seq 恢复（U3）；轮转 7 天/10MiB（U4）；409 holder\_operation\_id/elapsed（探针 P4）；非法 UUID/枚举 → 400                 |
| 8 | 版本元数据、前端类型、同源托管、便携启动一致                                       | ✅ core/package/health 均 2.0.1；前端 build 48 模块通过；便携包从冻结候选构建，前端资产 hash 与工作区一致                                               |
| 9 | V1.5.0 与 V2.0.0 核心回归                                         | ✅ 独立复跑：\_v201 77/0、\_v15\_r\_rework 48/0、\_v20\_smoke 20/0、\_v2\_t5\_crud\_check 15/0、\_v14\_t7 12/0(3 SUSPEND Key 门禁)   |

### 7.2 独立探针（仓库外，覆盖开发侧登记未执行/部分项）

P1 X-Operation-ID 头接受与回传；P2 Experience create → SUCCEEDED + tx\_commit 阶段 + 诊断摘要重建；P3 注入 reconciliation 失败 → FAILED + ROLLED\_BACK + 异常传播（D5）；P4 门禁占用中诊断 <1s（5ms）+ 409 holder\_operation\_id/elapsed\_ms（R1/D9/D10）；P5 日志写失败 → DEGRADED + 业务仍成功 + 恢复后正常（D16）；P6 JSONL 无 Key/正文/Windows 路径/邮箱。**合计 20 PASS / 0 FAIL。**

### 7.3 便携包（T7 收尾证据）

- `dist/ResumeAssistant/ResumeAssistant.exe`：15,900,563 字节，构建时间 2026-09-02 20:18（晚于冻结 commit 20:13），SHA-256 `27aa923dc2489e7b788e87141c577a01c41e9331fc4e11baa6c184a0f793570a`。

- 前端资产绑定：包内 `_internal/frontend/dist` 与工作区 `frontend/dist` 的 `index.html` / `index-BQ8NVfq6.js` / `index-BhYhvUqU.css` 逐文件 SHA-256 完全一致。

- 包内容扫描：无 `.env`、`.db`/`.sqlite`、API Key 字符串、本机绝对路径；验证脚本 `_v201_validation.py` 未混入包内。

### 7.4 最终结论

- **T8 独立源码验收：通过。功能验收：通过。结构变更验收：通过。阻断项 0。**

- 绑定精确候选 `9319782d5f1a8d5f543e6795f2f024143fa9dbc7`；验收后未修改候选源码、测试或构建配置。

- 观察项（非阻断，记录备查）：① 生成链 `embedding_ready` 阶段新增 status\_summary DB 读，若抛错会使本可成功的生成失败（观测/业务耦合，宜评估 fail-open）；② Experience create/update 阶段事件表观“先 COMPLETED、回滚后补 ROLLED\_BACK”，由最终 FAILED 兜底；③ update/delete 未命中 404 记整 op FAILED（诊断噪音，与基线一致）。

- 待办门禁：人工界面确认（T8 后半）、文档收口与发布决定；需真实 Key 的 D1/D3、浏览器级 D11、性能对照 D19 在人工阶段按需补充，不替代本源码验收。

