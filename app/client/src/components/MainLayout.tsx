import { NavLink, Outlet } from 'react-router-dom'
import './MainLayout.css'

const NAV_ITEMS = [
    { to: '/', label: 'Workflow' },
    { to: '/nodes', label: 'Nodes' },
    { to: '/models', label: 'Models' },
    { to: '/config', label: 'Configurations' },
]

export default function MainLayout() {
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
            </header>

            <main className="main-layout-content">
                <Outlet />
            </main>
        </div>
    )
}
