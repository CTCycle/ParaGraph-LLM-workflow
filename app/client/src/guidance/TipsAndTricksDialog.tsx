import { Lightbulb } from 'lucide-react'

import GuidanceDialog from './GuidanceDialog'
import { TIPS_AND_TRICKS } from './guidanceContent'

type TipsAndTricksDialogProps = {
    isOpen: boolean
    onClose: () => void
    onReplayTour: () => void
    onBrowseTemplates: () => void
    onOpenConfigurations: () => void
}

export default function TipsAndTricksDialog({
    isOpen,
    onClose,
    onReplayTour,
    onBrowseTemplates,
    onOpenConfigurations,
}: TipsAndTricksDialogProps) {
    function runAction(action: 'templates' | 'config' | 'tour'): void {
        if (action === 'templates') {
            onBrowseTemplates()
        } else if (action === 'config') {
            onOpenConfigurations()
        } else {
            onReplayTour()
        }
    }

    return (
        <GuidanceDialog
            id="tips-and-tricks-dialog"
            isOpen={isOpen}
            ariaLabel="Tips and tricks"
            title="Tips & Tricks"
            description="A few shortcuts for building and running workflows with less trial and error."
            onRequestClose={onClose}
            actions={<button type="button" className="guidance-primary-button" onClick={onClose}>Close</button>}
        >
            <div className="guidance-tips-grid">
                {TIPS_AND_TRICKS.map((tip) => (
                    <article key={tip.id} className="guidance-tip-card">
                        <div className="guidance-tip-card-icon" aria-hidden="true">
                            <Lightbulb size={15} />
                        </div>
                        <div>
                            <h3>{tip.title}</h3>
                            <p>{tip.body}</p>
                            {tip.action && (
                                <button type="button" className="guidance-tip-card-action" onClick={() => runAction(tip.action!)}>
                                    {tip.action === 'templates' ? 'Browse templates' : tip.action === 'config' ? 'Open configurations' : 'Replay editor tour'}
                                </button>
                            )}
                        </div>
                    </article>
                ))}
            </div>
        </GuidanceDialog>
    )
}
