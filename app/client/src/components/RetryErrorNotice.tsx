type RetryErrorNoticeProps = {
    message: string
    onRetry: () => void
    className?: string
    retryLabel?: string
}

export default function RetryErrorNotice({
    message,
    onRetry,
    className = 'models-error',
    retryLabel = 'Retry',
}: RetryErrorNoticeProps) {
    return (
        <div className={className}>
            <span>{message}</span>
            <button type="button" onClick={onRetry}>
                {retryLabel}
            </button>
        </div>
    )
}

