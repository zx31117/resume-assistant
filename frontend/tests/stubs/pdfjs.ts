/**
 * pdfjs-dist 替身（仅组件测试用，经 vitest resolve.alias 注入）。
 *
 * 组件测试只验证「命中层契约 / 受控选择行为」，不验证 PDF 解析正确性——
 * 后者由浏览器 Gate 在最终包上以真实 pdf.js 验证。这里给出与 pdf.js 一致的
 * viewport 坐标换算（convertToViewportPoint：y 自底向上 → 自顶向下），
 * 使命中矩形与真实渲染语义同构。
 */
export const GlobalWorkerOptions: { workerSrc?: string } = {}

const BASE_W = 612 // A4 宽 pt
const BASE_H = 792 // A4 高 pt

function makePage() {
  return {
    getViewport: ({ scale }: { scale: number }) => ({
      width: BASE_W * scale,
      height: BASE_H * scale,
      convertToViewportPoint: (x: number, y: number): [number, number] => [
        x * scale,
        BASE_H * scale - y * scale,
      ],
    }),
    render: () => ({ promise: Promise.resolve(), cancel() {} }),
  }
}

export function getDocument(opts?: unknown) {
  // 替身只保证「单页文档 + viewport 坐标换算」契约；opts 内容不参与渲染语义。
  void opts
  const doc = {
    numPages: 1,
    getPage: async (n: number) => {
      if (!Number.isInteger(n) || n < 1) throw new Error(`bad page: ${n}`)
      return makePage()
    },
    destroy: async () => undefined,
  }
  return { promise: Promise.resolve(doc) }
}

export interface PDFDocumentProxy {
  numPages: number
  getPage(n: number): Promise<unknown>
  destroy(): Promise<void>
}

export interface PDFPageProxy {
  getViewport(p: { scale: number }): {
    width: number
    height: number
    convertToViewportPoint(x: number, y: number): [number, number]
  }
}

export interface RenderTask {
  promise: Promise<void>
  cancel(): void
}