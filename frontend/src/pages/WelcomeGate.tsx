import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { useServices } from '../services'
import GeneratePage from './GeneratePage'

/**
 * V2.1.0（T7）：欢迎双冷启动门控 —— 位于路由 "/"。
 *
 * 真实门控：以 useServices().experience.list() 判断「我的经历」是否为空。
 * - 有经历 → 渲染现有 GeneratePage（DS-002 生成工作台）；
 * - 无经历 → 渲染欢迎视图（两条路径卡 + 三条原则）；
 * - 读取失败 → 显示可见错误与重试，绝不渲染假状态。
 *
 * 欢迎页仅提供两条真实/诚实路径：
 * - 卡 A「我有一份现有简历」→ 跳转 /profile?import=1（ProfilePage 识别后打开导入弹窗）；
 * - 卡 B「我还没有简历」→ Coming Soon：点击仅展示可见提示，不调 API、不落任何状态。
 */
export default function WelcomeGate() {
  const services = useServices()
  const [state, setState] = useState<
    | { phase: 'loading' }
    | { phase: 'has-experiences' }
    | { phase: 'empty' }
    | { phase: 'error'; message: string }
  >({ phase: 'loading' })

  const check = useCallback(async () => {
    setState({ phase: 'loading' })
    try {
      const list = await services.experience.list()
      setState(list.length > 0 ? { phase: 'has-experiences' } : { phase: 'empty' })
    } catch (e) {
      setState({ phase: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [services])

  useEffect(() => {
    void check()
  }, [check])

  if (state.phase === 'has-experiences') {
    return <GeneratePage />
  }

  return (
    <div className="page welcome-page">
      {state.phase === 'loading' && (
        <p className="muted" style={{ padding: 'var(--s8) 0', textAlign: 'center' }}>
          正在读取本地经历…
        </p>
      )}

      {state.phase === 'error' && (
        <div className="empty">
          <p className="empty__title">无法读取本地经历</p>
          <p className="empty__desc">读取「我的经历」失败：{state.message}。请确认本地服务可用后重试。</p>
          <Button variant="secondary" onClick={() => void check()}>
            重试
          </Button>
        </div>
      )}

      {state.phase === 'empty' && <WelcomeView />}
    </div>
  )
}

/** 欢迎视图：无经历时的冷启动页面（语义对齐 DS-002 welcome 视图，视觉随 T8 统一对照）。 */
function WelcomeView() {
  // 卡 B「我还没有简历」为 Coming Soon：仅本地提示状态，不调 API、不落任何状态
  const [soonOpen, setSoonOpen] = useState(false)

  return (
    <>
      <div className="welcome-hero">
        <div className="welcome-eyebrow">简历助手 · 本地预览版</div>
        <h1 className="welcome-title">按岗位，一键生成可投递简历</h1>
        <p className="welcome-lead">
          提供真实经历与目标岗位，系统完成选材、表达与排版；每条内容都能回查所依据的事实，失败时输入可保留。
        </p>
      </div>

      <div className="welcome-paths">
        {/* 卡 A：真实上传路径 —— 进入「我的经历」并打开 PDF 导入弹窗 */}
        <Link className="path-card" to="/profile?import=1">
          <div className="path-card__head">
            <span className="path-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
              </svg>
            </span>
            <Badge tone="ok">Active · PDF 解析</Badge>
          </div>
          <h3>我有一份现有简历</h3>
          <p>
            上传 PDF，在本机完成解析与提取。AI 推断或补全的条目会请你逐条确认后再写入「我的经历」，随后即可进入生成。
          </p>
          <span className="path-card__cta">开始上传 →</span>
        </Link>

        {/* 卡 B：Coming Soon —— 只展示说明，点击仅给可见提示 */}
        <button
          type="button"
          className="path-card path-card--soon"
          aria-pressed={soonOpen}
          onClick={() => setSoonOpen((v) => !v)}
        >
          <div className="path-card__head">
            <span className="path-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </span>
            <Badge tone="neutral">即将上线</Badge>
          </div>
          <h3>我还没有简历</h3>
          <p>通过几次简短问答，把零散的经历整理成形。该功能即将上线。</p>
          <span className="path-card__cta">即将上线 →</span>
        </button>
      </div>

      {soonOpen && (
        <div className="notice notice--warn" role="status" style={{ marginTop: 0 }}>
          「对话整理经历」即将上线：上线后将围绕教育、实习、项目与技能做简短问答，每段事实经你确认后才会写入「我的经历」。在此之前，请先上传现有简历，或在「我的经历」中手工逐条新增。
        </div>
      )}

      <p className="welcome-manual">
        没有现成 PDF？也可以到{' '}
        <Link to="/profile">我的经历</Link> 手工逐条新增。
      </p>

      <div className="welcome-principles">
        <div className="principle">
          <h4>事实来自你</h4>
          <p>学校、公司、时间、结果只来自你上传或确认的内容；生成结果的每条内容都可逐条回查所依据的事实。</p>
        </div>
        <div className="principle">
          <h4>按岗位选材与表达</h4>
          <p>系统依据目标岗位决定选什么、怎么写，不让你先成为简历专家，也不把模板与字号当作主流程。</p>
        </div>
        <div className="principle">
          <h4>失败可见、输入可保留</h4>
          <p>材料不足或关键模型失败会被明确告知，且你已填写的身份信息与 JD 在一次生成尝试内不会被悄悄丢弃。</p>
        </div>
      </div>
    </>
  )
}
