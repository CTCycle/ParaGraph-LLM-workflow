import { useEffect, useMemo, useState } from 'react'
import {
    NODE_ARTIFACTS,
    NODE_CONTRACT_SNIPPET,
    NODE_SYSTEM_PRINCIPLES,
    NODE_TAXONOMY,
    WORKFLOW_EXECUTABLE_TYPES,
} from '../nodeSystem'
import { fetchWorkflowCatalog } from '../services/workflow'
import { NodeCategory, WorkflowNodeDefinition, WorkflowPort } from '../types'
import './NodesPage.css'

type CategoryFilter = 'all' | NodeCategory
type CapabilityFilter = 'all' | 'runnable' | 'catalog-only'
type SortMode = 'recommended' | 'name' | 'runnable-first'

const CATEGORY_LABELS: Record<NodeCategory, string> = {
    input: 'Inputs',
    process: 'Process',
    output: 'Output',
}

const ARTIFACT_GROUPS = [
    { label: 'Conversation artifacts', keys: ['messages', 'conversation-memory'] },
    { label: 'LLM artifacts', keys: ['prompt-template', 'llm-response', 'structured-object', 'json-schema'] },
    { label: 'Retrieval artifacts', keys: ['document-set', 'embedding-vector', 'retriever-config', 'score'] },
    { label: 'Tooling/control artifacts', keys: ['tool-invocation', 'tool-result', 'decision', 'control-signal'] },
] as const

function truncateText(value: string, limit: number): string {
    if (value.length <= limit) {
        return value
    }
    return `${value.slice(0, limit - 1).trim()}...`
}

function summarizeLabels(labels: string[], limit: number): string {
    if (labels.length === 0) {
        return 'None'
    }

    const visible = labels.slice(0, limit)
    const hiddenCount = labels.length - visible.length

    if (hiddenCount <= 0) {
        return visible.join(', ')
    }

    return `${visible.join(', ')} +${hiddenCount} more`
}

function summarizePorts(ports: WorkflowPort[], limit: number): string {
    return summarizeLabels(ports.map((port) => port.label), limit)
}

function isDefined<T>(value: T | undefined): value is T {
    return value !== undefined
}

