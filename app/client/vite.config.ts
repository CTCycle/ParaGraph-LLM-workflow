import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const normalizeApiBase = (value: string) => {
    const candidate = value.trim()
    if (!candidate) {
        throw new Error('VITE_API_BASE_URL must be set in settings/.env.')
    }
    if (/^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(candidate)) {
        throw new Error('VITE_API_BASE_URL must be a relative path (for example /api).')
    }

    const withLeadingSlash = candidate.startsWith('/') ? candidate : `/${candidate}`
    if (withLeadingSlash.length > 1 && withLeadingSlash.endsWith('/')) {
        return withLeadingSlash.slice(0, -1)
    }
    return withLeadingSlash
}

const requiredEnv = (env: Record<string, string | undefined>, key: string): string => {
    const value = env[key]?.trim()
    if (!value) {
        throw new Error(`${key} must be set in settings/.env.`)
    }
    return value
}

const requiredPort = (env: Record<string, string | undefined>, key: string): number => {
    const value = requiredEnv(env, key)
    if (!/^\d+$/.test(value)) {
        throw new Error(`${key} must be an integer between 1 and 65535.`)
    }
    const port = Number(value)
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error(`${key} must be an integer between 1 and 65535.`)
    }
    return port
}

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const buildProxy = (apiBase: string, apiTarget: string) => {
    const baseRegex = new RegExp(`^${escapeRegExp(apiBase)}`)
    return {
        [apiBase]: {
            target: apiTarget,
            changeOrigin: true,
            ws: true,
            rewrite: (proxyPath: string) => proxyPath.replace(baseRegex, ''),
        },
    }
}

export default defineConfig(({ mode }) => {
    const envDir = path.resolve(__dirname, '../../settings')
    const clientEnv = loadEnv(mode, __dirname, '')
    const settingsEnv = loadEnv(mode, envDir, '')
    const env = { ...process.env, ...clientEnv, ...settingsEnv }

    const apiHost = requiredEnv(env, 'FASTAPI_HOST')
    const apiPort = requiredEnv(env, 'FASTAPI_PORT')
    const apiTarget = `http://${apiHost}:${apiPort}`
    const uiHost = requiredEnv(env, 'UI_HOST')
    const uiPort = requiredPort(env, 'UI_PORT')
    const apiBase = normalizeApiBase(requiredEnv(env, 'VITE_API_BASE_URL'))
    const cacheRoot = path.resolve(__dirname, '../../app/tests/cache')
    const cacheDir = path.join(cacheRoot, 'vite')
    const buildOutDir = path.join(cacheRoot, 'frontend-dist')

    return {
        cacheDir,
        build: {
            outDir: buildOutDir,
            emptyOutDir: true,
        },
        envDir,
        plugins: [react()],
        server: {
            host: uiHost,
            port: uiPort,
            strictPort: true,
            proxy: buildProxy(apiBase, apiTarget),
        },
        preview: {
            host: uiHost,
            port: uiPort,
            strictPort: true,
            proxy: buildProxy(apiBase, apiTarget),
        },
    }
})
