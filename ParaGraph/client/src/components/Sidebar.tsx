import { BrainCircuit, FileSearch, FileStack } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import './Sidebar.css'

const navItems = [
    { path: '/dataset', icon: FileStack, label: 'Dataset' },
    { path: '/training', icon: BrainCircuit, label: 'Training' },
    { path: '/inference', icon: FileSearch, label: 'Inference' },
]

export default function Sidebar() {
    return (
        <nav className="sidebar" aria-label="Primary navigation">
            {navItems.map((item) => (
                <NavLink
                    key={item.path}
                    to={item.path}
                    title={item.label}
                    className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
                >
                    <item.icon size={24} />
                    <span className="sidebar-link-label">{item.label}</span>
                </NavLink>
            ))}
        </nav>
    )
}
