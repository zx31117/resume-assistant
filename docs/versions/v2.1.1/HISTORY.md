# V2.1.1 版本历史

> 本文件记录 V2.1.1 内影响计划、技术路线、候选身份或跨角色协作的重要事件。
> 它不是开发范围、当前 Gate 状态或验收结论真源；当前合同以 `PLAN.md`（形成后）为准，实际结果
> 以 `RESULT.md`（形成后）为准。普通 Bug、长日志和逐次命令不写入本文件。

## VH-001 新交付工作流与版本历史机制获批

- 日期：2026-09-11
- 阶段：V2.1.1 DRAFT
- 触发事实：V2.1.0 在进入独立验收前发生多轮文档打回；PLAN 持续追加后同时包含多条已失效
  技术路线，Development 与 Documentation 之间逐项补漏，无法稳定实现“开发首次正式交付即可
  进入独立验收”的目标。
- 根因：PLAN 缺少用户结果到实施和证据的逐项映射；高风险路线未先通过真实纵切；开发完成声明
  与强制 Gate 没有硬绑定；Documentation 交接审查没有被定义为一次完整的语义一致性检查。
- Product Owner 决定：
  1. V2.1.1 起，版本目录增加 `HISTORY.md` 保存重要演进历史；具有跨版本价值的结论再提炼到
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
- 影响：上述机制写入 V2.1.1 DRAFT，并作为 V2.1.1 正式 PLAN 必须继承的工作流基线；不反向
  修改 V2.1.0 的 PLAN、候选或验收合同。
- 全局提炼：D-040；`docs/HUMAN_AI_WORKFLOW.md` 的 PLAN 修订、交付与文档审查规则。

## VH-002 文档交接与源码验收边界澄清

- 日期：2026-09-12
- 阶段：V2.1.1 DRAFT
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
- 影响：V2.1.1 正式 PLAN 必须包含 `RESULT Delivery Contract`，RESULT 模板必须包含“待独立验收
  问题”；D-040 与全局工作流按上述边界修正，并增加上下文压缩或任务恢复后的角色边界重读门禁。
  V2.1.0 的既有 PLAN、候选和本轮 H8 处置不追溯改变。
- 全局提炼：D-040；`docs/HUMAN_AI_WORKFLOW.md` 的角色、RESULT、交接与验收规则。
