from __future__ import annotations

from pymilvus import MilvusClient

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
    _sanitize_metadata_entry,
    _score_from_metric,
    _store_attr,
)


class MilvusVectorStoreAdapter(VectorStoreAdapter):
    backend = "milvus"
    supports_faiss_augmentation = False

    def _build_client(self, *, endpoint_url: str, api_key: str, database_name: str):
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
            raise VectorStoreError(
                "Hybrid search is not currently supported for Milvus in this runtime"
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
        token = str(config.get("api_key") or "").strip()
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
