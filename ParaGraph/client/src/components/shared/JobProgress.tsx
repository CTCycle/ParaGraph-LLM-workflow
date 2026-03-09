type JobProgressProps = {
    label: string
    progress: number
}

export default function JobProgress({ label, progress }: JobProgressProps) {
    return (
        <div style={{ width: '100%', marginTop: '1rem' }}>
            <div style={{ marginBottom: '0.4rem', fontSize: '0.9rem' }}>
                {label}: {Math.round(progress)}%
            </div>
            <div style={{ height: '10px', borderRadius: '8px', background: '#e2e8f0' }}>
                <div
                    style={{
                        height: '10px',
                        borderRadius: '8px',
                        width: `${Math.max(0, Math.min(100, progress))}%`,
                        background: '#2563eb',
                    }}
                />
            </div>
        </div>
    )
}
