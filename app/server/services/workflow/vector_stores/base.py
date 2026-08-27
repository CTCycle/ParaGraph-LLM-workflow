from __future__ import annotations

import json
import logging
import re
import shutil
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import faiss
import numpy as np
import portalocker

from server.common import path as common_path
from server.common.security import (
    ensure_path_within_root,
    is_cloud_deployment,
)
from server.contracts.node_catalog import VectorStoreCapabilities
from server.contracts.workflow_payloads import (
    RetrievalHit,
    VectorCollectionInfo,
    VectorMutationResult,
    VectorPoint,
    VectorStoreHandle,
)


VECTORSTORE_ROOT = common_path.ARTIFACT_ROOT / "vectorstores"
INDEX_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
logger = logging.getLogger(__name__)
_SECRET_REGISTRY: OrderedDict[str, str] = OrderedDict()
_SECRET_REGISTRY_LIMIT = 64

###############################################################################
def _resolve_vectorstore_root(storage_directory: str | None) -> Path:
    selected = str(storage_directory or "").strip()
    default_root = VECTORSTORE_ROOT.resolve()
    if not selected:
        return default_root

    candidate = Path(selected).expanduser()
    if not candidate.is_absolute():
        raise VectorStoreError("storage_directory must be an absolute path")

    resolved = candidate.resolve()
    if is_cloud_deployment():
        return ensure_path_within_root(
            resolved, default_root, label="storage_directory"
        )
    return resolved

###############################################################################
def _normalize_index_name(index_name: str) -> str:
    normalized = str(index_name or "").strip()
    if not INDEX_NAME_PATTERN.fullmatch(normalized):
        raise VectorStoreError(
            "index_name must contain only letters, numbers, dot, underscore, or dash"
        )
    return normalized

###############################################################################
class VectorStoreError(ValueError):
    code = "vector_store_error"

###############################################################################
class VectorStoreUnsupportedOperationError(VectorStoreError):
    code = "unsupported_operation"

###############################################################################
class VectorStoreConflictError(VectorStoreError):
    code = "duplicate_vector_ids"

    # -------------------------------------------------------------------------
    def __init__(self, conflicts: list[str]) -> None:
        self.conflicts = sorted(set(conflicts))
        super().__init__(f"Duplicate vector record IDs: {', '.join(self.conflicts)}")

###############################################################################
class VectorStoreLockTimeoutError(VectorStoreError):
    code = "lock_timeout"

###############################################################################
@contextmanager
def _store_lock(store_path: Path, timeout: float):
    lock_path = store_path.with_name(f"{store_path.name}.lock")
    try:
        with portalocker.Lock(str(lock_path), mode="a", timeout=max(0.1, timeout)):
            yield
    except portalocker.exceptions.LockException as exc:
        raise VectorStoreLockTimeoutError(
            f"Timed out waiting for vector store lock: {store_path.name}"
        ) from exc

###############################################################################
def _point_attr(point: VectorPoint | dict[str, Any], name: str) -> Any:
    if isinstance(point, dict):
        return point.get(name)
    return getattr(point, name)

###############################################################################
def _store_attr(store: VectorStoreHandle | dict[str, Any], name: str) -> Any:
    if isinstance(store, dict):
        return store.get(name)
    return getattr(store, name)

###############################################################################
def _metric_code(metric: str):
    normalized = metric.lower().strip()
    if normalized == "cosine":
        return faiss.METRIC_INNER_PRODUCT
    if normalized == "ip":
        return faiss.METRIC_INNER_PRODUCT
    if normalized == "l2":
        return faiss.METRIC_L2
    raise VectorStoreError(f"Unsupported vector metric: {metric}")

###############################################################################
def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0.0, 1.0, norms)
    return vectors / safe_norms

###############################################################################
def _index_paths(root_path: Path, index_name: str) -> tuple[Path, Path, Path, Path]:
    store_path = root_path / index_name
    return (
        store_path,
        store_path / "manifest.json",
        store_path / "metadata.json",
        store_path / "vectors.npy",
    )

###############################################################################
def _index_file_path(store_path: Path) -> Path:
    return store_path / "index.faiss"

###############################################################################
def _build_index(
    vectors: np.ndarray,
    *,
    metric: str,
    index_type: str,
    nlist: int,
    hnsw_m: int,
):
    dim = int(vectors.shape[1])
    normalized_metric = metric.lower().strip()
    normalized_index_type = index_type.lower().strip()
    faiss_metric = _metric_code(normalized_metric)

    index = None
    if normalized_index_type == "flat":
        if faiss_metric == faiss.METRIC_L2:
            index = faiss.IndexFlatL2(dim)
        else:
            index = faiss.IndexFlatIP(dim)
    elif normalized_index_type == "hnsw_flat":
        index = faiss.IndexHNSWFlat(dim, hnsw_m, faiss_metric)
    elif normalized_index_type == "ivf_flat":
        quantizer = (
            faiss.IndexFlatL2(dim)
            if faiss_metric == faiss.METRIC_L2
            else faiss.IndexFlatIP(dim)
        )
        nlist_value = max(1, min(nlist, int(vectors.shape[0])))
        index = faiss.IndexIVFFlat(quantizer, dim, nlist_value, faiss_metric)
        if vectors.shape[0] == 0:
            raise VectorStoreError("Cannot build IVF index without vectors")
        index.train(vectors)
    else:
        raise VectorStoreError(f"Unsupported FAISS index type: {index_type}")

    index.add(vectors)
    return index

