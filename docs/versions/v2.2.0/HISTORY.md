# V2.2.0 版本历史

> 本文件记录 V2.2.0 内影响计划、技术路线、候选身份或跨角色协作的重要事件。
> 它不是开发范围、当前 Gate 状态或验收结论真源；当前合同以 `PLAN.md`（形成后）为准，实际结果
> 以 `RESULT.md`（形成后）为准。普通 Bug、长日志和逐次命令不写入本文件。

## VH-001 新交付工作流与版本历史机制获批

- 日期：2026-09-11
- 阶段：原 V2.1.1 DRAFT，现已迁移至 V2.2.0 DRAFT
- 触发事实：V2.1.0 在进入独立验收前发生多轮文档打回；PLAN 持续追加后同时包含多条已失效
  技术路线，Development 与 Documentation 之间逐项补漏，无法稳定实现“开发首次正式交付即可
  进入独立验收”的目标。
- 根因：PLAN 缺少用户结果到实施和证据的逐项映射；高风险路线未先通过真实纵切；开发完成声明
  与强制 Gate 没有硬绑定；Documentation 交接审查没有被定义为一次完整的语义一致性检查。
- Product Owner 决定：
  1. V2.2.0 起，版本目录增加 `HISTORY.md` 保存重要演进历史；具有跨版本价值的结论再提炼到
     `DECISIONS.md` 或 `HUMAN_AI_WORKFLOW.md`。
  2. `PLAN.md` 只保存当前唯一有效、可独立执行的合同。开发轮次不等于 PLAN Revision；只有产品
     范围、技术路线、Design Baseline 或强制验收合同实质变化时才形成新 Revision。
  3. 开发正式交付必须提供 `PLAN ID → 用户要求/产品结果 → 开发理解 → 实际交付 → 证据 → 偏差`
     映射，并在开发负责的强制 Gate 全部完成后才能声明 Ready For Review。
  4. Documentation Agent 的交接职责是依据 PLAN 与 RESULT 核对开发声明是否完整、内部一致，以及
     开发是否正确理解用户和 PLAN 要求；不能缩减为机械验签，也不替代 Acceptance Agent 的源码
     正确性验证。
  5. Documentation Agent 对一个完整交付执行一次集中审查，只能给出 `DOC_ALIGNED`、
     `DOC_RETURNED` 或 `PLAN_REVISION_REQUIRED`；不得发现一个问题就结束整轮并串行打回。
- 影响：上述机制随草稿迁移至 V2.2.0，并作为 V2.2.0 正式 PLAN 必须继承的工作流基线；不反向
  修改 V2.1.0 的 PLAN、候选或验收合同。
- 全局提炼：D-040；`docs/HUMAN_AI_WORKFLOW.md` 的 PLAN 修订、交付与文档审查规则。

## VH-002 文档交接与源码验收边界澄清

- 日期：2026-09-12
- 阶段：原 V2.1.1 DRAFT，现已迁移至 V2.2.0 DRAFT
- 触发事实：H8 开发交付后，Documentation Agent 因“语义交付审查”的表述过宽，直接读取源码和
  原始运行证据并自行作出源码级打回判断。Product Owner 指出该行为越过文档交接边界；该轮不按
  此判断处置。
- 根因：现行规则一方面规定 Documentation Agent 不读取源码，另一方面又要求其判断“实际技术路线
  是否符合、旧路线是否退出”，没有明确区分“RESULT 中的开发声明”与“真实源码事实”。在上下文
  压缩或交接信息不足时，宽泛措辞容易被错误解释为源码审查授权。
- Product Owner 澄清：
  1. 文档 Agent 应在 PLAN 中提前定义 RESULT 的交付内容和格式；
  2. 开发 Agent 用 RESULT 逐项说明理解、实际交付、开发验证、证据入口和偏差；
  3. 文档 Agent 依据 RESULT、机械身份和证据入口判断文档是否完整、内部一致及理解是否符合 PLAN，
     不读取源码、测试实现或原始日志独立判断代码正确性；
  4. RESULT 缺少开发本应提交的字段、自测或证据时退回开发；只有源码和运行验证才能确定的真实性
     问题写入“待独立验收问题”，由 Acceptance Agent 补足；
  5. `DOC_ALIGNED` 只表示 RESULT 已具备进入独立验收的条件，不代表实现已经通过。
