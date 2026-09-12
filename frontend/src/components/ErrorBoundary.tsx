import { Component, type ErrorInfo, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Button from './ui/Button'

/**
 * V2.1.0 R21 应用级错误边界。
 *
 * - 最外层包裹路由出口/工作台（main.tsx 挂载 <AppErrorBoundary>，生产 build 与
 *   onedir 同样可见），任一子组件渲染期抛错 → 显示固定布局的普通用户可理解错误界面；
 * - 恢复按钮只做「重试页面渲染（重置边界并重新渲染子树）」与「返回生成工作台
 *   （路由回退到 "/"）」，两者都不重新提交生成 API / 不创建新 operation / 不计费 /
 *   不删除或覆盖已成功 artifact；
 * - 诊断记录脱敏：仅记录组件栈 + 版本号 + 错误类型，绝不携带 error.message 或完整
 *   error.stack —— 不含 API Key / 完整履历 / JD / 正文。
 */

const APP_VERSION = '2.1.0'

interface ErrorBoundaryProps {
  children: ReactNode
  /** 「返回生成工作台」回调：调用方只做路由回退（navigate('/')）。 */
  onGoHome?: () => void
  /** 是否展示脱敏技术诊断折叠区（组件栈只含组件名，不涉业务正文）。 */
  showDiagnostics?: boolean
}

interface ErrorBoundaryState {
  hasError: boolean
  errorName: string | null
  componentStack: string
}

/** 组件栈脱敏/截断：只取有限行纯组件栈文本，过滤空行与空白。 */
function trimComponentStack(raw: string | null | undefined): string {
  return (raw ?? '')
    .split('\n')
    .map((l) => l.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .slice(0, 15)
    .join('\n')
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, errorName: null, componentStack: '' }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, errorName: error?.name || 'Error' }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    const componentStack = trimComponentStack(info?.componentStack)
    this.setState({ componentStack })
    // 脱敏诊断：不含 error.message / 完整 stack —— 不记录 API Key / 履历 / JD / 正文。
    console.error('[ErrorBoundary] 页面渲染异常（诊断已脱敏）', {
      appVersion: APP_VERSION,
      errorName: error?.name || 'Unknown',
      componentStack: componentStack || '(无组件栈)',
      occurredAt: new Date().toISOString(),
    })
  }

  handleRetry = () => {
    this.setState({ hasError: false, errorName: null, componentStack: '' })
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }
    const { onGoHome, showDiagnostics = true } = this.props
    return (
      <div className="page eb-page" role="alert" aria-live="assertive">
        <div className="eb-card">
          <p className="eb-eyebrow">简历助手 · 应用异常</p>
          <h1 className="eb-title">页面渲染时出了点问题</h1>
          <p className="eb-desc">
            刚才的操作没有继续执行。你已保存的经历与已成功生成的结果都留在本机，不会被改动或覆盖。
            可以重试一次页面渲染，或回到生成工作台继续。
          </p>
          <div className="eb-actions">
            <Button variant="primary" size="md" onClick={this.handleRetry}>
              重试页面渲染
            </Button>
            {onGoHome && (
              <Button variant="secondary" size="md" onClick={onGoHome}>
                返回生成工作台
              </Button>
            )}
          </div>
          {showDiagnostics && this.state.componentStack && (
            <details className="eb-diag">
              <summary>技术诊断（仅排障用）</summary>
              <div className="eb-diag__meta">
                版本 {APP_VERSION}
                {this.state.errorName ? ` · 异常类型 ${this.state.errorName}` : ''}
              </div>
              <pre className="eb-diag__stack">{this.state.componentStack}</pre>
            </details>
          )}
        </div>
      </div>
    )
  }
}

/**
 * 路由态错误边界：以 location.key 为 key，路由每次变化都重建边界，
 * 因此「返回生成工作台」即使发生在当前已在 "/" 的情况，也能清空错误态恢复子树。
 */
export default function AppErrorBoundary({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  return (
    <ErrorBoundary key={location.key} onGoHome={() => navigate('/')}>
      {children}
    </ErrorBoundary>
  )
}
