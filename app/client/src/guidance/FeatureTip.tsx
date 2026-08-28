import { X } from 'lucide-react'
import type { ReactNode } from 'react'

type FeatureTipProps = {
    title: string
    children: ReactNode
    actions?: ReactNode
    onDismiss: () => void
}

export default function FeatureTip({ title, children, actions, onDismiss }: FeatureTipProps) {
    return (
        <aside className="guidance-feature-tip" role="note" aria-label={title}>
            <div className="guidance-feature-tip-header">
                <div>
                    <span className="guidance-eyebrow">Helpful tip</span>
                    <h2>{title}</h2>
                </div>
                <button type="button" className="guidance-icon-button" aria-label={`Dismiss ${title}`} onClick={onDismiss}>
                    <X size={15} aria-hidden="true" />
                </button>
            </div>
            <div className="guidance-feature-tip-copy">{children}</div>
            <div className="guidance-feature-tip-actions">
                {actions}
                <button type="button" className="guidance-secondary-button" onClick={onDismiss}>Dismiss</button>
            </div>
        </aside>
    )
}
