import {
  DatabaseConnectionCheckResponse,
  DatabaseSchemaResponse,
  NodeCatalogResponse,
  NodeManifest,
  UploadedDirectoryResponse,
  VectorStoreConnectionCheckResponse,
} from '../../workflow/schema/types'
import { getApiBase, requestJson } from './api'

async function extractApiErrorDetail(response: Response): Promise<string> {
  let detail = `${response.status} ${response.statusText}`
  try {
    const payload = (await response.json()) as { detail?: string | string[] }
    if (Array.isArray(payload.detail)) {
      detail = payload.detail.join('; ')
    } else if (payload.detail) {
      detail = payload.detail
    }
  } catch {
    // Use default HTTP status detail.
  }
  return detail
}

export function fetchNodeCatalog(): Promise<NodeCatalogResponse> {
  return requestJson<NodeCatalogResponse>('/nodes/catalog')
}

export function importNodeManifest(manifest: NodeManifest): Promise<NodeManifest> {
  return requestJson<NodeManifest>('/nodes/import', {
    method: 'POST',
    body: JSON.stringify(manifest),
  })
}

export async function uploadNodeDirectory(files: File[]): Promise<UploadedDirectoryResponse> {
  if (files.length === 0) {
    throw new Error('No files selected')
  }

  const formData = new FormData()
  for (const file of files) {
    const relativePath = file.webkitRelativePath || file.name
    formData.append('files', file, relativePath)
  }

  const response = await fetch(`${getApiBase()}/nodes/uploads/directory`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(await extractApiErrorDetail(response))
  }

  return (await response.json()) as UploadedDirectoryResponse
}

export function checkDatabaseConnection(
  nodeType: 'SQL_DATABASE' | 'SQL_FILE_DATABASE',
  nodeVersion: number,
  parameters: Record<string, unknown>,
): Promise<DatabaseConnectionCheckResponse> {
  return requestJson<DatabaseConnectionCheckResponse>('/nodes/check-database-connection', {
    method: 'POST',
    body: JSON.stringify({
      node_type: nodeType,
      node_version: nodeVersion,
      parameters,
    }),
  })
}

export function inspectDatabaseSchema(
  nodeType: 'SQL_DATABASE' | 'SQL_FILE_DATABASE',
  nodeVersion: number,
  parameters: Record<string, unknown>,
): Promise<DatabaseSchemaResponse> {
  return requestJson<DatabaseSchemaResponse>('/nodes/database-schema', {
    method: 'POST',
    body: JSON.stringify({
      node_type: nodeType,
      node_version: nodeVersion,
      parameters,
    }),
  })
}

export function checkVectorStoreConnection(
  nodeType: 'VECTOR_STORE',
  nodeVersion: number,
  parameters: Record<string, unknown>,
): Promise<VectorStoreConnectionCheckResponse> {
  return requestJson<VectorStoreConnectionCheckResponse>('/nodes/check-vector-store-connection', {
    method: 'POST',
    body: JSON.stringify({
      node_type: nodeType,
      node_version: nodeVersion,
      parameters,
    }),
  })
}
