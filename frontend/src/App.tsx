import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import ProfilePage from './pages/ProfilePage'
import PrivacyPage from './pages/PrivacyPage'
import SystemPage from './pages/SystemPage'
import WelcomeGate from './pages/WelcomeGate'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {/* V2.1.0 T7：/ 为真实门控 —— 无经历显示欢迎，有经历渲染 GeneratePage */}
        <Route path="/" element={<WelcomeGate />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        {/* 开发者后台：普通导航隐藏，仅通过侧栏脚注入口进入 */}
        <Route path="/system" element={<SystemPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
