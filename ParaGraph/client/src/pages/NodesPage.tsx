import { FormEvent, useMemo, useState } from 'react'

import StatusBanner from '../components/StatusBanner'
import { importNodeManifest } from '../app/services/workflowApi'
import { useNodeCatalog } from '../workflow/hooks/useNodeCatalog'
import { NodeManifest } from '../workflow/schema/types'
import { NODE_CATEGORY_LABELS, NodeCategoryFilter, toNodeCategoryFilter } from '../workflow/schema/nodeCategory'
import './NodesPage.css'

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
}

function isNodeManifest(value: unknown): value is NodeManifest {
    if (!isRecord(value)) {
        return false
    }

    const ui = value.ui
    const runtime = value.runtime

    return (
        typeof value.id === 'string' &&
        typeof value.version === 'number' &&
        typeof value.name === 'string' &&
        typeof value.category === 'string' &&
        typeof value.description === 'string' &&
        Array.isArray(value.inputs) &&
        Array.isArray(value.outputs) &&
        Array.isArray(value.parameters) &&
        isRecord(ui) &&
        isRecord(runtime)
    )
}

export default function NodesPage() {
    const { catalog, loading, error, reload } = useNodeCatalog()
    const [search, setSearch] = useState('')
    const [category, setCategory] = useState<NodeCategoryFilter>('all')
    const [jsonText, setJsonText] = useState('')
    const [importStatus, setImportStatus] = useState<string | null>(null)
    const [isImporting, setIsImporting] = useState(false)

    const filteredCatalog = useMemo(() => {
        const normalized = search.trim().toLowerCase()
        return catalog.filter((node) => {
            if (category !== 'all' && node.category !== category) {
                return false
            }
            if (!normalized) {
                return true
            }
            return `${node.name} ${node.id} ${node.description}`.toLowerCase().includes(normalized)
        })
    }, [catalog, category, search])

    function validateJson(): NodeManifest {
        const parsed: unknown = JSON.parse(jsonText)
        if (!isNodeManifest(parsed)) {
            throw new Error('JSON must contain a node manifest object')
        }
        return parsed
    }

    async function handleImport(event: FormEvent<HTMLFormElement>): Promise<void> {
        event.preventDefault()
        setImportStatus(null)

        let manifest: NodeManifest
        try {
            manifest = validateJson()
            setImportStatus(`Valid manifest: ${manifest.id} v${manifest.version}`)
        } catch (validationError) {
            setImportStatus(validationError instanceof Error ? validationError.message : 'Invalid JSON payload')
            return
        }

        setIsImporting(true)
        try {
            const created = await importNodeManifest(manifest)
            setImportStatus(`Imported ${created.id} v${created.version}`)
            await reload()
            setJsonText('')
        } catch (importError) {
            setImportStatus(importError instanceof Error ? importError.message : 'Failed to import node manifest')
        } finally {
            setIsImporting(false)
        }
    }

    return (
        <section className="nodes-page">
            <header className="nodes-header">
                <p className="nodes-eyebrow">Nodes</p>
                <h1>Compact catalog and JSON import</h1>
                <p className="nodes-lede">Browse the live manifest registry and add new nodes directly from JSON.</p>
            </header>

            <StatusBanner className="nodes-banner" message={error || importStatus} />

            <div className="nodes-layout">
                <section className="nodes-panel">
                    <div className="nodes-panel-header">
                        <div>
                            <h2>Node Preview</h2>
                            <p>{filteredCatalog.length} visible</p>
                        </div>
                        <div className="nodes-tools">
                            <input
                                type="search"
                                value={search}
                                placeholder="Search nodes"
                                onChange={(event) => setSearch(event.target.value)}
                            />
                            <select value={category} onChange={(event) => setCategory(toNodeCategoryFilter(event.target.value))}>
                                <option value="all">All categories</option>
                                {Object.entries(NODE_CATEGORY_LABELS).map(([value, label]) => (
                                    <option key={value} value={value}>
                                        {label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="nodes-preview-list" role="list" aria-label="Node previews">
                        {loading && <div className="nodes-empty">Loading catalog...</div>}
                        {!loading && filteredCatalog.length === 0 && <div className="nodes-empty">No nodes matched.</div>}
                        {!loading &&
                            filteredCatalog.map((node) => (
                                <article key={`${node.id}-${node.version}`} className="nodes-preview-row" role="listitem">
                                    <div>
                                        <h3>{node.name}</h3>
                                        <p>{node.description}</p>
                                    </div>
                                    <span>{NODE_CATEGORY_LABELS[node.category]}</span>
                                </article>
                            ))}
                    </div>
                </section>

                <section className="nodes-panel">
                    <div className="nodes-panel-header">
                        <div>
                            <h2>Import JSON</h2>
                            <p>Paste a single node manifest.</p>
                        </div>
                    </div>

                    <form className="nodes-import-form" onSubmit={(event) => void handleImport(event)}>
                        <textarea
                            value={jsonText}
                            onChange={(event) => setJsonText(event.target.value)}
                            placeholder='{
  "id": "CUSTOM_NODE",
  "version": 1,
  "name": "Custom Node"
}'
                            rows={18}
                        />
                        <div className="nodes-import-actions">
                            <button
                                type="button"
                                onClick={() => {
                                    try {
                                        const manifest = validateJson()
                                        setImportStatus(`Valid manifest: ${manifest.id} v${manifest.version}`)
                                    } catch (validationError) {
                                        setImportStatus(
                                            validationError instanceof Error ? validationError.message : 'Invalid JSON payload',
                                        )
                                    }
                                }}
                            >
                                Validate
                            </button>
                            <button type="submit" disabled={isImporting || !jsonText.trim()}>
                                {isImporting ? 'Importing...' : 'Import Node'}
                            </button>
                        </div>
                    </form>
                </section>
            </div>
        </section>
    )
}
