import { useMemo, useState } from 'react'
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
import { useNavigate } from 'react-router-dom'

import { useErrorMessage } from '../app/hooks/useErrorMessage'
import { useEscapeToClose } from '../app/hooks/useEscapeToClose'
import { usePageMetadata } from '../app/hooks/usePageMetadata'
import SectionHeading from '../components/SectionHeading'
import StatusBanner from '../components/StatusBanner'
import { useNodeCatalog } from '../workflow/hooks/useNodeCatalog'
import { NODE_CATEGORY_LABELS, NODE_CATEGORY_ORDER } from '../workflow/schema/nodeCategory'
import { NodeCategory, NodeManifest, WorkflowNavigationState, WorkflowOpenIntent, WorkflowTemplate } from '../workflow/schema/types'
import NodeCategoryFilterOption from './nodes/NodeCategoryFilterOption'
import NodePreviewCard from './nodes/NodePreviewCard'
import { type NodePreviewDetailItem } from './nodes/types'
import { NODE_MANIFEST_TEMPLATE } from './nodes/nodeManifest'
import { useNodeManifestImport } from './nodes/useNodeManifestImport'
import { useWorkflowTemplates } from './nodes/useWorkflowTemplates'
import WorkflowTemplateCard from './nodes/WorkflowTemplateCard'
import './NodesPage.css'

const NODE_CATEGORY_ICONS: Record<NodeCategory, LucideIcon> = {
    input: ArrowDownToLine,
    web: Globe,
    prompt: MessageSquare,
    model: BrainCircuit,
    memory: HardDrive,
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
    memory: 0,
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
    const description = node.description.trim().replace(/\s+/g, ' ')
    return description || 'No description provided.'
}

function formatNodeMatchSummary(count: number): string {
    return `${count} node${count === 1 ? '' : 's'} ${count === 1 ? 'matches' : 'match'} the current filters.`
}

function buildNodeDetails(node: NodeManifest): NodePreviewDetailItem[] {
    const parameterNames = node.parameters.map((parameter) => parameter.name)

    return [
        { label: 'Inputs', value: formatPortSummary(node.inputs.map((port) => port.name)) },
        { label: 'Outputs', value: formatPortSummary(node.outputs.map((port) => port.name)) },
        ...(parameterNames.length > 0 ? [{ label: 'Parameters', value: formatPortSummary(parameterNames) }] : []),
    ]
}

function getNodeControllers(node: NodeManifest): string[] {
    return (node.controllers ?? []).map((controller) => controller.name)
}

function buildTemplateFlowPreview(template: WorkflowTemplate): string[] {
    const nameByNodeType = new Map(template.required_nodes.map((manifest) => [manifest.id, manifest.name]))
    const previewSteps = template.definition.nodes.slice(0, 5).map((node) => nameByNodeType.get(node.node_type) ?? node.node_type)
    const remaining = template.definition.nodes.length - previewSteps.length

    if (remaining <= 0) {
        return previewSteps
    }

    return [...previewSteps, `+${remaining} more`]
}

