import { useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { WORKFLOW_ADDABLE_TYPES, WORKFLOW_ADD_EVENT, WORKFLOW_RUN_EVENT } from '../types'
import './MainLayout.css'

const NAV_ITEMS = [
    { to: '/config', label: 'Configurations' },
    { to: '/', label: 'Workflow' },
    { to: '/edit', label: 'Edit' },
    { to: '/help', label: 'Help' },
]

export default function MainLayout() {
    const location = useLocation()
    const [selectedType, setSelectedType] = useState<string>('Prompt')

    const isWorkflowPage = useMemo(() => location.pathname === '/', [location.pathname])

    const handleAddNode = () => {
        window.dispatchEvent(
            new CustomEvent(WORKFLOW_ADD_EVENT, {
                detail: { nodeType: selectedType },
            }),
        )
    }

    const handleRunWorkflow = () => {
        window.dispatchEvent(new Event(WORKFLOW_RUN_EVENT))
    }

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

                <div className="topbar-actions">
                    <select
                        aria-label="Node type"
                        value={selectedType}
                        onChange={(event) => setSelectedType(event.target.value)}
                        disabled={!isWorkflowPage}
                    >
                        {WORKFLOW_ADDABLE_TYPES.map((typeName) => (
                            <option key={typeName} value={typeName}>
                                {typeName}
                            </option>
                        ))}
                    </select>
                    <button type="button" onClick={handleAddNode} disabled={!isWorkflowPage}>
                        Add Node
                    </button>
                    <button type="button" className="run-btn" onClick={handleRunWorkflow} disabled={!isWorkflowPage}>
                        Run
                    </button>
                </div>
            </header>

            <main className="main-layout-content">
                <Outlet />
            </main>
        </div>
    )
}