###############################################################################
def _resolve_store_path_from_handle(store: VectorStoreHandle | dict[str, Any]) -> Path:
    artifact_path = str(_store_attr(store, "artifact_path") or "").strip()
    artifact_root = common_path.ARTIFACT_ROOT.resolve()
    if artifact_path:
        candidate = Path(artifact_path).expanduser()
        if candidate.is_absolute():
            resolved = candidate.resolve()
            if is_cloud_deployment():
                return ensure_path_within_root(
                    resolved, artifact_root, label="artifact_path"
                )
            return resolved
        resolved = (common_path.ARTIFACT_ROOT / candidate).resolve()
        return ensure_path_within_root(resolved, artifact_root, label="artifact_path")

    index_name = _normalize_index_name(str(_store_attr(store, "index_name") or ""))
    root = _resolve_vectorstore_root(_store_attr(store, "storage_directory"))
    return (root / index_name).resolve()

###############################################################################
def _load_store(
    store: VectorStoreHandle | dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray, Any]:
    store_path = _resolve_store_path_from_handle(store)
    manifest_path = store_path / "manifest.json"
    metadata_path = store_path / "metadata.json"
    vectors_path = store_path / "vectors.npy"
    index_path = _index_file_path(store_path)
    if not store_path.exists():
        raise VectorStoreError(f"Vector store not found: {store_path}")
    if (
        not manifest_path.exists()
        or not metadata_path.exists()
        or not vectors_path.exists()
        or not index_path.exists()
    ):
        raise VectorStoreError(f"Vector store is incomplete: {store_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    vectors = np.load(vectors_path)
    index = faiss.read_index(str(index_path))
    return manifest, metadata, vectors, index

###############################################################################
def _candidate_value(item: dict[str, Any], field_name: str) -> Any:
    current: Any = item
    for part in field_name.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current

###############################################################################
def _matches_clause(item: dict[str, Any], clause: dict[str, Any]) -> bool:
    field_name = str(clause.get("field") or "").strip()
    operator = str(clause.get("op") or "eq").strip().lower()
    expected = clause.get("value")
    if not field_name:
        raise VectorStoreError("Filter clauses require a field")
    actual = _candidate_value(item, field_name)

    if operator == "exists":
        return actual is not None
    if operator == "eq":
        return actual == expected
    if operator == "in":
        return isinstance(expected, list) and actual in expected
    if operator == "contains":
        if isinstance(actual, str):
            return str(expected or "") in actual
        if isinstance(actual, list):
            return expected in actual
        return False
    if operator == "gt":
        return actual is not None and actual > expected
    if operator == "gte":
        return actual is not None and actual >= expected
    if operator == "lt":
        return actual is not None and actual < expected
    if operator == "lte":
        return actual is not None and actual <= expected
    raise VectorStoreError(f"Unsupported filter operator: {operator}")

###############################################################################
def _matches_filter(item: dict[str, Any], filter_spec: dict[str, Any] | None) -> bool:
    if not filter_spec:
        return True

    _validate_filter_shape(filter_spec)
    must = filter_spec.get("must", [])
    should = filter_spec.get("should", [])
    must_not = filter_spec.get("must_not", [])
    minimum_should_match = filter_spec.get(
        "minimum_should_match", 1 if should else 0
    )

    if any(
        _matches_clause(item, clause) for clause in must_not
    ):
        return False
    if any(not _matches_clause(item, clause) for clause in must):
        return False

    if should:
        matched = sum(1 for clause in should if _matches_clause(item, clause))
        if matched < minimum_should_match:
            return False
    return True

###############################################################################
def _validate_filter_shape(filter_spec: dict[str, Any]) -> None:
    if not isinstance(filter_spec, dict):
        raise VectorStoreError("metadata filter must be an object")
    allowed_keys = {"must", "should", "must_not", "minimum_should_match"}
    unknown_keys = sorted(set(filter_spec).difference(allowed_keys))
    if unknown_keys:
        raise VectorStoreError(
            "Unsupported metadata filter keys: " + ", ".join(unknown_keys)
        )

    for group_name in ("must", "should", "must_not"):
        group = filter_spec.get(group_name, [])
        if not isinstance(group, list):
            raise VectorStoreError("Filter groups must be arrays")
        for clause in group:
            if not isinstance(clause, dict):
                raise VectorStoreError("Filter clauses must be objects")
            unknown_clause_keys = sorted(
                set(clause).difference({"field", "op", "value"})
            )
            if unknown_clause_keys:
                raise VectorStoreError(
                    "Unsupported filter clause keys: "
                    + ", ".join(unknown_clause_keys)
                )
            field_name = str(clause.get("field") or "").strip()
            if not field_name:
                raise VectorStoreError("Filter clauses require a field")
            operator = str(clause.get("op") or "eq").strip().lower()
            if operator not in {
                "eq",
                "in",
                "exists",
                "contains",
                "gt",
                "gte",
                "lt",
                "lte",
            }:
                raise VectorStoreError(f"Unsupported filter operator: {operator}")
            if operator == "in" and not isinstance(clause.get("value"), list):
                raise VectorStoreError("The 'in' filter operator requires a list value")

    if "minimum_should_match" in filter_spec:
        minimum_should_match = filter_spec["minimum_should_match"]
        if (
            isinstance(minimum_should_match, bool)
            or not isinstance(minimum_should_match, int)
            or minimum_should_match < 0
        ):
            raise VectorStoreError("minimum_should_match must be a non-negative integer")
        should_count = len(filter_spec.get("should", []))
        if minimum_should_match > should_count:
            raise VectorStoreError(
                "minimum_should_match cannot exceed the number of should clauses"
            )
        if not should_count and minimum_should_match:
            raise VectorStoreError(
                "minimum_should_match requires at least one should clause"
            )

###############################################################################
def _score_from_metric(
    metric: str, raw_score: float, *, raw_semantics: str = "similarity"
) -> float:
    normalized = _coerce_metric(metric)
    value = float(raw_score)
    if normalized == "cosine":
        if raw_semantics == "distance":
            return max(0.0, min(1.0, 1.0 - value))
        if raw_semantics == "cosine_similarity":
            return max(0.0, min(1.0, (value + 1.0) / 2.0))
        return max(0.0, min(1.0, value))
    if normalized == "l2":
        return 1.0 / (1.0 + max(value, 0.0))
    if normalized == "dot":
        if raw_semantics == "distance":
            return 1.0 - value
        return value
    raise VectorStoreError(f"Unsupported vector metric: {metric}")

###############################################################################
def _coerce_metric(metric: str) -> str:
    normalized = metric.lower().strip()
    if normalized == "euclidean":
        return "l2"
    return normalized

###############################################################################
def _score_semantics_for_metric(metric: str) -> str:
    return (
        "native_similarity"
        if _coerce_metric(metric) == "dot"
        else "normalized_similarity"
    )

###############################################################################
def _validate_vector_capabilities_filter(
    capabilities: VectorStoreCapabilities,
    filter_spec: dict[str, Any] | None,
) -> None:
    if not filter_spec:
        return
    _validate_filter_shape(filter_spec)
    if not capabilities.supports_metadata_filtering:
        raise VectorStoreError(
            f"Backend '{capabilities.backend}' does not support metadata filtering"
        )
    groups = {
        group_name: filter_spec.get(group_name, [])
        for group_name in ("must", "should", "must_not")
    }
    if not capabilities.supports_filter_groups and any(groups.values()):
        raise VectorStoreError(
            f"Backend '{capabilities.backend}' does not support grouped metadata filters"
        )
    supported_operators = set(capabilities.supported_filter_operators)
    for group in groups.values():
        for clause in group:
            operator = str(clause.get("op") or "eq").strip().lower()
            if operator not in supported_operators:
                raise VectorStoreError(
                    f"Backend '{capabilities.backend}' does not support metadata filter operator '{operator}'"
                )
    if (
        "minimum_should_match" in filter_spec
        and not capabilities.supports_minimum_should_match
    ):
        raise VectorStoreError(
            f"Backend '{capabilities.backend}' does not support minimum_should_match"
        )

###############################################################################
def validate_vector_request_capabilities(
    capabilities: VectorStoreCapabilities,
    *,
    metric: str | None = None,
    namespace: str = "",
    search_mode: str | None = None,
    search_engine: str | None = None,
    filter_spec: dict[str, Any] | None = None,
    keyword_query: str | None = None,
    create_keyword_index: bool = False,
) -> None:
    if metric is not None:
        normalized_metric = _coerce_metric(metric)
        if normalized_metric not in capabilities.supported_metrics:
            raise VectorStoreError(
                f"Backend '{capabilities.backend}' does not support metric '{normalized_metric}'"
            )
    if namespace.strip() and not capabilities.supports_namespaces:
        raise VectorStoreError(
            f"Backend '{capabilities.backend}' does not support namespaces"
        )
    if (
        search_mode is not None
        and search_mode not in capabilities.supported_search_modes
    ):
        mode_label = (
            "hybrid mode" if search_mode == "hybrid" else f"search mode '{search_mode}'"
        )
        raise VectorStoreError(
            f"Backend '{capabilities.backend}' does not support {mode_label}"
        )
    if (
        search_engine is not None
        and search_engine not in capabilities.supported_search_engines
    ):
        engine_label = (
            "faiss_augmented engine"
            if search_engine == "faiss_augmented"
            else f"search engine '{search_engine}'"
        )
        raise VectorStoreError(
            f"Backend '{capabilities.backend}' does not support {engine_label}"
        )
    if keyword_query and search_mode not in {"keyword", "hybrid"}:
        raise VectorStoreError(
            "keyword_query is only valid for keyword or hybrid search"
        )
    if create_keyword_index and not capabilities.supports_keyword_index:
        raise VectorStoreError(
            f"Backend '{capabilities.backend}' does not support keyword indexes"
        )
    _validate_vector_capabilities_filter(capabilities, filter_spec)

###############################################################################
def _extract_provider_config(
    *,
    provider_config: dict[str, Any] | None,
    endpoint_url: str,
    api_key: str,
) -> tuple[dict[str, Any], str, str]:
    config = provider_config if isinstance(provider_config, dict) else {}
    endpoint = str(config.get("endpoint_url") or endpoint_url or "").strip()
    if endpoint:
        parsed_endpoint = urlsplit(endpoint)
        if parsed_endpoint.username or parsed_endpoint.password:
            raise VectorStoreError("Credential-bearing vector store URLs are forbidden")
    token = str(config.get("api_key") or api_key or "").strip()
    return config, endpoint, token

###############################################################################
def _register_runtime_secret(secret: str) -> str:
    if not secret:
        return ""
    handle = f"vector-secret:{uuid4().hex}"
    _SECRET_REGISTRY[handle] = secret
    while len(_SECRET_REGISTRY) > _SECRET_REGISTRY_LIMIT:
        _SECRET_REGISTRY.popitem(last=False)
    return handle

###############################################################################
def _resolve_runtime_secret(config: dict[str, Any]) -> str:
    handle = str(config.get("secret_handle") or "")
    secret = _SECRET_REGISTRY.get(handle, "")
    if secret:
        return secret
    profile_name = str(config.get("credential_profile") or "").strip()
    provider = str(config.get("provider") or "").strip().lower()
    if not profile_name or not provider:
        return ""
    from server.services.configuration import configuration_service

    try:
        access_key = configuration_service.resolve_access_key(
            profile_name=profile_name, provider=provider
        )
    except (KeyError, ValueError):
        return ""
    return access_key.api_key or ""

###############################################################################
def reset_vector_secret_registry() -> None:
    _SECRET_REGISTRY.clear()

###############################################################################
def _redacted_provider_config(config: dict[str, Any], token: str) -> dict[str, Any]:
    safe = {
        key: value
        for key, value in config.items()
        if key.lower() not in {"api_key", "password", "token", "authorization"}
    }
    if token:
        safe["secret_handle"] = _register_runtime_secret(token)
    return safe

###############################################################################
def _qdrant_condition(clause: dict[str, Any], qm: Any) -> Any:
    field = str(clause.get("field") or "").strip()
    op = str(clause.get("op") or "eq").strip().lower()
    value = clause.get("value")
    if not field:
        return None
    if op == "eq":
        return qm.FieldCondition(key=field, match=qm.MatchValue(value=value))
    if op == "in" and isinstance(value, list):
        return qm.FieldCondition(key=field, match=qm.MatchAny(any=value))
    if op in {"gt", "gte", "lt", "lte"}:
        kwargs: dict[str, Any] = {}
        if op == "gt":
            kwargs["gt"] = value
        elif op == "gte":
            kwargs["gte"] = value
        elif op == "lt":
            kwargs["lt"] = value
        elif op == "lte":
            kwargs["lte"] = value
        return qm.FieldCondition(key=field, range=qm.Range(**kwargs))
    return None

###############################################################################
def _pinecone_clause(clause: dict[str, Any]) -> dict[str, Any] | None:
    field = str(clause.get("field") or "").strip()
    op = str(clause.get("op") or "eq").strip().lower()
    value = clause.get("value")
    if not field:
        return None
    key = f"metadata.{field}"
    if op == "eq":
        return {key: {"$eq": value}}
    if op == "in" and isinstance(value, list):
        return {key: {"$in": value}}
    if op == "gt":
        return {key: {"$gt": value}}
    if op == "gte":
        return {key: {"$gte": value}}
    if op == "lt":
        return {key: {"$lt": value}}
    if op == "lte":
        return {key: {"$lte": value}}
    return None

###############################################################################
def _milvus_format_value(value: Any) -> str:
    if isinstance(value, str):
        return '"' + value.replace('"', '"') + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)

