import { useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

/**
 * V2.2.0 R3 / PLAN G07 / RESULT §R3-18 D：品牌区完整键盘语义。
 *
 * 统一支持 mouse click、Enter、Space、focus-visible，并返回工作台根路由 `/`；
 * 只做路由跳转，不清空当前 Task、不新建任务、不新增模型调用。
 *
 * 为什么要自建而不是直接用 `<NavLink>`：
 * - 原生 `<a>` 只在 Enter 时激活，Space 既不会激活链接，还会滚动页面；
 * - 置 `<a>` 保留原生语义（role=link、可聚焦、右键/中键行为），但显式接管
 *   click / Enter / Space 三条激活路径，并用 preventDefault 阻止 Space 滚动，
 *   同时对 key repeat 做闸门，保证**单次导航、无双激活**。
 */
export default function BrandLink({
  to = '/',
  className,
  label,
  children,
}: {
  to?: string
  className: string
  label: string
  children: React.ReactNode
}) {
  const navigate = useNavigate()
  const firedRef = useRef(0)

  const activate = useCallback(
    (e: React.SyntheticEvent) => {
      e.preventDefault()
      // 同一毫秒内的重复激活（如 Enter 触发的 click 与 keydown 同时到达）只允许一次导航。
      const now = Date.now()
      if (now - firedRef.current < 250) return
      firedRef.current = now
      navigate(to)
    },
    [navigate, to],
  )

  return (
    <a
      href={to}
      className={className}
      role="link"
      aria-label={label}
      tabIndex={0}
      data-role="brand-home"
      onClick={activate}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar' || e.key === 'Space') {
          if (e.repeat) {
            // 长按不重复导航；同时阻止 Space 的默认滚动。
            e.preventDefault()
            return
          }
          activate(e)
        }
      }}
    >
      {children}
    </a>
  )
}