- 影响：V2.2.0 正式 PLAN 必须包含 `RESULT Delivery Contract`，RESULT 模板必须包含“待独立验收
  问题”；D-040 与全局工作流按上述边界修正，并增加上下文压缩或任务恢复后的角色边界重读门禁。
  V2.1.0 的既有 PLAN、候选和本轮 H8 处置不追溯改变。
- 全局提炼：D-040；`docs/HUMAN_AI_WORKFLOW.md` 的角色、RESULT、交接与验收规则。

## VH-003 功能草稿升版并确定渐进生成技术方向

- 日期：2026-09-12
- 阶段：V2.2.0 DRAFT
- 触发事实：原 V2.1.1 草稿从单一的工作台跨路由状态保持，扩展到浏览器页面生命周期下的任务
  重新识别、JD/召回/润色全过程渐进输出、生成性能优化和经历级并行，已经不再属于补丁版本。
- Product Owner 决定：
  1. 原 V2.1.1 功能草稿整体提升为 V2.2.0；V2.1.1 仅保留给 V2.1.0 的必要紧急修复；
  2. 浏览器刷新或页面重开不得导致用户看不到仍在运行的后台任务，但 V2 不建设关闭整个应用、
     后端退出、崩溃或系统重启后的任务续跑；完整持久任务留给 V3；
  3. P1 JD 分析、P2 Fact 召回、P3 经历润色和 P4 产物生成均可提供真实渐进状态；旧阶段可点击
     回看，断线重连不得重复调用；
  4. P3 按经历分组并执行有界并行，例如两个实习或实习与项目可以同时生成；同一经历内不继续
     拆分并发。完整 Fact 校验后再写入预览，选择理由可以逐字渐进显示；
  5. 最终产物路线保持 ResumeDocument→DOCX→Microsoft Word COM→PDF；渐进 HTML 不成为第二
     最终产物真源；
  6. 性能优化与流式体验一并进入草稿，正式 PLAN 必须以真实分阶段基线冻结并发、调用次数、延迟
     和质量不退化门禁。
- 影响：草稿目录、版本索引以及 D-040/全局工作流的首次生效版本统一迁移至 V2.2.0。当前仍处于
  需求收集阶段，不形成 PLAN、不授权开发，也不提前固定尚未完成真实纵切验证的流式协议。

## VH-004 任务连续性、流式状态与性能边界获批

- 日期：2026-09-13
- 阶段：V2.2.0 DRAFT
- 触发事实：渐进输出不仅涉及页面动画，还涉及刷新后的任务恢复、未提交身份/JD 草稿、取消后立即
  开始新任务、经历并行、调用计数和最终产物一致性。若不先冻结状态真源与任务身份，开发容易把
  “流式”实现成只存在于当前 React 内存中的视觉效果，刷新后丢进度或把旧任务结果写入新任务。
