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

## VH-014 PLAN Revision 2 获 Product Owner 批准

- 日期：2026-09-15
- 阶段：V2.2.0 PLAN Revision 2 → 第二批开发授权
- Product Owner 决定：批准 Revision 2 的完整当前合同，包括 `DS-003` 实施矩阵、过程 HTML 与最终
  PDF 的真源边界、路由/刷新连续性、实际取消、P1～P4 渐进体验、真实能力映射、七视口设计门禁、
  最终包真实模型纵切和 RESULT Delivery Contract。
- 批准内容身份：commit `af2f8f9bc193fbe78e77e5d6009b5ad7836d6f3e`，PLAN blob
  `7104bfbd430cefb66cfc29bb92520c2ff65aeaff`。批准后只修改批准状态、活动开发入口与本条历史，
  不改变 Product Owner 审阅的合同正文。
- Design 身份：源 `D-003` → canonical `DS-003`；入口 `prototype/index.html`；manifest SHA-256
  `cc699466af400ee603a7e9fe39ef22e75bc7db37bd7150f41a0f0718ac9d0a61`；28 个文件；导入对照
  mismatch=0。
- 授权边界：Revision 2 立即取代 Revision 1 成为唯一有效开发合同。Development Agent 必须从
  `docs/README.md` 的固定角色入口读取 Required Reading 和 `DS-003`，在 current 的
  `version/v2.2.0` 上继续；不得跟随 Design 工作稿，也不得把最终包真实纵切转给独立验收代跑。
- 批准收口 commit：`e3c68ac7405abe3a70e807b22d51a25ddb80731f`；当前已批准 PLAN blob：
  `e134703ce6e37a2f4d5df389662119f38638fae8`。

## VH-015 Revision 2 候选完成独立验收，发现发布版本元数据阻断

- 日期：2026-09-19
- 阶段：V2.2.0 Revision 2 独立验收 → 待发布前处置
- 候选身份：`3e156bc8abb3c3747c08c4260ca4e0d88292c4a0`；批准 PLAN blob
  `e134703ce6e37a2f4d5df389662119f38638fae8`；Documentation Gate 为 `DOC_ALIGNED`。
- 验收过程：首轮静态审计通过，但因最终包、真实模型凭据和 GUI/Word 环境不可用而
  `ACCEPTANCE_BLOCKED`。环境解除后，同一独立 Acceptance Agent 在同一候选上补齐最终包身份、真实模型
  纵切、PDF.js/双下载、七视口、Word COM 与 Integration/Release Gate，最终结论为
  `ACCEPTANCE_PASS`；验收前后 review HEAD 未变化且 clean。
- 验收事实：最终包为 4045 files / 170,356,413 B；EXE SHA-256
  `9E6DF063E6056E7847A6FF78F4207BD903CD4A23CA97ACB40EF0D56841FAF9C6`；真实模型 P1→P4
  `SUCCEEDED`；viewer 与下载 PDF 同源；Word/PDF 双下载、七视口和进程清理均通过。
- 发布阻断：最终包对外版本元数据仍报告 `2.1.0`。该字段由 `core.version.APP_VERSION` 提供并进入产品包；
  若改为 `2.2.0`，属于验收后入包源码/可执行元数据变化，当前验收按工作流自动失效。不得把版本 bump 当作
  纯文档发布动作，也不得在当前包上继续人工验收或发布。
- 下一步：由 Development Agent 在原 PLAN 范围内完成版本元数据单点修正、受影响回归与 clean onedir
  重建，冻结新候选；Documentation Agent 重新完成机械接收，独立 Acceptance Agent 对新包复验。无需修改
  PLAN，也不更新 CURRENT_STATE、版本索引、根 README、远端 main 或正式 tag。

## VH-016 版本元数据候选冻结，旧验收结论不继承

- 日期：2026-09-19
- 阶段：V2.2.0 Revision 2 发布阻断处置 → 新候选待独立复验
- 开发交付：Development Agent 将 `core.version.APP_VERSION` 从 2.1.0 改为 2.2.0，并同步两个受影响
  版本断言；未改变 PLAN、产品功能、全局文档或冻结设计。版本元数据源码提交为
  `a2f4f3a3325b46624f05ede48022b06c192903ed`，最终开发侧 RESULT 候选为
  `be59acd268dcfe88ba19fa02be2e12c62d476d77`，父链为 `be59acd → a2f4f3a → 3e156bc`。
- 新包身份：4045 files / 170,356,336 B；EXE SHA-256
  `4C66F8B9464FF9835AB13E0AE22BCDE2BF7F5A5AA00EC2A3BC45BB232782156C`；开发侧报告版本端点均为
  2.2.0，precheck、包审计和真实模型最终纵切 exit 0。
