import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import ConfigurationsPage from './pages/ConfigurationsPage'
import DatabaseSchemaPage from './pages/DatabaseSchemaPage'
import NodesPage from './pages/NodesPage'
import ModelsPage from './pages/ModelsPage'
import WorkflowPage from './pages/WorkflowPage'

export default function App() {
    return (
        <BrowserRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
            <Routes>
                <Route path="/" element={<MainLayout />}>
                <Route index element={<WorkflowPage />} />
                <Route path="database-schema/:nodeId" element={<DatabaseSchemaPage />} />
                <Route path="nodes" element={<NodesPage />} />
                    <Route path="models" element={<ModelsPage />} />
                    <Route path="config" element={<ConfigurationsPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
            </Routes>
        </BrowserRouter>
    )
}
