from __future__ import annotations

import json
import importlib
import logging
import re
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import faiss
from ParaGraph.server.common.constants import RESOURCES_PATH
from ParaGraph.server.common.security import ensure_path_within_root, is_cloud_deployment
from ParaGraph.server.domain.workflow_payloads import RetrievalHit, VectorPoint, VectorStoreHandle


ARTIFACT_ROOT = Path(RESOURCES_PATH) / "artifacts"
VECTORSTORE_ROOT = ARTIFACT_ROOT / "vectorstores"
INDEX_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
logger = logging.getLogger(__name__)


def _import_module_or_error(module_name: str, package_hint: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise VectorStoreError(f"{package_hint} support requires installing the '{module_name}' package") from exc


def _import_pinecone_client() -> tuple[Any, Any]:
    pinecone_module = _import_module_or_error("pinecone", "Pinecone")
    pinecone_client = getattr(pinecone_module, "Pinecone", None)
    serverless_spec = getattr(pinecone_module, "ServerlessSpec", None)
    if pinecone_client is None or serverless_spec is None:
        raise VectorStoreError("Installed pinecone package does not expose Pinecone client APIs")
    return pinecone_client, serverless_spec


def _import_milvus_client() -> Any:
    milvus_module = _import_module_or_error("pymilvus", "Milvus")
    milvus_client = getattr(milvus_module, "MilvusClient", None)
    if milvus_client is None:
        raise VectorStoreError("Installed pymilvus package does not expose MilvusClient")
    return milvus_client


def _import_qdrant_clients() -> tuple[Any, Any]:
    qdrant_module = _import_module_or_error("qdrant_client", "Qdrant")
    qdrant_client = getattr(qdrant_module, "QdrantClient", None)
    qdrant_models = getattr(qdrant_module, "models", None)
    if qdrant_client is None or qdrant_models is None:
        raise VectorStoreError("Installed qdrant-client package does not expose required client APIs")
    return qdrant_client, qdrant_models


def _import_weaviate_module() -> Any:
    return _import_module_or_error("weaviate", "Weaviate")


def _import_chromadb_module() -> Any:
    return _import_module_or_error("chromadb", "Chroma")


def _import_lancedb_module() -> Any:
    return _import_module_or_error("lancedb", "LanceDB")

def _resolve_vectorstore_root(storage_directory: str | None) -> Path:
    selected = str(storage_directory or "").strip()
    default_root = VECTORSTORE_ROOT.resolve()
    if not selected:
        return default_root

    candidate = Path(selected).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
        if is_cloud_deployment():
            return ensure_path_within_root(resolved, default_root, label="storage_directory")
        return resolved

    # Keep legacy relative roots anchored under artifacts/vectorstores.
    resolved = (VECTORSTORE_ROOT / candidate).resolve()
    return ensure_path_within_root(resolved, default_root, label="storage_directory")




def _normalize_index_name(index_name: str) -> str:
    normalized = str(index_name or "").strip()
    if not INDEX_NAME_PATTERN.fullmatch(normalized):
        raise VectorStoreError("index_name must contain only letters, numbers, dot, underscore, or dash")
    return normalized


class VectorStoreError(ValueError):
    pass

def _point_attr(point: VectorPoint | dict[str, Any], name: str) -> Any:
    if isinstance(point, dict):
        return point.get(name)
    return getattr(point, name)


def _store_attr(store: VectorStoreHandle | dict[str, Any], name: str) -> Any:
    if isinstance(store, dict):
        return store.get(name)
    return getattr(store, name)



def _metric_code(metric: str):
    normalized = metric.lower().strip()
    if normalized == "cosine":
        return faiss.METRIC_INNER_PRODUCT
    if normalized == "ip":
        return faiss.METRIC_INNER_PRODUCT
    if normalized == "l2":
        return faiss.METRIC_L2
    raise VectorStoreError(f"Unsupported vector metric: {metric}")


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    safe_norms = np.where(norms == 0.0, 1.0, norms)
    return vectors / safe_norms


def _index_paths(root_path: Path, index_name: str) -> tuple[Path, Path, Path, Path]:
    store_path = root_path / index_name
    return (
        store_path,
        store_path / "manifest.json",
        store_path / "metadata.json",
        store_path / "vectors.npy",
    )


def _index_file_path(store_path: Path) -> Path:
    return store_path / "index.faiss"

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
        quantizer = faiss.IndexFlatL2(dim) if faiss_metric == faiss.METRIC_L2 else faiss.IndexFlatIP(dim)
        nlist_value = max(1, min(nlist, int(vectors.shape[0])))
        index = faiss.IndexIVFFlat(quantizer, dim, nlist_value, faiss_metric)
        if vectors.shape[0] == 0:
            raise VectorStoreError("Cannot build IVF index without vectors")
        index.train(vectors)
    else:
        raise VectorStoreError(f"Unsupported FAISS index type: {index_type}")

    index.add(vectors)
    return index


def _resolve_store_path_from_handle(store: VectorStoreHandle | dict[str, Any]) -> Path:
    artifact_path = str(_store_attr(store, "artifact_path") or "").strip()
    artifact_root = ARTIFACT_ROOT.resolve()
    if artifact_path:
        candidate = Path(artifact_path).expanduser()
        if candidate.is_absolute():
            resolved = candidate.resolve()
            if is_cloud_deployment():
                return ensure_path_within_root(resolved, artifact_root, label="artifact_path")
            return resolved
        resolved = (ARTIFACT_ROOT / candidate).resolve()
        return ensure_path_within_root(resolved, artifact_root, label="artifact_path")

    index_name = _normalize_index_name(str(_store_attr(store, "index_name") or ""))
    root = _resolve_vectorstore_root(_store_attr(store, "storage_directory"))
    return (root / index_name).resolve()


def _load_store(store: VectorStoreHandle | dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray, Any]:
    store_path = _resolve_store_path_from_handle(store)
    manifest_path = store_path / "manifest.json"
    metadata_path = store_path / "metadata.json"
    vectors_path = store_path / "vectors.npy"
    index_path = _index_file_path(store_path)
    if not store_path.exists():
        raise VectorStoreError(f"Vector store not found: {store_path}")
    if not manifest_path.exists() or not metadata_path.exists() or not vectors_path.exists() or not index_path.exists():
        raise VectorStoreError(f"Vector store is incomplete: {store_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    vectors = np.load(vectors_path)
    index = faiss.read_index(str(index_path))
    return manifest, metadata, vectors, index

def _candidate_value(item: dict[str, Any], field_name: str) -> Any:
    current: Any = item
    for part in field_name.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


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


def _matches_filter(item: dict[str, Any], filter_spec: dict[str, Any] | None) -> bool:
    if not filter_spec:
        return True

    must = filter_spec.get("must", [])
    should = filter_spec.get("should", [])
    must_not = filter_spec.get("must_not", [])
    minimum_should_match = int(filter_spec.get("minimum_should_match", 1 if should else 0))

    if not isinstance(must, list) or not isinstance(should, list) or not isinstance(must_not, list):
        raise VectorStoreError("Filter groups must be arrays")

    if any(_matches_clause(item, clause) for clause in must_not if isinstance(clause, dict)):
        return False
    if any(not _matches_clause(item, clause) for clause in must if isinstance(clause, dict)):
        return False

    if should:
        matched = sum(1 for clause in should if isinstance(clause, dict) and _matches_clause(item, clause))
        if matched < minimum_should_match:
            return False
    return True


def _score_from_metric(metric: str, raw_score: float) -> float:
    normalized = metric.lower().strip()
    if normalized == "l2":
        return 1.0 / (1.0 + max(raw_score, 0.0))
    return raw_score



def _coerce_metric(metric: str) -> str:
    normalized = metric.lower().strip()
    if normalized == "euclidean":
        return "l2"
    return normalized


def _extract_provider_config(
    *,
    provider_config: dict[str, Any] | None,
    endpoint_url: str,
    api_key: str,
) -> tuple[dict[str, Any], str, str]:
    config = provider_config if isinstance(provider_config, dict) else {}
    endpoint = str(config.get("endpoint_url") or endpoint_url or "").strip()
    token = str(config.get("api_key") or api_key or "").strip()
    return config, endpoint, token


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


def _milvus_format_value(value: Any) -> str:
    if isinstance(value, str):
        return '"' + value.replace('"', '\"') + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


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
def _sanitize_metadata_entry(point: VectorPoint | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _point_attr(point, "id"),
        "chunk_id": _point_attr(point, "chunk_id"),
        "document_id": _point_attr(point, "document_id"),
        "text": _point_attr(point, "text"),
        "source_uri": _point_attr(point, "source_uri"),
        "embedding_provider": _point_attr(point, "embedding_provider"),
        "embedding_model": _point_attr(point, "embedding_model"),
        "metadata": _point_attr(point, "metadata") or {},
    }


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


class VectorStoreAdapter:
    backend = "faiss"

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
        _ = namespace, endpoint_url, api_key, collection_name, database_name, provider_config
        _normalize_index_name(index_name)
        _resolve_vectorstore_root(storage_directory)

    def describe_capabilities(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "supports_hybrid_search": False,
            "supports_metadata_filtering": True,
        }

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
        **_: Any,
    ) -> VectorStoreHandle:
        _ = namespace, endpoint_url, api_key, collection_name, database_name, provider_config
        if not points:
            raise VectorStoreError("Vector store write requires at least one vector point")

        normalized_index_name = _normalize_index_name(index_name)
        root_path = _resolve_vectorstore_root(storage_directory)
        root_path.mkdir(parents=True, exist_ok=True)
        dimension = len(_point_attr(points[0], "vector"))
        if any(len(_point_attr(point, "vector")) != dimension for point in points):
            raise VectorStoreError("All vector points must have the same dimension")

        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        vectors = np.asarray([_point_attr(point, "vector") for point in points], dtype=np.float32)
        if metric.lower().strip() == "cosine":
            vectors = _normalize_vectors(vectors)

        metadata_entries = [_sanitize_metadata_entry(point) for point in points]
        store_path, manifest_path, metadata_path, vectors_path = _index_paths(root_path, normalized_index_name)
        index_path = _index_file_path(store_path)

        if write_mode_normalized == "append" and store_path.exists():
            existing_manifest, existing_metadata, existing_vectors, _ = _load_store({"artifact_path": str(store_path)})
            if int(existing_manifest.get("dimension", 0)) != dimension:
                raise VectorStoreError("Existing vector store dimension does not match incoming vectors")
            if str(existing_manifest.get("metric", "")).lower() != metric.lower().strip():
                raise VectorStoreError("Existing vector store metric does not match incoming vectors")
            if str(existing_manifest.get("embedding_provider", "")).lower() != str(_point_attr(points[0], "embedding_provider") or "").lower():
                raise VectorStoreError("Existing vector store embedding provider does not match incoming vectors")
            if str(existing_manifest.get("embedding_model", "")) != str(_point_attr(points[0], "embedding_model") or ""):
                raise VectorStoreError("Existing vector store embedding model does not match incoming vectors")
            vectors = np.vstack([existing_vectors.astype(np.float32), vectors])
            metadata_entries = [*existing_metadata, *metadata_entries]
        elif store_path.exists():
            shutil.rmtree(store_path)

        store_path.mkdir(parents=True, exist_ok=True)
        index = _build_index(vectors, metric=metric, index_type=index_type, nlist=nlist, hnsw_m=hnsw_m)
        faiss.write_index(index, str(index_path))
        np.save(vectors_path, vectors)

        manifest = {
            "backend": self.backend,
            "index_name": normalized_index_name,
            "metric": metric.lower().strip(),
            "index_type": index_type.lower().strip(),
            "dimension": dimension,
            "count": len(metadata_entries),
            "embedding_provider": str(_point_attr(points[0], "embedding_provider") or ""),
            "embedding_model": str(_point_attr(points[0], "embedding_model") or ""),
            "nlist": nlist,
            "hnsw_m": hnsw_m,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata_entries, indent=2), encoding="utf-8")

        return VectorStoreHandle(
            backend=self.backend,
            index_name=normalized_index_name,
            artifact_path=str(store_path),
            metric=manifest["metric"],
            dimension=dimension,
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            metadata={
                "index_type": manifest["index_type"],
                "count": manifest["count"],
                "nlist": nlist,
                "hnsw_m": hnsw_m,
                "storage_directory": str(root_path),
            },
        )

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
        _ = keyword_query, vector_weight, keyword_weight
        if search_mode != "vector":
            raise VectorStoreError(f"Search mode '{search_mode}' is not supported by backend '{self.backend}'")
        manifest, metadata, vectors, index = _load_store(store)
        if len(query_vector) != int(manifest.get("dimension", 0)):
            raise VectorStoreError("Query vector dimension does not match the vector store")

        query = np.asarray([query_vector], dtype=np.float32)
        metric = str(manifest.get("metric", "cosine"))
        if metric == "cosine":
            query = _normalize_vectors(query)

        candidate_indexes = [
            idx for idx, item in enumerate(metadata)
            if isinstance(item, dict) and _matches_filter(item, filter_spec)
        ]
        if not candidate_indexes:
            return []

        if len(candidate_indexes) != len(metadata):
            filtered_vectors = vectors[candidate_indexes]
            raw_scores = filtered_vectors @ query[0] if metric in {"cosine", "ip"} else np.sum((filtered_vectors - query[0]) ** 2, axis=1)
            order = np.argsort(raw_scores if metric == "l2" else -raw_scores)
            ranked = [(candidate_indexes[int(pos)], float(raw_scores[int(pos)])) for pos in order[:top_k]]
        else:
            normalized_depth = max(1, int(ann_search_depth))
            if hasattr(index, "hnsw") and hasattr(index.hnsw, "efSearch"):
                try:
                    index.hnsw.efSearch = normalized_depth
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Unable to apply HNSW efSearch=%s: %s", normalized_depth, exc)
            if hasattr(index, "nprobe"):
                try:
                    index.nprobe = max(1, normalized_depth)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Unable to apply IVF nprobe=%s: %s", normalized_depth, exc)

            search_limit = min(max(top_k * 5, top_k, normalized_depth), len(metadata))
            distances, indices = index.search(query, search_limit)
            ranked = [
                (int(candidate_index), float(distance))
                for candidate_index, distance in zip(indices[0], distances[0], strict=False)
                if int(candidate_index) >= 0
            ]

        results: list[RetrievalHit] = []
        for item_index, raw_score in ranked:
            entry = metadata[item_index]
            score = _score_from_metric(metric, raw_score)
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
                    metadata=entry.get("metadata", {}) if include_metadata else {},
                )
            )
            if len(results) >= top_k:
                break
        return results


