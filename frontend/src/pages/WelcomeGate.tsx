import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { useServices } from '../services'
import GeneratePage from './GeneratePage'

/**
 * V2.1.0 T12-R1：无简历初始页（冷启动门控）— 位于路由 "/"。
 *
 * 真实门控：以 useServices().experience.list() 判断「我的经历」是否为空。
 * - 有经历 → 渲染现有 GeneratePage（DS-002 生成工作台）；
 * - 无经历 → 渲染欢迎视图（两条路径卡 + 三条原则）；
 * - 读取失败 → 显示可见错误与重试，绝不渲染假状态。
 *
 * 欢迎页两条路径：
 * - 卡 A「我有一份现有简历」整张 = 上传 drop zone：单击立即打开系统文件选择器
 *   （不先跳到独立 /upload 页面），拖入 PDF 立即接收；选中后 navigate('/upload', { state: { file } })
 *   让 UploadPage 接管真实解析链；
 * - 卡 B「我还没有简历」保留占位外观但 disabled + aria-disabled：不进入演示、
 *   不产生 toast/假状态，符合 D-002 "即将上线"语义。
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

/** 欢迎视图：无经历时的冷启动页面（语义对齐 DS-002 welcome 视图）。 */
function WelcomeView() {
  // V2.1.0 T12-R1：左卡内嵌 file input 触发真实文件选择；选中后跳到 /upload 路由
  // 并通过 router state 把 File 对象带过去（仅在 SPA 内传递，刷新不保留：可接受）。
  const fileInputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const [dragOver, setDragOver] = useState(false)

  function takeFile(file: File | undefined) {
    if (!file) return
    // 类型校验：仅接受 PDF；其它（即使带 .pdf 扩展）一律提示。
    const isPdf = file.type === 'application/pdf' || /\.pdf$/i.test(file.name)
    if (!isPdf) {
      // 显式可见错误：不静默忽略，也不假通到解析页。
      window.alert('仅支持 PDF 文件，请重新选择。')
      return
    }
    navigate('/upload', { state: { file } })
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    takeFile(f)
    // 允许同一文件再次选择也能触发 change
    e.target.value = ''
  }

  function onCardDrop(e: React.DragEvent<HTMLLabelElement>) {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer?.files?.[0]
    takeFile(f)
  }

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
        {/* 卡 A：整张就是 drop zone —— 整张 label 包裹 file input。
            标签原生语义：点击 / 拖拽 / 键盘 Enter/Space 都会触发文件选择器。 */}
        <label
          className={'path-card path-card--drop' + (dragOver ? ' path-card--drag' : '')}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onCardDrop}
          htmlFor="welcome-pdf-input"
        >
          <input
            ref={fileInputRef}
            id="welcome-pdf-input"
            type="file"
            accept="application/pdf,.pdf"
            className="path-card__file"
            onChange={onFileChange}
            tabIndex={0}
            aria-label="选择 PDF 简历（单击或拖入）"
          />
          <div className="path-card__head">
            <span className="path-card__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
                <path d="M8 13h8M8 17h6" />
              </svg>
            </span>
            <Badge tone="ok">Active · PDF 解析</Badge>
          </div>
          <h3>我有一份现有简历</h3>
          <p>
            上传 PDF，在本机完成解析与提取。AI 推断或补全的条目会请你逐条确认后再写入「我的经历」，随后即可进入生成。
          </p>
          <span className="path-card__cta">开始上传 →</span>
        </label>

        {/* 卡 B：Coming Soon —— 整卡不可点击、不产生假状态。 */}
        <button
          type="button"
          className="path-card path-card--soon"
          disabled
          aria-disabled="true"
          aria-label="我还没有简历（即将上线）"
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
          <span className="path-card__cta path-card__cta--soon">即将上线 · 暂不可用</span>
        </button>
      </div>

      <p className="welcome-manual">
        没有现成 PDF？也可以到{' '}
        <Link to="/profile">我的经历</Link> 手工逐条新增，或点击{' '}
        <Link to="/upload">上传简历</Link> 直接进入上传视图。
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
