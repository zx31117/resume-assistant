import { Navigate, Route, Routes } from 'react-router-dom'
import WorkbenchShell from './components/layout/WorkbenchShell'
import WorkbenchPage from './pages/workbench/WorkbenchPage'
import { WorkbenchTaskProvider } from './pages/workbench/WorkbenchTaskContext'
import PrivacyPage from './pages/PrivacyPage'
import RecordsPage from './pages/RecordsPage'
import SystemPage from './pages/SystemPage'
import UploadPage from './pages/UploadPage'
import ProfilePage from './pages/ProfilePage'

/**
 * V2.2.0 T02/T03/T07：路由。
 * 所有页面统一使用 DS-003「Theme A 工作台顶栏壳」（WorkbenchShell，无旧常驻侧栏）：
 * - `/` 工作台；/experiences（我的经历）、/records（我的简历）、/privacy（个人与隐私）
 *   为头像菜单子页，复用同一顶栏壳与导航能力。
 * - 保留 /upload、/system（开发者后台）+ /profile 旧入口别名，同样置于 Theme A 壳下。
 * - 其余匹配回退到 `/`。
 *
 * T07：`WorkbenchTaskProvider` 提升到路由最外层，使「我的经历/我的简历/个人与隐私」共享同一
 * 当前任务真源；从这些页面返回 `/` 时 task/input/阶段在内存中不丢失，无需重新触发拉取或调用
 * （PLAN §7.2 Gate：返回后不丢失、不新增调用）。
 */
export default function App() {
  return (
    <WorkbenchTaskProvider>
      <WorkbenchShell>
        <Routes>
          <Route path="/" element={<WorkbenchPage />} />
          <Route path="/experiences" element={<ProfilePage />} />
          <Route path="/records" element={<RecordsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/system" element={<SystemPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </WorkbenchShell>
    </WorkbenchTaskProvider>
  )
}