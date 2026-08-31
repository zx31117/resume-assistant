import type { ReactNode } from 'react'

interface CardProps {
  title?: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
}

export default function Card({
  title,
  subtitle,
  actions,
  children,
  className,
}: CardProps) {
  return (
    <section className={['card', className].filter(Boolean).join(' ')}>
      {(title || actions) && (
        <header className="card__head">
          <div>
            {title && <h2 className="card__title">{title}</h2>}
            {subtitle && <p className="card__subtitle">{subtitle}</p>}
          </div>
          {actions && <div className="card__actions">{actions}</div>}
        </header>
      )}
      {children && <div className="card__body">{children}</div>}
    </section>
  )
}