import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useWorkbenchTask } from './WorkbenchTaskContext'
import StepRail, { WB_STEPS } from './StepRail'
import StepIdentity from './StepIdentity'
import StepUnderstand from './StepUnderstand'
import StepMatch from './StepMatch'
import StepCheckout from './StepCheckout'
import StepDownload from './StepDownload'
import StepIdentityAside from './StepIdentityAside'
import StepSuccessAside from './StepSuccessAside'
import type { PdfAnchor, TaskStatus } from '../../api/types'

/**
 * V2.2.0 T02/T03/T04/T06：工作台主体 —— 三栏 work-grid。
 * 左：步骤导轨；中：主面板（当前步骤或历史回看）；右：随步骤切换的说明卡。
 * 冻结 DS-003：工作台首页不在 work-grid 前渲染额外 hero（接下来直接是三栏网格）。
 * T04：历史回看 —— 点击已 done 步骤可回看其权威快照结果，不回暂停后台生成。
 * T06：P4 成功后主面板以真实 PDF viewer 为主视觉；下载在右侧说明卡固位。
 *
 * V2.2.0 DOC_RETURNED 返工：P4 选择状态**提升**到本组件（主面板与说明卡的最近公共祖先），
 * 由 StepDownload 转交 PdfPreview、StepSuccessAside 消费同一对象；主面板与说明卡因此始终
 * 一致，且 PdfPreview 成为纯受控组件（DS-003 语义）。切换任务时清空选择。
 */

/** 由 status + snapshotPhase 推导“当前实时步骤”(0 基)。RUNNING→快照阶段；SUCCEEDED→第 4 步；其余→第 1 步。 */
function liveStep(status: TaskStatus | null, phase: string): number {
  if (status === 'SUCCEEDED') return 3
  if (status === 'RUNNING') {
    const m = phase.match(/(\d)/)
    if (m) {
      const n = Number(m[1])
      if (n >= 1 && n <= 4) return n - 1
    }
    return 0
  }
  return 0
}

