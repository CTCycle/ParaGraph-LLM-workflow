import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
    persistWorkflowState,
    readPersistedWorkflowState,
} from './workflowPersistence'

describe('workflow persistence', () => {
    beforeEach(() => {
        window.localStorage.clear()
    })

    afterEach(() => {
        window.localStorage.clear()
    })

    it('round-trips the editor state through localStorage', () => {
        const state = {
            nodes: [
                {
                    id: 'node-1',
                    manifest_id: 'core.text',
                    manifest_version: 1,
                    position: { x: 12, y: 24 },
                    width: undefined,
                    height: undefined,
                    parameters: { text: 'hello' },
                    collapsed: false,
                    items_expanded: true,
                    pinged: false,
                    skipped: false,
                },
            ],
            edges: [
                {
                    id: 'edge-1',
                    source: 'node-1',
                    target: 'node-2',
                    source_handle: 'output',
                    target_handle: null,
                },
            ],
            is_library_visible: true,
            is_grid_visible: false,
            search: 'text',
            selected_manifest_key: 'core.text@1',
            execution_session_id: 'session-1',
            active_run: { run_id: 'run-1', poll_interval: 1500 },
        }

        persistWorkflowState(state)

        expect(readPersistedWorkflowState()).toEqual(state)
    })

    it('filters malformed entries and invalid active runs', () => {
        window.localStorage.setItem('paragraph.workflow.state.v1', JSON.stringify({
            nodes: [{ id: 'missing-position' }],
            edges: [{ source: 'node-1', target: 'node-2' }],
            active_run: { run_id: '', poll_interval: 0 },
        }))

        expect(readPersistedWorkflowState()).toEqual({
            nodes: [],
            edges: [{
                id: 'node-1--node-2-',
                source: 'node-1',
                target: 'node-2',
                source_handle: null,
                target_handle: null,
            }],
            is_library_visible: false,
            is_grid_visible: true,
            search: '',
            selected_manifest_key: null,
            execution_session_id: '',
            active_run: null,
        })
    })
})
