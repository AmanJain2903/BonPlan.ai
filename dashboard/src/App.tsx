import { Routes, Route, Navigate } from 'react-router-dom'
import DashboardLayout from './layouts/DashboardLayout'
import SkuManager from './pages/SkuManager'
import UsageViewer from './pages/UsageViewer'
import WorldMapBackground from './components/shared/WorldMapBackground'

function App() {
  return (
    <Routes>
      <Route path="/map" element={<WorldMapBackground />} />
      <Route path="/" element={<DashboardLayout />}>
        <Route index element={<Navigate to="/rate-limits/skus" replace />} />
        <Route path="rate-limits/skus" element={<SkuManager />} />
        <Route path="rate-limits/usage" element={<UsageViewer />} />
      </Route>
    </Routes>
  )
}

export default App
