import { ReactNode } from 'react'

type StatusBannerProps = {
    message: ReactNode
    className: string
}

export default function StatusBanner({ message, className }: StatusBannerProps) {
    if (!message) {
        return null
    }

    return <div className={className}>{message}</div>
}
