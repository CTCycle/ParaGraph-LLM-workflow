import { ReactNode } from 'react'

type StatusBannerProps = {
    message: ReactNode
    className: string
    role?: 'alert' | 'status'
    ariaLive?: 'polite' | 'assertive'
}

export default function StatusBanner({ message, className, role, ariaLive }: StatusBannerProps) {
    if (!message) {
        return null
    }

    return (
        <div className={className} role={role} aria-live={ariaLive}>
            {message}
        </div>
    )
}
