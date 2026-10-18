import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

const SAVE_TARGET_FOLDER_NAME = 'pg-t3-01-save'
const CHUNK_PHRASES = [
    'Apples are crisp',
    'Bananas are soft',
    'Carrots are crunchy',
    'Dates are sweet',
]
const EXPECTED_SAVED_FILE_NAMES = [
    `${SAVE_TARGET_FOLDER_NAME}_000001.md`,
    `${SAVE_TARGET_FOLDER_NAME}_000002.md`,
    `${SAVE_TARGET_FOLDER_NAME}_000003.md`,
    `${SAVE_TARGET_FOLDER_NAME}_000004.md`,
]

const STATUS_SECONDS = 15_000
const RUN_SECONDS = 90_000
const CATALOG_SECONDS = 60_000

type CatalogEntry = {
    id: string
    version: number
    name: string
    category: string
    description: string
    inputs: Array<{ name: string; data_type: string; required?: boolean }>
    outputs: Array<{ name: string; data_type: string; required?: boolean }>
    parameters: Array<{ name: string; data_type: string; default?: unknown }>
    ui?: { default_width?: number; accent_color?: string; collapsed_by_default?: boolean }
    runtime: { executor_key: string; cacheable: boolean; deterministic: boolean; side_effecting: boolean }
}

type RunPortValue = {
    documents?: Record<string, unknown>[]
    chunks?: Record<string, unknown>[]
    artifact?: Record<string, unknown>
}

type RunStep = {
    step_id: string
    node_id: string
    node_type: string
    status: string
    output?: { ports: RunPortValue }
}

type RunPayload = {
    run_id: string
    status: string
    steps: RunStep[]
}

const WORKFLOW_NAME = 'Upload Document Chunk Review'
const BUNDLE_FILE_NAME = 'upload-document.spec-bundle.json'

const UPLOAD_CHAIN_NODE_IDS: Array<[string, number]> = [
    ['LOAD_DOCUMENTS', 1],
    ['DOCUMENT_TEXT_EXTRACTOR', 1],
    ['BY_DELIMITER_CHUNKS', 1],
    ['SAVE_AS_FOLDER', 1],
    ['JSON_OUTPUT', 1],
]

function statusText(page: Page) {
    return page.locator('.workflow-toolbar-status strong')
}

function workflowNode(page: Page, headerName: string) {
    return page.locator('.workflow-node', { hasText: headerName })
}

function buildUploadFixtureDirectory() {
    const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'pg-t3-01-upload-')))
    return {
        root,
        newFile: (relativeName: string, content: string) => {
            const filePath = path.join(root, relativeName)
            fs.mkdirSync(path.dirname(filePath), { recursive: true })
            fs.writeFileSync(filePath, content, 'utf-8')
            return filePath
        },
    }
}

function installBrowserPickerSupport(page: Page) {
    return page.addInitScript(`
        (() => {
            window.__pgT3SaveTargetName = '${SAVE_TARGET_FOLDER_NAME}'

            window.showDirectoryPicker = async () => {
                const opfsRoot = await navigator.storage.getDirectory()
                const handle = await opfsRoot.getDirectoryHandle(window.__pgT3SaveTargetName, { create: true })
                window.__pgShowDirectoryPickerPayloads = window.__pgShowDirectoryPickerPayloads ?? []
                window.__pgShowDirectoryPickerPayloads.push({ name: handle.name })
                return handle
            }

            const nativeInputClick = HTMLInputElement.prototype.click
            HTMLInputElement.prototype.click = function (...args) {
                if (this.type === 'file' && !this.isConnected) {
                    document.documentElement.appendChild(this)
                    try {
                        return nativeInputClick.apply(this, args)
                    } finally {
                        queueMicrotask(() => this.remove())
                    }
                }
                return nativeInputClick.apply(this, args)
            }
        })()
    `)
}

async function waitForLiveBackend(page: Page) {
    await expect.poll(
        async () => (await page.request.get('/api/nodes/catalog')).ok(),
        { timeout: CATALOG_SECONDS, intervals: [500, 1_000, 2_000] },
    ).toBeTruthy()
}

