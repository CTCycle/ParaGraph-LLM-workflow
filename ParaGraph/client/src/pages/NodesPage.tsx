import { useEffect, useMemo, useState } from 'react'
import {
    NODE_ARTIFACTS,
    NODE_CONTRACT_SNIPPET,
    NODE_SYSTEM_PRINCIPLES,
    NODE_TAXONOMY,
    WORKFLOW_EXECUTABLE_TYPES,
} from '../nodeSystem'
import { fetchWorkflowCatalog } from '../services/workflow'
import { NodeCategory, WorkflowNodeDefinition } from '../types'
import './NodesPage.css'

type CategoryFilter = 'all' | NodeCategory

const CATEGORY_LABELS: Record<NodeCategory, string> = {
    input: 'Inputs',
    process: 'Process',
    output: 'Output',
}

export default function NodesPage() {
    const [catalog, setCatalog] = useState<WorkflowNodeDefinition[]>([])
    const [catalogError, setCatalogError] = useState<string | null>(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all')

    useEffect(() => {
        let mounted = true

        fetchWorkflowCatalog()
            .then((payload) => {
                if (!mounted) {
                    return
                }
                setCatalog(payload.nodes)
                setCatalogError(null)
            })
            .catch((error: unknown) => {
                if (!mounted) {
                    return
                }
                const message = error instanceof Error ? error.message : 'Failed to load workflow catalog'
                setCatalogError(message)
            })

        return () => {
            mounted = false
        }
    }, [])

    const executableTypes = useMemo(() => new Set<string>(WORKFLOW_EXECUTABLE_TYPES), [])
    const filteredCatalog = useMemo(() => {
        const normalizedQuery = searchTerm.trim().toLowerCase()

        return catalog.filter((definition) => {
            if (categoryFilter !== 'all' && definition.category !== categoryFilter) {
                return false
            }

            if (!normalizedQuery) {
                return true
            }

            const searchableText = [
                definition.type,
                definition.label,
                definition.description,
                definition.category,
                ...definition.parameters.map((parameter) => `${parameter.label} ${parameter.key}`),
                ...definition.ports.map((port) => `${port.label} ${port.data_type}`),
            ]
                .join(' ')
                .toLowerCase()

            return searchableText.includes(normalizedQuery)
        })
    }, [catalog, categoryFilter, searchTerm])

    const totalPorts = useMemo(() => catalog.reduce((count, definition) => count + definition.ports.length, 0), [catalog])
    const executableCount = useMemo(
        () => catalog.filter((definition) => executableTypes.has(definition.type)).length,
        [catalog, executableTypes],
    )

    return (
        <section className="nodes-page">
            <div className="nodes-hero">
                <div>
                    <p className="nodes-eyebrow">Node Registry</p>
                    <h1>Typed nodes for real workflow execution</h1>
                    <p className="nodes-lede">
                        ParaGraph should behave like a typed graph runtime, not a canvas that wires prompts together. This
                        page exposes the current node catalog, the artifact types that flow through it, and the separation
                        between the UI editor and the execution engine.
                    </p>
                </div>

                <div className="nodes-metrics">
                    <article>
                        <strong>{catalog.length}</strong>
                        <span>Catalog nodes</span>
                    </article>
                    <article>
                        <strong>{executableCount}</strong>
                        <span>Runnable now</span>
                    </article>
                    <article>
                        <strong>{totalPorts}</strong>
                        <span>Typed ports</span>
                    </article>
                </div>
            </div>

            {catalogError && <div className="nodes-alert">Catalog error: {catalogError}</div>}

            <div className="nodes-layout">
                <div className="nodes-main">
                    <section className="nodes-panel">
                        <div className="nodes-panel-header">
                            <div>
                                <h2>Catalog</h2>
                                <p>Explore node definitions exactly as the workflow client receives them from the server.</p>
                            </div>

                            <div className="nodes-toolbar">
                                <input
                                    type="search"
                                    value={searchTerm}
                                    placeholder="Search nodes, ports, or parameters"
                                    onChange={(event) => setSearchTerm(event.target.value)}
                                />
                                <div className="nodes-filters" role="tablist" aria-label="Node category filters">
                                    <button
                                        type="button"
                                        className={categoryFilter === 'all' ? 'active' : ''}
                                        onClick={() => setCategoryFilter('all')}
                                    >
                                        All
                                    </button>
                                    {(['input', 'process', 'output'] as const).map((category) => (
                                        <button
                                            key={category}
                                            type="button"
                                            className={categoryFilter === category ? 'active' : ''}
                                            onClick={() => setCategoryFilter(category)}
                                        >
                                            {CATEGORY_LABELS[category]}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <div className="nodes-catalog-grid">
                            {filteredCatalog.map((definition) => {
                                const isExecutable = executableTypes.has(definition.type)
                                const inputPorts = definition.ports.filter((port) => port.direction === 'input')
                                const outputPorts = definition.ports.filter((port) => port.direction === 'output')

                                return (
                                    <article key={definition.type} className="node-card">
                                        <div className="node-card-header">
                                            <div>
                                                <h3>{definition.label}</h3>
                                                <p>{definition.description}</p>
                                            </div>
                                            <div className="node-card-badges">
                                                <span className={`node-badge category-${definition.category}`}>
                                                    {CATEGORY_LABELS[definition.category]}
                                                </span>
                                                <span className={`node-badge ${isExecutable ? 'status-live' : 'status-draft'}`}>
                                                    {isExecutable ? 'Runnable' : 'Catalog only'}
                                                </span>
                                            </div>
                                        </div>

                                        <div className="node-card-meta">
                                            <div>
                                                <span>Type</span>
                                                <strong>{definition.type}</strong>
                                            </div>
                                            <div>
                                                <span>Parameters</span>
                                                <strong>{definition.parameters.length}</strong>
                                            </div>
                                            <div>
                                                <span>Ports</span>
                                                <strong>{definition.ports.length}</strong>
                                            </div>
                                        </div>

                                        <div className="node-card-section">
                                            <h4>Inputs</h4>
                                            {inputPorts.length > 0 ? (
                                                <ul>
                                                    {inputPorts.map((port) => (
                                                        <li key={port.handle}>
                                                            <strong>{port.label}</strong>
                                                            <span>{port.handle}</span>
                                                            <em>{port.data_type}</em>
                                                        </li>
                                                    ))}
                                                </ul>
                                            ) : (
                                                <p className="node-empty">No input ports.</p>
                                            )}
                                        </div>

                                        <div className="node-card-section">
                                            <h4>Outputs</h4>
                                            {outputPorts.length > 0 ? (
                                                <ul>
                                                    {outputPorts.map((port) => (
                                                        <li key={port.handle}>
                                                            <strong>{port.label}</strong>
                                                            <span>{port.handle}</span>
                                                            <em>{port.data_type}</em>
                                                        </li>
                                                    ))}
                                                </ul>
                                            ) : (
                                                <p className="node-empty">No output ports.</p>
                                            )}
                                        </div>

                                        <div className="node-card-section">
                                            <h4>Parameters</h4>
                                            {definition.parameters.length > 0 ? (
                                                <div className="node-parameter-list">
                                                    {definition.parameters.map((parameter) => (
                                                        <span key={parameter.key} className="node-parameter-chip">
                                                            {parameter.label}
                                                        </span>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="node-empty">No configurable parameters.</p>
                                            )}
                                        </div>
                                    </article>
                                )
                            })}

                            {filteredCatalog.length === 0 && (
                                <div className="nodes-empty-results">
                                    <h3>No nodes matched</h3>
                                    <p>Adjust the search term or category filter to inspect the rest of the registry.</p>
                                </div>
                            )}
                        </div>
                    </section>

                    <section className="nodes-panel">
                        <div className="nodes-panel-header">
                            <div>
                                <h2>Core artifacts</h2>
                                <p>These are the kinds of typed values an LLM-first graph should exchange.</p>
                            </div>
                        </div>
                        <div className="nodes-artifact-grid">
                            {NODE_ARTIFACTS.map((artifact) => (
                                <article key={artifact.key} className="nodes-artifact-card">
                                    <h3>{artifact.label}</h3>
                                    <p>{artifact.description}</p>
                                </article>
                            ))}
                        </div>
                    </section>
                </div>

                <aside className="nodes-sidebar">
                    <section className="nodes-panel">
                        <h2>Execution model</h2>
                        <div className="nodes-principles">
                            {NODE_SYSTEM_PRINCIPLES.map((principle) => (
                                <article key={principle.title}>
                                    <h3>{principle.title}</h3>
                                    <p>{principle.description}</p>
                                </article>
                            ))}
                        </div>
                    </section>

                    <section className="nodes-panel">
                        <h2>Node contract</h2>
                        <pre>{NODE_CONTRACT_SNIPPET}</pre>
                    </section>

                    <section className="nodes-panel">
                        <h2>Recommended taxonomy</h2>
                        <div className="nodes-taxonomy">
                            {NODE_TAXONOMY.map((entry) => (
                                <article key={entry.label}>
                                    <h3>{entry.label}</h3>
                                    <p>{entry.description}</p>
                                </article>
                            ))}
                        </div>
                    </section>
                </aside>
            </div>
        </section>
    )
}
