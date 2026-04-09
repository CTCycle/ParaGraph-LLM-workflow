import { FormEvent, useMemo, useState } from 'react'
import {
    ArrowDownToLine,
    ArrowUpToLine,
    BrainCircuit,
    Database,
    Globe,
    MessageSquare,
    HardDrive,
    GitBranch,
    Cog,
    Plus,
    Scissors,
    Search,
    X,
    type LucideIcon,
} from 'lucide-react'

import { useErrorMessage } from '../app/hooks/useErrorMessage'
import { useEscapeToClose } from '../app/hooks/useEscapeToClose'
import { usePageMetadata } from '../app/hooks/usePageMetadata'
import SectionHeading from '../components/SectionHeading'
import StatusBanner from '../components/StatusBanner'
import { importNodeManifest } from '../app/services/nodesApi'
import { useNodeCatalog } from '../workflow/hooks/useNodeCatalog'
import { NODE_CATEGORY_LABELS, NODE_CATEGORY_ORDER } from '../workflow/schema/nodeCategory'
import { NodeCategory, NodeManifest } from '../workflow/schema/types'
import './NodesPage.css'

const NODE_MANIFEST_TEMPLATE = `{
  "id": "CUSTOM_NODE",
  "version": 1,
  "name": "Custom Node",
  "category": "processing",
  "description": "Describe what the node does.",
  "inputs": [
    {
      "name": "input_text",
      "data_type": "TEXT",
      "required": true,
      "accepts_multiple": false,
      "description": "Incoming text payload."
    }
  ],
  "outputs": [
    {
      "name": "result",
      "data_type": "TEXT",
      "required": true,
      "accepts_multiple": false,
      "description": "Processed text output."
    }
  ],
  "parameters": [
    {
      "name": "mode",
      "data_type": "TEXT",
      "default": "default",
      "constraints": { "options": ["default", "fast"] },
      "ui_control": "select",
      "description": "Execution mode."
    }
  ],
  "ui": {
    "default_width": 320,
    "accent_color": "#4aa3ff",
    "icon": "sparkles",
    "collapsed_by_default": false
  },
  "runtime": {
    "executor_key": "custom.plugin",
    "cacheable": false,
    "deterministic": true,
    "side_effecting": false,
    "plugin": {
      "script_path": "plugins/custom_node.py",
      "entrypoint": "execute"
    }
  }
}`

const NODE_CATEGORY_ICONS: Record<NodeCategory, LucideIcon> = {
    input: ArrowDownToLine,
    web: Globe,
    prompt: MessageSquare,
    model: BrainCircuit,
    retrieval: Search,
    embeddings: BrainCircuit,
    processing: Cog,
    text_segmentation: Scissors,
    output: ArrowUpToLine,
    serialization: HardDrive,
    database: Database,
    vector_storage: Database,
    control: GitBranch,
}

const EMPTY_CATEGORY_COUNTS: Record<NodeCategory, number> = {
    input: 0,
    web: 0,
    prompt: 0,
    model: 0,
    retrieval: 0,
    embeddings: 0,
    processing: 0,
    text_segmentation: 0,
    output: 0,
    serialization: 0,
    database: 0,
    vector_storage: 0,
    control: 0,
}

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

function formatPortSummary(names: string[]): string {
    if (names.length === 0) {
        return 'None'
    }
    if (names.length <= 3) {
        return names.join(', ')
    }
    return `${names.slice(0, 3).join(', ')} +${names.length - 3}`
}

function buildNodeExplanation(node: NodeManifest): string {
    const description = node.description.trim()
    const inputCount = node.inputs.length
    const outputCount = node.outputs.length
    const ioSummary = `${inputCount} input${inputCount === 1 ? '' : 's'} -> ${outputCount} output${outputCount === 1 ? '' : 's'}`
    if (!description) {
        return `Node details: ${ioSummary}.`
    }
    return `${description} (${ioSummary})`
}

