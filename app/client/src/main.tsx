import React from 'react'
import ReactDOM from 'react-dom/client'
import '@xyflow/react/dist/style.css'
import App from './App.tsx'
import './index.css'

const rootElement = document.getElementById('root')
if (!(rootElement instanceof HTMLElement)) {
    throw new Error('Root element "#root" was not found.')
}

ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>,
)