- 身份影响：旧 §R2-12 的 `ACCEPTANCE_PASS` 只绑定 `3e156bc`，因入包源码与可执行元数据变化而不再
  覆盖当前发布候选。该事件不改变 Revision 2 产品范围、技术路线、Design Baseline 或强制验收合同，
  因此无需 PLAN Revision。
- 文档收口：Documentation Agent 在 canonical 保护本地候选引用
  `candidates/v2.2.0/be59acd`，一次性修正 RESULT 顶部身份、章节编号、源码/完整 diff 与包身份；
  Documentation Gate 为 `DOC_ALIGNED`，不把开发自测升级为独立验收。
- 验收准备：精确新包与三份开发证据已复制到独立验收暂存区并复核 hash；固定 review 已 detached 到
  `be59acd`，PLAN blob 一致且 tracked/index clean。
- 下一步：由未参与实现、自测或修复的 Acceptance Agent 对精确候选与精确新包完成独立复验。复验通过
  前不进行 Product Owner 人工验收、全局文档收口或发布。

## VH-017 版本元数据新候选完成独立复验

- 日期：2026-09-19
- 阶段：V2.2.0 Revision 2 新候选独立复验 → 待 Product Owner 人工验收
- 验收对象：`be59acd268dcfe88ba19fa02be2e12c62d476d77`；批准 PLAN blob
  `e134703ce6e37a2f4d5df389662119f38638fae8`；精确包 4045 files / 170,356,336 B，EXE SHA-256
  `4C66F8B9464FF9835AB13E0AE22BCDE2BF7F5A5AA00EC2A3BC45BB232782156C`。
- 独立结论：Acceptance Agent 未参与候选实现、自测、修复或开发结论编写；静态单一版本真源检查、
  受影响回归、precheck、包审计、隔离版本端点、真实模型 P1→P4、PDF.js/双下载、七视口和进程清理
  全部完成，无 `FAIL/NOT_RUN`，最终结论为 `ACCEPTANCE_PASS`。
- cleanup 纠正：首份验收报告称临时副本和工作目录已清理，但 Documentation Agent 机械复核发现
  `_acc_src` 与 `_acc_work` 仍在，因此没有直接采纳 PASS。Acceptance Agent 随后仅清理这两个已核定
  临时目录；文档侧复核确认目录已不存在、封存包与证据 hash 未变、review 仍 detached 同一候选且
  clean、相关进程无残留。该纠正不改变候选或包，不需要重复功能验收。
- 下一步：Product Owner 使用同一精确包完成人工验收。人工验收通过前不更新 CURRENT_STATE、版本索引、
  根 README，不将候选纳入 canonical 本地 main，也不操作远端 main 或正式 tag。

## VH-018 Product Owner 因 Design Fidelity 打回 V2.2.0

- 日期：2026-09-19
- 阶段：V2.2.0 Product Owner 人工验收 → 打回开发
- 决定：Product Owner 明确打回 `be59acd`。候选的页面壳、信息层级、P4/成功页、我的经历、我的简历、
  个人与隐私以及窄屏回流未按冻结 HTML / `DS-003` Theme A 一比一还原，偏差规模超过可接受视觉误差。
- 边界：独立 `ACCEPTANCE_PASS` 只说明已执行的技术、产物与运行门禁通过，不替代 Product Owner 体验
  验收。RESULT 当前状态改为“需修正”，候选不可发布。
- 分类：自然语言修改/“开始编辑”、单 Fact 重生成/锁定、主题切换、评审批注等仍按 PLAN 保持
  `HIDDEN` 或 Design-only；除此之外，Task/SSE、Career Memory、记录、PDF.js 和下载链已经存在，相关
  页面差异均按开发呈现错误处理，不得以技术模块缺失为理由保留。
- 归档：实际差异与当前门禁收录在 RESULT §R2-16；本 HISTORY 只保留候选被打回这一重要事件。此次
  未改变产品范围、技术路线、Design Baseline 或强制验收合同，不触发 PLAN Revision，也不新增执行文档。
- 下一步：Development Agent 继续执行同一 PLAN Revision 2。产品代码或入包文件变化后按 PLAN §9 冻结
  新候选并重新验收；此前不更新 CURRENT_STATE 或发布入口。

## VH-019 `ac36edf` 未通过 Documentation Gate