class LanceDbVectorStoreAdapter(VectorStoreAdapter):
    backend = "lancedb"

    def _load_lancedb(self):
        return _import_lancedb_module()

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
        create_vector_index: bool = True,
        **_: Any,
    ) -> VectorStoreHandle:
        _ = namespace, endpoint_url, api_key, collection_name, database_name, provider_config
        if not points:
            raise VectorStoreError("Vector store write requires at least one vector point")

        lancedb = self._load_lancedb()
        normalized_index_name = _normalize_index_name(index_name)
        root_path = _resolve_vectorstore_root(storage_directory)
        root_path.mkdir(parents=True, exist_ok=True)

        dimension = len(_point_attr(points[0], "vector"))
        if any(len(_point_attr(point, "vector")) != dimension for point in points):
            raise VectorStoreError("All vector points must have the same dimension")

        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        metric_normalized = metric.lower().strip()
        if metric_normalized not in {"l2", "cosine", "dot"}:
            raise VectorStoreError(f"Unsupported LanceDB metric: {metric}")

        rows = [_sanitize_metadata_entry(point) | {"vector": [float(item) for item in _point_attr(point, "vector")]} for point in points]
        db = lancedb.connect(str(root_path))
        table_names = set(db.table_names())

        if write_mode_normalized == "append" and normalized_index_name in table_names:
            table = db.open_table(normalized_index_name)
            current_rows = _materialize_lancedb_rows(table)
            if current_rows:
                existing_vector = current_rows[0].get("vector") if isinstance(current_rows[0], dict) else None
                if not isinstance(existing_vector, list) or len(existing_vector) != dimension:
                    raise VectorStoreError("Existing LanceDB table dimension does not match incoming vectors")
                existing_provider = str(current_rows[0].get("embedding_provider", "")) if isinstance(current_rows[0], dict) else ""
                existing_model = str(current_rows[0].get("embedding_model", "")) if isinstance(current_rows[0], dict) else ""
                incoming_provider = str(_point_attr(points[0], "embedding_provider") or "")
                incoming_model = str(_point_attr(points[0], "embedding_model") or "")
                if existing_provider.lower() != incoming_provider.lower():
                    raise VectorStoreError("Existing LanceDB table embedding provider does not match incoming vectors")
                if existing_model != incoming_model:
                    raise VectorStoreError("Existing LanceDB table embedding model does not match incoming vectors")
            table.add(rows)
        else:
            table = db.create_table(normalized_index_name, data=rows, mode="overwrite")

        if create_vector_index:
            try:
                table.create_index(vector_column_name="vector", metric=metric_normalized, num_partitions=max(1, nlist))
            except TypeError:
                try:
                    table.create_index("vector", metric=metric_normalized, num_partitions=max(1, nlist))
                except TypeError:
                    table.create_index("vector")

        return VectorStoreHandle(
            backend=self.backend,
            index_name=normalized_index_name,
            artifact_path=str(root_path / normalized_index_name),
            metric=metric_normalized,
            dimension=dimension,
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            metadata={
                "index_type": index_type.lower().strip(),
                "count": len(_materialize_lancedb_rows(table)),
                "storage_directory": str(root_path),
                "table_name": normalized_index_name,
                "create_vector_index": bool(create_vector_index),
                "num_partitions": max(1, nlist),
                "hnsw_m": hnsw_m,
            },
        )

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
        _ = keyword_query, vector_weight, keyword_weight
        if search_mode != "vector":
            raise VectorStoreError(f"Search mode '{search_mode}' is not supported by backend '{self.backend}'")
        lancedb = self._load_lancedb()
        store_metadata = _store_attr(store, "metadata") if isinstance(_store_attr(store, "metadata"), dict) else {}
        root_path = _resolve_vectorstore_root(store_metadata.get("storage_directory") if isinstance(store_metadata, dict) else None)
        db = lancedb.connect(str(root_path))
        table_name = str((store_metadata.get("table_name") if isinstance(store_metadata, dict) else None) or _store_attr(store, "index_name") or "").strip()
        if not table_name:
            raise VectorStoreError("LanceDB search requires a table name")
        table = db.open_table(table_name)
        search_payload = table.search(query_vector).limit(max(1, top_k * 5, int(ann_search_depth)))
        rows = _materialize_lancedb_rows(search_payload)

        results: list[RetrievalHit] = []
        for entry in rows:
            if not isinstance(entry, dict) or not _matches_filter(entry, filter_spec):
                continue
            raw_score = float(entry.get("_distance", 0.0))
            score = _score_from_metric(str(_store_attr(store, "metric") or "cosine"), raw_score)
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
                    metadata=entry.get("metadata", {}) if include_metadata else {},
                )
            )
            if len(results) >= top_k:
                break
        return results