async function buildWorkflowBundle(page: Page) {
    const catalogResponse = await page.request.get('/api/nodes/catalog')
    expect(catalogResponse.ok()).toBeTruthy()
    const catalog = (await catalogResponse.json()) as { nodes: CatalogEntry[] }

    const requiredNodes = UPLOAD_CHAIN_NODE_IDS.map(([nodeId, version]) => {
        const match = catalog.nodes.find((entry) => entry.id === nodeId && entry.version === version)
        expect(match, `Live backend must provide ${nodeId} v${version}`).toBeTruthy()
        return match
    })

    const bundle = {
        bundle_version: 1,
        app: 'ParaGraph',
        created_at: new Date().toISOString(),
        workflow: {
            name: WORKFLOW_NAME,
            definition: {
                schema_version: 2,
                nodes: [
                    { node_id: 'upload_load_1', node_type: 'LOAD_DOCUMENTS', node_version: 1, parameters: {} },
                    {
                        node_id: 'upload_extract_1',
                        node_type: 'DOCUMENT_TEXT_EXTRACTOR',
                        node_version: 1,
                        parameters: { include_empty_pages: false },
                    },
                    {
                        node_id: 'upload_chunk_1',
                        node_type: 'BY_DELIMITER_CHUNKS',
                        node_version: 1,
                        parameters: {
                            delimiter: 'period',
                            keep_delimiter: false,
                            drop_empty: true,
                            max_chunk_size: 0,
                            overflow_strategy: 'split_further',
                        },
                    },
                    {
                        node_id: 'upload_save_1',
                        node_type: 'SAVE_AS_FOLDER',
                        node_version: 1,
                        parameters: { output_path: '', extension: '.txt' },
                    },
                    { node_id: 'upload_output_1', node_type: 'JSON_OUTPUT', node_version: 1, parameters: {} },
                ],
                connections: [
                    {
                        from_node: 'upload_load_1',
                        connection_type: 'data',
                        from_output: 'documents',
                        to_node: 'upload_extract_1',
                        to_input: 'documents',
                    },
                    {
                        from_node: 'upload_extract_1',
                        connection_type: 'data',
                        from_output: 'documents',
                        to_node: 'upload_chunk_1',
                        to_input: 'documents',
                    },
                    {
                        from_node: 'upload_chunk_1',
                        connection_type: 'data',
                        from_output: 'chunks',
                        to_node: 'upload_save_1',
                        to_input: 'chunks',
                    },
                    {
                        from_node: 'upload_save_1',
                        connection_type: 'data',
                        from_output: 'artifact',
                        to_node: 'upload_output_1',
                        to_input: 'value',
                    },
                ],
                metadata: {},
            },
            visual_graph: {
                schema_version: 2,
                nodes: [
                    { node_id: 'upload_load_1', x: 120, y: 160, width: 360, height: 190, collapsed: false },
                    { node_id: 'upload_extract_1', x: 580, y: 160, width: 360, height: 190, collapsed: false },
                    { node_id: 'upload_chunk_1', x: 1040, y: 160, width: 360, height: 190, collapsed: false },
                    { node_id: 'upload_save_1', x: 1500, y: 160, width: 380, height: 190, collapsed: false },
                    { node_id: 'upload_output_1', x: 1960, y: 160, width: 380, height: 190, collapsed: false },
                ],
                groups: [],
                comments: [],
            },
        },
        required_nodes: requiredNodes,
    }

    return JSON.stringify(bundle, null, 2)
}

async function importUploadWorkflow(page: Page, bundleJson: string) {
    await page.goto('/')
    await expect(statusText(page)).toHaveText('Ready', { timeout: CATALOG_SECONDS })

    const importChooser = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Import JSON' }).click()
    const chooser = await importChooser
    await chooser.setFiles({
        name: BUNDLE_FILE_NAME,
        mimeType: 'application/json',
        buffer: Buffer.from(bundleJson, 'utf-8'),
    })

    await expect(statusText(page)).toHaveText(
        `Imported workflow "${WORKFLOW_NAME}" from ${BUNDLE_FILE_NAME}`,
        { timeout: STATUS_SECONDS },
    )
    await expect(workflowNode(page, 'Load Documents')).toBeVisible()
}

async function uploadDocumentDirectory(page: Page, fixtureRoot: string): Promise<string> {
    const loadNode = workflowNode(page, 'Load Documents')
    const stagedFolderName = path.basename(fixtureRoot)
    const uploadChooser = page.waitForEvent('filechooser')
    await loadNode.getByRole('button', { name: 'Browse' }).click()
    const chooser = await uploadChooser
    await chooser.setFiles(fixtureRoot)

    await expect(statusText(page)).toHaveText(`Selected ${stagedFolderName} (2 files)`, { timeout: STATUS_SECONDS })
    const folderPathInput = loadNode.getByRole('textbox').first()
    await expect
        .poll(
            async () => {
                const stagedPath = await folderPathInput.inputValue()
                return stagedPath.length > 0 && stagedPath.includes('browser_uploads')
            },
            { timeout: STATUS_SECONDS, intervals: [250, 500, 1_000] },
        )
        .toBeTruthy()
    return stagedFolderName
}

