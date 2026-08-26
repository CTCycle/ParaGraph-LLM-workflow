import type { GuidanceId, TourStepDefinition } from './types'

export const GUIDANCE_CONTENT_VERSIONS: Record<GuidanceId, number> = {
    'editor-onboarding': 1,
    'editor-tour': 1,
    'config-setup': 1,
}

export const EDITOR_TOUR_STEPS: TourStepDefinition[] = [
    {
        id: 'node-library',
        target: 'node-library',
        title: 'Choose a node',
        body: 'Search or expand a category, then drag a node onto the canvas.',
        placement: 'right',
    },
    {
        id: 'workflow-canvas',
        target: 'workflow-canvas',
        title: 'Arrange your workflow',
        body: 'Drop nodes here and place them in the order your workflow should run.',
        placement: 'top',
    },
    {
        id: 'workflow-connections',
        target: 'workflow-canvas',
        title: 'Connect compatible ports',
        body: 'Drag from an output to a compatible input. Blue data ports carry values; amber controller ports attach shared handles.',
        placement: 'bottom',
        media: 'connect-ports',
    },
    {
        id: 'run-workflow',
        target: 'run-workflow',
        title: 'Compile, then run',
        body: 'Run Workflow compiles the graph first. Fix blocking diagnostics before execution starts.',
        placement: 'bottom',
    },
]

export type TipDefinition = {
    id: string
    title: string
    body: string
    action?: 'templates' | 'config' | 'tour'
}

export const TIPS_AND_TRICKS: TipDefinition[] = [
    {
        id: 'templates',
        title: 'Start with a template',
        body: 'Templates on the Nodes page give you a known-good workflow shape to adapt.',
        action: 'templates',
    },
    {
        id: 'ports',
        title: 'Ports have different jobs',
        body: 'Blue data ports carry values. Amber controller ports attach reusable providers, memory, or stores.',
    },
    {
        id: 'compile',
        title: 'Run includes the compile step',
        body: 'Run Workflow checks the graph before execution. Read blocking diagnostics beside the editor when a run cannot start.',
        action: 'tour',
    },
    {
        id: 'chat-history',
        title: 'Chat history is scoped',
        body: 'Connect Chat History to Chat, and to LLM Chat when earlier turns should reach the model. Reset clears that Chat scope.',
    },
    {
        id: 'node-actions',
        title: 'Right-click a node',
        body: 'Use the node context menu to clone, skip, reset configuration, or set a node global.',
    },
    {
        id: 'provider-setup',
        title: 'Set up a provider before running',
        body: 'Configure a local endpoint or cloud key, check its status, then choose the provider and model in the workflow.',
        action: 'config',
    },
]
