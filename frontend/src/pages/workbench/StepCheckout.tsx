import { useMemo } from 'react'
import { useWorkbenchTask } from './WorkbenchTaskContext'

/**
 * V2.2.0 T05：步骤 4「修改与下载」P3 过程预览（HTML，仅查看，无导出动作）。
 * 数据唯一真源 = WorkbenchTaskContext.snapshotPayload.experiences（权威快照）。
 *
 * 展示模型（诚实）：
 *  - 快照中的「完整事实」（有 fact_id+headline+body）逐条呈现为简历式条目；
 *  - 每条旁标注「与岗位的联系」：优先取快照 reasons[fact_id]（已兜底/权威），
 *    否则取累积的理由增量 reasons[fact_id]；两者皆无则显示静默占位，绝不编造；
 *  - 「依据」展开列出 fact_refs 原文事实 id；无则诚实标注「该条目未记录引用事实」；
 *  - 运行中实时冒泡的 fact.done（快照尚未纳管）源事实即时出现，快照刷新后由权威数据覆盖；
 *  - 运行中展示流式提示；SSE 断连（done 帧 / error）如实提示「连接中断 · 已显示内容保留」。
 */

interface SnapshotFact {
  fact_id?: string
  headline?: string
  body?: string
  fact_refs?: string[]
}

interface SnapshotExperience {
  experience_id?: string
  sort_order?: number
  title?: string
  facts?: SnapshotFact[]
}

/** 统一的一条展示事实（快照已纳管 / 实时冒泡 结构一致）。 */
interface DisplayFact {
  fact_id: string
  headline: string
  body: string
  fact_refs: string[]
  live: boolean
}

interface DisplayGroup {
  key: string
  title: string
  sort_order: number
  facts: DisplayFact[]
}

function isCompleteFact(f: SnapshotFact | undefined): f is SnapshotFact {
  return !!f && typeof f.fact_id === 'string' && !!(f.fact_id) &&
    typeof f.headline === 'string' && !!f.headline &&
    typeof f.body === 'string' && !!f.body
}