async function prepareSaveNode(page: Page) {
    const saveNode = workflowNode(page, 'Save As Folder')

    await saveNode.getByRole('button', { name: 'Browse' }).click()
    await expect(statusText(page)).toHaveText(`Save target set to ${SAVE_TARGET_FOLDER_NAME}`, {
        timeout: STATUS_SECONDS,
    })

    await saveNode.getByRole('textbox').first().fill(SAVE_TARGET_FOLDER_NAME)
    await saveNode.getByRole('combobox').selectOption('.md')
}

async function startUploadRun(page: Page) {
    const startResponse = page.waitForResponse(
        (response) =>
            response.url().endsWith('/api/executions') &&
            response.request().method() === 'POST' &&
            response.status() === 202,
        { timeout: RUN_SECONDS },
    )
    await page.getByRole('button', { name: 'Run Workflow' }).click()
    const response = await startResponse
    expect(response.ok()).toBeTruthy()
    return ((await response.json()) as { run_id: string }).run_id
}

async function waitForCompletedRun(page: Page, runId: string) {
    await expect
        .poll(
            async () => {
                const pollResponse = await page.request.get(`/api/executions/${runId}`)
                expect(pollResponse.ok()).toBeTruthy()
                return ((await pollResponse.json()) as RunPayload).status
            },
            { timeout: RUN_SECONDS, intervals: [250, 500, 1_000] },
        )
        .toBe('completed')
}

async function fetchRunPayload(page: Page, runId: string) {
    const runResponse = await page.request.get(`/api/executions/${runId}`)
    expect(runResponse.ok()).toBeTruthy()
    return (await runResponse.json()) as RunPayload
}

function findRunStep(run: RunPayload, nodeType: string): RunStep {
    const step = run.steps.find((item) => item.node_type === nodeType)
    if (!step) {
        throw new Error(`Completed run does not include a ${nodeType} step`)
    }
    return step
}

async function readOpfsSaveFolder(page: Page) {
    return page.evaluate(async ([folderName]) => {
        const opfsRoot = await navigator.storage.getDirectory()
        const saveFolder = await opfsRoot.getDirectoryHandle(folderName as string)
        const savedFiles: Array<{ name: string; text: string }> = []
        for await (const [name, handle] of saveFolder.entries()) {
            if (handle.kind !== 'file') {
                continue
            }
            const file = await (await saveFolder.getFileHandle(name)).getFile()
            savedFiles.push({ name, text: await file.text() })
        }
        return savedFiles
    }, [SAVE_TARGET_FOLDER_NAME])
}

async function captureEvidence(page: Page, label: string) {
    const evidenceRoot = process.env.PG_T3_EVIDENCE_DIR
    if (!evidenceRoot) {
        return
    }
    fs.mkdirSync(evidenceRoot, { recursive: true })
    await page.screenshot({ path: path.join(evidenceRoot, `${label}.png`), fullPage: false })
}

function redactLocalResourcePaths(value: unknown): unknown {
    if (typeof value === 'string') {
        return value.replace(/^(?:[A-Za-z]:\\|\/).*?browser_uploads[\\/]+/g, '<RESOURCES>/')
    }
    if (Array.isArray(value)) {
        return value.map(redactLocalResourcePaths)
    }
    if (value && typeof value === 'object') {
        return Object.fromEntries(
            Object.entries(value as Record<string, unknown>).map(([key, item]) => [
                key,
                redactLocalResourcePaths(item),
            ]),
        )
    }
    return value
}

async function writeRunEvidence(page: Page, runId: string, label: string) {
    const evidenceRoot = process.env.PG_T3_EVIDENCE_DIR
    if (!evidenceRoot) {
        return
    }
    fs.mkdirSync(evidenceRoot, { recursive: true })
    const run = await fetchRunPayload(page, runId)
    const eventsResponse = await page.request.get(`/api/executions/${runId}/events`)
    expect(eventsResponse.ok()).toBeTruthy()
    const events = (await eventsResponse.json()) as {
        events: Array<{ event_type: string; sequence: number }>
    }
    fs.writeFileSync(
        path.join(evidenceRoot, `${label}.json`),
        `${JSON.stringify({ run: redactLocalResourcePaths(run), events }, null, 2)}\n`,
        'utf-8',
    )
}

let currentUploadFixtureDirectory: string | null = null

test.afterEach(() => {
    if (currentUploadFixtureDirectory && fs.existsSync(currentUploadFixtureDirectory)) {
        fs.rmSync(currentUploadFixtureDirectory, { recursive: true, force: true })
    }
    currentUploadFixtureDirectory = null
})

