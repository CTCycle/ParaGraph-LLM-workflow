from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from server.common.constants import ARTIFACT_ROOT
from server.common.security import (
    ensure_path_within_root,
    is_cloud_deployment,
)
from server.domain.workflow_payloads import (
    RetrievalHit,
    VectorPoint,
    VectorStoreHandle,
)


VECTORSTORE_ROOT = ARTIFACT_ROOT / "vectorstores"
INDEX_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
logger = logging.getLogger(__name__)


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


def _normalize_index_name(index_name: str) -> str:
    normalized = str(index_name or "").strip()
    if not INDEX_NAME_PATTERN.fullmatch(normalized):
        raise VectorStoreError(
            "index_name must contain only letters, numbers, dot, underscore, or dash"
        )
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


def _resolve_store_path_from_handle(store: VectorStoreHandle | dict[str, Any]) -> Path:
    artifact_path = str(_store_attr(store, "artifact_path") or "").strip()
    artifact_root = ARTIFACT_ROOT.resolve()
    if artifact_path:
        candidate = Path(artifact_path).expanduser()
        if candidate.is_absolute():
            resolved = candidate.resolve()
            if is_cloud_deployment():
                return ensure_path_within_root(
                    resolved, artifact_root, label="artifact_path"
                )
            return resolved
        resolved = (ARTIFACT_ROOT / candidate).resolve()
        return ensure_path_within_root(resolved, artifact_root, label="artifact_path")

    index_name = _normalize_index_name(str(_store_attr(store, "index_name") or ""))
    root = _resolve_vectorstore_root(_store_attr(store, "storage_directory"))
    return (root / index_name).resolve()


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
    minimum_should_match = int(
        filter_spec.get("minimum_should_match", 1 if should else 0)
    )

    if (
        not isinstance(must, list)
        or not isinstance(should, list)
        or not isinstance(must_not, list)
    ):
        raise VectorStoreError("Filter groups must be arrays")

    if any(
        _matches_clause(item, clause) for clause in must_not if isinstance(clause, dict)
    ):
        return False
    if any(
        not _matches_clause(item, clause) for clause in must if isinstance(clause, dict)
    ):
        return False

    if should:
        matched = sum(
            1
            for clause in should
            if isinstance(clause, dict) and _matches_clause(item, clause)
        )
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
        return '"' + value.replace('"', '"') + '"'
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
    supports_hybrid_search = False
    supports_metadata_filtering = True
    supports_faiss_augmentation = True

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
            namespace,
            endpoint_url,
            api_key,
            collection_name,
            database_name,
            provider_config,
        )
        _normalize_index_name(index_name)
        _resolve_vectorstore_root(storage_directory)

    def describe_capabilities(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "supports_hybrid_search": bool(self.supports_hybrid_search),
            "supports_metadata_filtering": bool(self.supports_metadata_filtering),
            "supports_faiss_augmentation": bool(self.supports_faiss_augmentation),
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
        _ = (
            namespace,
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

        vectors = np.asarray(
            [_point_attr(point, "vector") for point in points], dtype=np.float32
        )
        if metric.lower().strip() == "cosine":
            vectors = _normalize_vectors(vectors)

        metadata_entries = [_sanitize_metadata_entry(point) for point in points]
        store_path, manifest_path, metadata_path, vectors_path = _index_paths(
            root_path, normalized_index_name
        )
        index_path = _index_file_path(store_path)

        if write_mode_normalized == "append" and store_path.exists():
            existing_manifest, existing_metadata, existing_vectors, _ = _load_store(
                {"artifact_path": str(store_path)}
            )
            if int(existing_manifest.get("dimension", 0)) != dimension:
                raise VectorStoreError(
                    "Existing vector store dimension does not match incoming vectors"
                )
            if (
                str(existing_manifest.get("metric", "")).lower()
                != metric.lower().strip()
            ):
                raise VectorStoreError(
                    "Existing vector store metric does not match incoming vectors"
                )
            if (
                str(existing_manifest.get("embedding_provider", "")).lower()
                != str(_point_attr(points[0], "embedding_provider") or "").lower()
            ):
                raise VectorStoreError(
                    "Existing vector store embedding provider does not match incoming vectors"
                )
            if str(existing_manifest.get("embedding_model", "")) != str(
                _point_attr(points[0], "embedding_model") or ""
            ):
                raise VectorStoreError(
                    "Existing vector store embedding model does not match incoming vectors"
                )
            vectors = np.vstack([existing_vectors.astype(np.float32), vectors])
            metadata_entries = [*existing_metadata, *metadata_entries]
        elif store_path.exists():
            shutil.rmtree(store_path)

        store_path.mkdir(parents=True, exist_ok=True)
        index = _build_index(
            vectors, metric=metric, index_type=index_type, nlist=nlist, hnsw_m=hnsw_m
        )
        faiss.write_index(index, str(index_path))
        np.save(vectors_path, vectors)

        manifest = {
            "backend": self.backend,
            "index_name": normalized_index_name,
            "metric": metric.lower().strip(),
            "index_type": index_type.lower().strip(),
            "dimension": dimension,
            "count": len(metadata_entries),
            "embedding_provider": str(
                _point_attr(points[0], "embedding_provider") or ""
            ),
            "embedding_model": str(_point_attr(points[0], "embedding_model") or ""),
            "nlist": nlist,
            "hnsw_m": hnsw_m,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        metadata_path.write_text(
            json.dumps(metadata_entries, indent=2), encoding="utf-8"
        )

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
            raise VectorStoreError(
                f"Search mode '{search_mode}' is not supported by backend '{self.backend}'"
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



