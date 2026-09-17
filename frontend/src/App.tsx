import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
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
 * - `/`：DS-003 工作台（顶栏壳，步骤 1 身份与 JD）。
 * - 头像菜单子路由：/experiences（我的经历）、/records（我的简历）、/privacy（个人与隐私）。
 * - 保留 /upload、/system（开发者后台）+ /profile 旧入口别名。
 * - 其余匹配回退到 `/`。
 *
 * T07：`WorkbenchTaskProvider` 提升到路由最外层，使「我的经历/我的简历/个人与隐私」共享同一
 * 当前任务真源；从这些页面返回 `/` 时 task/input/阶段在内存中不丢失，无需重新触发拉取或调用
 * （PLAN §7.2 Gate：返回后不丢失、不新增调用）。
 */
export default function App() {
  return (
    <WorkbenchTaskProvider>
      <Routes>
        {/* 工作台：专用顶栏壳（无常驻侧栏） */}
        <Route
          path="/"
          element={
            <WorkbenchShell>
              <WorkbenchPage />
            </WorkbenchShell>
          }
        />

        {/* 次级页面：保留左侧栏壳 */}
        <Route element={<AppShell />}>
          <Route path="/experiences" element={<ProfilePage />} />
          <Route path="/records" element={<RecordsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/system" element={<SystemPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </WorkbenchTaskProvider>
  )
}