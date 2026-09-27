import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

/**
 * V2.2.0 DOC_RETURNED 返工：前端组件级正反向测试配置（PLAN §R3-24 §24.4-4）。
 *
 * - environment=jsdom：PdfPreview 依赖真实 DOM 布局语义（clientWidth / ResizeObserver 由
 *   tests/setup.ts 提供确定性替身），不需要真实浏览器；
 * - pdfjs-dist 与 worker `?url` 一律 alias 到 tests/stubs/*：组件测试只验证**命中层契约与
 *   选择行为**，不做真实 PDF 解析（真实解析由浏览器 Gate 在最终包上验证）；
 * - define.__H6_INJECT__=null：与正式构建一致，测试环境不得存在 H6 注入入口。
 */
const stub = (p: string) => fileURLToPath(new URL(p, import.meta.url))

export default defineConfig({
  plugins: [react()],
  define: { __H6_INJECT__: 'null' },
  resolve: {
    alias: [
      { find: /^pdfjs-dist\/build\/pdf\.worker\.min\.mjs\?url$/, replacement: stub('./tests/stubs/pdfWorkerUrl.ts') },
      { find: /^pdfjs-dist$/, replacement: stub('./tests/stubs/pdfjs.ts') },
    ],
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
})