import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useWorkbenchTask } from '../../pages/workbench/WorkbenchTaskContext'
import type { TaskStatus } from '../../api/types'

/**
 * V2.2.0 T02：工作台顶栏壳（DS-003 顶栏 + 头像菜单）。
 * 顶栏 3 列：左 = 头像按钮/菜单，中 = 品牌，右 = 状态 + 开始新任务/取消生成。
 */
function statusText(status: TaskStatus | null, phase: string, saving: boolean, dirty: boolean, loadState: string, loadError: string | null): string {
  if (loadState === 'loading') return '正在读取任务…'
  if (loadError) return '任务读取失败'
  switch (status) {
    case null:
      return '新任务 · 尚未填写'
    case 'DRAFT':
      if (dirty) return '草稿未保存'
      return saving ? '保存中…' : '草稿已保存'
    case 'READY':
      return '草稿已保存'
    case 'RUNNING':
      return phase ? `生成中 · ${phase}` : '生成中 · 准备中'
    case 'SUCCEEDED':
      return '已完成 · 文件已就绪'
    case 'FAILED':
      return '生成失败'
    case 'CANCELLED':
      return '已取消 · 输入已保留'
    default:
      return '—'
  }
}

interface MenuItem {
  title: string
  sub: string
  to: string
}

const MENU_ITEMS: MenuItem[] = [
  { title: '我的经历', sub: '查看、补充与纠正事实', to: '/experiences' },
  { title: '我的简历', sub: '已生成的简历与文件', to: '/records' },
  { title: '个人与隐私', sub: '本次身份、数据使用边界', to: '/privacy' },
]

export default function WorkbenchShell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const { status, snapshotPhase, saving, dirty, loadState, loadError, cancel, startNewTask, generatePending } = useWorkbenchTask()
  const [menuOpen, setMenuOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)
  const avatarBtnRef = useRef<HTMLButtonElement>(null)

  // 点击外部 / Escape 关闭菜单（T09：关闭后焦点归还触发按钮，便于键盘继续操作）
  useEffect(() => {
    if (!menuOpen) return
    function closeAndRefocus() {
      setMenuOpen(false)
      avatarBtnRef.current?.focus()
    }
    function onDoc(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) closeAndRefocus()
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeAndRefocus()
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [menuOpen])

  const running = status === 'RUNNING'
  const statusLabel = statusText(status, snapshotPhase, saving, dirty, loadState, loadError)

  async function onPrimaryAction() {
    if (running) {
      await cancel()
    } else {
      startNewTask()
    }
  }

  function go(to: string) {
    setMenuOpen(false)
    navigate(to)
  }

  return (
    <div className="wb-shell">
      <header className="wb-topbar">
        <div className="wb-topbar__left">
          <div className="wb-avatar-wrap" ref={wrapRef}>
            <button
              type="button"
              ref={avatarBtnRef}
              className="wb-avatar-btn"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="我的菜单"
              onClick={() => setMenuOpen((v) => !v)}
            >
              <span className="wb-avatar-btn__circle" aria-hidden="true">
                我
              </span>
              <span className="wb-avatar-btn__label">我的</span>
              <svg className="wb-avatar-btn__chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="m6 9 6 6 6-6" />
              </svg>
            </button>
            {menuOpen && (
              <div className="wb-avatar-menu" role="menu" aria-label="我的">
                {MENU_ITEMS.map((it) => (
                  <button key={it.to} type="button" className="wb-avatar-menu__item" role="menuitem" onClick={() => go(it.to)}>
                    <span className="wb-avatar-menu__item-title">{it.title}</span>
                    <span className="wb-avatar-menu__item-sub">{it.sub}</span>
                  </button>
                ))}
                <div className="wb-avatar-menu__sep" aria-hidden="true" />
                <button type="button" className="wb-avatar-menu__back" role="menuitem" onClick={() => go('/')}>
                  <span aria-hidden="true">←</span> 返回当前生成任务
                </button>
              </div>
            )}
          </div>
        </div>

        {/* V220-R3-G07：品牌区可点击 / 键盘可达，仅路由跳转回工作台根 `/`，
            不清空当前 Task、不新建任务、不新增模型调用（区别于右侧 onPrimaryAction）。 */}
        <Link
          to="/"
          className="wb-topbar__center wb-brand-link"
          aria-label="简历助手，返回工作台首页"
        >
          <div className="wb-brand-logo" aria-hidden="true">
            简
          </div>
          <span className="wb-brand-name">
            简历助手
            <small>RESUME ASSISTANT</small>
          </span>
        </Link>

        <div className="wb-topbar__right">
          <span className="wb-top-status" aria-live="polite">
            {statusLabel}
          </span>
          {/* 无任务时开始新任务；运行中显示取消生成 */}
          <button
            type="button"
            className={running ? 'wb-btn wb-btn--ghost wb-btn--sm' : 'wb-btn wb-btn--primary wb-btn--sm'}
            onClick={() => void onPrimaryAction()}
            disabled={generatePending}
          >
            {running ? '取消生成' : '＋ 开始新任务'}
          </button>
        </div>
      </header>

      {/* 工作区内容由子路由填充（task-heading + work-grid） */}
      {children}
    </div>
  )
}