import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发模式：Vite dev server 将 /api 代理到本地后端（127.0.0.1:8000），
// 避免启用跨来源 CORS；生产模式由 FastAPI 同源托管构建产物，无需代理。
export default defineConfig({
  plugins: [react()],
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