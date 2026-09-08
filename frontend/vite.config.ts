import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

declare const process: { env?: Record<string, string | undefined> } // H6 test-only env 读取（避免引 node types）

// 开发模式：Vite dev server 将 /api 代理到本地后端（127.0.0.1:8000），
// 避免启用跨来源 CORS；生产模式由 FastAPI 同源托管构建产物，无需代理。
export default defineConfig({
  plugins: [react()],
  // V2.1.0 H6 test-only：注入目标由构建期常量控制；正式构建不设 VITE_H6_INJECT → null →
  // 注入 throw 不可达并被压缩消除，正式产物不含注入入口（PLAN §18.2.3/§18.3）。
  define: {
    __H6_INJECT__: JSON.stringify(process.env?.VITE_H6_INJECT ?? null),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})