export default function NodesPage() {
    usePageMetadata({
        title: 'Workflow Nodes Library',
        description:
            'Browse ParaGraph workflow nodes by category and import custom JSON manifests for execution-ready flows.',
    })

    const { catalog, loading, error, reload } = useNodeCatalog()
    const navigate = useNavigate()
    const [search, setSearch] = useState('')
    const [templateSearch, setTemplateSearch] = useState('')
    const [selectedCategories, setSelectedCategories] = useState<NodeCategory[]>(() => [...NODE_CATEGORY_ORDER])
    const getErrorMessage = useErrorMessage()
    const { templates, templatesLoading, templatesError } = useWorkflowTemplates({ getErrorMessage })
    const {
        importStatus,
        isImporting,
        isImportModalOpen,
        jsonText,
        closeImportModal,
        handleImport,
        handleJsonValidation,
        openImportModal,
        setJsonText,
    } = useNodeManifestImport({
        getErrorMessage,
        onImported: reload,
    })
    const importModalTitleId = 'nodes-import-modal-title'
    const importModalDescriptionId = 'nodes-import-modal-description'
    const pageBannerMessage = error || templatesError

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

    const filteredTemplates = useMemo(() => {
        const normalized = templateSearch.trim().toLowerCase()
        return templates.filter((template) => {
            if (!normalized) {
                return true
            }
            const haystack = `${template.name} ${template.description} ${template.tags.join(' ')}`.toLowerCase()
            return haystack.includes(normalized)
        })
    }, [templateSearch, templates])

    useEscapeToClose({
        enabled: isImportModalOpen && !isImporting,
        onClose: closeImportModal,
    })

    function toggleCategory(category: NodeCategory): void {
        setSelectedCategories((current) =>
            current.includes(category) ? current.filter((item) => item !== category) : [...current, category],
        )
    }

    function navigateToWorkflow(intent: WorkflowOpenIntent): void {
        navigate('/', { state: { workflow_intent: intent } satisfies WorkflowNavigationState })
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

                <StatusBanner className="nodes-banner" message={pageBannerMessage} />
                {!isImportModalOpen && importStatus && (
                    <StatusBanner
                        className="nodes-banner nodes-import-status"
                        message={importStatus}
                        role="alert"
                        ariaLive="assertive"
                    />
                )}

                <div className="nodes-split-layout">
                    <section className="nodes-split-panel nodes-split-panel-nodes">
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
                                {NODE_CATEGORY_ORDER.map((category) => (
                                    <NodeCategoryFilterOption
                                        key={category}
                                        category={category}
                                        count={categoryCounts[category]}
                                        checked={selectedCategories.includes(category)}
                                        icon={NODE_CATEGORY_ICONS[category]}
                                        onToggle={toggleCategory}
                                    />
                                ))}
                            </div>
                        </aside>

                        <div className="nodes-preview-shell">
                            <div className="nodes-preview-header">
                                <SectionHeading
                                    className="nodes-section-heading"
                                    title="Node preview"
                                    description={formatNodeMatchSummary(filteredCatalog.length)}
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
                                        onClick={openImportModal}
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
                                        const detailItems = buildNodeDetails(node)
                                        const controllerNames = getNodeControllers(node)
                                        return (
                                            <NodePreviewCard
                                                key={`${node.id}-${node.version}`}
                                                node={node}
                                                categoryLabel={NODE_CATEGORY_LABELS[node.category]}
                                                icon={Icon}
                                                summary={buildNodeExplanation(node)}
                                                detailItems={detailItems}
                                                controllerNames={controllerNames}
                                                onAddNode={(manifest) =>
                                                    navigateToWorkflow({
                                                        type: 'add-node',
                                                        node_id: manifest.id,
                                                        node_version: manifest.version,
                                                    })
                                                }
                                            />
                                        )
                                    })}
                            </div>
                        </div>
                    </section>
                        </div>
                    </section>

                    <section className="nodes-split-panel nodes-split-panel-templates">
                        <div className="nodes-templates-shell">
                            <div className="nodes-templates-header">
                                <SectionHeading
                                    className="nodes-section-heading"
                                    title="Templates"
                                    description="Load prebuilt workflows directly into the canvas."
                                />
                                <div className="nodes-templates-search">
                                    <input
                                        type="search"
                                        value={templateSearch}
                                        placeholder="Search templates"
                                        aria-label="Search templates"
                                        onChange={(event) => setTemplateSearch(event.target.value)}
                                    />
                                </div>
                            </div>

                            <div className="nodes-templates-grid" role="list" aria-label="Workflow templates">
                                {templatesLoading && <div className="nodes-empty">Loading templates...</div>}
                                {!templatesLoading && filteredTemplates.length === 0 && (
                                    <div className="nodes-empty">No templates match the current search.</div>
                                )}
                                {!templatesLoading &&
                                    filteredTemplates.map((template) => (
                                        <WorkflowTemplateCard
                                            key={template.id}
                                            template={template}
                                            flowPreview={buildTemplateFlowPreview(template)}
                                            onUseTemplate={navigateToWorkflow}
                                        />
                                    ))}
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
                            closeImportModal()
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
                                onClick={closeImportModal}
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
                            {importStatus && (
                                <StatusBanner
                                    className="nodes-banner nodes-import-status"
                                    message={importStatus}
                                    role="alert"
                                    ariaLive="assertive"
                                />
                            )}
                            <textarea
                                value={jsonText}
                                onChange={(event) => setJsonText(event.target.value)}
                                placeholder={NODE_MANIFEST_TEMPLATE}
                                rows={20}
                            />
                            <div className="nodes-import-actions">
                                <button type="button" onClick={closeImportModal} disabled={isImporting}>
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





