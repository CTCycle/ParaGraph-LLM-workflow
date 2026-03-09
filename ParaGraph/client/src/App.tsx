import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import PlaceholderPage from './pages/PlaceholderPage'
import WorkflowPage from './pages/WorkflowPage'

export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<MainLayout />}>
                    <Route index element={<WorkflowPage />} />
                    <Route
                        path="config"
                        element={
                            <PlaceholderPage
                                title="Configurations"
                                description="Manage providers, defaults, and shared settings for workflow runs."
                            />
                        }
                    />
                    <Route
                        path="edit"
                        element={
                            <PlaceholderPage
                                title="Edit"
                                description="Editing tools will be expanded in the next iteration of the workflow builder."
                            />
                        }
                    />
                    <Route
                        path="help"
                        element={
                            <PlaceholderPage
                                title="Help"
                                description="Use Add Node, connect Prompt → LLM → Output, then click Run to execute your graph."
                            />
                        }
                    />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
            </Routes>
        </BrowserRouter>
    )
}