export default function NodesPage() {
    const [catalog, setCatalog] = useState<WorkflowNodeDefinition[]>([])
    const [catalogError, setCatalogError] = useState<string | null>(null)
    const [isCatalogLoading, setIsCatalogLoading] = useState(true)
    const [searchTerm, setSearchTerm] = useState('')
    const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all')
    const [capabilityFilter, setCapabilityFilter] = useState<CapabilityFilter>('all')
    const [sortMode, setSortMode] = useState<SortMode>('recommended')
    const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({})
    const [showFullContract, setShowFullContract] = useState(false)
    const [showJsonNodeHint, setShowJsonNodeHint] = useState(false)
    const [isArtifactsCollapsed, setIsArtifactsCollapsed] = useState(false)

    useEffect(() => {
        let mounted = true

        setIsCatalogLoading(true)

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
            .finally(() => {
                if (!mounted) {
                    return
                }
                setIsCatalogLoading(false)
            })

        return () => {
            mounted = false
        }
    }, [])

    const executableTypes = useMemo(() => new Set<string>(WORKFLOW_EXECUTABLE_TYPES), [])
    const filteredCatalog = useMemo(() => {
        const normalizedQuery = searchTerm.trim().toLowerCase()

        const filtered = catalog.filter((definition) => {
            if (categoryFilter !== 'all' && definition.category !== categoryFilter) {
                return false
            }

            if (capabilityFilter === 'runnable' && !executableTypes.has(definition.type)) {
                return false
            }

            if (capabilityFilter === 'catalog-only' && executableTypes.has(definition.type)) {
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

        if (sortMode === 'name') {
            return [...filtered].sort((left, right) => left.label.localeCompare(right.label))
        }

        if (sortMode === 'runnable-first') {
            return [...filtered].sort((left, right) => {
                const leftExecutable = executableTypes.has(left.type) ? 1 : 0
                const rightExecutable = executableTypes.has(right.type) ? 1 : 0

                if (leftExecutable !== rightExecutable) {
                    return rightExecutable - leftExecutable
                }

                return left.label.localeCompare(right.label)
            })
        }

        return filtered
    }, [catalog, categoryFilter, capabilityFilter, executableTypes, searchTerm, sortMode])

    const totalPorts = useMemo(() => catalog.reduce((count, definition) => count + definition.ports.length, 0), [catalog])
    const executableCount = useMemo(
        () => catalog.filter((definition) => executableTypes.has(definition.type)).length,
        [catalog, executableTypes],
    )
    const contractPreview = useMemo(() => NODE_CONTRACT_SNIPPET.trim().split('\n').slice(0, 10).join('\n'), [])
    const artifactLookup = useMemo(() => new Map(NODE_ARTIFACTS.map((artifact) => [artifact.key, artifact])), [])
    const groupedArtifacts = useMemo(
        () =>
            ARTIFACT_GROUPS.map((group) => ({
                label: group.label,
                artifacts: group.keys.map((key) => artifactLookup.get(key)).filter(isDefined),
            })),
        [artifactLookup],
    )

    function toggleNodeDetails(type: string): void {
        setExpandedNodes((current) => ({
            ...current,
            [type]: !current[type],
        }))
    }

    return (
        <section className="nodes-page">
            <header className="nodes-header">
                <p className="nodes-eyebrow">Node Registry</p>
                <h1>Browse typed nodes for workflow execution</h1>
                <p className="nodes-lede">
                    Inspect node definitions first, then open runtime references only when needed. The catalog remains the
                    primary workspace.
                </p>
            </header>

            {catalogError && <div className="nodes-alert">Catalog error: {catalogError}</div>}

            <section className="nodes-controls-panel" aria-label="Catalog controls">
                <div className="nodes-toolbar-row">
                    <input
                        type="search"
                        value={searchTerm}
                        className="nodes-search-input"
                        placeholder="Search nodes, ports, or parameters"
                        onChange={(event) => setSearchTerm(event.target.value)}
                    />
                    <label className="nodes-sort">
                        <span>Sort</span>
                        <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)}>
                            <option value="recommended">Recommended</option>
                            <option value="name">Name</option>
                            <option value="runnable-first">Runnable first</option>
                        </select>
                    </label>
                </div>

                <div className="nodes-filter-row">
                    <div className="nodes-filter-group" role="group" aria-label="Node category filters">
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

                    <div className="nodes-filter-group" role="group" aria-label="Node capability filters">
                        <button
                            type="button"
                            className={capabilityFilter === 'all' ? 'active' : ''}
                            onClick={() => setCapabilityFilter('all')}
                        >
                            Any capability
                        </button>
                        <button
                            type="button"
                            className={capabilityFilter === 'runnable' ? 'active' : ''}
                            onClick={() => setCapabilityFilter('runnable')}
                        >
                            Runnable
                        </button>
                        <button
                            type="button"
                            className={capabilityFilter === 'catalog-only' ? 'active' : ''}
                            onClick={() => setCapabilityFilter('catalog-only')}
                        >
                            Catalog only
                        </button>
                    </div>
                </div>

                <div className="nodes-summary-strip" aria-label="Catalog summary">
                    <span>
                        <strong>{catalog.length}</strong> catalog nodes
                    </span>
                    <span>
                        <strong>{executableCount}</strong> runnable
                    </span>
                    <span>
                        <strong>{totalPorts}</strong> typed ports
                    </span>
                    <span>
                        <strong>{filteredCatalog.length}</strong> results
                    </span>
                </div>
            </section>

            <div className="nodes-layout">
                <div className="nodes-main">
                    <section className="nodes-panel nodes-panel-catalog">
                        <div className="nodes-panel-header">
                            <div>
                                <h2>Node catalog</h2>
                                <p>Preview node contracts before opening details.</p>
                            </div>
                            <div className="nodes-catalog-actions">
                                <p className="nodes-result-count">{filteredCatalog.length} nodes</p>
                                <button
                                    type="button"
                                    className="nodes-add-json-button"
                                    onClick={() => setShowJsonNodeHint((current) => !current)}
                                >
                                    Add JSON node
                                </button>
                            </div>
                        </div>

                        {showJsonNodeHint && (
                            <p className="nodes-inline-hint">JSON node import wiring is reserved for the next update.</p>
                        )}

                        <div className="nodes-catalog-scroll" role="list" aria-label="Node preview list">
                            {isCatalogLoading && (
                                <div className="nodes-empty-results">
                                    <h3>Loading catalog...</h3>
                                    <p>Fetching node definitions from the server.</p>
                                </div>
                            )}

                            {!isCatalogLoading &&
                                filteredCatalog.map((definition) => {
                                    const isExecutable = executableTypes.has(definition.type)
                                    const inputPorts = definition.ports.filter((port) => port.direction === 'input')
                                    const outputPorts = definition.ports.filter((port) => port.direction === 'output')
                                    const isExpanded = Boolean(expandedNodes[definition.type])
                                    const parameterLabels = definition.parameters.map((parameter) => parameter.label)

                                    return (
                                        <article key={definition.type} className="node-row" role="listitem">
                                            <div className="node-row-main">
                                                <div className="node-row-title">
                                                    <h3>{definition.label}</h3>
                                                    <p>{truncateText(definition.description, 110)}</p>
                                                </div>
                                                <div className="node-row-meta">
                                                    <span className={`node-badge category-${definition.category}`}>
                                                        {CATEGORY_LABELS[definition.category]}
                                                    </span>
                                                    <span className={`node-badge ${isExecutable ? 'status-live' : 'status-draft'}`}>
                                                        {isExecutable ? 'Runnable' : 'Catalog only'}
                                                    </span>
                                                    <span className="node-row-type">{definition.type}</span>
                                                </div>
                                            </div>

                                            <div className="node-row-actions">
                                                <span>
                                                    <strong>{definition.parameters.length}</strong> parameters
                                                </span>
                                                <span>
                                                    <strong>{definition.ports.length}</strong> ports
                                                </span>
                                                <button
                                                    type="button"
                                                    className="node-row-toggle"
                                                    aria-expanded={isExpanded}
                                                    onClick={() => toggleNodeDetails(definition.type)}
                                                >
                                                    {isExpanded ? 'Hide schema' : 'View schema'}
                                                </button>
                                            </div>

                                            {isExpanded && (
                                                <div className="node-row-details">
                                                    <p>
                                                        <span>Inputs:</span> {summarizePorts(inputPorts, 3)}
                                                    </p>
                                                    <p>
                                                        <span>Outputs:</span> {summarizePorts(outputPorts, 3)}
                                                    </p>
                                                    <p>
                                                        <span>Parameters:</span> {summarizeLabels(parameterLabels, 6)}
                                                    </p>
                                                </div>
                                            )}
                                        </article>
                                    )
                                })}

                            {!isCatalogLoading && filteredCatalog.length === 0 && (
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
                                <p>Grouped artifact names for fast reference.</p>
                            </div>
                            <button
                                type="button"
                                className="nodes-compact-toggle"
                                aria-expanded={!isArtifactsCollapsed}
                                onClick={() => setIsArtifactsCollapsed((current) => !current)}
                            >
                                {isArtifactsCollapsed ? 'Expand' : 'Collapse'}
                            </button>
                        </div>
                        {!isArtifactsCollapsed && (
                            <div className="nodes-artifact-groups nodes-artifact-groups-compact">
                                {groupedArtifacts.map((group) => (
                                    <article key={group.label} className="nodes-artifact-group">
                                        <h3>{group.label}</h3>
                                        <ul className="nodes-artifact-pill-list">
                                            {group.artifacts.map((artifact) => (
                                                <li key={artifact.key} title={artifact.description}>
                                                    {artifact.label}
                                                </li>
                                            ))}
                                        </ul>
                                    </article>
                                ))}
                            </div>
                        )}
                    </section>
                </div>

                <aside className="nodes-reference-rail">
                    <section className="nodes-panel nodes-reference-panel">
                        <h2>System reference</h2>
                        <p className="nodes-reference-lede">Quick runtime rules and naming guidance.</p>

                        <details className="nodes-accordion" open>
                            <summary>Execution model</summary>
                            <div className="nodes-accordion-content">
                                <ul className="nodes-simple-list">
                                    {NODE_SYSTEM_PRINCIPLES.map((principle) => (
                                        <li key={principle.title}>
                                            <strong>{principle.title}:</strong> {principle.description}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </details>

                        <details className="nodes-accordion">
                            <summary>Node contract</summary>
                            <div className="nodes-accordion-content">
                                <pre>{showFullContract ? NODE_CONTRACT_SNIPPET : contractPreview}</pre>
                                <button
                                    type="button"
                                    className="contract-expand-button"
                                    onClick={() => setShowFullContract((current) => !current)}
                                >
                                    {showFullContract ? 'Show shorter preview' : 'Expand full contract'}
                                </button>
                            </div>
                        </details>

                        <details className="nodes-accordion">
                            <summary>Recommended taxonomy</summary>
                            <div className="nodes-accordion-content">
                                <ul className="nodes-simple-list nodes-taxonomy-list">
                                    {NODE_TAXONOMY.map((entry) => (
                                        <li key={entry.label}>
                                            <strong>{entry.label}:</strong> {entry.description}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </details>
                    </section>
                </aside>
            </div>
        </section>
    )
}
