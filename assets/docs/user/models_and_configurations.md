# Models And Configurations
Last updated: 2026-06-18

## Configurations Page
Manage:

- Ollama base URL and connectivity checks
- Cloud provider keys such as OpenAI, Gemini, Claude, and DeepSeek when enabled in the UI
- OpenAI-compatible local provider endpoints for LM Studio and llama.cpp, including optional API keys and default chat or embedding model metadata
- Hugging Face access keys
- Named configuration profiles through save and load flows

Configuration APIs are backed by `/configurations` and `/configurations/profiles`.
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
