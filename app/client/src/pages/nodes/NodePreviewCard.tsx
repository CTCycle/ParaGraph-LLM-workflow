import { Plus, type LucideIcon } from 'lucide-react'

import { type NodeManifest } from '../../workflow/schema/types'
import { type NodePreviewDetailItem } from './types'

type NodePreviewCardProps = {
    node: NodeManifest
    categoryLabel: string
    icon: LucideIcon
    summary: string
    detailItems: NodePreviewDetailItem[]
    controllerNames: string[]
    onAddNode: (manifest: NodeManifest) => void
}

export default function NodePreviewCard({
    node,
    categoryLabel,
    icon: Icon,
    summary,
    detailItems,
    controllerNames,
    onAddNode,
}: NodePreviewCardProps): JSX.Element {
    return (
        <article className="nodes-preview-row" role="listitem">
            <div className="nodes-preview-row-header">
                <div className="nodes-preview-icon">
                    <Icon size={17} strokeWidth={1.8} />
                </div>
                <div className="nodes-preview-title-group">
                    <div className="nodes-preview-title-row">
                        <h3>{node.name}</h3>
                        <span>{categoryLabel}</span>
                        <button
                            type="button"
                            className="nodes-node-add-button"
                            aria-label={`Add ${node.name} to canvas`}
                            title="Add to canvas"
                            onClick={() => onAddNode(node)}
                        >
                            <Plus size={14} strokeWidth={2.1} />
                        </button>
                    </div>
                </div>
            </div>
            <p className="nodes-preview-summary">{summary}</p>
            {controllerNames.length > 0 && (
                <div className="nodes-preview-controllers" aria-label={`${node.name} controllers`}>
                    <span className="nodes-preview-controllers-label">Controllers</span>
                    <div className="nodes-preview-controller-chips">
                        {controllerNames.map((controllerName) => (
                            <span key={`${node.id}-ctrl-${controllerName}`} className="nodes-preview-controller-chip">
                                {controllerName}
                            </span>
                        ))}
                    </div>
                </div>
            )}
            <dl className="nodes-preview-meta" aria-label={`${node.name} metadata`}>
                {detailItems.map((item) => (
                    <div key={`${node.id}-${item.label}`} className="nodes-preview-meta-item">
                        <dt>{item.label}</dt>
                        <dd>{item.value}</dd>
                    </div>
                ))}
            </dl>
        </article>
    )
}