- Product Owner 决定：
  1. 引入顶层 `task_id`，贯穿身份/JD 草稿、上传解析、生成 operation、经历子任务、
     ResumeRevision 和 artifact；点击生成时原子冻结 `input_revision`。
  2. V2.2.0 使用后端临时任务草稿作为状态真源。姓名必填，电话、邮箱、所在地选填；这些字段只来自
     生成前“身份摘要”表单。每个新任务重新填写，不建立持久 Profile；同一任务中已保存的身份和 JD
     可在浏览器刷新或页面重开后恢复。活动任务在当前后端运行期间不定时清理；未活动草稿及
     `FAILED/CANCELLED` 临时状态保留 24 小时；成功工作台状态保留到开始新任务，已发布最终简历不随
     临时状态清理。提供主动清除草稿入口。关闭整个应用或后端后的恢复仍不属于 V2 范围。
  3. 取消必须真实停止本产品可控的排队任务、事件发布和产物提交，关闭当前 Provider 流、终止自有
     Word worker，并用 task/revision fence 丢弃迟到结果；释放活动槽后允许立即创建新任务。第三方
     Provider 已接收请求后的内部计算或计费不承诺可取消。
  4. 渐进输出采用“权威状态/完成结果/当前展示快照持久化 + SSE 增量传输”。逐字或逐 token delta
     不逐条写入数据库；断线后先取权威快照，再从新序号继续。历史阶段回看最终业务结果，不回放动画；
     只输出面向用户的选材理由，不暴露模型思维链。
  5. P3 以单个经历为并行单元，V2.2.0 最大并发固定为 2；同一经历内部串行，跨经历共享同一 JD、
     风格和事实约束。正常逻辑调用预算为 1 次 JD 分析加 N 次已选经历生成，SDK HTTP 重试另行计数。
  6. 润色标题、正文、技能与选择理由只属于当前 ResumeRevision/ResumeDocument，不回写或替换
     Career Memory 的 Experience/Fact；简历导入查重整体延期到后续专项版本。
  7. 性能先用脱敏短/典型/长样例分别测冷启动与热启动，各做 3 次真实模型运行，报告中位数和最大值；
     同时记录首个真实状态、首个 JD 条目、首个召回 Fact、首个完成 Fact、P1-P4、总时长、排队、
     Provider、逻辑调用/HTTP attempt、token/成本、重试与取消耗时。确定性 fixture 只做高频回归，
     不能替代真实模型 E2E；最终阈值在基线后由 Product Owner 批准。
  8. 新工作流在实行前可先写入 DRAFT/HISTORY；形成正式 PLAN 时，把跨版本规则一次性提炼到全局
     文档，PLAN 只保留本版本开发合同和必要引用，HISTORY 保留演进事实，避免形成第二套工作流或把
     历史材料全部塞给开发。
- 影响：以上决定是正式 PLAN 必须转写的产品和技术边界；当前仍为需求草稿，不授权源码开发。任务
  物理容量上限、目标模型及真实性能阈值仍需通过 schema 估算和真实基线后冻结。
- 全局提炼：第 8 项在形成 V2.2.0 正式 PLAN 时迁移；其余产品/技术选择是否具有跨版本价值，在该次
  迁移审查中决定，不在草稿阶段提前制造重复规范。

- 收口状态：Product Owner 于 2026-09-13 表示主要需求已基本提出，并认可上述保留/清理默认方案、
  性能基线办法和“范围复述 → Design Snapshot → 基线与最小纵切 → 正式 PLAN”的顺序。当前进入
  集中收口但尚未正式范围冻结，因此仍不授权 Development Agent 修改产品源码。

## VH-005 以用户目标而非既定方案冻结 V2.2.0 范围

- 日期：2026-09-13
- 阶段：V2.2.0 DRAFT → 范围基线冻结
- 触发事实：Product Owner 确认第 4 节范围清单没有遗漏，同时指出最新工作流中的“冻结”不能被解释
  为任何情况下都不允许改变；产品开发必须以目标达成为中心，证据证明路线不合适时应主动修正。
- Product Owner 决定：
  1. 冻结用户目标、可观察结果、事实/安全边界、明确不做项和既有回归不变量；
  2. 普通实现细节在不改变上述基线时允许由开发调整，不为每个代码选择制造 PLAN Revision；
  3. 技术路线若难以稳定达到目标，任何角色必须发起 Architecture Challenge，先暂停受影响实现，
     再用证据比较替代路线；“范围已冻结”、已有投入和时间紧迫都不能成为继续错误路线的理由；
  4. 不允许借路线调整静默缩小用户目标、改变可见交互或降低强制 Gate。涉及这些实质变化时，必须
     形成变化摘要或 PLAN Revision 并重新取得 Product Owner 批准；
  5. PLAN 前的证据变化回写 DRAFT/HISTORY；PLAN 后保持一份完整当前 PLAN，通过 Revision 取代旧版。
