import { X } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useId, useRef, type ReactNode } from 'react'

import { useEscapeToClose } from '../app/hooks/useEscapeToClose'
import { useDialogFocus } from './useDialogFocus'

type GuidanceDialogProps = {
    id?: string
    isOpen: boolean
    ariaLabel: string
    title: string
    description: string
    children: ReactNode
    actions?: ReactNode
    onRequestClose: () => void
}

export default function GuidanceDialog({
    id,
    isOpen,
    ariaLabel,
    title,
    description,
    children,
    actions,
    onRequestClose,
}: GuidanceDialogProps) {
    const titleId = useId()
    const descriptionId = useId()
    const dialogRef = useRef<HTMLDivElement | null>(null)
    const closeButtonRef = useRef<HTMLButtonElement | null>(null)

    useEscapeToClose({
        enabled: isOpen,
        onClose: onRequestClose,
    })
    useDialogFocus(isOpen, dialogRef, closeButtonRef)

    if (!isOpen) {
        return null
    }

    return createPortal(
        <div
            className="guidance-dialog-backdrop"
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget) {
                    onRequestClose()
                }
            }}
        >
            <div
                ref={dialogRef}
                id={id}
                className="guidance-dialog"
                role="dialog"
                aria-modal="true"
                aria-label={ariaLabel}
                aria-labelledby={titleId}
                aria-describedby={descriptionId}
                tabIndex={-1}
                onMouseDown={(event) => event.stopPropagation()}
            >
                <div className="guidance-dialog-header">
                    <div>
                        <span className="guidance-eyebrow">Tips &amp; Tricks</span>
                        <h2 id={titleId}>{title}</h2>
                    </div>
                    <button
                        ref={closeButtonRef}
                        type="button"
                        className="guidance-dialog-close"
                        aria-label={`Close ${ariaLabel}`}
                        onClick={onRequestClose}
                    >
                        <X size={16} aria-hidden="true" />
                    </button>
                </div>
                <p id={descriptionId} className="guidance-dialog-description">{description}</p>
                {children}
                {actions && <div className="guidance-dialog-actions">{actions}</div>}
            </div>
        </div>,
        document.body,
    )
}
