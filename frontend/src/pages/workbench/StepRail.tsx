import { Link } from 'react-router-dom'
import { useWorkbenchTask } from './WorkbenchTaskContext'

export const WB_STEPS: Array<{ label: string; sub: string }> = [
  { label: '身份与目标', sub: '本次身份 · 职位描述' },
  { label: '理解岗位', sub: '提取职责与要求' },
  { label: '匹配经历', sub: '寻找相关事实' },
  { label: '修改与下载', sub: '润色、查看详情与导出' },
]

function StepIcon({ state }: { state: string }) {
  if (state === 'done') {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" style={{ width: 14, height: 14 }} aria-hidden="true">
        <path d="M20 6 9 17l-5-5" />
      </svg>
    )
  }
  if (state === 'failed') {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" style={{ width: 14, height: 14 }} aria-hidden="true">
        <path d="M18 6 6 18M6 6l12 12" />
      </svg>
    )
  }
  return null
}

/**
 * V2.2.0 T03：左侧步骤导轨。
 * 每步：.active（当前、自动选中、不可点、aria-current）/
 * .done（对勾、可点回看历史）/.future（禁用、弱化）。
 */
export default function StepRail({
  selected,
  onSelect,
}: {
  selected: number
  onSelect: (index: number) => void
}) {
  const { stepStates } = useWorkbenchTask()

  return (
    <div className="wb-panel wb-panel--steps">
      <div className="wb-panel__head">
        <div>
          <div className="wb-panel__head-title">生成流程</div>
          <div className="wb-panel__head-sub">4 步完成一份可投递简历</div>
        </div>
      </div>
      <div className="wb-panel__scroll">
        <ol className="wb-steps" aria-label="生成流程步骤">
          {WB_STEPS.map((s, i) => {
            const state = stepStates[i] ?? 'future'
            const active = state === 'active'
            const clickable = state === 'done' || state === 'failed'
            let cls = 'wb-step'
            if (active) cls += ' is-active'
            else if (state === 'done') cls += ' is-done'
            else if (state === 'failed') cls += ' is-failed is-done'
            else cls += ' is-future'
            return (
              <li key={s.label} style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                <button
                  type="button"
                  className={cls}
                  onClick={() => clickable && onSelect(i)}
                  disabled={!clickable && !active}
                  tabIndex={active || clickable ? 0 : -1}
                  aria-current={active ? 'step' : undefined}
                >
                  <span className={`wb-step__num${i === selected ? ' is-selected' : ''}`} aria-hidden="true">
                    {state === 'done' || state === 'failed' ? <StepIcon state={state} /> : i + 1}
                  </span>
                  <span>
                    <span className="wb-step__label">{s.label}</span>
                    <span className="wb-step__sub">{s.sub}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      </div>
      <div className="wb-panel__foot">
        <div className="wb-steps-foot">
          <div>真实经历，清楚表达。</div>
          <Link to="/experiences">查看 / 补充我的经历 ↗</Link>
        </div>
      </div>
    </div>
  )
}