class QdrantVectorStoreAdapter(VectorStoreAdapter):
    backend = "qdrant"

    def _load_client(self):
        return _import_qdrant_clients()

    def _build_client(self, *, storage_directory: str, endpoint_url: str, api_key: str):
        QdrantClient, _ = self._load_client()
        if endpoint_url:
            return QdrantClient(url=endpoint_url, api_key=api_key or None)
        root_path = _resolve_vectorstore_root(storage_directory)
        root_path.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(root_path / "qdrant_local"))

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
        _ = namespace, database_name
        _normalize_index_name(collection_name or index_name)
        config, endpoint, token = _extract_provider_config(
            provider_config=provider_config,
            endpoint_url=endpoint_url,
            api_key=api_key,
        )
        client = self._build_client(storage_directory=storage_directory, endpoint_url=endpoint, api_key=token)
        timeout = float(config.get("timeout") or 5)
        client.get_collections(timeout=timeout)

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
        **_: Any,
    ) -> VectorStoreHandle:
        _ = namespace, database_name
        if not points:
            raise VectorStoreError("Vector store write requires at least one vector point")

        normalized_metric = _coerce_metric(metric)
        if normalized_metric not in {"cosine", "l2", "dot"}:
            raise VectorStoreError(f"Unsupported Qdrant metric: {metric}")

        collection = _normalize_index_name(collection_name or index_name)
        dimension = len(_point_attr(points[0], "vector"))
        if any(len(_point_attr(point, "vector")) != dimension for point in points):
            raise VectorStoreError("All vector points must have the same dimension")

        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        config, endpoint, token = _extract_provider_config(
            provider_config=provider_config,
            endpoint_url=endpoint_url,
            api_key=api_key,
        )
        client = self._build_client(storage_directory=storage_directory, endpoint_url=endpoint, api_key=token)
        _, qm = self._load_client()

        distance_map = {"cosine": qm.Distance.COSINE, "l2": qm.Distance.EUCLID, "dot": qm.Distance.DOT}
        existing = {item.name for item in client.get_collections().collections}
        if collection in existing and write_mode_normalized == "overwrite":
            client.delete_collection(collection_name=collection)
            existing.remove(collection)
        if collection not in existing:
            client.create_collection(
                collection_name=collection,
                vectors_config=qm.VectorParams(size=dimension, distance=distance_map[normalized_metric]),
            )

        payloads = []
        for point in points:
            entry = _sanitize_metadata_entry(point)
            payloads.append(
                qm.PointStruct(
                    id=str(entry["id"]),
                    vector=[float(item) for item in _point_attr(point, "vector")],
                    payload={
                        "chunk_id": entry["chunk_id"],
                        "document_id": entry["document_id"],
                        "text": entry["text"],
                        "source_uri": entry["source_uri"],
                        "embedding_provider": entry["embedding_provider"],
                        "embedding_model": entry["embedding_model"],
                        "metadata": entry["metadata"],
                    },
                )
            )
        client.upsert(collection_name=collection, points=payloads)

        return VectorStoreHandle(
            backend=self.backend,
            index_name=collection,
            artifact_path="",
            metric=normalized_metric,
            dimension=dimension,
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            metadata={
                "endpoint_url": endpoint,
                "storage_directory": storage_directory,
                "collection_name": collection,
                "provider_config": {**config, "api_key": token},
            },
        )


    def _map_filter(self, filter_spec: dict[str, Any] | None, qm: Any) -> Any:
        if not filter_spec:
            return None
        must = [_qdrant_condition(clause, qm) for clause in filter_spec.get("must", []) if isinstance(clause, dict)]
        should = [_qdrant_condition(clause, qm) for clause in filter_spec.get("should", []) if isinstance(clause, dict)]
        must_not = [_qdrant_condition(clause, qm) for clause in filter_spec.get("must_not", []) if isinstance(clause, dict)]
        must = [item for item in must if item is not None]
        should = [item for item in should if item is not None]
        must_not = [item for item in must_not if item is not None]
        if not must and not should and not must_not:
            return None
        return qm.Filter(must=must or None, should=should or None, must_not=must_not or None)

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
        _ = keyword_query, vector_weight, keyword_weight
        if search_mode != "vector":
            raise VectorStoreError("Hybrid search is not currently supported for Qdrant in this runtime")

        metadata = _store_attr(store, "metadata") if isinstance(_store_attr(store, "metadata"), dict) else {}
        config = metadata.get("provider_config") if isinstance(metadata.get("provider_config"), dict) else {}
        endpoint = str(metadata.get("endpoint_url") or config.get("endpoint_url") or "").strip()
        storage_directory = str(metadata.get("storage_directory") or "").strip()
        token = str(config.get("api_key") or "").strip()
        collection = str(metadata.get("collection_name") or _store_attr(store, "index_name") or "").strip()
        if not collection:
            raise VectorStoreError("Qdrant search requires a collection name")

        client = self._build_client(storage_directory=storage_directory, endpoint_url=endpoint, api_key=token)
        _, qm = self._load_client()
        qdrant_filter = self._map_filter(filter_spec, qm)

        query_params = None
        try:
            query_params = qm.SearchParams(hnsw_ef=max(1, int(ann_search_depth)))
        except Exception:
            query_params = None

        response = client.search(
            collection_name=collection,
            query_vector=[float(item) for item in query_vector],
            query_filter=qdrant_filter,
            limit=max(1, int(top_k)),
            search_params=query_params,
        )

        metric = str(_store_attr(store, "metric") or "cosine")
        results: list[RetrievalHit] = []
        for point in response or []:
            payload = point.payload if isinstance(getattr(point, "payload", None), dict) else {}
            entry_for_filter = {
                "chunk_id": payload.get("chunk_id"),
                "document_id": payload.get("document_id"),
                "text": payload.get("text"),
                "source_uri": payload.get("source_uri"),
                "metadata": payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {},
            }
            if filter_spec and not _matches_filter(entry_for_filter, filter_spec):
                continue
            raw_score = float(getattr(point, "score", 0.0) or 0.0)
            score = _score_from_metric(metric, raw_score)
            if score < score_threshold:
                continue
            results.append(
                RetrievalHit(
                    id=str(getattr(point, "id", "")),
                    chunk_id=str(payload.get("chunk_id", "")),
                    document_id=str(payload.get("document_id", "")),
                    text=str(payload.get("text", "")),
                    source_uri=str(payload.get("source_uri", "")),
                    score=score,
                    metadata=(payload.get("metadata", {}) if include_metadata else {}),
                )
            )
        return results