test('uploads documents through the picker, chunks them, and saves browser-staged files client-side', async ({ page }) => {
    test.setTimeout(240_000)

    await installBrowserPickerSupport(page)
    await waitForLiveBackend(page)

    const fixture = buildUploadFixtureDirectory()
    currentUploadFixtureDirectory = fixture.root
    fixture.newFile('dataset/readme.txt', 'Apples are crisp. Bananas are soft.')
    fixture.newFile('dataset/nested/notes.md', 'Carrots are crunchy. Dates are sweet.')

    const bundleJson = await buildWorkflowBundle(page)
    await importUploadWorkflow(page, bundleJson)
    await captureEvidence(page, '01-imported')

    const stagedFolderName = await uploadDocumentDirectory(page, fixture.root)
    await captureEvidence(page, '02-upload-staged')

    await prepareSaveNode(page)
    await captureEvidence(page, '03-save-target')

    const runId = await startUploadRun(page)
    await waitForCompletedRun(page, runId)
    await captureEvidence(page, '04-completed')
    await writeRunEvidence(page, runId, 'upload-run')

    await expect(statusText(page)).toHaveText(
        'Workflow completed (saved 4 files to selected local path)',
        { timeout: STATUS_SECONDS },
    )

    const run = await fetchRunPayload(page, runId)
    expect(run.status).toBe('completed')

    const loadStep = findRunStep(run, 'LOAD_DOCUMENTS')
    const documents = loadStep.output?.ports?.documents ?? []
    expect(documents).toHaveLength(2)
    expect(
        documents
            .map((item) => (item['metadata'] as Record<string, unknown>)?.relative_path)
            .sort(),
    ).toEqual(
        [
            `${stagedFolderName}/dataset/nested/notes.md`,
            `${stagedFolderName}/dataset/readme.txt`,
        ].sort(),
    )

    const extractStep = findRunStep(run, 'DOCUMENT_TEXT_EXTRACTOR')
    const extractedDocuments = extractStep.output?.ports?.documents ?? []
    expect(extractedDocuments).toHaveLength(2)
    for (const document of extractedDocuments) {
        expect((document['metadata'] as Record<string, unknown>)?.document_id).toBeTruthy()
    }

    const chunkStep = findRunStep(run, 'BY_DELIMITER_CHUNKS')
    const chunks = chunkStep.output?.ports?.chunks ?? []
    expect(chunks.length).toBeGreaterThanOrEqual(4)

    const saveStep = findRunStep(run, 'SAVE_AS_FOLDER')
    const artifact = saveStep.output?.ports?.artifact ?? {}
    expect(artifact['count']).toBe(4)
    expect(artifact['extension']).toBe('.md')
    expect(artifact['path']).toBe(SAVE_TARGET_FOLDER_NAME)
    expect(artifact['files']).toHaveLength(4)
    expect(artifact['item_texts']).toHaveLength(4)

    const savedFiles = await readOpfsSaveFolder(page)
    expect(savedFiles).toHaveLength(4)
    expect(savedFiles.map((item) => item.name).sort()).toEqual(EXPECTED_SAVED_FILE_NAMES.sort())
    const savedText = savedFiles.map((item) => item.text).join('\n')
    for (const phrase of CHUNK_PHRASES) {
        expect(savedText.includes(phrase)).toBeTruthy()
    }

    await expect(workflowNode(page, 'Save As Folder')).toBeVisible()
    await expect(
        workflowNode(page, 'JSON Output').locator('.workflow-node-runtime-output'),
    ).toContainText(`${SAVE_TARGET_FOLDER_NAME}_000001.md`)

    await page.reload()
    await expect(workflowNode(page, 'Load Documents')).toBeVisible({ timeout: STATUS_SECONDS })
    await expect(workflowNode(page, 'Save As Folder')).toBeVisible()
    await captureEvidence(page, '05-reloaded')
})

test('flags missing upload directories as a blocked run without side effects', async ({ page }) => {
    test.setTimeout(180_000)

    await installBrowserPickerSupport(page)
    await waitForLiveBackend(page)

    const bundleJson = await buildWorkflowBundle(page)
    await importUploadWorkflow(page, bundleJson)

    const missingDirectory = path.join(os.tmpdir(), `pg-t3-01-missing-${Date.now()}`)
    const loadNode = workflowNode(page, 'Load Documents')
    await loadNode.getByRole('textbox').first().fill(missingDirectory)

    await page.getByRole('button', { name: 'Run Workflow' }).click()

    const errorDialog = page.getByRole('dialog', { name: 'Workflow execution error' })
    await expect(errorDialog).toBeVisible({ timeout: RUN_SECONDS })
    await captureEvidence(page, '06-missing-directory-error')
    await expect(errorDialog).toContainText('Directory not found')

    await page.getByRole('button', { name: 'Close error dialog' }).click()
    await expect(errorDialog).toBeHidden()
    await expect(page.getByRole('button', { name: 'Run Workflow' })).toBeEnabled()
})
