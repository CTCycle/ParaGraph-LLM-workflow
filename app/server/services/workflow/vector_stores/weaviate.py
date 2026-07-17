from __future__ import annotations

import weaviate

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
    _sanitize_metadata_entry,
    _score_from_metric,
    _store_attr,
)

###############################################################################
class WeaviateVectorStoreAdapter(VectorStoreAdapter):
    backend = "weaviate"
    supported_operations = frozenset({"insert", "upsert", "search", "close"})
    supports_faiss_augmentation = False

    # -------------------------------------------------------------------------
    def _connect(self, *, endpoint_url: str, api_key: str):
        if not endpoint_url:
            raise VectorStoreError("Weaviate requires endpoint_url")
        if api_key:
            return weaviate.connect_to_weaviate_cloud(
                cluster_url=endpoint_url,
                auth_credentials=weaviate.Auth.api_key(api_key),
            )
        return weaviate.connect_to_custom(
            http_host=endpoint_url, http_port=443, http_secure=True
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
        _ = storage_directory, namespace, database_name
        if not points:
            raise VectorStoreError(
                "Vector store write requires at least one vector point"
            )
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
                "provider_config": _redacted_provider_config(config, token),
            },
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
        _ = ann_search_depth, keyword_query, vector_weight, keyword_weight
        if search_mode != "vector":
            raise VectorStoreError(
                "Hybrid search is not currently supported for Weaviate in this runtime"
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
        token = _resolve_runtime_secret(config)
        collection = str(
            metadata.get("collection_name") or _store_attr(store, "index_name") or ""
        ).strip()
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
            properties = (
                getattr(item, "properties", {})
                if isinstance(getattr(item, "properties", {}), dict)
                else {}
            )
            meta = (
                properties.get("metadata", {})
                if isinstance(properties.get("metadata"), dict)
                else {}
            )
            entry_for_filter = {
                "chunk_id": properties.get("chunk_id"),
                "document_id": properties.get("document_id"),
                "text": properties.get("text"),
                "source_uri": properties.get("source_uri"),
                "metadata": meta,
            }
            if filter_spec and not _matches_filter(entry_for_filter, filter_spec):
                continue
            distance = float(
                getattr(getattr(item, "metadata", None), "distance", 0.0) or 0.0
            )
            score = _score_from_metric(
                metric, distance if metric == "l2" else 1.0 - distance
            )
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
