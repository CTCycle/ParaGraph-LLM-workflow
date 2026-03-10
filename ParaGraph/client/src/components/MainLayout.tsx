import { NavLink, Outlet } from 'react-router-dom'
import './MainLayout.css'

const NAV_ITEMS = [
    { to: '/', label: 'Workflow' },
    { to: '/nodes', label: 'Nodes' },
]

export default function MainLayout() {
    return (
        <div className="main-layout">
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
