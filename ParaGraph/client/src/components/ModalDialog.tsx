import { ReactNode } from 'react'

type ModalDialogProps = {
    isOpen: boolean
    ariaLabel: string
    title: string
    description: string
    children: ReactNode
    actions: ReactNode
}

export default function ModalDialog({
    isOpen,
    ariaLabel,
    title,
    description,
    children,
    actions,
}: ModalDialogProps) {
    if (!isOpen) {
        return null
    }

    return (
        <div className="config-modal-backdrop" role="presentation">
            <div className="config-modal" role="dialog" aria-modal="true" aria-label={ariaLabel}>
                <h3>{title}</h3>
                <p>{description}</p>
                {children}
                <div className="config-modal-actions">{actions}</div>
            </div>
        </div>
    )
}