class PineconeVectorStoreAdapter(VectorStoreAdapter):
    backend = "pinecone"

    def _load_client(self):
        return _import_pinecone_client()

    def _map_filter(self, filter_spec: dict[str, Any] | None) -> dict[str, Any] | None:
        if not filter_spec:
            return None
        clauses: list[dict[str, Any]] = []
        must_not: list[dict[str, Any]] = []
        should: list[dict[str, Any]] = []
        minimum_should_match = int(filter_spec.get("minimum_should_match", 1))

        for clause in filter_spec.get("must", []):
            if not isinstance(clause, dict):
                continue
            translated = _pinecone_clause(clause)
            if translated:
                clauses.append(translated)
        for clause in filter_spec.get("must_not", []):
            if not isinstance(clause, dict):
                continue
            translated = _pinecone_clause(clause)
            if translated:
                must_not.append(translated)
        for clause in filter_spec.get("should", []):
            if not isinstance(clause, dict):
                continue
            translated = _pinecone_clause(clause)
            if translated:
                should.append(translated)

        if not clauses and not must_not and not should:
            return None
        if clauses and not must_not and not should and len(clauses) == 1:
            return clauses[0]

        output: dict[str, Any] = {}
        if clauses:
            output["$and"] = clauses
        if must_not:
            output["$nor"] = must_not
        if should:
            output["$or"] = should
            if minimum_should_match > 1:
                output["$comment"] = f"minimum_should_match={minimum_should_match}"
        return output

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
        _ = storage_directory, namespace, endpoint_url, database_name
        _, _, token = _extract_provider_config(provider_config=provider_config, endpoint_url="", api_key=api_key)
        if not token:
            raise VectorStoreError("Pinecone requires api_key")
        Pinecone, _ = self._load_client()
        client = Pinecone(api_key=token)
        target = _normalize_index_name(collection_name or index_name)
        names = {item.name for item in client.list_indexes()}
        if target and target not in names:
            logger.debug("Pinecone index '%s' does not exist yet (will be created on first write)", target)

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
        **_: Any,
    ) -> VectorStoreHandle:
        _ = storage_directory, endpoint_url, database_name
        if not points:
            raise VectorStoreError("Vector store write requires at least one vector point")

        normalized_metric = _coerce_metric(metric)
        if normalized_metric not in {"cosine", "dot", "l2"}:
            raise VectorStoreError(f"Unsupported Pinecone metric: {metric}")

        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        config, _, token = _extract_provider_config(provider_config=provider_config, endpoint_url="", api_key=api_key)
        if not token:
            raise VectorStoreError("Pinecone requires api_key")

        Pinecone, ServerlessSpec = self._load_client()
        client = Pinecone(api_key=token)

        target_index = _normalize_index_name(collection_name or index_name)
        dimension = len(_point_attr(points[0], "vector"))
        if any(len(_point_attr(point, "vector")) != dimension for point in points):
            raise VectorStoreError("All vector points must have the same dimension")

        region = str(config.get("region") or "us-east-1").strip()
        cloud = str(config.get("cloud") or "aws").strip()
        existing = {item.name for item in client.list_indexes()}
        if target_index not in existing:
            client.create_index(
                name=target_index,
                dimension=dimension,
                metric=normalized_metric,
                spec=ServerlessSpec(cloud=cloud, region=region),
            )
        elif write_mode_normalized == "overwrite":
            client.Index(target_index).delete(delete_all=True, namespace=namespace or None)

        index = client.Index(target_index)
        vectors = []
        for point in points:
            entry = _sanitize_metadata_entry(point)
            vectors.append(
                {
                    "id": str(entry["id"]),
                    "values": [float(item) for item in _point_attr(point, "vector")],
                    "metadata": {
                        "chunk_id": entry["chunk_id"],
                        "document_id": entry["document_id"],
                        "text": entry["text"],
                        "source_uri": entry["source_uri"],
                        "embedding_provider": entry["embedding_provider"],
                        "embedding_model": entry["embedding_model"],
                        "metadata": entry["metadata"],
                    },
                }
            )
        index.upsert(vectors=vectors, namespace=namespace or None)

        return VectorStoreHandle(
            backend=self.backend,
            index_name=target_index,
            artifact_path="",
            metric=normalized_metric,
            dimension=dimension,
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            metadata={
                "namespace": namespace,
                "collection_name": target_index,
                "provider_config": {**config, "api_key": token},
            },
        )

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
        **_: Any,
    ) -> list[RetrievalHit]:
        _ = ann_search_depth
        if search_mode != "vector":
            raise VectorStoreError("Hybrid search is not currently supported for Pinecone in this runtime")

        metadata = _store_attr(store, "metadata") if isinstance(_store_attr(store, "metadata"), dict) else {}
        config = metadata.get("provider_config") if isinstance(metadata.get("provider_config"), dict) else {}
        token = str(config.get("api_key") or "").strip()
        if not token:
            raise VectorStoreError("Pinecone search requires api_key in provider_config")

        Pinecone, _ = self._load_client()
        client = Pinecone(api_key=token)
        index_name = str(metadata.get("collection_name") or _store_attr(store, "index_name") or "").strip()
        if not index_name:
            raise VectorStoreError("Pinecone search requires an index name")
        namespace = str(metadata.get("namespace") or "").strip() or None

        pinecone_filter = self._map_filter(filter_spec)
        response = client.Index(index_name).query(
            vector=[float(item) for item in query_vector],
            top_k=max(1, top_k),
            namespace=namespace,
            include_metadata=True,
            include_values=False,
            filter=pinecone_filter,
        )

        matches = response.get("matches") if isinstance(response, dict) else getattr(response, "matches", [])
        results: list[RetrievalHit] = []
        for match in matches or []:
            record = match if isinstance(match, dict) else getattr(match, "to_dict", lambda: {})()
            item_metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
            score = float(record.get("score") or 0.0)
            if score < score_threshold:
                continue
            results.append(
                RetrievalHit(
                    id=str(record.get("id", "")),
                    chunk_id=str(item_metadata.get("chunk_id", "")),
                    document_id=str(item_metadata.get("document_id", "")),
                    text=str(item_metadata.get("text", "")),
                    source_uri=str(item_metadata.get("source_uri", "")),
                    score=score,
                    metadata=(item_metadata.get("metadata", {}) if include_metadata else {}),
                )
            )
        return results


