import path from 'node:path'
import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const clientRoot = fileURLToPath(new URL('.', import.meta.url))
const cacheRoot = path.resolve(clientRoot, '../../assets/cache/playwright')
process.env.PLAYWRIGHT_BROWSERS_PATH ??= path.join(cacheRoot, 'browsers')

export default defineConfig({
    testDir: './tests/e2e',
    outputDir: path.join(cacheRoot, 'test-results'),
    timeout: 30_000,
    expect: {
        timeout: 7_500,
    },
    fullyParallel: false,
    retries: 0,
    reporter: [
        ['list'],
        ['html', { outputFolder: path.join(cacheRoot, 'report'), open: 'never' }],
    ],
    use: {
        baseURL: 'http://127.0.0.1:4173',
        headless: true,
        trace: 'retain-on-failure',
    },
    projects: [
        {
            name: 'chromium',
            use: {
                ...devices['Desktop Chrome'],
            },
        },
    ],
    webServer: {
        command: 'npm run dev -- --host 127.0.0.1 --port 4173',
        url: 'http://127.0.0.1:4173',
        reuseExistingServer: true,
        timeout: 120_000,
    },
})
