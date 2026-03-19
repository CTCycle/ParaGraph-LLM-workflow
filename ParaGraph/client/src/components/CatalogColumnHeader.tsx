import { ReactNode } from 'react'

type CatalogColumnHeaderProps = {
    title: string
    description: string
    actionLabel: string
    busyLabel: string
    disabled: boolean
    isBusy: boolean
    actionIcon?: ReactNode
    onAction: () => void
}

export default function CatalogColumnHeader({
    title,
    description,
    actionLabel,
    busyLabel,
    disabled,
    isBusy,
    actionIcon,
    onAction,
}: CatalogColumnHeaderProps) {
    return (
        <div className="models-column-header">
            <div>
                <h2>{title}</h2>
                <p>{description}</p>
            </div>
            <button type="button" onClick={onAction} disabled={disabled}>
                {actionIcon}
                {isBusy ? busyLabel : actionLabel}
            </button>
        </div>
    )
}
