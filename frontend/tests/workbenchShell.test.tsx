import { useEffect } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkbenchShell from '../src/components/layout/WorkbenchShell'
import PrivacyPage from '../src/pages/PrivacyPage'

/**
 * V2.2.0 DOC_RETURNED 返工：非工作台顶栏路由感知语义 + 返回无副作用（PLAN §R3-24 §24.3）。
 *
 * 正向：工作台 `/` 且 RUNNING → 取消；其他状态 → 开始新任务；
 *       experiences / records / privacy → 「返回工作台」，mouse / Enter / Space 三条激活路径均返回 `/`。
 * 反向：非工作台路由不提供「开始新任务」，不调用 startNewTask、不新建 Task、不产生任何网络请求。
 */

const ctx = vi.hoisted(() => ({
  status: 'DRAFT' as string | null,
  snapshotPhase: '',
  saving: false,
  dirty: false,
  loadState: 'idle',
  loadError: null as string | null,
  cancel: vi.fn(async () => undefined),
  startNewTask: vi.fn(),
  generatePending: false,
}))

vi.mock('../src/pages/workbench/WorkbenchTaskContext', () => ({
  useWorkbenchTask: () => ctx,
}))

function Probe({ onPath }: { onPath: (p: string) => void }) {
  const loc = useLocation()
  useEffect(() => {
    onPath(loc.pathname)
  }, [loc.pathname, onPath])
  return <div data-testid="path">{loc.pathname}</div>
}

function renderShell(initial: string, onPath: (p: string) => void = () => {}) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route
          path="*"
          element={
            <WorkbenchShell>
              <Probe onPath={onPath} />
            </WorkbenchShell>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  ctx.status = 'DRAFT'
  ctx.snapshotPhase = ''
  ctx.cancel.mockClear()
  ctx.startNewTask.mockClear()
  vi.stubGlobal('fetch', vi.fn())
})

describe('WorkbenchShell 工作台路由（正向）', () => {
  it('DRAFT → 主动作为「开始新任务」，点击调用 startNewTask 且不跳转', async () => {
    ctx.status = 'DRAFT'
    renderShell('/')
    const btn = await screen.findByRole('button', { name: /开始新任务/ })
    expect(btn.getAttribute('data-action')).toBe('new-task')
    expect(screen.queryByRole('link', { name: '返回工作台' })).toBeNull()
    await userEvent.setup().click(btn)
    expect(ctx.startNewTask).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('path').textContent).toBe('/')
  })

  it('RUNNING → 主动作为「取消生成」，点击调用 cancel 而非 startNewTask', async () => {
    ctx.status = 'RUNNING'
    ctx.snapshotPhase = 'MATCHING'
    renderShell('/')
    const btn = await screen.findByRole('button', { name: /取消生成/ })
    expect(btn.getAttribute('data-action')).toBe('cancel')
    await userEvent.setup().click(btn)
    expect(ctx.cancel).toHaveBeenCalledTimes(1)
    expect(ctx.startNewTask).not.toHaveBeenCalled()
  })

  it('RUNNING 状态下顶栏状态文案体现当前阶段', async () => {
    ctx.status = 'RUNNING'
    ctx.snapshotPhase = 'MATCHING'
    renderShell('/')
    await waitFor(() => expect(screen.getByText(/生成中 · MATCHING/)).toBeInTheDocument())
  })
})

describe('WorkbenchShell 非工作台路由（正向 + 反向）', () => {
  const routes = ['/experiences', '/records', '/privacy'] as const

  for (const [i, route] of routes.entries()) {
    const label = ['mouse 点击', 'Enter 键', 'Space 键'][i]
    it(`${route} → 「返回工作台」（${label}），返回 `/` 且不新建任务、不产生请求`, async () => {
      ctx.status = 'SUCCEEDED'
      const paths: string[] = []
      renderShell(route, (p) => paths.push(p))
      const back = await screen.findByRole('link', { name: '返回工作台' })
      expect(back.getAttribute('data-role')).toBe('top-back')
      expect(screen.queryByRole('button', { name: /开始新任务/ })).toBeNull()
      expect(screen.queryByText('开始新任务')).toBeNull()

      if (i === 0) {
        await userEvent.setup().click(back)
      } else {
        back.focus()
        expect(document.activeElement).toBe(back)
        await userEvent.setup().keyboard(i === 1 ? '{Enter}' : '{Space}')
      }

      await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/'))
      expect(paths.filter((p) => p === '/')).toHaveLength(1)
      // 反向：返回不调用 startNewTask、不发起任何请求（无模型调用、无建任务）
      expect(ctx.startNewTask).not.toHaveBeenCalled()
      expect(vi.mocked(fetch)).not.toHaveBeenCalled()
    })
  }

  it('返回工作台单飞：同一时刻连续两次 Enter 只导航一次', async () => {
    ctx.status = 'SUCCEEDED'
    const paths: string[] = []
    renderShell('/records', (p) => paths.push(p))
    const back = await screen.findByRole('link', { name: '返回工作台' })
    back.focus()
    fireEvent.keyDown(back, { key: 'Enter' })
    fireEvent.keyDown(back, { key: 'Enter' })
    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/'))
    expect(paths.filter((p) => p === '/')).toHaveLength(1)
    expect(ctx.startNewTask).not.toHaveBeenCalled()
  })

  it('非工作台路由的品牌区仍只回工作台 `/`，不新建任务', async () => {
    ctx.status = 'DRAFT'
    renderShell('/privacy')
    const brand = await screen.findByRole('link', { name: /返回工作台首页/ })
    expect(brand.getAttribute('data-role')).toBe('brand-home')
    await userEvent.setup().click(brand)
    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/'))
    expect(ctx.startNewTask).not.toHaveBeenCalled()
  })
})

describe('PrivacyPage 文案（不再把「开始新任务」描述为全局动作）', () => {
  it('明确「开始新任务」只在工作台出现，其他页面只提供「返回工作台」且不新建/不清空/无模型调用', async () => {
    render(
      <MemoryRouter initialEntries={['/privacy']}>
        <PrivacyPage />
      </MemoryRouter>,
    )
    const text = document.body.textContent ?? ''
    expect(text).toContain('该入口只出现在工作台')
    expect(text).toContain('返回不会新建任务、不会清空当前任务，也不产生任何模型调用')
    expect(text).not.toMatch(/开始新任务[^。]{0,20}(所有页面|任意页面|每个页面|全局)/)
  })
})