export default function NodesPage() {
    usePageMetadata({
        title: 'Workflow Nodes Library',
        description:
            'Browse ParaGraph workflow nodes by category and import custom JSON manifests for execution-ready flows.',
    })

    const { catalog, loading, error, reload } = useNodeCatalog()
    const [search, setSearch] = useState('')
    const [selectedCategories, setSelectedCategories] = useState<NodeCategory[]>(() => [...NODE_CATEGORY_ORDER])
    const [jsonText, setJsonText] = useState('')
    const [importStatus, setImportStatus] = useState<string | null>(null)
    const [isImporting, setIsImporting] = useState(false)
    const [isImportModalOpen, setIsImportModalOpen] = useState(false)
    const getErrorMessage = useErrorMessage()
    const importModalTitleId = 'nodes-import-modal-title'
    const importModalDescriptionId = 'nodes-import-modal-description'

    const categoryCounts = useMemo(() => {
        return NODE_CATEGORY_ORDER.reduce<Record<NodeCategory, number>>((counts, category) => {
            counts[category] = catalog.filter((node) => node.category === category).length
            return counts
        }, { ...EMPTY_CATEGORY_COUNTS })
    }, [catalog])

    const filteredCatalog = useMemo(() => {
        const normalized = search.trim().toLowerCase()
        return catalog.filter((node) => {
            if (!selectedCategories.includes(node.category)) {
                return false
            }
            if (!normalized) {
                return true
            }
            return `${node.name} ${node.description}`.toLowerCase().includes(normalized)
        })
    }, [catalog, search, selectedCategories])

    useEscapeToClose({
        enabled: isImportModalOpen && !isImporting,
        onClose: () => setIsImportModalOpen(false),
    })

    function toggleCategory(category: NodeCategory): void {
        setSelectedCategories((current) =>
            current.includes(category) ? current.filter((item) => item !== category) : [...current, category],
        )
    }

    function validateJson(): NodeManifest {
        const parsed: unknown = JSON.parse(jsonText)
        if (!isNodeManifest(parsed)) {
            throw new Error('JSON must contain a node manifest object')
        }
        return parsed
    }

    function handleJsonValidation(): void {
        try {
            const manifest = validateJson()
            setImportStatus(`Valid manifest: ${manifest.id} v${manifest.version}`)
        } catch (validationError) {
            setImportStatus(getErrorMessage(validationError, 'Invalid JSON payload'))
        }
    }

    async function handleImport(event: FormEvent<HTMLFormElement>): Promise<void> {
        event.preventDefault()
        setImportStatus(null)

        let manifest: NodeManifest
        try {
            manifest = validateJson()
            setImportStatus(`Valid manifest: ${manifest.id} v${manifest.version}`)
        } catch (validationError) {
            setImportStatus(getErrorMessage(validationError, 'Invalid JSON payload'))
            return
        }

        setIsImporting(true)
        try {
            const created = await importNodeManifest(manifest)
            setImportStatus(`Imported ${created.id} v${created.version}`)
            await reload()
            setJsonText('')
            setIsImportModalOpen(false)
        } catch (importError) {
            setImportStatus(getErrorMessage(importError, 'Failed to import node manifest'))
        } finally {
            setIsImporting(false)
        }
    }

    return (
        <>
            <section className="nodes-page">
                <header className="nodes-header">
                    <h1>Workflow Nodes Library</h1>
                    <p className="nodes-lede">
                        Explore built-in node types, then import custom JSON manifests for reusable workflow execution.
                    </p>
                </header>

                <StatusBanner className="nodes-banner" message={error || importStatus} />

                <div className="nodes-layout">
                    <section className="nodes-catalog-column">
                        <aside className="nodes-category-toolbar" aria-label="Category filters">
                            <SectionHeading
                                className="nodes-section-heading"
                                title="Categories"
                                description="Select the groups you want to keep in the preview list."
                            />
                            <div className="nodes-category-actions">
                                <button type="button" onClick={() => setSelectedCategories([...NODE_CATEGORY_ORDER])}>
                                    Select all
                                </button>
                                <button type="button" onClick={() => setSelectedCategories([])}>
                                    Clear
                                </button>
                            </div>
                            <div className="nodes-category-list">
                                {NODE_CATEGORY_ORDER.map((category) => {
                                    const Icon = NODE_CATEGORY_ICONS[category]
                                    return (
                                        <label key={category} className="nodes-category-option">
                                            <input
                                                type="checkbox"
                                                checked={selectedCategories.includes(category)}
                                                onChange={() => toggleCategory(category)}
                                            />
                                            <span className="nodes-category-option-icon">
                                                <Icon size={15} strokeWidth={1.8} />
                                            </span>
                                            <span className="nodes-category-option-text">{NODE_CATEGORY_LABELS[category]}</span>
                                            <span className="nodes-category-option-count">{categoryCounts[category]}</span>
                                        </label>
                                    )
                                })}
                            </div>
                        </aside>

                        <div className="nodes-preview-shell">
                            <div className="nodes-preview-header">
                                <SectionHeading
                                    className="nodes-section-heading"
                                    title="Node preview"
                                    description={`${filteredCatalog.length} nodes match the current filters.`}
                                />
                                <div className="nodes-preview-header-controls">
                                    <input
                                        type="search"
                                        value={search}
                                        placeholder="Search nodes"
                                        aria-label="Search nodes"
                                        onChange={(event) => setSearch(event.target.value)}
                                    />
                                    <button
                                        type="button"
                                        className="nodes-preview-add-button"
                                        aria-label="Open custom node JSON import"
                                        title="Import custom node JSON"
                                        onClick={() => setIsImportModalOpen(true)}
                                    >
                                        <Plus size={16} strokeWidth={2.1} />
                                    </button>
                                </div>
                            </div>

                            <div className="nodes-preview-list" role="list" aria-label="Node previews">
                                {loading && <div className="nodes-empty">Loading catalog...</div>}
                                {!loading && filteredCatalog.length === 0 && (
                                    <div className="nodes-empty">No nodes match the current filters.</div>
                                )}
                                {!loading &&
                                    filteredCatalog.map((node) => {
                                        const Icon = NODE_CATEGORY_ICONS[node.category]
                                        return (
                                            <article key={`${node.id}-${node.version}`} className="nodes-preview-row" role="listitem">
                                                <div className="nodes-preview-icon">
                                                    <Icon size={18} strokeWidth={1.8} />
                                                </div>
                                                <div className="nodes-preview-body">
                                                    <div className="nodes-preview-title-row">
                                                        <h3>{node.name}</h3>
                                                        <span>{NODE_CATEGORY_LABELS[node.category]}</span>
                                                    </div>
                                                    <p>{buildNodeExplanation(node)}</p>
                                                    <div className="nodes-preview-io">
                                                        <strong>In</strong>
                                                        <span>{formatPortSummary(node.inputs.map((port) => port.name))}</span>
                                                        <strong>Out</strong>
                                                        <span>{formatPortSummary(node.outputs.map((port) => port.name))}</span>
                                                    </div>
                                                </div>
                                            </article>
                                        )
                                    })}
                            </div>
                        </div>
                    </section>
                </div>
            </section>

            {isImportModalOpen && (
                <div
                    className="nodes-modal-backdrop"
                    role="presentation"
                    onMouseDown={(event) => {
                        if (event.target === event.currentTarget && !isImporting) {
                            setIsImportModalOpen(false)
                        }
                    }}
                >
                    <div
                        className="nodes-modal"
                        role="dialog"
                        aria-modal="true"
                        aria-label="Custom node JSON import"
                        aria-labelledby={importModalTitleId}
                        aria-describedby={importModalDescriptionId}
                    >
                        <div className="nodes-modal-header">
                            <SectionHeading
                                className="nodes-section-heading"
                                title="Custom node JSON import"
                                titleId={importModalTitleId}
                                descriptionId={importModalDescriptionId}
                                description="Start from the template, validate your manifest, then import it into the active catalog."
                            />
                            <button
                                type="button"
                                className="nodes-modal-close"
                                aria-label="Close import dialog"
                                onClick={() => setIsImportModalOpen(false)}
                                disabled={isImporting}
                            >
                                <X size={16} strokeWidth={2.2} />
                            </button>
                        </div>

                        <form className="nodes-import-form" onSubmit={(event) => void handleImport(event)}>
                            <div className="nodes-import-toolbar">
                                <span>Template includes metadata, ports, parameters, UI, runtime, and optional plugin script wiring.</span>
                                <button type="button" onClick={() => setJsonText(NODE_MANIFEST_TEMPLATE)}>
                                    Use template
                                </button>
                            </div>
                            <textarea
                                value={jsonText}
                                onChange={(event) => setJsonText(event.target.value)}
                                placeholder={NODE_MANIFEST_TEMPLATE}
                                rows={20}
                            />
                            <div className="nodes-import-actions">
                                <button type="button" onClick={() => setIsImportModalOpen(false)} disabled={isImporting}>
                                    Cancel
                                </button>
                                <button type="button" onClick={handleJsonValidation} disabled={!jsonText.trim() || isImporting}>
                                    Validate
                                </button>
                                <button type="submit" disabled={isImporting || !jsonText.trim()}>
                                    {isImporting ? 'Importing...' : 'Import Node'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </>
    )
}





