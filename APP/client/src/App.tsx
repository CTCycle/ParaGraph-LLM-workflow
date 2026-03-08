import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppStateProvider } from './AppStateContext'
import MainLayout from './components/MainLayout'
import DatasetPage from './pages/DatasetPage'
import DatasetValidationPage from './pages/DatasetValidationPage'
import InferencePage from './pages/InferencePage'
import TrainingPage from './pages/TrainingPage'

export default function App() {
    return (
        <AppStateProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<MainLayout />}>
                        <Route index element={<Navigate to="/dataset" replace />} />
                        <Route path="dataset" element={<DatasetPage />} />
                        <Route path="dataset/validate/:datasetName" element={<DatasetValidationPage />} />
                        <Route path="training" element={<TrainingPage />} />
                        <Route path="inference" element={<InferencePage />} />
                    </Route>
                </Routes>
            </BrowserRouter>
        </AppStateProvider>
    )
}