- 影响：V2.2.0 范围收集结束，进入 Design Snapshot、真实性能基线、SSE/并发最小纵切和正式 PLAN
  准备；本次范围冻结本身仍不构成产品源码开发授权。
- 全局提炼：形成正式 PLAN 时，将“目标导向冻结＋路线可挑战＋目标变化须批准”提炼到
  `docs/HUMAN_AI_WORKFLOW.md`，PLAN 仅引用并定义本版具体 Challenge 决策点。

## VH-006 Design 与开发前技术证据并行，产品实施分两批授权

- 日期：2026-09-13
- 阶段：V2.2.0 PLAN 准备
- 触发事实：D-003 设计工作稿已经形成多状态与多视口阶段性证据，但最终 Design Snapshot 尚未冻结；
  同时，性能基线、SSE 恢复、真实流式边界、经历并发 2、字段断点和任务容量均不依赖最终视觉布局。
  Product Owner 要求先推进不相干工作，待设计完成后再进行设计相关的第二批开发。
- Product Owner 决定：
  1. Design 轨与开发前技术证据轨并行；后者由 Development Evidence Agent 执行，不属于独立验收；
  2. 技术证据轨不得修改正式产品候选、冻结候选或写发布结论；
  3. 证据完成后可以先形成只授权设计无关工作的完整 PLAN Revision 1；未获批准前仍无产品源码
     开发授权；
  4. Design Snapshot 获批后形成完整 Revision 2 并取代 Revision 1，绑定 `DS-xxx` 后授权设计相关
     实现与最终集成；这两批是预先批准的依赖拆分，不记为返工轮次；
  5. 两批产品源码仍由同一 Development Integrator 负责；Acceptance Agent 只在冻结候选后启动。
- 固定开发基线：正式 tag `v2.1.0`，commit `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`。
- 全局提炼：分批 PLAN、Design Gate 与角色边界已同步至 `docs/HUMAN_AI_WORKFLOW.md`，长期选择登记为
  `D-041`。

## VH-007 开发前证据否定单流路线并形成两阶段候选

- 日期：2026-09-13
- 阶段：V2.2.0 PLAN 准备
- 触发事实：技术证据轨完成真实模型、短/典型/长基线、首个 Fact、两阶段 reason、并发 2、字段链和
  容量测量。当前 V2.1.0 从点击到首个完整 Fact 为 50.57～114.24 秒，无法达到候选 15 秒目标；把
  Fact 与 reason 放在一次复杂结构化流中只有 1/3 能稳定绑定，且 reason 不是所需的旁侧逐字输出。
- 证据结论：
  1. `deepseek-v4-pro-ga-260813 + reasoning_effort=minimal` 的结构化 Fact 探针 3/3 通过；
  2. “紧凑 JD → 本地召回重叠 → Fact 结构化流 → 独立 reason 文本流”的点击零点首 Fact 为
     12.26 / 12.86 / 13.02 秒，3/3 达到 15 秒候选目标；
  3. 经历级并发 2 相对串行有明显延迟收益；并发 3 未测试且继续排除；
  4. 短样例 cold 4/4、warm 3/3 均暴露既有 `TemplateRenderer.render` 错误，成为 V2.2.0 正确性
     阻断，不纳入成功耗时统计；
  5. 长任务临时状态峰值约 26.9 KiB，活动任务和已发布 artifact 保护测试 0 违规。
- 路线处置：证据已否定“单次复杂结构化流同时输出 Fact 与 reason”，推荐按经历两阶段；P1/P2 发布
  完成并校验的结构化业务项，P3 的 Fact 整条进入预览，reason 才使用绑定 `fact_id` 的真实文本增量。
  断流不得撤销已完成 Fact，使用完整 reason 补偿事件或明确失败态。
- 文档处置：DRAFT §4.6 已记录证据和参数歧义修正。正式 PLAN 不得直接照抄原建议中的模糊 retry、
  Token、页面离开清理或 artifact 引用表述；应把 LLM/Embedding 计数、每 attempt/每任务 Token、清理
  触发点和单活动任务约束分别冻结。
