import { useWorkbenchTask } from './WorkbenchTaskContext'

/**
 * V2.2.0 T04：步骤 2「理解岗位」视图（主面板内容）。
 * 数据唯一真源 = WorkbenchTaskContext.snapshotPayload.compact_jd（后端权威快照）。
 * 只渲染快照中真实存在的字段；数组为空时诚实标注「暂无」，绝不编造。
 */

interface JdCompact {
  position?: string
  industry?: string
  required_skills?: string[]
  preferred_skills?: string[]
  responsibilities?: string[]
  keywords?: string[]
  experience_preferences?: string[]
}

interface GroupSpec {
  key: keyof JdCompact
  label: string
  items?: string[]
}

export default function StepUnderstand() {
  const { snapshotPayload } = useWorkbenchTask()

  const jd =
    snapshotPayload && typeof snapshotPayload.compact_jd === 'object' && snapshotPayload.compact_jd !== null
      ? (snapshotPayload.compact_jd as JdCompact)
      : null

  // 尚无权威快照（未开始 / 正在生成初始阶段）
  if (!jd) {
    return (
      <div className="wb-analyzing">
        <div className="wb-analyzing__pulse" aria-hidden="true" />
        <div className="wb-analyzing__title">正在分析岗位…</div>
        <p className="wb-analyzing__sub">系统正在从 JD 中提取职责与要求，完成后会在此展示。</p>
      </div>
    )
  }

  const groups: GroupSpec[] = [
    { key: 'responsibilities', label: '职责' },
    { key: 'required_skills', label: '必备技能' },
    { key: 'preferred_skills', label: '加分技能' },
    { key: 'experience_preferences', label: '经验偏好' },
    { key: 'keywords', label: '关键词' },
  ]

  const headerFields: Array<{ label: string; value?: string }> = [
    { label: '目标岗位', value: jd.position },
    { label: '行业', value: jd.industry },
  ]

  return (
    <div className="wb-understand">
      <div className="wb-understand__why">
        以下内容来自对 JD 的分析结果，按原文提取并未做补充。
      </div>

      <section className="wb-understand__section">
        {headerFields.map((f) => (
          <div className="wb-understand__field" key={f.label}>
            <span className="wb-understand__field-label">{f.label}</span>
            {f.value ? (
              <span className="wb-understand__field-value">{f.value}</span>
            ) : (
              <span className="wb-understand__empty">暂无</span>
            )}
          </div>
        ))}
      </section>

      {groups.map((g) => {
        const list = Array.isArray(jd[g.key]) ? (jd[g.key] as string[]) : []
        return (
          <section className="wb-understand__section" key={g.key}>
            <h3 className="wb-understand__group-title">{g.label}</h3>
            {list.length > 0 ? (
              <ul className="wb-understand__list">
                {list.map((item, i) => (
                  <li className="wb-understand__item" key={`${g.key}-${i}`}>
                    <span className="wb-understand__item-dot" aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="wb-understand__empty">暂无</p>
            )}
          </section>
        )
      })}
    </div>
  )
}