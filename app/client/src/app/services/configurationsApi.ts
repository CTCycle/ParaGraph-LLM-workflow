import {
  AppConfigurationPayload,
  ConfigurationProfileListResponse,
  OllamaStatusResponse,
} from '../../workflow/schema/types'
import { requestJson } from './api'

export function fetchConfigurations(sessionName = 'default'): Promise<AppConfigurationPayload> {
  const params = new URLSearchParams({ session_name: sessionName })
  return requestJson<AppConfigurationPayload>(`/configurations?${params.toString()}`)
}

export function saveConfigurations(payload: AppConfigurationPayload): Promise<AppConfigurationPayload> {
  return requestJson<AppConfigurationPayload>('/configurations', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function listConfigurationProfiles(sessionName = 'default'): Promise<ConfigurationProfileListResponse> {
  const params = new URLSearchParams({ session_name: sessionName })
  return requestJson<ConfigurationProfileListResponse>(`/configurations/profiles?${params.toString()}`)
}

export function loadConfigurationProfile(profileName: string, sessionName = 'default'): Promise<AppConfigurationPayload> {
  const params = new URLSearchParams({ session_name: sessionName })
  return requestJson<AppConfigurationPayload>(`/configurations/profiles/${encodeURIComponent(profileName)}?${params.toString()}`)
}

export function saveConfigurationProfile(profileName: string, payload: AppConfigurationPayload): Promise<AppConfigurationPayload> {
  return requestJson<AppConfigurationPayload>(`/configurations/profiles/${encodeURIComponent(profileName)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function pingOllama(baseUrl: string | null): Promise<OllamaStatusResponse> {
  return requestJson<OllamaStatusResponse>('/configurations/ollama/ping', {
    method: 'POST',
    body: JSON.stringify({ base_url: baseUrl }),
  })
}
