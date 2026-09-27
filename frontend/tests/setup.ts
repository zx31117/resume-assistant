import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

/**
 * 组件测试使用 vitest 的显式 API（不启用 globals），因此 @testing-library/react 的
 * 自动清理不会自动注册；这里显式挂载 cleanup，避免用例间 DOM 累积导致误判「多个元素」。
 */
afterEach(() => {
  cleanup()
})

/**
 * PdfPreview 的命中层几何依赖「预览滚动区可用宽度」与 ResizeObserver。
 * jsdom 不实现布局（clientWidth 恒为 0）也不提供 ResizeObserver，会导致命中层永远不渲染，
 * 使组件测试退化为「测不到东西」。这里给出确定性替身：可用宽度固定 800px，A4 页宽 612pt，
 * 于是 cssScale = 800/612，命中矩形可被确定性断言。
 */
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub

Object.defineProperty(Element.prototype, 'clientWidth', {
  configurable: true,
  get() {
    return 800
  },
})
Object.defineProperty(Element.prototype, 'clientHeight', {
  configurable: true,
  get() {
    return 600
  },
})

/**
 * jsdom 未实现 canvas 2D 上下文，会向 console.error 打「Not implemented」噪声，
 * 使「无 console 错误」的反向断言失去意义。渲染任务本身已由 pdfjs 替身接管，
 * 这里只需给出非 null 的 ctx，让真实渲染路径被走到（而不是在 `if (!ctx) continue` 处提前跳过）。
 */
Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  configurable: true,
  value: () => ({}),
})