- 日期：2026-09-22
- 阶段：V2.2.0 Design Fidelity 返工 → Documentation Gate
- 交付身份：实际开发候选为 `ac36edf49e4f0e0331781e86d5e9cc6b5e42956d`，唯一 parent 为
  `d5449d6090e7a71f49a9aa28d14367a167490bde`；现场包为 4045 files / 170,356,136 B，EXE SHA-256
  `EE106DBCCE994F75EB5EDFDB75B6FA7EBA2A0B4F2C18FB53899FAE8BFF4E483D`。
- 失效原因：RESULT 记录了错误的完整 commit 身份；新候选未交付 §7.4 强制的前端 type/build/Hooks、
  clean 重建和六格真实性能完整重跑；Design Fidelity 证据未形成所声明的 failed 与 P1～P3 状态；
  failure matrix 的两个证据入口给出互相冲突的 PASS/FAIL 结论。
- 门禁影响：Documentation Agent 结论为 `DOC_RETURNED`，PLAN Revision 2 不变。该候选未被保护，固定
  `review` 继续保持旧候选 `be59acd`，不得进入独立验收、人工验收、CURRENT_STATE 收口或发布。
- 当前执行缺口以 RESULT §R2-20 为准；本 HISTORY 只记录候选失效事件，不构成开发指令。

## VH-020 `bfcab15` 通过 Documentation Gate

- 日期：2026-09-22
- 阶段：V2.2.0 Design Fidelity 二次返工 → 独立验收准备
- 候选身份：H2-SRC 为 `bfcab15c172804fc32b9a11761be7da5077eba20`，H2-HANDOFF 为
  `53fbc6f37016b25b803a73a37570df92cc8179fe`；二者之间只有 RESULT 文档变化。PLAN Revision 2 blob
  `e134703ce6e37a2f4d5df389662119f38638fae8` 未变。
- 门禁结果：§R2-20 的三项实质缺口已闭合；Documentation Agent 对 RESULT 的数值和摘要缺项完成一次性
  机械校正后给出 `DOC_ALIGNED`。该结论只表示交付可进入独立验收，不表示源码或运行已经验收通过。
- 包与交接：精确包为 4045 files / 170,356,115 B，EXE SHA-256
  `133A1394189BF008AFEFCCADD5B27F626AB49CA1E6A9BD4F2DE15255F6486B12`；canonical 已保护 handoff，
  固定 review 已 detached 到 `53fbc6f` 且 clean，包和证据已封存至对应 acceptance-staging 目录。
- 下一步：由未参与本候选实现、自测或修复的 Acceptance Agent 绑定同一 H2-HANDOFF 与精确包完成独立
  验收。旧 `be59acd` 的通过结论不继承；本轮独立结论返回前不得进入人工验收、全局文档收口或发布。

## VH-021 `53fbc6f` 独立验收通过，发布卫生要求形成最小修正候选

- 日期：2026-09-22
- 阶段：V2.2.0 独立验收 → 发布卫生修正
- 验收结论：未参与实现、自测或修复的 Acceptance Agent 绑定 H2-HANDOFF `53fbc6f`、H2-SRC
  `bfcab15c` 与精确包完成 Design Fidelity、Integration、失败矩阵、真实性能、artifact、资源清理和
  包审计；全部必做项无 FAIL/NOT_RUN，最终结论为 `ACCEPTANCE_PASS`。验收前后 review HEAD 未变化且
  clean，一次性副本和隔离 runtime 已清理。
- 后置卫生复核：已验收包不含 Key、开发路径或测试注入，但 tracked 根包审计摘要仍指向旧包，根 failure
  matrix 证据含用户临时目录，package audit 验证脚本还硬编码用户特定临时路径。该问题不推翻
  `53fbc6f` 的产品验收事实，但不符合公开源码脱敏规则。
- 身份影响：当前状态改为“需修正”，PLAN Revision 2 不变；固定 review 暂留已验收的 `53fbc6f`。
  Development Agent 形成仅限验证脚本与证据卫生的新候选后，重新执行 Documentation Gate 和定向独立
  复核；不得以旧 PASS 自动覆盖新候选，也不得在修正前进入人工验收或发布。
- 当前执行细节以 RESULT §R2-23 为准；本 HISTORY 只记录验收通过与候选后置失效原因，不构成开发指令。

## VH-022 卫生候选 `5dc16d8` 进入定向独立复核

- 日期：2026-09-22
- 阶段：V2.2.0 发布卫生修正 → 定向独立复核
- 候选身份：H3-SRC 为 `5dc16d8ebc26c03d7f1c9a00986bc9cfd2533dfc`，H3-HANDOFF 为
  `6822f4acc788f75c8afdb5903c7db3d50c048f54`；二者之间只有 RESULT 文档变化。PLAN Revision 2 blob
  `e134703ce6e37a2f4d5df389662119f38638fae8` 未变。
