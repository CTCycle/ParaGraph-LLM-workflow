import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import {
    Background,
    BackgroundVariant,
    Edge,
    MarkerType,
    Node,
    NodeProps,
    ReactFlow,
} from '@xyflow/react'

import { inspectDatabaseSchema } from '../app/services/nodesApi'
import {
    DatabaseSchemaResponse,
    DatabaseSchemaTable,
    NodeManifest,
} from '../workflow/schema/types'
import './DatabaseSchemaPage.css'

type DatabaseSchemaRouteState = {
    nodeId: string
    manifest: NodeManifest
    parameters: Record<string, unknown>
}

type TableNodeData = {
    table: DatabaseSchemaTable
}

function isDatabaseSchemaRouteState(value: unknown): value is DatabaseSchemaRouteState {
    if (typeof value !== 'object' || value === null) {
        return false
    }
    const record = value as Record<string, unknown>
    const manifest = record.manifest as Record<string, unknown> | undefined
    return (
        typeof record.nodeId === 'string'
        && typeof manifest?.id === 'string'
        && (manifest.id === 'SQL_DATABASE' || manifest.id === 'SQL_FILE_DATABASE')
        && typeof manifest.version === 'number'
        && typeof manifest.name === 'string'
        && typeof record.parameters === 'object'
        && record.parameters !== null
    )
}

function TableSchemaNode({ data }: NodeProps<Node<TableNodeData>>) {
    const table = data.table
    return (
        <article className="database-schema-table-node">
            <header>
                <strong title={table.name}>{table.name}</strong>
            </header>
            <ul>
                {table.columns.map((column) => {
                    const flags = [
                        column.primary_key ? 'PK' : null,
                        !column.nullable ? 'NN' : null,
                    ].filter(Boolean).join(' ')
                    return (
                        <li key={column.name}>
                            <span className="database-schema-column-name" title={column.name}>{column.name}</span>
                            <span className="database-schema-column-type" title={column.type}>{column.type}</span>
                            <span className="database-schema-column-flags">{flags}</span>
                        </li>
                    )
                })}
            </ul>
        </article>
    )
}

const nodeTypes = { tableSchema: TableSchemaNode }

function buildSchemaGraph(schema: DatabaseSchemaResponse): {
    nodes: Array<Node<TableNodeData>>
    edges: Edge[]
} {
    const nodes = schema.tables.map<Node<TableNodeData>>((table, index) => {
        const columnCount = Math.max(table.columns.length, 1)
        return {
            id: table.name,
            type: 'tableSchema',
            position: {
                x: (index % 3) * 360,
                y: Math.floor(index / 3) * Math.max(220, 90 + columnCount * 34),
            },
            data: { table },
        }
    })
    const tableNames = new Set(schema.tables.map((table) => table.name))
    const edges = schema.tables.flatMap<Edge>((table) =>
        table.foreign_keys
            .filter((foreignKey) => foreignKey.referred_table && tableNames.has(foreignKey.referred_table))
            .map((foreignKey, index) => ({
                id: `${table.name}-${foreignKey.referred_table}-${foreignKey.name ?? index}`,
                source: table.name,
                target: foreignKey.referred_table ?? '',
                label: foreignKey.columns.join(', '),
                markerEnd: { type: MarkerType.ArrowClosed },
                style: { stroke: '#38bdf8', strokeWidth: 2 },
            })),
    )
    return { nodes, edges }
}

export default function DatabaseSchemaPage() {
    const location = useLocation()
    const navigate = useNavigate()
    const params = useParams()
    const routeState = isDatabaseSchemaRouteState(location.state) ? location.state : null
    const [schema, setSchema] = useState<DatabaseSchemaResponse | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        if (!routeState) {
            return
        }
        setLoading(true)
        setError(null)
        void inspectDatabaseSchema(
            routeState.manifest.id as 'SQL_DATABASE' | 'SQL_FILE_DATABASE',
            routeState.manifest.version,
            routeState.parameters,
        )
            .then((payload) => setSchema(payload))
            .catch((loadError) => {
                setError(loadError instanceof Error ? loadError.message : 'Failed to load database schema')
            })
            .finally(() => setLoading(false))
    }, [routeState])

    const graph = useMemo(() => buildSchemaGraph(schema ?? { tables: [] }), [schema])

    return (
        <section className="database-schema-page">
            <div className="database-schema-toolbar">
                <strong>{routeState?.manifest.name ?? 'Database schema'}{params.nodeId ? `: ${params.nodeId}` : ''}</strong>
                <button type="button" onClick={() => navigate('/')}>
                    Back to canvas
                </button>
            </div>
            {!routeState ? (
                <div className="database-schema-message">
                    <h1>No database node selected</h1>
                    <p>Open this view from a database node context menu.</p>
                </div>
            ) : loading ? (
                <div className="database-schema-message">
                    <h1>Loading schema</h1>
                    <p>Inspecting the current database connection.</p>
                </div>
            ) : error ? (
                <div className="database-schema-message">
                    <h1>Schema unavailable</h1>
                    <p>{error}</p>
                </div>
            ) : graph.nodes.length === 0 ? (
                <div className="database-schema-message">
                    <h1>No tables found</h1>
                    <p>The connected database did not report any tables.</p>
                </div>
            ) : (
                <div className="database-schema-canvas">
                    <ReactFlow
                        nodes={graph.nodes}
                        edges={graph.edges}
                        nodeTypes={nodeTypes}
                        fitView
                        fitViewOptions={{ padding: 0.2 }}
                        proOptions={{ hideAttribution: true }}
                    >
                        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="rgba(125, 211, 252, 0.32)" />
                    </ReactFlow>
                </div>
            )}
        </section>
    )
}
