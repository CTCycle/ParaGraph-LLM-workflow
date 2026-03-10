import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import ConfigurationsPage from './pages/ConfigurationsPage'
import NodesPage from './pages/NodesPage'
import WorkflowPage from './pages/WorkflowPage'

export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<MainLayout />}>
                    <Route index element={<WorkflowPage />} />
                    <Route path="nodes" element={<NodesPage />} />
                    <Route path="config" element={<ConfigurationsPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
            </Routes>
        </BrowserRouter>
    )
}