export default function StepCheckout() {
  const { snapshotPayload, reasons, factDone, streamEnded, status } = useWorkbenchTask()

  const running = status === 'RUNNING'
  const succeeded = status === 'SUCCEEDED'

  const experiences =
    snapshotPayload && Array.isArray(snapshotPayload.experiences)
      ? (snapshotPayload.experiences as SnapshotExperience[])
      : null

  const snapshotReasons =
    snapshotPayload && typeof snapshotPayload.reasons === 'object' && snapshotPayload.reasons !== null
      ? (snapshotPayload.reasons as Record<string, unknown>)
      : null

  const groups = useMemo<DisplayGroup[]>(() => {
    const groupMap = new Map<string, DisplayGroup>()
    const snapshotFactIds = new Set<string>()
    const orderedGroups: DisplayGroup[] = []

    // 1) 权威快照：经历 → 完整事实
    if (experiences) {
      const ordered = [...experiences].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
      for (const exp of ordered) {
        const eid = exp.experience_id
        if (!eid) continue
        const facts = (Array.isArray(exp.facts) ? exp.facts : []).filter(isCompleteFact)
        for (const f of facts) if (f.fact_id) snapshotFactIds.add(f.fact_id)
        const group: DisplayGroup = {
          key: eid,
          title: exp.title || '未命名经历',
          sort_order: exp.sort_order ?? 0,
          facts: facts.map((f) => ({
            fact_id: f.fact_id!,
            headline: f.headline!,
            body: f.body!,
            fact_refs: Array.isArray(f.fact_refs) ? (f.fact_refs as string[]) : [],
            live: false,
          })),
        }
        orderedGroups.push(group)
        groupMap.set(eid, group)
      }
    }

    // 2) 实时冒泡的 fact.done（快照尚未纳管）→ 归入所属经历；经历未知则落到兜底分组
    const liveEntries = Object.entries(factDone)
    const liveWithoutSnapshot = liveEntries.filter(([fid]) => !snapshotFactIds.has(fid))
    if (liveWithoutSnapshot.length > 0) {
      for (const [fid, done] of liveWithoutSnapshot) {
        let group = done.experience_id ? groupMap.get(done.experience_id) : undefined
        if (!group) {
          const key = done.experience_id ?? `live-${fid}`
          group = { key, title: done.experience_id ? '经历条目' : '新条目', sort_order: Number.MAX_SAFE_INTEGER, facts: [] }
          groupMap.set(key, group)
          orderedGroups.push(group)
        }
        if (!group.facts.some((f) => f.fact_id === fid)) {
          group.facts.push({
            fact_id: fid,
            headline: done.headline,
            body: done.body,
            fact_refs: done.fact_refs,
            live: true,
          })
        }
      }
    }

    return orderedGroups
  }, [experiences, factDone])

  const resolveReason = useMemo(
    () => (fid: string) => {
      const sr = snapshotReasons?.[fid]
      if (typeof sr === 'string' && sr.length > 0) return { text: sr, settled: true }
      const acc = reasons[fid]
      if (typeof acc === 'string' && acc.length > 0) return { text: acc, settled: false }
      return { text: '', settled: false }
    },
    [reasons, snapshotReasons],
  )

  // —— 空态：尚未有可展示条目 ——
  if (groups.length === 0) {
    return (
      <div className="wb-analyzing wb-analyzing--empty">
        <div className="wb-analyzing__pulse" aria-hidden="true" />
        <div className="wb-analyzing__title">
          {running || !succeeded ? '正在整理简历条目…' : '暂无可展示的修改条目'}
        </div>
        <p className="wb-analyzing__sub">
          系统正在针对岗位逐条生成简历表述与理由，完成后会在此展示过程预览。
        </p>
      </div>
    )
  }

  return (
    <div className="wb-checkout">
      <div className="wb-understand__why">
        以下为针对目标岗位逐步生成的简历条目草稿（HTML 过程预览）：每条标注其对岗位的联系与已确认的原文依据。
        理由仅作为旁注呈现，不混入简历正文。
      </div>

      {groups.map((group) => (
        <section className="wb-checkout__group" key={group.key}>
          <h3 className="wb-checkout__group-title">{group.title}</h3>
          <ol className="wb-checkout__list">
            {group.facts.map((fact) => {
              const reason = resolveReason(fact.fact_id)
              const streaming = running && !streamEnded && !reason.settled && reason.text.length > 0
              return (
                <li className="wb-checkout__fact" key={fact.fact_id}>
                  <div className="wb-checkout__entry">
                    <div className="wb-checkout__headline">{fact.headline}</div>
                    <div className="wb-checkout__body">{fact.body}</div>
                  </div>

                  <div className="wb-checkout__reason">
                    <div className="wb-checkout__reason-label">
                      与岗位的联系
                      {fact.live && <span className="wb-checkout__tag">新生成</span>}
                    </div>
                    {reason.text ? (
                      <p className="wb-checkout__reason-text">
                        {reason.text}
                        {streaming && <span className="wb-checkout__stream">正在整理…</span>}
                      </p>
                    ) : (
                      <p className="wb-checkout__reason-empty">等待该条事实的理由…</p>
                    )}
                  </div>

                  <details className="wb-checkout__evidence">
                    <summary className="wb-checkout__evidence-summary">查看已确认的原始事实</summary>
                    {fact.fact_refs.length > 0 ? (
                      <ul className="wb-checkout__refs">
                        {fact.fact_refs.map((ref) => (
                          <li className="wb-checkout__ref" key={ref}>{ref}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="wb-checkout__refs-empty">该条目未记录引用事实</p>
                    )}
                  </details>
                </li>
              )
            })}
          </ol>
        </section>
      ))}

      {running && (
        <div className="wb-checkout__streamfoot" role="status">
          {streamEnded ? '连接中断 · 已显示内容保留' : '正在整理新内容…'}
        </div>
      )}
    </div>
  )
}