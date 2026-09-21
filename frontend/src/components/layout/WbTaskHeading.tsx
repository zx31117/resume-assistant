import type { ReactNode } from 'react'

/**
 * V2.2.0 R2-16 返工/DS-003：二级页面页头（对应冻结原型 subpage 的 task-heading）。
 * eyebrow「YOUR NEXT CHAPTER」+ h1 + 描述 + 右操区，统一所有头像菜单子页的页壳。
 */
export default function WbTaskHeading({
  title,
  desc,
  actions,
}: {
  title: string
  desc?: string
  actions?: ReactNode
}) {
  return (
    <div className="wb-task-heading">
      <div>
        <div className="wb-task-heading__eyebrow">YOUR NEXT CHAPTER</div>
        <h1 className="wb-task-heading__h1" id="main-title" tabIndex={-1}>
          {title}
        </h1>
        {desc && <p className="wb-task-heading__sub">{desc}</p>}
      </div>
      {actions && <div className="wb-task-heading__actions">{actions}</div>}
    </div>
  )
}