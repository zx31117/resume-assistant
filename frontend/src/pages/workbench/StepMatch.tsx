import { useWorkbenchTask } from './WorkbenchTaskContext'

/**
 * V2.2.0 T04：步骤 3「匹配经历」视图（主面板内容）。
 * 数据唯一真源 = WorkbenchTaskContext.snapshotPayload.experiences（后端权威快照）。
 * 后端 P2 快照只发布「已选中经历集合 + 每条事实数」，不发布逐条匹配理由，
 * 因此这里只如实呈现选中集合与事实数作为匹配依据，绝不编造「匹配理由」。
 */

interface SelectedExperience {
  experience_id: string
  sort_order: number
  title: string
  fact_count: number
}

export default function StepMatch() {
  const { snapshotPayload } = useWorkbenchTask()

  const experiences =
    snapshotPayload && Array.isArray(snapshotPayload.experiences)
      ? (snapshotPayload.experiences as SelectedExperience[])
      : null

  if (experiences === null) {
    return (
      <div className="wb-analyzing">
        <div className="wb-analyzing__pulse" aria-hidden="true" />
        <div className="wb-analyzing__title">正在匹配经历…</div>
        <p className="wb-analyzing__sub">系统正在从你的经历中筛选与岗位相关的事实。</p>
      </div>
    )
  }

  const ranked = [...experiences].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))

  if (ranked.length === 0) {
    return (
      <div className="wb-analyzing wb-analyzing--empty">
        <div className="wb-analyzing__title">暂无可展示的匹配经历</div>
        <p className="wb-analyzing__sub">该阶段尚未产出选中经历，请在后台任务完成后重试查看。</p>
      </div>
    )
  }

  return (
    <div className="wb-match">
      <div className="wb-understand__why">
        以下为后端按相关事实数选中的经历集合，按排序权重排列。
      </div>
      <ol className="wb-match__list">
        {ranked.map((exp, i) => (
          <li className="wb-match__card" key={exp.experience_id ?? `exp-${i}`}>
            <span className="wb-match__rank" aria-hidden="true">
              {exp.sort_order ?? i + 1}
            </span>
            <div className="wb-match__body">
              <div className="wb-match__title">{exp.title || '未命名经历'}</div>
              <div className="wb-match__meta">可用事实 {exp.fact_count ?? 0} 条</div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}