###############################################################################
def _milvus_clause_expression(clause: dict[str, Any]) -> str:
    field = str(clause.get("field") or "").strip()
    op = str(clause.get("op") or "eq").strip().lower()
    value = clause.get("value")
    if not field:
        return ""
    if op == "eq":
        return f"{field} == {_milvus_format_value(value)}"
    if op == "gt":
        return f"{field} > {_milvus_format_value(value)}"
    if op == "gte":
        return f"{field} >= {_milvus_format_value(value)}"
    if op == "lt":
        return f"{field} < {_milvus_format_value(value)}"
    if op == "lte":
        return f"{field} <= {_milvus_format_value(value)}"
    if op == "in" and isinstance(value, list):
        values = ", ".join(_milvus_format_value(item) for item in value)
        return f"{field} in [{values}]"
    return ""

###############################################################################
def _sanitize_metadata_entry(point: VectorPoint | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _point_attr(point, "id"),
        "chunk_id": _point_attr(point, "chunk_id"),
        "document_id": _point_attr(point, "document_id"),
        "text": _point_attr(point, "text"),
        "source_uri": _point_attr(point, "source_uri"),
        "embedding_provider": _point_attr(point, "embedding_provider"),
        "embedding_model": _point_attr(point, "embedding_model"),
        "embedding_revision": _point_attr(point, "embedding_revision") or "",
        "normalized": bool(_point_attr(point, "normalized")),
        "metadata": _point_attr(point, "metadata") or {},
    }