- 当前状态：技术证据轨完成；候选性能、Token/调用、容量与保留参数等待 Product Owner 一次批准。
  该事件不构成产品源码开发或验收完成。

## VH-008 参数边界获批，反思机制迁入全局

- 日期：2026-09-13
- 阶段：V2.2.0 PLAN Revision 1 准备
- Product Owner 决定：批准 VH-007 的两阶段路线、15 秒首 Fact、同样例总耗时中位数降低 25%、
  经历并发 2、调用/重试、Token 总预算、任务容量与保留边界；紧凑 JD 的 1024 completion tokens 是
  默认值，允许开发在 512～2048 内用证据调整，不是不可变常量。
- 边界澄清：原始 JD 输入与结构化 JD 输出是两种容量；不得因输出上限静默截断用户 JD。允许区间内
  调参不产生 PLAN Revision，但超出区间、降低性能目标、增加逻辑调用或任务总预算必须发起
  Architecture Challenge。
- 全局迁移：DRAFT §3.8 的长期反思规则已经提炼到 `docs/HUMAN_AI_WORKFLOW.md` §3.4，并登记
  `DECISIONS.md` D-042；开发不需要读取 DRAFT 才能获得 Pre-mortem、Architecture Check、
  Falsification Check、证据等级和 `CHALLENGE_OPEN` 规则。
- 下一步：形成只授权设计无关实现的完整 PLAN Revision 1；Design Snapshot 获批后再由 Revision 2
  取代，导入设计并授权可见布局与最终集成。

## VH-009 修复“规则已存在但新 Agent 不可发现”的阅读入口

- 日期：2026-09-13
- 阶段：V2.2.0 PLAN Revision 1 审阅
- 触发事实：Product Owner 指出 Development 的既有默认路径为 `docs/README → CURRENT_STATE →
  PLAN → 源码`，而新迁入的反思机制位于 `HUMAN_AI_WORKFLOW.md`；该文件头又写着“不进入开发
  Agent 默认上下文”。即使 PLAN 正文引用 §3.4，新 Agent 仍可能不知道哪些全局章节是强制输入。
- 根因：文档拥有权与可发现性被分开维护，只完成了“规则落盘”，没有同时更新从唯一开发入口出发的
  角色路由；这是入口合同缺口，不是开发 Agent 的阅读疏忽。
- 修正：`docs/README.md` 新增 §0 Agent 执行入口；`HUMAN_AI_WORKFLOW.md` 明确“不全文默认读取”
  不等于“不读取 PLAN 点名章节”；V2.2.0 PLAN 顶部新增 Required Reading，精确列出开发必须重读的
  权限、冻结、反思、开发职责和上下文控制章节。
- 防复发：以后新增或迁移全局工作流规则时，Documentation Agent 必须同时检查三个入口：
  `docs/README` 的角色路由、当前 PLAN 的 Required Reading、目标全局文件自己的阅读说明。只改规则
  正文而未更新入口，文档 Gate 不得判为完成。

## VH-010 PLAN Revision 1 获 Product Owner 批准

- 日期：2026-09-13
- 阶段：V2.2.0 PLAN Revision 1 → 第一批开发授权
- Product Owner 决定：批准 V2.2.0 Revision 1 的产品目标、两阶段流式路线、经历并发 2、任务连续性、
  实际取消、性能/Token/容量边界、内容修正和 RESULT Delivery Contract；授权范围仍限于设计无关第一批。
- 批准范围：紧凑 JD 输出默认 1024 completion tokens，允许在 512～2048 内由证据调节；正常 LLM
  调用按最终 Fact 数量 `F` 计算为 `1 + 2F`；Fact/reason 两阶段、Embedding 单独计数；超出授权区间或改变
  产品目标、调用/总预算、Design Gate 或强制验收合同必须发起 Architecture Challenge。
