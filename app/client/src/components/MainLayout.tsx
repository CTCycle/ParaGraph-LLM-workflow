import { HelpCircle } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useGuidance } from '../guidance/GuidanceContext'
import TipsAndTricksDialog from '../guidance/TipsAndTricksDialog'
import './MainLayout.css'

const NAV_ITEMS = [
    { to: '/', label: 'Workflow' },
    { to: '/nodes', label: 'Nodes' },
    { to: '/models', label: 'Models' },
    { to: '/config', label: 'Configurations' },
]

export default function MainLayout() {
    const location = useLocation()
    const navigate = useNavigate()
    const { requestTour } = useGuidance()
    const [isTipsOpen, setIsTipsOpen] = useState(false)

    function replayEditorTour(): void {
        setIsTipsOpen(false)
        requestTour('editor')
        if (location.pathname !== '/') {
            navigate('/')
        }
    }

    return (
        <div className="main-layout">
            <div
                className="desktop-viewport-gate"
                role="alert"
                aria-label="Desktop window requirement"
            >
                <div className="desktop-viewport-gate-card">
                    <strong>Desktop window required</strong>
                    <p>
                        ParaGraph requires a desktop browser window at least 1024 pixels wide. Widen or maximize the
                        window to continue.
                    </p>
                </div>
            </div>

            <header className="topbar">
                <div className="topbar-brand">ParaGraph</div>
                <nav className="topbar-nav" aria-label="Main navigation">
                    {NAV_ITEMS.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            end={item.to === '/'}
                            className={({ isActive }) => `topbar-link${isActive ? ' active' : ''}`}
                        >
                            {item.label}
                        </NavLink>
                    ))}
                </nav>
                <button
                    type="button"
                    className="guidance-topbar-button"
                    aria-expanded={isTipsOpen}
                    aria-controls="tips-and-tricks-dialog"
                    aria-haspopup="dialog"
                    onClick={() => setIsTipsOpen(true)}
                >
                    <HelpCircle size={15} aria-hidden="true" />
                    Help
                </button>
            </header>

            <main className="main-layout-content">
                <Outlet />
            </main>

            <TipsAndTricksDialog
                isOpen={isTipsOpen}
                onClose={() => setIsTipsOpen(false)}
                onReplayTour={replayEditorTour}
                onBrowseTemplates={() => {
                    setIsTipsOpen(false)
                    navigate('/nodes#workflow-templates')
                }}
                onOpenConfigurations={() => {
                    setIsTipsOpen(false)
                    navigate('/config')
                }}
            />
        </div>
    )
}