class WeaviateVectorStoreAdapter(VectorStoreAdapter):
    backend = "weaviate"

    def _load_client(self):
        return _import_weaviate_module()

    def _connect(self, *, endpoint_url: str, api_key: str):
        weaviate = self._load_client()
        if not endpoint_url:
            raise VectorStoreError("Weaviate requires endpoint_url")
        if api_key:
            return weaviate.connect_to_weaviate_cloud(
                cluster_url=endpoint_url,
                auth_credentials=weaviate.Auth.api_key(api_key),
            )
        return weaviate.connect_to_custom(http_host=endpoint_url, http_port=443, http_secure=True)

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
        _ = storage_directory, namespace, database_name
        _, endpoint, token = _extract_provider_config(
            provider_config=provider_config,
            endpoint_url=endpoint_url,
            api_key=api_key,
        )
        collection = _normalize_index_name(collection_name or index_name)
        client = self._connect(endpoint_url=endpoint, api_key=token)
        try:
            client.collections.exists(collection)
        finally:
            client.close()

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
        **_: Any,
    ) -> VectorStoreHandle:
        _ = storage_directory, namespace, database_name
        if not points:
            raise VectorStoreError("Vector store write requires at least one vector point")
        normalized_metric = _coerce_metric(metric)
        if normalized_metric not in {"cosine", "l2", "dot"}:
            raise VectorStoreError(f"Unsupported Weaviate metric: {metric}")
        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        config, endpoint, token = _extract_provider_config(
            provider_config=provider_config,
            endpoint_url=endpoint_url,
            api_key=api_key,
        )
        collection = _normalize_index_name(collection_name or index_name)
        dimension = len(_point_attr(points[0], "vector"))
        if any(len(_point_attr(point, "vector")) != dimension for point in points):
            raise VectorStoreError("All vector points must have the same dimension")

        client = self._connect(endpoint_url=endpoint, api_key=token)
        try:
            exists = client.collections.exists(collection)
            if exists and write_mode_normalized == "overwrite":
                client.collections.delete(collection)
                exists = False
            if not exists:
                client.collections.create(name=collection, vectorizer_config=None)
            coll = client.collections.get(collection)
            for point in points:
                entry = _sanitize_metadata_entry(point)
                coll.data.insert(
                    uuid=str(entry["id"]),
                    vector=[float(item) for item in _point_attr(point, "vector")],
                    properties={
                        "chunk_id": entry["chunk_id"],
                        "document_id": entry["document_id"],
                        "text": entry["text"],
                        "source_uri": entry["source_uri"],
                        "embedding_provider": entry["embedding_provider"],
                        "embedding_model": entry["embedding_model"],
                        "metadata": entry["metadata"],
                    },
                )
        finally:
            client.close()

        return VectorStoreHandle(
            backend=self.backend,
            index_name=collection,
            artifact_path="",
            metric=normalized_metric,
            dimension=dimension,
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            metadata={
                "endpoint_url": endpoint,
                "collection_name": collection,
                "provider_config": {**config, "api_key": token},
            },
        )

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
        _ = ann_search_depth, keyword_query, vector_weight, keyword_weight
        if search_mode != "vector":
            raise VectorStoreError("Hybrid search is not currently supported for Weaviate in this runtime")

        metadata = _store_attr(store, "metadata") if isinstance(_store_attr(store, "metadata"), dict) else {}
        config = metadata.get("provider_config") if isinstance(metadata.get("provider_config"), dict) else {}
        endpoint = str(metadata.get("endpoint_url") or config.get("endpoint_url") or "").strip()
        token = str(config.get("api_key") or "").strip()
        collection = str(metadata.get("collection_name") or _store_attr(store, "index_name") or "").strip()
        if not collection:
            raise VectorStoreError("Weaviate search requires a collection name")

        client = self._connect(endpoint_url=endpoint, api_key=token)
        try:
            coll = client.collections.get(collection)
            response = coll.query.near_vector(
                near_vector=[float(item) for item in query_vector],
                limit=max(1, int(top_k)),
                return_metadata=["distance"],
            )
            objects = getattr(response, "objects", []) or []
        finally:
            client.close()

        metric = str(_store_attr(store, "metric") or "cosine")
        hits: list[RetrievalHit] = []
        for item in objects:
            properties = getattr(item, "properties", {}) if isinstance(getattr(item, "properties", {}), dict) else {}
            meta = properties.get("metadata", {}) if isinstance(properties.get("metadata"), dict) else {}
            entry_for_filter = {
                "chunk_id": properties.get("chunk_id"),
                "document_id": properties.get("document_id"),
                "text": properties.get("text"),
                "source_uri": properties.get("source_uri"),
                "metadata": meta,
            }
            if filter_spec and not _matches_filter(entry_for_filter, filter_spec):
                continue
            distance = float(getattr(getattr(item, "metadata", None), "distance", 0.0) or 0.0)
            score = _score_from_metric(metric, distance if metric == "l2" else 1.0 - distance)
            if score < score_threshold:
                continue
            hits.append(
                RetrievalHit(
                    id=str(getattr(item, "uuid", "")),
                    chunk_id=str(properties.get("chunk_id", "")),
                    document_id=str(properties.get("document_id", "")),
                    text=str(properties.get("text", "")),
                    source_uri=str(properties.get("source_uri", "")),
                    score=score,
                    metadata=(meta if include_metadata else {}),
                )
            )
        return hits