export default function WorkbenchPage() {
  const { status, input, saving, dirty, saveError, loadState, retryLoad, snapshotPhase, stepStates, generateError, terminalError, generatePending, continueScope, generate, taskId } =
    useWorkbenchTask()
  const current = liveStep(status, snapshotPhase)
  const [selected, setSelected] = useState(current)
  const [reviewStep, setReviewStep] = useState<number | null>(null)
  const [step1Error, setStep1Error] = useState<string | null>(null)
  // V2.2.0 DOC_RETURNED 返工：P4 受控选择（提升后的唯一真源）。
  const [p4Selection, setP4Selection] = useState<PdfAnchor | null>(null)

  // 切换任务（含 startNewTask / 续试）时清空 P4 选择，避免跨任务残留旧锚点。
  useEffect(() => {
    setP4Selection(null)
  }, [taskId])

  // 未在回看时：主面板自动跟随实时步骤（生成推进时自动前进/追平）
  useEffect(() => {
    if (reviewStep === null) setSelected(current)
  }, [current, reviewStep])

  // 主面板标题（按当前选中/回看步骤取真解）
  const activeIdx = selected >= 0 && selected < WB_STEPS.length ? selected : 0
  const reviewing = reviewStep !== null && reviewStep !== current

  function handleSelect(i: number) {
    // 仅已 done 步骤可回看；点当前实时步骤回到实时视图
    if (i === current) {
      setSelected(i)
      setReviewStep(null)
      return
    }
    if (stepStates[i] === 'done' || stepStates[i] === 'failed') {
      setSelected(i)
      setReviewStep(i)
      return
    }
  }

  function returnToLive() {
    setSelected(current)
    setReviewStep(null)
  }

  function saveIndicator(): React.ReactNode {
    if (loadState === 'loading') {
      return (
        <span className="wb-save-state">
          <span className="wb-save-state__dot" />
          读取任务中…
        </span>
      )
    }
    if (loadState === 'error') {
      return <span className="wb-save-state wb-save-state--error">任务读取失败</span>
    }
    if (status === null) {
      return <span className="wb-save-state">尚未创建任务 · 填写后自动保存</span>
    }
    if (status === 'DRAFT') {
      if (saveError) return <span className="wb-save-state wb-save-state--error">保存失败</span>
      if (saving) {
        return (
          <span className="wb-save-state wb-save-state--saving">
            <span className="wb-save-state__dot" />
            保存中…
          </span>
        )
      }
      if (dirty) {
        return (
          <span className="wb-save-state wb-save-state--dirty">
            <span className="wb-save-state__dot" />
            未保存
          </span>
        )
      }
      return (
        <span className="wb-save-state wb-save-state--saved">
          <span className="wb-save-state__dot" />
          已保存
        </span>
      )
    }
    // 非编辑态：已冻结/运行
    return <span className="wb-save-state wb-save-state--saved">已保存 · 输入已冻结</span>
  }

  function mainContent(): React.ReactNode {
    // T08：终态失败/已取消 —— 诚实面板（不无提示跳回第 1 步），保留输入与已完成经历，给真实下一步。
    if (status === 'FAILED') {
      return (
        <div className="wb-failed" role="alert">
          <div className="wb-failed__title">本次生成未完成</div>
          <p className="wb-failed__reason">
            {generateError ||
              (terminalError
                ? `后端错误码：${terminalError}`
                : '任务以失败状态结束，请重试或补充材料后重新生成。')}
          </p>
          <ul className="wb-failed__list">
            <li>你已填写的身份与 JD 仍在输入中保留，未丢失。</li>
            <li>已完成选材/经历与事实（若有）仍保留在真实数据库中，重新生成会复用，不会重复计费已成功事实。</li>
            <li>如需补充材料或纠正某段经历，请到「我的经历」修改后再回来重新制作（范围化重试）。</li>
          </ul>
          <div className="wb-failed__actions">
            <button
              type="button"
              className="wb-btn wb-btn--primary wb-btn--sm"
              disabled={generatePending}
              onClick={continueScope}
            >
              {generatePending ? '正在创建续试…' : '续试失败范围 ›'}
            </button>
            <Link className="wb-btn wb-btn--ghost wb-btn--sm" to="/experiences">
              去我的经历补充材料 ›
            </Link>
            <span className="wb-failed__muted">
              续试会复用已完成经历（不再重复调用），仅对失败范围重新生成。
            </span>
          </div>
        </div>
      )
    }
    if (status === 'CANCELLED') {
      return (
        <div className="wb-failed" role="status">
          <div className="wb-failed__title">生成已取消</div>
          <p className="wb-failed__reason">
            你已填写的输入依然保留；已完成的部分不会发布为成果文件。
          </p>
          <div className="wb-failed__actions">
            <span className="wb-failed__muted">
              右上角「＋ 开始新任务」可重新制作一份简历。
            </span>
          </div>
        </div>
      )
    }
    if (activeIdx === 0) return <StepIdentity />
    if (activeIdx === 1) return <StepUnderstand />
    if (activeIdx === 2) return <StepMatch />
    if (activeIdx === 3) {
      // T06：P4 成功后切换到真实 PDF 成品视图；运行/回看期间保留 P3 过程预览
      if (status === 'SUCCEEDED') {
        return <StepDownload selection={p4Selection} onSelect={setP4Selection} />
      }
      return <StepCheckout />
    }
    return (
      <div className="wb-placeholder">
        <div className="wb-placeholder__title">{WB_STEPS[activeIdx].label}</div>
        <p>
          该步骤的详情视图将在生成流程推进后开放。
          当前任务状态：{status ?? '无任务'} {snapshotPhase ? `· ${snapshotPhase}` : ''}。
        </p>
      </div>
    )
  }

  /** 步骤 1 主操作：校验并触发真实生成（保持在 foot，不随内容漂移）。 */
  const step1Generatable = status === null || status === 'DRAFT' || status === 'READY'
  function handleGenerate() {
    setStep1Error(null)
    if (!input.name.trim()) {
      setStep1Error('请填写姓名。')
      document.getElementById('wb-name')?.focus()
      return
    }
    if (input.jd.trim().length < 60) {
      setStep1Error('请粘贴包含职责与任职要求的完整 JD（至少 60 字）。')
      document.getElementById('wb-jd')?.focus()
      return
    }
    void generate()
  }

  /** 右栏说明卡：随步骤 / 阶段切换（冻结 inputAside / successAside / 通用任务说明）。 */
  function asideContent(): React.ReactNode {
    if (status === 'SUCCEEDED' && activeIdx === 3) return <StepSuccessAside selection={p4Selection} />
    if (activeIdx === 0) return <StepIdentityAside />
    return (
      <>
        <div className="wb-panel__head">
          <div>
            <div className="wb-panel__head-title">任务说明</div>
            <div className="wb-panel__head-sub">真实流程 · 无占位成功</div>
          </div>
        </div>
        <div className="wb-panel__scroll">
          <div className="wb-aside-block">
            <div className="wb-aside-block__title">保存与恢复</div>
            <div className="wb-aside-block__body">
              <p>
                姓名与 JD 填写后草稿自动保存在本机；刷新页面可恢复。只有后端返回确认后才显示「已保存」，不会伪造保存成功。
              </p>
              <p style={{ marginTop: 8 }}>
                目标岗位字段仅用于本次输入提示，不会上传；求职意向始终以 JD 分析为准。
              </p>
            </div>
          </div>
          <div className="wb-aside-block" style={{ borderTop: '1px solid var(--border)' }}>
            <div className="wb-aside-block__title">生成可信度</div>
            <div className="wb-aside-block__body">
              <p>每次生成基于真实经历与事实；失败会明确告知并保留你已输入的字段。</p>
            </div>
          </div>
        </div>
        {(loadState === 'error' || input.jd.length === 0) && (
          <div className="wb-panel__foot" style={{ minHeight: 'auto', paddingTop: 12, paddingBottom: 12 }}>
            {loadState === 'error' ? (
              <button type="button" className="wb-btn wb-btn--ghost wb-btn--sm" onClick={retryLoad}>
                重试加载任务
              </button>
            ) : null}
          </div>
        )}
      </>
    )
  }

  return (
    <div className="wb-work">
      <StepRail selected={selected} onSelect={handleSelect} />

      {/* 主面板 */}
      <div className="wb-panel wb-panel--main">
        <div className="wb-panel__head">
          <div>
            <div className="wb-panel__head-title">
              步骤 {activeIdx + 1} · {WB_STEPS[activeIdx].label}
            </div>
            <div className="wb-panel__head-sub">{WB_STEPS[activeIdx].sub}</div>
          </div>
        </div>
        {reviewing && (
          <div className="wb-review-banner" role="status">
            <span className="wb-review-banner__text">↶ 正在回看已完成结果</span>
            <button type="button" className="wb-review-banner__back" onClick={returnToLive}>
              返回当前阶段
            </button>
          </div>
        )}
        <div className="wb-panel__scroll">{mainContent()}</div>
        {activeIdx === 0 && !(status === 'FAILED' || status === 'CANCELLED') ? (
          <div className="wb-panel__foot wb-panel__foot--generate">
            <div className="wb-footinfo">
              <span className="wb-form-hint">姓名必填；未填写的联系方式不进入简历。</span>
              {step1Error && (
                <span className="wb-footinfo__err" role="alert">
                  {step1Error}
                </span>
              )}
            </div>
            <div className="wb-footactions">
              {saveIndicator()}
              <button
                type="button"
                className="wb-btn wb-btn--primary wb-form-actions__primary"
                onClick={handleGenerate}
                disabled={!step1Generatable || generatePending}
              >
                {generatePending ? '正在生成…' : '生成岗位简历 →'}
              </button>
            </div>
          </div>
        ) : (
          <div className="wb-panel__foot">{saveIndicator()}</div>
        )}
      </div>

      {/* 说明栏 */}
      <div className="wb-panel wb-panel--aside">{asideContent()}</div>
    </div>
  )
}