from __future__ import annotations

import qdrant_client.models as qdrant_models
from qdrant_client import QdrantClient

from server.contracts.node_catalog import VectorStoreCapabilities
from server.services.workflow.vector_stores.base import (
    Any,
    RetrievalHit,
    VectorPoint,
    VectorStoreAdapter,
    VectorStoreError,
    VectorStoreHandle,
    _coerce_metric,
    _extract_provider_config,
    _matches_filter,
    _normalize_index_name,
    _point_attr,
    _redacted_provider_config,
    _resolve_runtime_secret,
    _qdrant_condition,
    _resolve_vectorstore_root,
    _sanitize_metadata_entry,
    _score_from_metric,
    _score_semantics_for_metric,
    _store_attr,
    validate_vector_request_capabilities,
)

###############################################################################
class QdrantVectorStoreAdapter(VectorStoreAdapter):
    backend = "qdrant"
    capabilities = VectorStoreCapabilities(
        backend="qdrant",
        supported_metrics=["cosine", "l2", "dot"],
        supported_search_modes=["vector"],
        supported_search_engines=["native"],
        supports_metadata_filtering=True,
        supported_filter_operators=["eq", "in", "gt", "gte", "lt", "lte"],
        supports_filter_groups=True,
        supports_minimum_should_match=False,
        supported_operations=["insert", "upsert", "search", "close"],
        score_semantics_by_metric={
            "cosine": "normalized_similarity",
            "l2": "normalized_similarity",
            "dot": "native_similarity",
        },
    )

    # -------------------------------------------------------------------------
    def _build_client(self, *, storage_directory: str, endpoint_url: str, api_key: str):
        if endpoint_url:
            return QdrantClient(url=endpoint_url, api_key=api_key or None)
        root_path = _resolve_vectorstore_root(storage_directory)
        root_path.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(root_path / "qdrant_local"))

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
        self.validate_connection_capabilities(namespace=namespace)
        _ = database_name
        _normalize_index_name(collection_name or index_name)
        config, endpoint, token = _extract_provider_config(
            provider_config=provider_config,
            endpoint_url=endpoint_url,
            api_key=api_key,
        )
        client = self._build_client(
            storage_directory=storage_directory, endpoint_url=endpoint, api_key=token
        )
        timeout = float(config.get("timeout") or 5)
        try:
            client.get_collections(timeout=timeout)
        finally:
            client.close()

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
        **_: Any,
    ) -> VectorStoreHandle:
        self.validate_write_capabilities(
            metric=metric,
            namespace=namespace,
            create_keyword_index=bool(_.get("create_keyword_index", False)),
        )
        _ = database_name
        if not points:
            raise VectorStoreError(
                "Vector store write requires at least one vector point"
            )

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
        client = self._build_client(
            storage_directory=storage_directory, endpoint_url=endpoint, api_key=token
        )
        qm = qdrant_models

        distance_map = {
            "cosine": qm.Distance.COSINE,
            "l2": qm.Distance.EUCLID,
            "dot": qm.Distance.DOT,
        }
        existing = {item.name for item in client.get_collections().collections}
        if collection in existing and write_mode_normalized == "overwrite":
            client.delete_collection(collection_name=collection)
            existing.remove(collection)
        if collection not in existing:
            client.create_collection(
                collection_name=collection,
                vectors_config=qm.VectorParams(
                    size=dimension, distance=distance_map[normalized_metric]
                ),
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

        handle = VectorStoreHandle(
            backend=self.backend,
            index_name=collection,
            artifact_path="",
            metric=normalized_metric,
            dimension=dimension,
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            namespace=namespace,
            metadata={
                "endpoint_url": endpoint,
                "storage_directory": storage_directory,
                "collection_name": collection,
                "provider_config": _redacted_provider_config(config, token),
            },
        )
        client.close()
        return handle

    # -------------------------------------------------------------------------
    def _map_filter(self, filter_spec: dict[str, Any] | None, qm: Any) -> Any:
        if not filter_spec:
            return None
        validate_vector_request_capabilities(
            self.describe_capabilities(), filter_spec=filter_spec
        )
        must = [
            _qdrant_condition(clause, qm)
            for clause in filter_spec.get("must", [])
            if isinstance(clause, dict)
        ]
        should = [
            _qdrant_condition(clause, qm)
            for clause in filter_spec.get("should", [])
            if isinstance(clause, dict)
        ]
        must_not = [
            _qdrant_condition(clause, qm)
            for clause in filter_spec.get("must_not", [])
            if isinstance(clause, dict)
        ]
        must = [item for item in must if item is not None]
        should = [item for item in should if item is not None]
        must_not = [item for item in must_not if item is not None]
        if not must and not should and not must_not:
            return None
        return qm.Filter(
            must=must or None, should=should or None, must_not=must_not or None
        )

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
        self.validate_search_capabilities(
            store=store,
            search_mode=search_mode,
            search_engine=str(_.get("search_engine") or "native"),
            filter_spec=filter_spec,
            keyword_query=keyword_query,
        )

        metadata = (
            _store_attr(store, "metadata")
            if isinstance(_store_attr(store, "metadata"), dict)
            else {}
        )
        config = (
            metadata.get("provider_config")
            if isinstance(metadata.get("provider_config"), dict)
            else {}
        )
        endpoint = str(
            metadata.get("endpoint_url") or config.get("endpoint_url") or ""
        ).strip()
        storage_directory = str(metadata.get("storage_directory") or "").strip()
        token = _resolve_runtime_secret(config)
        collection = str(
            metadata.get("collection_name") or _store_attr(store, "index_name") or ""
        ).strip()
        if not collection:
            raise VectorStoreError("Qdrant search requires a collection name")

        client = self._build_client(
            storage_directory=storage_directory, endpoint_url=endpoint, api_key=token
        )
        qm = qdrant_models
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
            payload = (
                point.payload
                if isinstance(getattr(point, "payload", None), dict)
                else {}
            )
            entry_for_filter = {
                "chunk_id": payload.get("chunk_id"),
                "document_id": payload.get("document_id"),
                "text": payload.get("text"),
                "source_uri": payload.get("source_uri"),
                "metadata": payload.get("metadata", {})
                if isinstance(payload.get("metadata"), dict)
                else {},
            }
            if filter_spec and not _matches_filter(entry_for_filter, filter_spec):
                continue
            raw_score = float(getattr(point, "score", 0.0) or 0.0)
            raw_semantics = {
                "cosine": "cosine_similarity",
                "l2": "distance",
                "dot": "similarity",
            }.get(_coerce_metric(metric), "similarity")
            score = _score_from_metric(
                metric, raw_score, raw_semantics=raw_semantics
            )
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
                    score_semantics=_score_semantics_for_metric(metric),
                    metadata=(payload.get("metadata", {}) if include_metadata else {}),
                )
            )
        client.close()
        return results
