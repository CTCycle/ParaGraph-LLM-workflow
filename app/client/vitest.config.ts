import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const clientRoot = fileURLToPath(new URL('.', import.meta.url))
const testSetupFile = relative(
    clientRoot,
    fileURLToPath(new URL('./src/test/setup.ts', import.meta.url)),
).replaceAll('\\', '/')

export default defineConfig({
    root: clientRoot,
    plugins: [react()],
    test: {
        environment: 'jsdom',
        setupFiles: [testSetupFile],
        include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
        clearMocks: true,
        restoreMocks: true,
        unstubEnvs: true,
        unstubGlobals: true,
    },
})

