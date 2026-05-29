import { type NodeManifest } from '../../workflow/schema/types'

export const NODE_MANIFEST_TEMPLATE = `{
  "id": "CUSTOM_NODE",
  "version": 1,
  "name": "Custom Node",
  "category": "processing",
  "description": "Describe what the node does.",
  "inputs": [
    {
      "name": "input_text",
      "data_type": "TEXT",
      "required": true,
      "accepts_multiple": false,
      "description": "Incoming text payload."
    }
  ],
  "outputs": [
    {
      "name": "result",
      "data_type": "TEXT",
      "required": true,
      "accepts_multiple": false,
      "description": "Processed text output."
    }
  ],
  "parameters": [
    {
      "name": "mode",
      "data_type": "TEXT",
      "default": "default",
      "constraints": { "options": ["default", "fast"] },
      "ui_control": "select",
      "description": "Execution mode."
    }
  ],
  "ui": {
    "default_width": 320,
    "accent_color": "#4aa3ff",
    "icon": "sparkles",
    "collapsed_by_default": false
  },
  "runtime": {
    "executor_key": "custom.plugin",
    "cacheable": false,
    "deterministic": true,
    "side_effecting": false,
    "plugin": {
      "script_path": "plugins/custom_node.py",
      "entrypoint": "execute"
    }
  }
}`

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
}

export function isNodeManifest(value: unknown): value is NodeManifest {
    if (!isRecord(value)) {
        return false
    }

    const ui = value.ui
    const runtime = value.runtime

    return (
        typeof value.id === 'string' &&
        typeof value.version === 'number' &&
        typeof value.name === 'string' &&
        typeof value.category === 'string' &&
        typeof value.description === 'string' &&
        Array.isArray(value.inputs) &&
        Array.isArray(value.outputs) &&
        Array.isArray(value.parameters) &&
        isRecord(ui) &&
        isRecord(runtime)
    )
}
