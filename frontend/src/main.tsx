import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import AppErrorBoundary from './components/ErrorBoundary'
import { realServices } from './services'
import { ServicesProvider } from './services'
import { AppStateProvider } from './state'
import './styles/tokens.css'
import './styles/global.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ServicesProvider services={realServices}>
      <AppStateProvider>
        <BrowserRouter>
          {/* V2.1.0 R21：应用级错误边界 —— 生产 build 与 onedir 均由 main.tsx 挂载 */}
          <AppErrorBoundary>
            <App />
          </AppErrorBoundary>
        </BrowserRouter>
      </AppStateProvider>
    </ServicesProvider>
  </StrictMode>,
)
