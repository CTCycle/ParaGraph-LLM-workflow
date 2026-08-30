from __future__ import annotations

from pymilvus import MilvusClient

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
    _milvus_clause_expression,
    _normalize_index_name,
    _point_attr,
    _redacted_provider_config,
    _resolve_runtime_secret,
    _sanitize_metadata_entry,
    _score_from_metric,
    _score_semantics_for_metric,
    _store_attr,
    validate_vector_request_capabilities,
)


###############################################################################
class MilvusVectorStoreAdapter(VectorStoreAdapter):
    backend = "milvus"
    capabilities = VectorStoreCapabilities(
        backend="milvus",
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
    def _build_client(self, *, endpoint_url: str, api_key: str, database_name: str):
        uri = endpoint_url or "http://localhost:19530"
        kwargs: dict[str, Any] = {"uri": uri}
        if api_key:
            kwargs["token"] = api_key
        if database_name:
            kwargs["db_name"] = database_name
        return MilvusClient(**kwargs)

    # -------------------------------------------------------------------------
    def _milvus_filter(self, filter_spec: dict[str, Any] | None) -> str:
        if not filter_spec:
            return ""
        validate_vector_request_capabilities(
            self.describe_capabilities(), filter_spec=filter_spec
        )
        must = [
            _milvus_clause_expression(item)
            for item in filter_spec.get("must", [])
            if isinstance(item, dict)
        ]
        must_not = [
            _milvus_clause_expression(item)
            for item in filter_spec.get("must_not", [])
            if isinstance(item, dict)
        ]
        should = [
            _milvus_clause_expression(item)
            for item in filter_spec.get("should", [])
            if isinstance(item, dict)
        ]
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
        _ = storage_directory
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
        try:
            client.list_collections()
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
        _ = storage_directory
        if not points:
            raise VectorStoreError(
                "Vector store write requires at least one vector point"
            )
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
        client = self._build_client(
            endpoint_url=endpoint, api_key=token, database_name=database
        )

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
                    "metadata": entry["metadata"]
                    if isinstance(entry["metadata"], dict)
                    else {},
                }
            )
        client.insert(collection_name=collection, data=rows)

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
                "database_name": database,
                "collection_name": collection,
                "provider_config": _redacted_provider_config(config, token),
            },
        )
        client.close()
        return handle

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
        database = str(
            metadata.get("database_name") or config.get("database_name") or ""
        ).strip()
        token = _resolve_runtime_secret(config)
        collection = str(
            metadata.get("collection_name") or _store_attr(store, "index_name") or ""
        ).strip()
        if not collection:
            raise VectorStoreError("Milvus search requires a collection name")

        filter_expr = self._milvus_filter(filter_spec)
        client = self._build_client(
            endpoint_url=endpoint, api_key=token, database_name=database
        )
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
        for raw_hit in response[0] if isinstance(response, list) and response else []:
            hit = (
                raw_hit
                if isinstance(raw_hit, dict)
                else getattr(raw_hit, "to_dict", lambda: {})()
            )
            entity = hit.get("entity") if isinstance(hit.get("entity"), dict) else {}
            entry_for_filter = {
                "chunk_id": entity.get("chunk_id"),
                "document_id": entity.get("document_id"),
                "text": entity.get("text"),
                "source_uri": entity.get("source_uri"),
                "metadata": entity.get("metadata", {})
                if isinstance(entity.get("metadata"), dict)
                else {},
            }
            if filter_spec and not _matches_filter(entry_for_filter, filter_spec):
                continue
            raw_score = float(hit.get("distance", hit.get("score", 0.0)) or 0.0)
            normalized_metric = _coerce_metric(metric)
            raw_semantics = "distance" if normalized_metric == "l2" else "similarity"
            score = _score_from_metric(
                normalized_metric, raw_score, raw_semantics=raw_semantics
            )
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
                    score_semantics=_score_semantics_for_metric(normalized_metric),
                    metadata=(entity.get("metadata", {}) if include_metadata else {}),
                )
            )
        client.close()
        return hits
