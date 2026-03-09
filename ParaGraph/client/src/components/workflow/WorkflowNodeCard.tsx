import { ChangeEvent } from 'react'
import { Handle, Node, NodeProps, Position } from '@xyflow/react'
import { WorkflowNodeDefinition, WorkflowParameterSchema } from '../../types'
import './WorkflowNodeCard.css'

export type WorkflowNodeData = Record<string, unknown> & {
    definition: WorkflowNodeDefinition
    params: Record<string, unknown>
    onParamsPatch: (nodeId: string, patch: Record<string, unknown>) => void
    onDelete: (nodeId: string) => void
}

export type WorkflowCanvasNode = Node<WorkflowNodeData, 'workflowNode'>

function toDisplayValue(value: unknown): string {
    if (typeof value === 'string') {
        return value
    }
    if (typeof value === 'number') {
        return String(value)
    }
    if (typeof value === 'boolean') {
        return value ? 'true' : 'false'
    }
    if (value == null) {
        return ''
    }
    return JSON.stringify(value)
}

function formatParameterValue(params: Record<string, unknown>, schema: WorkflowParameterSchema): string {
    const value = params[schema.key] ?? schema.default
    return toDisplayValue(value)
}

function parseNumber(value: string): number | null {
    if (!value.trim()) {
        return null
    }
    const parsed = Number.parseFloat(value)
    return Number.isFinite(parsed) ? parsed : null
}

function renderParameterField(
    nodeId: string,
    schema: WorkflowParameterSchema,
    params: Record<string, unknown>,
    onParamsPatch: (nodeId: string, patch: Record<string, unknown>) => void,
) {
    const value = formatParameterValue(params, schema)

    if (schema.field_type === 'select') {
        return (
            <select
                className="workflow-node-input"
                value={value}
                onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    onParamsPatch(nodeId, { [schema.key]: event.target.value })
                }
            >
                {schema.options.map((option) => (
                    <option key={option} value={option}>
                        {option}
                    </option>
                ))}
            </select>
        )
    }

    if (schema.field_type === 'textarea') {
        return (
            <textarea
                className="workflow-node-textarea"
                value={value}
                rows={schema.key === 'outputText' ? 5 : 3}
                onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                    onParamsPatch(nodeId, { [schema.key]: event.target.value })
                }
                readOnly={schema.key === 'outputText'}
            />
        )
    }

    if (schema.field_type === 'number') {
        return (
            <input
                className="workflow-node-input"
                type="number"
                step="any"
                value={value}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                    onParamsPatch(nodeId, { [schema.key]: parseNumber(event.target.value) })
                }
            />
        )
    }

    return (
        <input
            className="workflow-node-input"
            type="text"
            value={value}
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                onParamsPatch(nodeId, { [schema.key]: event.target.value })
            }
        />
    )
}

export default function WorkflowNodeCard({ id, data, selected }: NodeProps<WorkflowCanvasNode>) {
    const inputPorts = data.definition.ports.filter((port) => port.direction === 'input')
    const outputPorts = data.definition.ports.filter((port) => port.direction === 'output')

    return (
        <div className={`workflow-node-card${selected ? ' selected' : ''}`}>
            <div className="workflow-node-header">
                <span>{data.definition.label}</span>
                <button
                    type="button"
                    className="workflow-node-delete"
                    aria-label={`Delete ${data.definition.label} node`}
                    onClick={() => data.onDelete(id)}
                >
                    ×
                </button>
            </div>

            {inputPorts.map((port, index) => (
                <Handle
                    key={port.handle}
                    id={port.handle}
                    type="target"
                    position={Position.Left}
                    className="workflow-node-handle"
                    style={{ top: 42 + index * 22 }}
                />
            ))}

            {outputPorts.map((port, index) => (
                <Handle
                    key={port.handle}
                    id={port.handle}
                    type="source"
                    position={Position.Right}
                    className="workflow-node-handle"
                    style={{ top: 42 + index * 22 }}
                />
            ))}

            <div className="workflow-node-body">
                {data.definition.parameters.map((schema) => (
                    <label key={schema.key} className="workflow-node-field">
                        <span>{schema.label}</span>
                        {renderParameterField(id, schema, data.params, data.onParamsPatch)}
                    </label>
                ))}
            </div>
        </div>
    )
}
