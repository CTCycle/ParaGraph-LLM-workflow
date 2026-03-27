# Nodes Library

ASSIGN_NAME (v1)
Category: control
Inputs: value (ANY, required)
Output: variable (JSON)
Notes: Emits `{ "<name>": value }` using the required `name` parameter. Preserves upstream value payload as-is.

PROMPT (v1)
Category: prompt
Inputs: none
Output: text (TEXT)
Notes: Emits `prompt_text` exactly as entered.

PROMPT_TEMPLATE (v1)
Category: prompt
Inputs: variables (ANY, accepts_multiple)
Output: text (TEXT)
Notes: Uses `{variable}` syntax only. Merges one or more incoming variable maps into a single dictionary. Fails fast when a placeholder is missing or when the same key is provided by multiple incoming maps.

MODEL_PROVIDER (v1)
Category: model
Inputs: none
Output: model controller (MODEL_HANDLE, source)
Notes: Publishes provider/model selection for downstream model nodes.

LLM_CHAT (v1)
Category: model
Inputs: user_prompt (TEXT), system_prompt (TEXT), image (IMAGE)
Output: response (TEXT)
Notes: Requires `model` controller input from MODEL_PROVIDER.

LLM_STRUCTURED (v1)
Category: model
Inputs: user_prompt (TEXT), system_prompt (TEXT), image (IMAGE)
Output: result (JSON)
Notes: Requires `model` controller input and validates model response against `response_schema`.

LOAD_DOCUMENTS (v1)
Category: serialization
Inputs: none
Output: documents (DOCUMENT_LIST)
Notes: Produces deferred document records from a selected folder.

LOAD_TEXT (v1)
Category: serialization
Inputs: none
Output: text (TEXT)
Notes: Loads text from a selected local file path.

FIXED_SIZE_CHUNKS (v1)
Category: text_segmentation
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: chunks (CHUNK_LIST)
Notes: Splits input into fixed-size chunks using configured unit/overlap.

BY_DELIMITER_CHUNKS (v1)
Category: text_segmentation
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: chunks (CHUNK_LIST)
Notes: Splits by delimiter/preset separators with overflow handling options.

BY_STRUCTURE_CHUNKS (v1)
Category: text_segmentation
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: chunks (CHUNK_LIST)
Notes: Splits by structural boundaries (paragraph/section/heading-content).

RECURSIVE_SPLIT_CHUNKS (v1)
Category: text_segmentation
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: chunks (CHUNK_LIST)
Notes: Applies ordered separator list recursively with fallback strategy.

REGEX_SPLIT_CHUNKS (v1)
Category: text_segmentation
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: chunks (CHUNK_LIST)
Notes: Splits text using a regex pattern.

SENTENCE_WINDOW_CHUNKS (v1)
Category: text_segmentation
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: chunks (CHUNK_LIST)
Notes: Builds overlapping sentence windows.

MERGE_SMALL_CHUNKS (v1)
Category: text_segmentation
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: chunks (CHUNK_LIST)
Notes: Merges small adjacent chunks toward target size constraints.

SAVE_AS_FILE (v1)
Category: serialization
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: artifact (JSON)
Notes: Writes one file. Multi-item input is concatenated with indexed order using `/n/n` separator. Supports deferred document resolution and client-side write mode metadata.

SAVE_AS_FOLDER (v1)
Category: serialization
Inputs: text (TEXT), documents (DOCUMENT_LIST), chunks (CHUNK_LIST)
Output: artifact (JSON)
Notes: Writes one file per item with indexed filenames. Supports deferred document resolution and client-side write mode metadata.

SQL_DATABASE (v1)
Category: database
Inputs: none
Output: connection controller (DATABASE_CONNECTION, source)
Notes: Exposes external database connection handle for SQL execution nodes.

SQL_FILE_DATABASE (v1)
Category: database
Inputs: none
Output: connection controller (DATABASE_CONNECTION, source)
Notes: Exposes embedded/sqlite database connection handle.

TEXT_OUTPUT (v1)
Category: output
Inputs: text (TEXT, required)
Output: none (terminal node)
Notes: Publishes final text result in execution outputs.

JSON_OUTPUT (v1)
Category: output
Inputs: value (JSON, required)
Output: none (terminal node)
Notes: Publishes final JSON result in execution outputs.