- 身份：用户批准的合同内容基线为前一提交 `50c4f23` 中的 PLAN blob `55624b0051e5079d96314f082ce820ffdb03b9f1`；本次
  收口只把状态标为“已批准”、移除活动 DRAFT 入口并更新索引，不改变合同语义。正式收口提交为
  `d4fc641431acf247b2ebb467c63091b56a415fb2`，当前 PLAN blob 为
  `324302a0ef6d81214c752d12281c221f2550f320`。
- 下一步：将批准的 PLAN 同步到固定开发路径 `<current-workspace>`，切换活动版本分支；开发必须先完成
  Required Reading、Pre-mortem 和 T01，再开始源码实现。

## VH-011 Revision 1 开发交接完成语义核对

- 日期：2026-09-15
- 阶段：V2.2.0 Revision 1 开发交接
- 事实：Revision 1 开发候选冻结为 `09ee23651161afe7dc24f2e839618f49213e4217`，工作区 clean，
  approved PLAN blob 为 `324302a0ef6d81214c752d12281c221f2550f320`。真实模型六格性能矩阵中首个
  完整 Fact 的各格最大值均不超过 15 秒；有 V2.1.0 基线的 typical/long cold/warm 总耗时中位数
  均降低至少 25%；short cold/warm 全部成功。
- 文档核对：Documentation Agent 依据 PLAN、RESULT、机械身份与证据入口完成集中语义审查，直接
  修正 RESULT 中的状态、时态、证据映射、checkpoint 身份和下一门禁等文档问题；结论为
  `DOC_ALIGNED`，文档提交为 `e4f9e499d1013fd03bf150bd9f50c8476cd01cbb`，未要求 Development Agent
  为文档措辞再次返工。
- 边界纠正：Revision 1 的批准合同要求 clean onedir 重建与隔离启动，但没有要求该批在最终包内再次
  完成真实模型纵切；该纵切属于 Revision 2 最终候选门禁。Documentation Agent 不得把后续批次门禁
  倒灌为前批开发返工项。以后发现交接文档可由文档角色确定修正且不改变候选事实时，由文档角色一次
  收口；只有产品实现、证据真实性或身份本身不满足合同才集中打回开发。

## VH-012 D-003 获批并导入为 DS-003

- 日期：2026-09-15
- 阶段：V2.2.0 Design Gate → PLAN Revision 2 准备
- Product Owner 决定：批准 Design Snapshot `D-003`，以主题 A 和四步连续任务工作台作为 V2.2.0
  Revision 2 的可见设计基线。
- 导入：源 `<design-workspace>/snapshots/D-003` 按原始字节导入
  `docs/design/baselines/V2.2.0/DS-003`；共 28 个文件，源 `CHECKSUMS.sha256` 的 SHA-256 为
  `cc699466af400ee603a7e9fe39ef22e75bc7db37bd7150f41a0f0718ac9d0a61`，manifest 登记的 27 个
  文件全部校验通过，源与 canonical 逐文件对照 mismatch=0。
- 范围：Snapshot 中的生产主题 A、四步状态、过程 Fact/reason、最终 PDF 预览、头像菜单与参考页面
  进入 Revision 2 取舍输入；评审工具、主题切换、fixture 和自然语言修改等 Design-only 能力不得因
  原型可点击而自动进入产品。

## VH-013 PLAN Revision 2 草案形成

- 日期：2026-09-15
- 阶段：V2.2.0 PLAN Revision 2 待批准
- 目的：Revision 2 取代 Revision 1 的执行合同，绑定 `DS-003`，只授权可见界面、真实能力映射、
  最终集成和候选冻结；复用 Revision 1 已完成的单一 Task/SSE/生成/artifact 链，不另建双真源。
- 门禁强化：最终开发候选必须从 clean 源码重建 onedir，并在隔离 runtime 使用真实模型跑通输入、
  P1～P4、PDF.js viewer 与 Word/PDF 双下载；该项出现 FAIL、NOT_RUN 或环境阻断时不得形成 H2，
  不得转交独立验收代跑。
- 当前状态：草案已形成但尚未获得 Product Owner 批准，不授权 Revision 2 产品源码开发；批准后登记
  approved commit/PLAN blob 并同步固定开发路径。
