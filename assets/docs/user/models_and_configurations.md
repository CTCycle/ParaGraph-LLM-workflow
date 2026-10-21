# Models And Configurations
Last updated: 2026-10-21

## Configurations Page
Manage:

- Ollama base URL and connectivity checks
- Cloud provider keys for OpenAI, Gemini, Claude, and DeepSeek
- OpenAI-compatible local provider endpoints for LM Studio and llama.cpp, including optional API keys and default chat or embedding model metadata
- Hugging Face API key
- Named configuration profiles through save and load flows

Provider endpoint, credential, and model metadata fields save automatically
after a short typing debounce. Moving focus, navigating away, and leaving the
page flush pending edits. The current saved values are used by subsequent
provider operations, and inline feedback reports success or a persistence
error. A failed write leaves the edited value visible for correction or retry.

Profiles are optional named snapshots. Loading a profile activates and saves it
as the current provider configuration, including its credentials, while API
responses keep secrets redacted. Database settings are managed separately and
require the explicit Apply action.

The provider catalog at `/providers/catalog` defines the supported providers,
configuration kinds, defaults, and capabilities. Configuration APIs are backed
by `/configurations` and `/configurations/profiles`, using a canonical
`provider_configurations` list. Reads redact API keys and return `has_api_key`
so the UI can preserve a saved secret without exposing it.
Provider status checks use `/configurations/ollama/ping` for Ollama and `/configurations/providers/ping` for OpenAI-compatible local providers.

## Models Page
### Ollama
- Browse available library models.
- Pull missing models into the local runtime.

### LM Studio And llama.cpp
- Use the workflow provider catalog with locally exposed OpenAI-compatible `/v1` endpoints.
- Configure default base URLs on the Configurations page:
  - LM Studio: `http://localhost:1234/v1`
  - llama.cpp: `http://localhost:8080/v1`

### Hugging Face
- Search, filter, and sort the model catalog.
- Start, monitor, or cancel model downloads.
- Open model cards in the browser.
