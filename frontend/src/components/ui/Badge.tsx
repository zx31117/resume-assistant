import type { ReactNode } from 'react'

type Tone = 'neutral' | 'ok' | 'warn' | 'danger' | 'accent'

export default function Badge({
  tone = 'neutral',
  children,
}: {
  tone?: Tone
  children: ReactNode
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}