###############################################################################
def _materialize_lancedb_rows(payload: Any) -> list[dict[str, Any]]:
    if hasattr(payload, "to_list"):
        try:
            rows = payload.to_list()
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        except Exception:  # noqa: BLE001
            pass

    if hasattr(payload, "to_arrow"):
        try:
            rows = payload.to_arrow().to_pylist()
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        except Exception:  # noqa: BLE001
            pass

    if hasattr(payload, "to_pandas"):
        try:
            frame = payload.to_pandas()
            return frame.to_dict(orient="records")
        except Exception:  # noqa: BLE001
            pass

    return []

###############################################################################
class VectorStoreAdapter:
    backend = "faiss"
    capabilities = VectorStoreCapabilities(
        backend="faiss",
        supported_metrics=["cosine", "l2", "dot"],
        supported_search_modes=["vector"],
        supported_search_engines=["native", "faiss_augmented"],
        supports_namespaces=False,
        supports_metadata_filtering=True,
        supported_filter_operators=[
            "eq",
            "in",
            "exists",
            "contains",
            "gt",
            "gte",
            "lt",
            "lte",
        ],
        supports_filter_groups=True,
        supports_minimum_should_match=True,
        supports_keyword_index=False,
        supported_operations=[
            "insert",
            "upsert",
            "update",
            "delete_ids",
            "delete_document",
            "delete_filter",
            "inspect",
            "delete_collection",
            "reload",
            "search",
            "close",
        ],
        score_semantics_by_metric={
            "cosine": "normalized_similarity",
            "l2": "normalized_similarity",
            "dot": "native_similarity",
        },
    )

    # -------------------------------------------------------------------------
    def validate_connection(
        self,
        *,
        index_name: str,
        storage_directory: str = "",
        namespace: str = "",
        endpoint_url: str = "",
        api_key: str = "",
        collection_name: str = "",
        database_name: str = "",
        provider_config: dict[str, Any] | None = None,
    ) -> None:
        _ = (
            endpoint_url,
            api_key,
            collection_name,
            database_name,
            provider_config,
        )
        self.validate_connection_capabilities(namespace=namespace)
        _normalize_index_name(index_name)
        _resolve_vectorstore_root(storage_directory)

    # -------------------------------------------------------------------------
    def describe_capabilities(self) -> VectorStoreCapabilities:
        return self.capabilities.model_copy(deep=True)

    # -------------------------------------------------------------------------
    def validate_connection_capabilities(self, *, namespace: str = "") -> None:
        validate_vector_request_capabilities(
            self.describe_capabilities(), namespace=namespace
        )

    # -------------------------------------------------------------------------
    def validate_write_capabilities(
        self, *, metric: str, namespace: str = "", create_keyword_index: bool = False
    ) -> None:
        validate_vector_request_capabilities(
            self.describe_capabilities(),
            metric=metric,
            namespace=namespace,
            create_keyword_index=create_keyword_index,
        )

    # -------------------------------------------------------------------------
    def validate_search_capabilities(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        search_mode: str,
        search_engine: str,
        filter_spec: dict[str, Any] | None,
        keyword_query: str | None,
    ) -> None:
        store_metric = str(_store_attr(store, "metric") or "cosine")
        store_namespace = str(_store_attr(store, "namespace") or "").strip()
        if not store_namespace:
            metadata = _store_attr(store, "metadata")
            if isinstance(metadata, dict):
                store_namespace = str(metadata.get("namespace") or "").strip()
        validate_vector_request_capabilities(
            self.describe_capabilities(),
            metric=store_metric,
            namespace=store_namespace,
            search_mode=search_mode,
            search_engine=search_engine,
            filter_spec=filter_spec,
            keyword_query=keyword_query,
        )

    # -------------------------------------------------------------------------
    def write_points(
        self,
        *,
        index_name: str,
        storage_directory: str = "",
        metric: str,
        write_mode: str,
        namespace: str = "",
        endpoint_url: str = "",
        api_key: str = "",
        collection_name: str = "",
        database_name: str = "",
        provider_config: dict[str, Any] | None = None,
        points: list[VectorPoint | dict[str, Any]],
        index_type: str = "hnsw_flat",
        nlist: int = 256,
        hnsw_m: int = 16,
        id_conflict_policy: str = "reject",
        lock_timeout: float = 10.0,
        **_: Any,
    ) -> VectorStoreHandle:
        self.validate_write_capabilities(
            metric=metric,
            namespace=namespace,
            create_keyword_index=bool(_.get("create_keyword_index", False)),
        )
        _ = (
            endpoint_url,
            api_key,
            collection_name,
            database_name,
            provider_config,
        )
        if not points:
            raise VectorStoreError(
                "Vector store write requires at least one vector point"
            )

        normalized_index_name = _normalize_index_name(index_name)
        root_path = _resolve_vectorstore_root(storage_directory)
        root_path.mkdir(parents=True, exist_ok=True)
        dimension = len(_point_attr(points[0], "vector"))
        if any(len(_point_attr(point, "vector")) != dimension for point in points):
            raise VectorStoreError("All vector points must have the same dimension")

        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        incoming_ids = [str(_point_attr(point, "id") or "") for point in points]
        duplicate_incoming = sorted(
            {point_id for point_id in incoming_ids if incoming_ids.count(point_id) > 1}
        )
        if duplicate_incoming:
            raise VectorStoreConflictError(duplicate_incoming)
        conflict_policy = id_conflict_policy.strip().lower()
        if conflict_policy not in {"reject", "upsert"}:
            raise VectorStoreError("id_conflict_policy must be 'reject' or 'upsert'")

        incoming_vectors = np.asarray(
            [_point_attr(point, "vector") for point in points], dtype=np.float32
        )
        normalized_metric = _coerce_metric(metric)
        normalized = normalized_metric == "cosine"
        if normalized:
            incoming_vectors = _normalize_vectors(incoming_vectors)
        incoming_metadata = [_sanitize_metadata_entry(point) for point in points]
        store_path = root_path / normalized_index_name

        manifest = {
            "backend": self.backend,
            "index_name": normalized_index_name,
            "metric": normalized_metric,
            "index_type": index_type.lower().strip(),
            "dimension": dimension,
            "count": len(incoming_metadata),
            "embedding_provider": str(
                _point_attr(points[0], "embedding_provider") or ""
            ),
            "embedding_model": str(_point_attr(points[0], "embedding_model") or ""),
            "embedding_revision": str(
                _point_attr(points[0], "embedding_revision") or ""
            ),
            "normalized": normalized,
            "nlist": nlist,
            "hnsw_m": hnsw_m,
        }

        with _store_lock(store_path, lock_timeout):
            vectors = incoming_vectors
            metadata_entries = incoming_metadata
            if write_mode_normalized == "append" and store_path.exists():
                existing_manifest, existing_metadata, existing_vectors, _ = _load_store(
                    {"artifact_path": str(store_path)}
                )
                compatibility_fields = (
                    "dimension",
                    "metric",
                    "embedding_provider",
                    "embedding_model",
                    "embedding_revision",
                    "normalized",
                )
                mismatches = [
                    field
                    for field in compatibility_fields
                    if existing_manifest.get(field) != manifest.get(field)
                ]
                if mismatches:
                    raise VectorStoreError(
                        "Existing vector store is incompatible: " + ", ".join(mismatches)
                    )
                existing_ids = {str(item.get("id", "")) for item in existing_metadata}
                conflicts = sorted(existing_ids.intersection(incoming_ids))
                if conflicts and conflict_policy == "reject":
                    raise VectorStoreConflictError(conflicts)
                if conflicts:
                    keep_indexes = [
                        index
                        for index, item in enumerate(existing_metadata)
                        if str(item.get("id", "")) not in conflicts
                    ]
                    existing_vectors = existing_vectors[keep_indexes]
                    existing_metadata = [existing_metadata[index] for index in keep_indexes]
                vectors = np.vstack([existing_vectors.astype(np.float32), vectors])
                metadata_entries = [*existing_metadata, *metadata_entries]

            manifest["count"] = len(metadata_entries)
            temp_path = store_path.with_name(f".{store_path.name}.tmp-{uuid4().hex}")
            backup_path = store_path.with_name(f".{store_path.name}.backup-{uuid4().hex}")
            try:
                temp_path.mkdir(parents=True)
                index = _build_index(
                    vectors,
                    metric=normalized_metric,
                    index_type=index_type,
                    nlist=nlist,
                    hnsw_m=hnsw_m,
                )
                faiss.write_index(index, str(_index_file_path(temp_path)))
                np.save(temp_path / "vectors.npy", vectors)
                (temp_path / "manifest.json").write_text(
                    json.dumps(manifest, indent=2), encoding="utf-8"
                )
                (temp_path / "metadata.json").write_text(
                    json.dumps(metadata_entries, indent=2), encoding="utf-8"
                )
                if store_path.exists():
                    store_path.replace(backup_path)
                temp_path.replace(store_path)
                shutil.rmtree(backup_path, ignore_errors=True)
            except Exception:
                shutil.rmtree(temp_path, ignore_errors=True)
                if backup_path.exists() and not store_path.exists():
                    backup_path.replace(store_path)
                raise

        return VectorStoreHandle(
            backend=self.backend,
            index_name=normalized_index_name,
            artifact_path=str(store_path),
            metric=manifest["metric"],
            dimension=dimension,
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            embedding_revision=manifest["embedding_revision"],
            normalized=normalized,
            namespace=namespace,
            metadata={
                "index_type": manifest["index_type"],
                "count": manifest["count"],
                "nlist": nlist,
                "hnsw_m": hnsw_m,
                "storage_directory": str(root_path),
            },
        )

    # -------------------------------------------------------------------------
    def _require_local_lifecycle(self, operation: str) -> None:
        if self.backend != "faiss":
            raise VectorStoreUnsupportedOperationError(
                f"Operation '{operation}' is not supported by backend '{self.backend}'"
            )

    # -------------------------------------------------------------------------
    def insert_points(self, **kwargs: Any) -> VectorStoreHandle:
        return self.write_points(
            **kwargs,
            write_mode="append",
            id_conflict_policy="reject",
        )

    # -------------------------------------------------------------------------
    def upsert_points(self, **kwargs: Any) -> VectorStoreHandle:
        return self.write_points(
            **kwargs,
            write_mode="append",
            id_conflict_policy="upsert",
        )

    # -------------------------------------------------------------------------
    def update_points(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        points: list[VectorPoint | dict[str, Any]],
        lock_timeout: float = 10.0,
    ) -> VectorMutationResult:
        self._require_local_lifecycle("update")
        manifest, metadata, _, _ = _load_store(store)
        existing_ids = {str(item.get("id", "")) for item in metadata}
        requested_ids = [str(_point_attr(point, "id") or "") for point in points]
        missing = sorted(set(requested_ids).difference(existing_ids))
        if missing:
            raise VectorStoreError(
                "Cannot update missing vector record IDs: " + ", ".join(missing)
            )
        store_path = _resolve_store_path_from_handle(store)
        self.write_points(
            index_name=str(manifest["index_name"]),
            storage_directory=str(store_path.parent),
            metric=str(manifest["metric"]),
            write_mode="append",
            id_conflict_policy="upsert",
            points=points,
            index_type=str(manifest.get("index_type", "flat")),
            nlist=int(manifest.get("nlist", 256)),
            hnsw_m=int(manifest.get("hnsw_m", 16)),
            lock_timeout=lock_timeout,
        )
        return VectorMutationResult(
            operation="update",
            affected_count=len(requested_ids),
            affected_ids=sorted(requested_ids),
        )

    # -------------------------------------------------------------------------
    def inspect_collection(
        self, *, store: VectorStoreHandle | dict[str, Any]
    ) -> VectorCollectionInfo:
        self._require_local_lifecycle("inspect")
        store_path = _resolve_store_path_from_handle(store)
        if not store_path.exists():
            return VectorCollectionInfo(
                backend=self.backend,
                index_name=str(_store_attr(store, "index_name") or store_path.name),
                exists=False,
            )
        manifest, metadata, _, _ = _load_store(store)
        return VectorCollectionInfo(
            backend=self.backend,
            index_name=str(manifest.get("index_name", store_path.name)),
            exists=True,
            count=len(metadata),
            metric=str(manifest.get("metric", "")),
            dimension=int(manifest.get("dimension", 0)),
            embedding_provider=str(manifest.get("embedding_provider", "")),
            embedding_model=str(manifest.get("embedding_model", "")),
            embedding_revision=str(manifest.get("embedding_revision", "")),
            normalized=bool(manifest.get("normalized", False)),
        )

    # -------------------------------------------------------------------------
    def reload(
        self, *, store: VectorStoreHandle | dict[str, Any]
    ) -> VectorStoreHandle:
        self._require_local_lifecycle("reload")
        manifest, metadata, _, _ = _load_store(store)
        store_path = _resolve_store_path_from_handle(store)
        return VectorStoreHandle(
            backend=self.backend,
            index_name=str(manifest["index_name"]),
            artifact_path=str(store_path),
            metric=str(manifest["metric"]),
            dimension=int(manifest["dimension"]),
            embedding_provider=str(manifest.get("embedding_provider", "")),
            embedding_model=str(manifest.get("embedding_model", "")),
            embedding_revision=str(manifest.get("embedding_revision", "")),
            normalized=bool(manifest.get("normalized", False)),
            namespace=str(_store_attr(store, "namespace") or ""),
            metadata={
                "index_type": str(manifest.get("index_type", "flat")),
                "count": len(metadata),
                "nlist": int(manifest.get("nlist", 256)),
                "hnsw_m": int(manifest.get("hnsw_m", 16)),
                "storage_directory": str(store_path.parent),
            },
        )

    # -------------------------------------------------------------------------
    def _replace_local_points(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        retained_indexes: list[int],
        operation: str,
        affected_ids: list[str],
        lock_timeout: float,
    ) -> VectorMutationResult:
        manifest, metadata, vectors, _ = _load_store(store)
        if not retained_indexes:
            self.delete_collection(store=store, lock_timeout=lock_timeout)
        else:
            points = [
                {
                    **metadata[index],
                    "vector": vectors[index].tolist(),
                }
                for index in retained_indexes
            ]
            self.write_points(
                index_name=str(manifest["index_name"]),
                storage_directory=str(_resolve_store_path_from_handle(store).parent),
                metric=str(manifest["metric"]),
                write_mode="overwrite",
                points=points,
                index_type=str(manifest.get("index_type", "flat")),
                nlist=int(manifest.get("nlist", 256)),
                hnsw_m=int(manifest.get("hnsw_m", 16)),
                lock_timeout=lock_timeout,
            )
        return VectorMutationResult(
            operation=operation,
            affected_count=len(affected_ids),
            affected_ids=sorted(affected_ids),
        )

    # -------------------------------------------------------------------------
    def delete_ids(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        ids: list[str],
        lock_timeout: float = 10.0,
    ) -> VectorMutationResult:
        self._require_local_lifecycle("delete_ids")
        _, metadata, _, _ = _load_store(store)
        requested = set(ids)
        affected = [str(item.get("id", "")) for item in metadata if item.get("id") in requested]
        retained = [index for index, item in enumerate(metadata) if item.get("id") not in requested]
        return self._replace_local_points(
            store=store,
            retained_indexes=retained,
            operation="delete_ids",
            affected_ids=affected,
            lock_timeout=lock_timeout,
        )

    # -------------------------------------------------------------------------
    def delete_document(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        document_id: str,
        lock_timeout: float = 10.0,
    ) -> VectorMutationResult:
        self._require_local_lifecycle("delete_document")
        _, metadata, _, _ = _load_store(store)
        affected = [
            str(item.get("id", ""))
            for item in metadata
            if str(item.get("document_id", "")) == document_id
        ]
        retained = [
            index
            for index, item in enumerate(metadata)
            if str(item.get("document_id", "")) != document_id
        ]
        return self._replace_local_points(
            store=store,
            retained_indexes=retained,
            operation="delete_document",
            affected_ids=affected,
            lock_timeout=lock_timeout,
        )

    # -------------------------------------------------------------------------
    def delete_filter(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        filter_spec: dict[str, Any],
        lock_timeout: float = 10.0,
    ) -> VectorMutationResult:
        self._require_local_lifecycle("delete_filter")
        _, metadata, _, _ = _load_store(store)
        affected = [
            str(item.get("id", "")) for item in metadata if _matches_filter(item, filter_spec)
        ]
        retained = [
            index for index, item in enumerate(metadata) if not _matches_filter(item, filter_spec)
        ]
        return self._replace_local_points(
            store=store,
            retained_indexes=retained,
            operation="delete_filter",
            affected_ids=affected,
            lock_timeout=lock_timeout,
        )

    # -------------------------------------------------------------------------
    def delete_collection(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        lock_timeout: float = 10.0,
    ) -> VectorMutationResult:
        self._require_local_lifecycle("delete_collection")
        store_path = _resolve_store_path_from_handle(store)
        affected_ids: list[str] = []
        with _store_lock(store_path, lock_timeout):
            if store_path.exists():
                _, metadata, _, _ = _load_store(store)
                affected_ids = [str(item.get("id", "")) for item in metadata]
                shutil.rmtree(store_path)
        return VectorMutationResult(
            operation="delete_collection",
            affected_count=len(affected_ids),
            affected_ids=sorted(affected_ids),
        )

    # -------------------------------------------------------------------------
    def close(self) -> None:
        return None

    # -------------------------------------------------------------------------
    def search(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        query_vector: list[float],
        top_k: int,
        score_threshold: float,
        filter_spec: dict[str, Any] | None,
        include_metadata: bool,
        ann_search_depth: int = 100,
        search_mode: str = "vector",
        keyword_query: str | None = None,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        **_: Any,
    ) -> list[RetrievalHit]:
        search_engine = str(_.get("search_engine") or "native")
        self.validate_search_capabilities(
            store=store,
            search_mode=search_mode,
            search_engine=search_engine,
            filter_spec=filter_spec,
            keyword_query=keyword_query,
        )
        manifest, metadata, vectors, index = _load_store(store)
        if len(query_vector) != int(manifest.get("dimension", 0)):
            raise VectorStoreError(
                "Query vector dimension does not match the vector store"
            )

        query = np.asarray([query_vector], dtype=np.float32)
        metric = str(manifest.get("metric", "cosine"))
        if metric == "cosine":
            query = _normalize_vectors(query)

        candidate_indexes = [
            idx
            for idx, item in enumerate(metadata)
            if isinstance(item, dict) and _matches_filter(item, filter_spec)
        ]
        if not candidate_indexes:
            return []

        if len(candidate_indexes) != len(metadata):
            filtered_vectors = vectors[candidate_indexes]
            raw_scores = (
                filtered_vectors @ query[0]
                if metric in {"cosine", "ip"}
                else np.sum((filtered_vectors - query[0]) ** 2, axis=1)
            )
            order = np.argsort(raw_scores if metric == "l2" else -raw_scores)
            ranked = [
                (candidate_indexes[int(pos)], float(raw_scores[int(pos)]))
                for pos in order[:top_k]
            ]
        else:
            normalized_depth = max(1, int(ann_search_depth))
            if hasattr(index, "hnsw") and hasattr(index.hnsw, "efSearch"):
                try:
                    index.hnsw.efSearch = normalized_depth
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Unable to apply HNSW efSearch=%s: %s", normalized_depth, exc
                    )
            if hasattr(index, "nprobe"):
                try:
                    index.nprobe = max(1, normalized_depth)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Unable to apply IVF nprobe=%s: %s", normalized_depth, exc
                    )

            search_limit = min(max(top_k * 5, top_k, normalized_depth), len(metadata))
            distances, indices = index.search(query, search_limit)
            ranked = [
                (int(candidate_index), float(distance))
                for candidate_index, distance in zip(
                    indices[0], distances[0], strict=False
                )
                if int(candidate_index) >= 0
            ]

        results: list[RetrievalHit] = []
        for item_index, raw_score in ranked:
            entry = metadata[item_index]
            raw_semantics = "cosine_similarity" if metric == "cosine" else "distance"
            if metric == "dot":
                raw_semantics = "similarity"
            score = _score_from_metric(
                metric, raw_score, raw_semantics=raw_semantics
            )
            if score < score_threshold:
                continue
            results.append(
                RetrievalHit(
                    id=str(entry.get("id", "")),
                    chunk_id=str(entry.get("chunk_id", "")),
                    document_id=str(entry.get("document_id", "")),
                    text=str(entry.get("text", "")),
                    source_uri=str(entry.get("source_uri", "")),
                    score=score,
                    score_semantics=_score_semantics_for_metric(metric),
                    metadata=entry.get("metadata", {}) if include_metadata else {},
                )
            )
            if len(results) >= top_k:
                break
        return results
