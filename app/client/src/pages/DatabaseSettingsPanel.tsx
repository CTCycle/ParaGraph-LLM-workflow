import { useEffect, useState } from 'react'

import {
    applyDatabaseConfiguration,
    DatabaseConfiguration,
    DatabaseConfigurationStatus,
    fetchDatabaseConfiguration,
    testDatabaseConfiguration,
} from '../app/services/databaseApi'

type Props = { onDatabaseChanged: () => Promise<void> }

export default function DatabaseSettingsPanel({ onDatabaseChanged }: Props) {
    const [status, setStatus] = useState<DatabaseConfigurationStatus | null>(null)
    const [databasePath, setDatabasePath] = useState('database.db')
    const [insertBatchSize, setInsertBatchSize] = useState('1000')
    const [message, setMessage] = useState('')
    const [tone, setTone] = useState<'success' | 'error' | 'neutral'>('neutral')
    const [isLoading, setIsLoading] = useState(true)
    const [isTesting, setIsTesting] = useState(false)
    const [isApplying, setIsApplying] = useState(false)

    useEffect(() => {
        let mounted = true
        void fetchDatabaseConfiguration()
            .then((response) => {
                if (!mounted) return
                setStatus(response)
                setDatabasePath(response.database_path)
                setInsertBatchSize(String(response.insert_batch_size))
                if (response.error) {
                    setMessage(`Database unavailable: ${response.error}`)
                    setTone('error')
                }
            })
            .catch((error: unknown) => {
                if (mounted) {
                    setMessage(error instanceof Error ? error.message : 'Unable to load database configuration')
                    setTone('error')
                }
            })
            .finally(() => mounted && setIsLoading(false))
        return () => { mounted = false }
    }, [])

    function draft(): DatabaseConfiguration | null {
        const batchSize = Number(insertBatchSize)
        if (!databasePath.trim()) {
            setMessage('Enter a database file path.')
            setTone('error')
            return null
        }
        if (!Number.isInteger(batchSize) || batchSize < 1 || batchSize > 100000) {
            setMessage('Batch size must be a whole number from 1 to 100,000.')
            setTone('error')
            return null
        }
        return { backend: 'sqlite', database_path: databasePath.trim(), insert_batch_size: batchSize }
    }

    async function testConnection(): Promise<void> {
        const configuration = draft()
        if (!configuration) return
        setIsTesting(true)
        setMessage('')
        try {
            const result = await testDatabaseConfiguration(configuration)
            setMessage(result.message)
            setTone('success')
        } catch (error) {
            setMessage(error instanceof Error ? error.message : 'Connection test failed')
            setTone('error')
        } finally {
            setIsTesting(false)
        }
    }

    async function apply(): Promise<void> {
        const configuration = draft()
        if (!configuration) return
        setIsApplying(true)
        setMessage('')
        try {
            const active = await applyDatabaseConfiguration(configuration)
            setStatus(active)
            setDatabasePath(active.database_path)
            setInsertBatchSize(String(active.insert_batch_size))
            await onDatabaseChanged()
            setMessage('Database activated. No settings or other data were copied; this database has its own settings.')
            setTone('success')
        } catch (error) {
            setMessage(error instanceof Error ? error.message : 'Database change was not applied')
            setTone('error')
        } finally {
            setIsApplying(false)
        }
    }

    return (
        <section className="config-panel config-panel-column database-settings-panel" aria-labelledby="database-settings-heading">
            <div className="config-panel-header">
                <div>
                    <h2 id="database-settings-heading">Application database</h2>
                    <p>Choose where ParaGraph stores provider configurations, profiles, and workflow run history.</p>
                </div>
                <span className={`database-state ${status?.connected ? 'database-state-connected' : 'database-state-unavailable'}`}>
                    {isLoading ? 'Loading' : status?.connected ? 'Connected' : 'Unavailable'}
                </span>
            </div>

            <div className="database-active-summary" role="status">
                <span className="database-summary-label">Active backend</span>
                <strong>SQLite</strong>
                <span className="database-summary-label">Active file</span>
                <code>{status?.resolved_path || 'Not connected'}</code>
            </div>

            <form className="config-panel-fields database-settings-fields" onSubmit={(event) => event.preventDefault()}>
                <label>
                    <span>Database file path</span>
                    <input
                        aria-label="Database file path"
                        value={databasePath}
                        onChange={(event) => setDatabasePath(event.target.value)}
                        placeholder="database.db or an absolute path"
                        autoComplete="off"
                    />
                    <small>Relative paths are resolved from the application data directory.</small>
                </label>
                <label>
                    <span>Insert batch size</span>
                    <input
                        aria-label="Insert batch size"
                        type="number"
                        min="1"
                        max="100000"
                        step="1"
                        value={insertBatchSize}
                        onChange={(event) => setInsertBatchSize(event.target.value)}
                    />
                    <small>Rows written per batch when importing tabular data.</small>
                </label>
            </form>

            <p className="database-switch-note">Switching databases reloads settings from that database. Data is never copied between database files.</p>

            <div className="config-panel-actions database-settings-actions">
                <button type="button" onClick={() => void testConnection()} disabled={isLoading || isTesting || isApplying}>
                    {isTesting ? 'Testing…' : 'Test Connection'}
                </button>
                <button type="button" onClick={() => void apply()} disabled={isLoading || isTesting || isApplying}>
                    {isApplying ? 'Applying…' : 'Apply'}
                </button>
            </div>

            {message && <p className={`config-panel-note database-feedback database-feedback-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>{message}</p>}
        </section>
    )
}
