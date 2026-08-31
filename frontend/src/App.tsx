import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import GeneratePage from './pages/GeneratePage'
import ProfilePage from './pages/ProfilePage'
import SystemPage from './pages/SystemPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<GeneratePage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/system" element={<SystemPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}