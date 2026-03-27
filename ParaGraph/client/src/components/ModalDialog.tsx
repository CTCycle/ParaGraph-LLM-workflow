import { ReactNode, useEffect, useId } from 'react'

type ModalDialogProps = {
    isOpen: boolean
    ariaLabel: string
    title: string
    description: string
    children: ReactNode
    actions: ReactNode
    onRequestClose?: () => void
}

export default function ModalDialog({
    isOpen,
    ariaLabel,
    title,
    description,
    children,
    actions,
    onRequestClose,
}: ModalDialogProps) {
    const titleId = useId()
    const descriptionId = useId()

    useEffect(() => {
        if (!isOpen || !onRequestClose) {
            return
        }

        const handleKeyDown = (event: KeyboardEvent): void => {
            if (event.key !== 'Escape') {
                return
            }
            event.preventDefault()
            onRequestClose()
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [isOpen, onRequestClose])

    if (!isOpen) {
        return null
    }

    return (
        <div
            className="config-modal-backdrop"
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget) {
                    onRequestClose?.()
                }
            }}
        >
            <div
                className="config-modal"
                role="dialog"
                aria-modal="true"
                aria-label={ariaLabel}
                aria-labelledby={titleId}
                aria-describedby={descriptionId}
                onMouseDown={(event) => event.stopPropagation()}
            >
                <h3 id={titleId}>{title}</h3>
                <p id={descriptionId}>{description}</p>
                {children}
                <div className="config-modal-actions">{actions}</div>
            </div>
        </div>
    )
}