- 变更边界：相对 §R2-23 文档基线只修改 package audit / failure matrix 两份验证脚本与两份持久化
  证据；产品源码、bundle、依赖、配置和精确包均未变化。精确包继续为 4045 files / 170,356,115 B，
  EXE SHA-256 `133A1394189BF008AFEFCCADD5B27F626AB49CA1E6A9BD4F2DE15255F6486B12`。
- 门禁结果：Documentation Agent 完成机械与 RESULT 语义复核并给出 `DOC_ALIGNED`；canonical 已保护
  H3-HANDOFF，固定 review 已 detached 到 `6822f4a` 且 clean，最新卫生证据已另行封存。该结论不自动
  继承 H2 的独立通过结论。
- 下一步：由未参与卫生修改、自测或开发结论编写的 Acceptance Agent 完成脚本检测能力、证据脱敏、
  package audit、failure matrix、包身份及 clean/cleanup 的定向独立复核；通过前不进入人工验收或发布。

## VH-023 H3 定向独立复核因检测能力回退失败

- 日期：2026-09-22
- 阶段：V2.2.0 发布卫生修正 → 定向独立复核失败
- 验收对象：H3-HANDOFF `6822f4acc788f75c8afdb5903c7db3d50c048f54`、H3-SRC
  `5dc16d8ebc26c03d7f1c9a00986bc9cfd2533dfc`；PLAN Revision 2 blob
  `e134703ce6e37a2f4d5df389662119f38638fae8` 未变。
- 失败原因：package audit 将项目树固定前缀替换为脚本所在仓库根后，在强制的一次性源码副本运行方式
  下不能识别指向真实开发、canonical 或 review 检出的项目树绝对路径；独立 A/B 探针证明该类别相对
  基线净收窄，开发侧“等价且更强”声明不成立。
- 未受影响事实：H3 仍只修改两份验证脚本、两份证据与 RESULT；产品源码、bundle、依赖、配置和精确包
  未变化。语法、当前包审计、失败矩阵、证据脱敏、包身份、clean 与 cleanup 均独立通过，H2 产品行为
  `ACCEPTANCE_PASS` 继续仅作为绑定旧对象的历史事实。
- 文档处置：当前状态改为“需修正”；RESULT 中非必要本机路径字面已由 Documentation Agent 统一替换为
  语义占位，并在 RESULT §R2-26 集中记录独立失败与最小返工边界。本次不修改 PLAN。
- 下一步：Development Agent 只恢复位置无关的项目树路径族检测并更新受影响证据，形成新 clean 候选；
  重新经过 Documentation Gate 与定向独立复核前，不进入人工验收或发布。

## VH-024 H4 恢复项目树路径族检测并进入定向复核

- 日期：2026-09-22
- 阶段：V2.2.0 发布卫生返工 → 定向独立复核
- 候选身份：H4-SRC `b378490a0f9429931c18d7f63ecc5acce3f5b8fc`、H4-HANDOFF
  `c9dfa0ea4cbc51a065b46732b32e80f32d19b7ef`；二者之间只修改 RESULT。PLAN Revision 2 blob
  `e134703ce6e37a2f4d5df389662119f38638fae8` 未变。
- 返工边界：相对 §R2-26 文档基线只修改 package audit 验证脚本，开发声明新增位置无关的
  current/canonical/review 项目树路径族检测，并用一次性副本内正反向探针和冻结包复跑形成证据；产品
  源码、bundle、依赖、配置、构建、failure matrix 和精确包均未变化。
- 门禁结果：Documentation Agent 完成机械身份、RESULT 映射和证据入口复核并给出 `DOC_ALIGNED`；
  canonical 已保护 H4-HANDOFF，固定 review 已 detached 到 `c9dfa0e` 且 clean，H4 证据已封存。该结论
  不表示新增脚本逻辑已独立通过。
- 下一步：由未参与 H4 实现、自测或开发结论编写的 Acceptance Agent 定向复核位置无关检测、正反向
  探针、脱敏、package audit、包身份及 clean/cleanup；通过前不进入人工验收或发布。

## VH-025 H4 定向独立复核因项目树误判与漏检失败

- 日期：2026-09-22
- 阶段：V2.2.0 发布卫生返工 → 定向独立复核失败
- 验收对象：H4-HANDOFF `c9dfa0ea4cbc51a065b46732b32e80f32d19b7ef`、H4-SRC
  `b378490a0f9429931c18d7f63ecc5acce3f5b8fc`；PLAN Revision 2 blob
  `e134703ce6e37a2f4d5df389662119f38638fae8` 未变。