class MilvusVectorStoreAdapter(VectorStoreAdapter):
    backend = "milvus"

    def _load_client(self):
        return _import_milvus_client()

    def _build_client(self, *, endpoint_url: str, api_key: str, database_name: str):
        MilvusClient = self._load_client()
        uri = endpoint_url or "http://localhost:19530"
        kwargs: dict[str, Any] = {"uri": uri}
        if api_key:
            kwargs["token"] = api_key
        if database_name:
            kwargs["db_name"] = database_name
        return MilvusClient(**kwargs)

    def _milvus_filter(self, filter_spec: dict[str, Any] | None) -> str:
        if not filter_spec:
            return ""
        must = [_milvus_clause_expression(item) for item in filter_spec.get("must", []) if isinstance(item, dict)]
        must_not = [_milvus_clause_expression(item) for item in filter_spec.get("must_not", []) if isinstance(item, dict)]
        should = [_milvus_clause_expression(item) for item in filter_spec.get("should", []) if isinstance(item, dict)]
        must = [item for item in must if item]
        must_not = [item for item in must_not if item]
        should = [item for item in should if item]

        parts: list[str] = []
        if must:
            parts.append("(" + " and ".join(must) + ")")
        if must_not:
            parts.append("(" + " and ".join(f"not ({item})" for item in must_not) + ")")
        if should:
            parts.append("(" + " or ".join(should) + ")")
        return " and ".join(parts)

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
        _ = storage_directory, namespace
        config, endpoint, token = _extract_provider_config(
            provider_config=provider_config,
            endpoint_url=endpoint_url,
            api_key=api_key,
        )
        _normalize_index_name(collection_name or index_name)
        client = self._build_client(
            endpoint_url=endpoint,
            api_key=token,
            database_name=str(config.get("database_name") or database_name or ""),
        )
        client.list_collections()

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
        **_: Any,
    ) -> VectorStoreHandle:
        _ = storage_directory, namespace
        if not points:
            raise VectorStoreError("Vector store write requires at least one vector point")
        normalized_metric = _coerce_metric(metric)
        metric_map = {"cosine": "COSINE", "l2": "L2", "dot": "IP"}
        if normalized_metric not in metric_map:
            raise VectorStoreError(f"Unsupported Milvus metric: {metric}")
        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        config, endpoint, token = _extract_provider_config(
            provider_config=provider_config,
            endpoint_url=endpoint_url,
            api_key=api_key,
        )
        collection = _normalize_index_name(collection_name or index_name)
        database = str(config.get("database_name") or database_name or "").strip()
        client = self._build_client(endpoint_url=endpoint, api_key=token, database_name=database)

        dimension = len(_point_attr(points[0], "vector"))
        if any(len(_point_attr(point, "vector")) != dimension for point in points):
            raise VectorStoreError("All vector points must have the same dimension")

        existing = set(client.list_collections())
        if collection in existing and write_mode_normalized == "overwrite":
            client.drop_collection(collection_name=collection)
            existing.remove(collection)
        if collection not in existing:
            client.create_collection(
                collection_name=collection,
                dimension=dimension,
                metric_type=metric_map[normalized_metric],
                consistency_level="Bounded",
            )

        rows = []
        for point in points:
            entry = _sanitize_metadata_entry(point)
            rows.append(
                {
                    "id": str(entry["id"]),
                    "vector": [float(item) for item in _point_attr(point, "vector")],
                    "chunk_id": str(entry["chunk_id"] or ""),
                    "document_id": str(entry["document_id"] or ""),
                    "text": str(entry["text"] or ""),
                    "source_uri": str(entry["source_uri"] or ""),
                    "embedding_provider": str(entry["embedding_provider"] or ""),
                    "embedding_model": str(entry["embedding_model"] or ""),
                    "metadata": entry["metadata"] if isinstance(entry["metadata"], dict) else {},
                }
            )
        client.insert(collection_name=collection, data=rows)

        return VectorStoreHandle(
            backend=self.backend,
            index_name=collection,
            artifact_path="",
            metric=normalized_metric,
            dimension=dimension,
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            metadata={
                "endpoint_url": endpoint,
                "database_name": database,
                "collection_name": collection,
                "provider_config": {**config, "api_key": token},
            },
        )

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
        _ = ann_search_depth, keyword_query, vector_weight, keyword_weight
        if search_mode != "vector":
            raise VectorStoreError("Hybrid search is not currently supported for Milvus in this runtime")

        metadata = _store_attr(store, "metadata") if isinstance(_store_attr(store, "metadata"), dict) else {}
        config = metadata.get("provider_config") if isinstance(metadata.get("provider_config"), dict) else {}
        endpoint = str(metadata.get("endpoint_url") or config.get("endpoint_url") or "").strip()
        database = str(metadata.get("database_name") or config.get("database_name") or "").strip()
        token = str(config.get("api_key") or "").strip()
        collection = str(metadata.get("collection_name") or _store_attr(store, "index_name") or "").strip()
        if not collection:
            raise VectorStoreError("Milvus search requires a collection name")

        filter_expr = self._milvus_filter(filter_spec)
        client = self._build_client(endpoint_url=endpoint, api_key=token, database_name=database)
        response = client.search(
            collection_name=collection,
            data=[[float(item) for item in query_vector]],
            limit=max(1, int(top_k)),
            filter=filter_expr or None,
            output_fields=[
                "chunk_id",
                "document_id",
                "text",
                "source_uri",
                "metadata",
                "embedding_provider",
                "embedding_model",
            ],
        )

        metric = str(_store_attr(store, "metric") or "cosine")
        hits: list[RetrievalHit] = []
        for raw_hit in (response[0] if isinstance(response, list) and response else []):
            hit = raw_hit if isinstance(raw_hit, dict) else getattr(raw_hit, "to_dict", lambda: {})()
            entity = hit.get("entity") if isinstance(hit.get("entity"), dict) else {}
            entry_for_filter = {
                "chunk_id": entity.get("chunk_id"),
                "document_id": entity.get("document_id"),
                "text": entity.get("text"),
                "source_uri": entity.get("source_uri"),
                "metadata": entity.get("metadata", {}) if isinstance(entity.get("metadata"), dict) else {},
            }
            if filter_spec and not _matches_filter(entry_for_filter, filter_spec):
                continue
            raw_score = float(hit.get("distance", hit.get("score", 0.0)) or 0.0)
            score = _score_from_metric(metric, raw_score)
            if score < score_threshold:
                continue
            hits.append(
                RetrievalHit(
                    id=str(hit.get("id", "")),
                    chunk_id=str(entity.get("chunk_id", "")),
                    document_id=str(entity.get("document_id", "")),
                    text=str(entity.get("text", "")),
                    source_uri=str(entity.get("source_uri", "")),
                    score=score,
                    metadata=(entity.get("metadata", {}) if include_metadata else {}),
                )
            )
        return hits


