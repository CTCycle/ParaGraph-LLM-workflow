import { requestJson } from './api'
import type {
    DatabaseConfigurationPayload,
    DatabaseConfigurationResponse,
    DatabaseTestResponse,
} from '../../workflow/schema/types'

export type DatabaseConfiguration = DatabaseConfigurationPayload
export type DatabaseConfigurationStatus = DatabaseConfigurationResponse
export type DatabaseTestResult = DatabaseTestResponse

export function fetchDatabaseConfiguration(): Promise<DatabaseConfigurationStatus> {
    return requestJson<DatabaseConfigurationStatus>('/database/configuration')
}

export function testDatabaseConfiguration(
    configuration: DatabaseConfiguration,
): Promise<DatabaseTestResult> {
    return requestJson<DatabaseTestResult>('/database/test', {
        method: 'POST',
        body: JSON.stringify(configuration),
    })
}

export function applyDatabaseConfiguration(
    configuration: DatabaseConfiguration,
): Promise<DatabaseConfigurationStatus> {
    return requestJson<DatabaseConfigurationStatus>('/database/configuration', {
        method: 'PUT',
        body: JSON.stringify(configuration),
    })
}