- 失败原因：H4 恢复了 current/canonical/review 三类正向检出，但只以“绝对路径 + 同名目录元素”判断
  项目树，导致普通同名绝对目录系统性误报；同时因固定 260 字节窗口与前置字符对齐，漏检带键名、
  引号或长前缀的真实项目路径。独立探针因此判定核心要求不成立。
- 未受影响事实：H4 仅修改 package audit 与 RESULT；产品源码、bundle、依赖、配置、构建、failure
  matrix 和精确包均未变化。语法、冻结包审计、脱敏、封存证据、包身份、clean 与 cleanup 均独立通过；
  H2 产品行为 `ACCEPTANCE_PASS` 继续仅作为绑定旧对象的历史事实。
- 文档处置：当前状态改为“需修正”，独立失败与最小返工边界集中记录在 RESULT §R2-29，不修改 PLAN。
- 下一步：Development Agent 只修复项目树身份判别与路径条目解析，补齐误报/漏检正反向探针并更新
  受影响证据；重新经过 Documentation Gate 与定向独立复核前，不进入人工验收或发布。

## VH-026 H5 形成项目身份与无窗口解析候选并进入定向复核

- 日期：2026-09-22
- 阶段：V2.2.0 发布卫生返工 → 定向独立复核
- 候选身份：H5-SRC `175eedd7b8ea4c2e9c0b0a392a0a5367970ae4ce`、H5-HANDOFF
  `ce78436336c92800c42f5b173197155a54b7b327`；二者之间只修改 RESULT。PLAN Revision 2 blob
  `e134703ce6e37a2f4d5df389662119f38638fae8` 未变。
- 返工边界：相对 §R2-29 文档基线只修改 package audit 验证脚本；开发声明以稳定项目标识区分真实项目
  树与普通同名目录，并用无固定窗口的路径条目解析覆盖键值、引号、JSON、盘符/UNC 和长前缀。产品
  源码、bundle、依赖、配置、构建、failure matrix 和精确包均未变化。
- 门禁结果：Documentation Agent 完成机械身份、RESULT 映射和证据入口复核并给出 `DOC_ALIGNED`；
  canonical 已保护 H5-HANDOFF，固定 review 已 detached 到 `ce78436` 且 clean，H5 证据已封存。该结论
  不表示新增解析逻辑已独立通过。
- 下一步：由未参与 H5 实现、自测或开发结论编写的 Acceptance Agent 独立覆盖项目路径、同名目录、
  URL/UNC、空格、转义和长上下文边界，并复核 package audit、脱敏、包身份及 clean/cleanup；通过前不
  进入人工验收或发布。

## VH-027 H5 定向独立复核因路径词法与归一化缺陷失败

- 日期：2026-09-22
- 阶段：V2.2.0 发布卫生返工 → 定向独立复核失败
- 验收对象：H5-HANDOFF `ce78436336c92800c42f5b173197155a54b7b327`、H5-SRC
  `175eedd7b8ea4c2e9c0b0a392a0a5367970ae4ce`；PLAN Revision 2 blob
  `e134703ce6e37a2f4d5df389662119f38638fae8` 未变。
- 失败原因：H5 已修复 H4 的普通同名目录误报和固定窗口漏检，但文件系统路径词法与归一化仍不完整：
  JSON 双反斜杠路径会触发未捕获 `IndexError` 并中断审计；HTTP(S) URL 会因盘符/UNC 头混淆被误判为
  项目树绝对路径；含空格 Windows 项目路径会因条目过早截断而漏检。
- 未受影响事实：H5 仅修改 package audit 与 RESULT；项目标识完整路径元素、普通同名目录反例、长上下文
  处理等已独立确认。语法、冻结包审计、脱敏、failure matrix 未变、精确包身份、clean 与 cleanup 均通过；
  产品源码、bundle、依赖、配置、构建、failure matrix 和精确包均未变化。
- 文档处置：当前状态改为“需修正”，统一阻断根因、已通过边界和 H6 最小返工要求集中记录在 RESULT
  §R2-32；不修改 PLAN，不把 §R2-31 的 `DOC_ALIGNED` 解释为验收通过。
- 下一步：Development Agent 仅修复路径词法、归一化与异常封闭，补齐 JSON 转义、URL/UNC、含空格路径
  及 malformed/binary 正反向探针并更新受影响证据；重新经过 Documentation Gate 与同口径定向独立
  复核前，不进入 Product Owner 人工验收或发布。
