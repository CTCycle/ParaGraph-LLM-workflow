import { randomUUID } from 'node:crypto'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const databaseNodeId = 'pg-t3-02-database'
const workflowStateStorageKey = 'paragraph.workflow.state.v1'
const runtimeCacheRoot = fileURLToPath(new URL('../../../../runtimes/cache/', import.meta.url))
const schemaScreenshotPath = fileURLToPath(new URL('../../../../assets/QA/pg-t3-02-database-schema.png', import.meta.url))

async function runSqlWorkflow(
    page: Page,
    databasePath: string,
    sql: string,
): Promise<void> {
    const suffix = randomUUID()
    const compileResponse = await page.request.post('/api/executions/compile', {
        data: {
            definition: {
                schema_version: 2,
                nodes: [
                    {
                        node_id: 'database',
                        node_type: 'SQL_FILE_DATABASE',
                        node_version: 1,
                        parameters: { db_path: databasePath, db_connect_timeout: 30 },
                    },
                    {
                        node_id: 'sql',
                        node_type: 'CUSTOM_SQL_QUERY',
                        node_version: 1,
                        parameters: { sql },
                    },
                ],
                connections: [
                    {
                        from_node: 'database',
                        connection_type: 'controller',
                        from_controller: 'connection',
                        to_node: 'sql',
                        to_controller: 'connection',
                    },
                ],
                metadata: {},
            },
        },
    })
    expect(compileResponse.ok()).toBeTruthy()
    const compiled = await compileResponse.json() as { valid: boolean; plan?: unknown }
    expect(compiled.valid).toBeTruthy()
    expect(compiled.plan).toBeTruthy()

    const startResponse = await page.request.post('/api/executions', {
        data: {
            workflow_id: `pg-t3-02-${suffix}`,
            execution_session_id: `pg-t3-02-${suffix}`,
            plan: compiled.plan,
        },
    })
    expect(startResponse.status()).toBe(202)
    const started = await startResponse.json() as { run_id: string }

    await expect.poll(
        async () => {
            const response = await page.request.get(`/api/executions/${started.run_id}`)
            expect(response.ok()).toBeTruthy()
            const run = await response.json() as { status: string }
            return run.status
        },
        { timeout: 60_000, intervals: [250, 500, 1_000] },
    ).toMatch(/^(completed|failed|cancelled)$/)
    const finalResponse = await page.request.get(`/api/executions/${started.run_id}`)
    const finalRun = await finalResponse.json() as { status: string; steps?: unknown[] }
    expect(finalRun.status, JSON.stringify(finalRun)).toBe('completed')
}

test('opens a live SQLite schema from the workflow and handles an empty database', async ({ page }) => {
    await mkdir(runtimeCacheRoot, { recursive: true })
    const databasePath = path.join(runtimeCacheRoot, `pg-t3-02-${randomUUID()}.sqlite`)
    await writeFile(databasePath, '')

    try {
        await runSqlWorkflow(
            page,
            databasePath,
            'create table users (id integer primary key, email text not null unique)',
        )

        await page.addInitScript(
            ({ storageKey, state }) => localStorage.setItem(storageKey, JSON.stringify(state)),
            {
                storageKey: workflowStateStorageKey,
                state: {
                    nodes: [{
                        id: databaseNodeId,
                        manifest_id: 'SQL_FILE_DATABASE',
                        manifest_version: 1,
                        position: { x: 80, y: 120 },
                        parameters: { db_path: databasePath, db_connect_timeout: 30 },
                        collapsed: false,
                        items_expanded: false,
                        pinged: false,
                        skipped: false,
                    }],
                    edges: [],
                    is_library_visible: false,
                    is_grid_visible: true,
                    search: '',
                    selected_manifest_key: null,
                    execution_session_id: `pg-t3-02-${randomUUID()}`,
                    active_run: null,
                },
            },
        )

        await page.goto('/')
        const databaseNode = page.locator(`.react-flow__node[data-id="${databaseNodeId}"]`)
        await expect(databaseNode).toBeVisible()
        await databaseNode.click({ button: 'right' })
        await page.getByRole('menuitem', { name: 'View schema' }).click()

        const schemaTable = page.locator('.database-schema-table-node')
        await expect(schemaTable).toContainText('users')
        await expect(schemaTable).toContainText('id')
        await expect(schemaTable).toContainText('INTEGER')
        await expect(schemaTable).toContainText('email')
        await expect(schemaTable).toContainText('TEXT')
        const columnFlags = schemaTable.locator('.database-schema-column-flags')
        await expect(columnFlags.nth(0)).toHaveText('PK')
        await expect(columnFlags.nth(1)).toHaveText('NN')
        await mkdir(path.dirname(schemaScreenshotPath), { recursive: true })
        await page.screenshot({ path: schemaScreenshotPath, fullPage: true })

        await page.getByRole('button', { name: 'Back to canvas' }).click()
        await expect(databaseNode).toBeVisible()
        await runSqlWorkflow(page, databasePath, 'drop table users')

        await databaseNode.click({ button: 'right' })
        await page.getByRole('menuitem', { name: 'View schema' }).click()
        await expect(page.getByRole('heading', { name: 'No tables found' })).toBeVisible()
        await page.getByRole('button', { name: 'Back to canvas' }).click()
        await expect(databaseNode).toBeVisible()
    } finally {
        try {
            await rm(databasePath, { force: true })
        } catch (error) {
            if (
                typeof error !== 'object'
                || error === null
                || !('code' in error)
                || error.code !== 'EBUSY'
            ) {
                throw error
            }
        }
    }
})