class ChromaVectorStoreAdapter(VectorStoreAdapter):
    backend = "chroma"

    def _load_client(self):
        return _import_chromadb_module()

    def _build_client(self, *, storage_directory: str, endpoint_url: str):
        chromadb = self._load_client()
        if endpoint_url:
            return chromadb.HttpClient(host=endpoint_url)
        root = _resolve_vectorstore_root(storage_directory)
        root.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(root / "chroma"))

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
        _ = namespace, api_key, database_name, provider_config
        client = self._build_client(storage_directory=storage_directory, endpoint_url=endpoint_url)
        _normalize_index_name(collection_name or index_name)
        client.heartbeat()

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
        **_: Any,
    ) -> VectorStoreHandle:
        _ = namespace, api_key, database_name, provider_config
        if not points:
            raise VectorStoreError("Vector store write requires at least one vector point")

        normalized_metric = _coerce_metric(metric)
        if normalized_metric not in {"cosine", "l2", "dot"}:
            raise VectorStoreError(f"Unsupported Chroma metric: {metric}")

        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        collection = _normalize_index_name(collection_name or index_name)
        client = self._build_client(storage_directory=storage_directory, endpoint_url=endpoint_url)

        if write_mode_normalized == "overwrite":
            try:
                client.delete_collection(name=collection)
            except Exception:
                pass

        coll = client.get_or_create_collection(name=collection)
        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for point in points:
            entry = _sanitize_metadata_entry(point)
            ids.append(str(entry["id"]))
            embeddings.append([float(item) for item in _point_attr(point, "vector")])
            documents.append(str(entry["text"]))
            metadatas.append(
                {
                    "chunk_id": entry["chunk_id"],
                    "document_id": entry["document_id"],
                    "source_uri": entry["source_uri"],
                    "embedding_provider": entry["embedding_provider"],
                    "embedding_model": entry["embedding_model"],
                    "metadata": entry["metadata"],
                }
            )
        coll.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

        return VectorStoreHandle(
            backend=self.backend,
            index_name=collection,
            artifact_path="",
            metric=normalized_metric,
            dimension=len(embeddings[0]),
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            metadata={
                "storage_directory": storage_directory,
                "endpoint_url": endpoint_url,
                "collection_name": collection,
            },
        )

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
        **_: Any,
    ) -> list[RetrievalHit]:
        _ = ann_search_depth
        if search_mode != "vector":
            raise VectorStoreError("Hybrid search is not currently supported for Chroma in this runtime")

        metadata = _store_attr(store, "metadata") if isinstance(_store_attr(store, "metadata"), dict) else {}
        storage_directory = str(metadata.get("storage_directory") or "").strip()
        endpoint_url = str(metadata.get("endpoint_url") or "").strip()
        collection = str(metadata.get("collection_name") or _store_attr(store, "index_name") or "").strip()
        if not collection:
            raise VectorStoreError("Chroma search requires a collection name")

        client = self._build_client(storage_directory=storage_directory, endpoint_url=endpoint_url)
        coll = client.get_collection(name=collection)

        results = coll.query(query_embeddings=[[float(item) for item in query_vector]], n_results=max(1, top_k))
        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        payloads: list[RetrievalHit] = []
        for idx, item_id in enumerate(ids):
            meta = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
            entry_for_filter = {
                "metadata": meta.get("metadata", {}) if isinstance(meta.get("metadata"), dict) else {},
                "document_id": meta.get("document_id"),
                "chunk_id": meta.get("chunk_id"),
                "source_uri": meta.get("source_uri"),
                "text": documents[idx] if idx < len(documents) else "",
            }
            if not _matches_filter(entry_for_filter, filter_spec):
                continue
            raw = float(distances[idx]) if idx < len(distances) else 0.0
            score = _score_from_metric(str(_store_attr(store, "metric") or "cosine"), raw)
            if score < score_threshold:
                continue
            payloads.append(
                RetrievalHit(
                    id=str(item_id),
                    chunk_id=str(meta.get("chunk_id", "")),
                    document_id=str(meta.get("document_id", "")),
                    text=str(documents[idx] if idx < len(documents) else ""),
                    source_uri=str(meta.get("source_uri", "")),
                    score=score,
                    metadata=(meta.get("metadata", {}) if include_metadata else {}),
                )
            )
        return payloads


VECTOR_STORE_ADAPTERS = {
    "faiss": VectorStoreAdapter(),
    "lancedb": LanceDbVectorStoreAdapter(),
    "qdrant": QdrantVectorStoreAdapter(),
    "pinecone": PineconeVectorStoreAdapter(),
    "weaviate": WeaviateVectorStoreAdapter(),
    "milvus": MilvusVectorStoreAdapter(),
    "chroma": ChromaVectorStoreAdapter(),
}


def get_vector_store_adapter(backend: str) -> VectorStoreAdapter:
    normalized = backend.lower().strip()
    adapter = VECTOR_STORE_ADAPTERS.get(normalized)
    if adapter is None:
        raise VectorStoreError(f"Unsupported vector store backend: {backend}")
    return adapter



















