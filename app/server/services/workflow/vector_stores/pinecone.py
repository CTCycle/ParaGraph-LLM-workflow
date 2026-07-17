from __future__ import annotations

from pinecone import Pinecone, ServerlessSpec

from server.services.workflow.vector_stores.base import (
    Any,
    RetrievalHit,
    VectorPoint,
    VectorStoreAdapter,
    VectorStoreError,
    VectorStoreHandle,
    _coerce_metric,
    _extract_provider_config,
    _normalize_index_name,
    _pinecone_clause,
    _point_attr,
    _redacted_provider_config,
    _resolve_runtime_secret,
    _sanitize_metadata_entry,
    _store_attr,
    logger,
)

###############################################################################
class PineconeVectorStoreAdapter(VectorStoreAdapter):
    backend = "pinecone"
    supported_operations = frozenset({"insert", "upsert", "search", "close"})
    supports_faiss_augmentation = False

    # -------------------------------------------------------------------------
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
        _ = storage_directory, namespace, endpoint_url, database_name
        _, _, token = _extract_provider_config(
            provider_config=provider_config, endpoint_url="", api_key=api_key
        )
        if not token:
            raise VectorStoreError("Pinecone requires api_key")
        client = Pinecone(api_key=token)
        target = _normalize_index_name(collection_name or index_name)
        names = {item.name for item in client.list_indexes()}
        if target and target not in names:
            logger.debug(
                "Pinecone index '%s' does not exist yet (will be created on first write)",
                target,
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
        **_: Any,
    ) -> VectorStoreHandle:
        _ = storage_directory, endpoint_url, database_name
        if not points:
            raise VectorStoreError(
                "Vector store write requires at least one vector point"
            )

        normalized_metric = _coerce_metric(metric)
        if normalized_metric not in {"cosine", "dot", "l2"}:
            raise VectorStoreError(f"Unsupported Pinecone metric: {metric}")

        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        config, _, token = _extract_provider_config(
            provider_config=provider_config, endpoint_url="", api_key=api_key
        )
        if not token:
            raise VectorStoreError("Pinecone requires api_key")

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
            client.Index(target_index).delete(
                delete_all=True, namespace=namespace or None
            )

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
        **_: Any,
    ) -> list[RetrievalHit]:
        _ = ann_search_depth
        if search_mode != "vector":
            raise VectorStoreError(
                "Hybrid search is not currently supported for Pinecone in this runtime"
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
        token = _resolve_runtime_secret(config)
        if not token:
            raise VectorStoreError(
                "Pinecone credentials are unavailable; reconnect using a secret reference"
            )

        client = Pinecone(api_key=token)
        index_name = str(
            metadata.get("collection_name") or _store_attr(store, "index_name") or ""
        ).strip()
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

        matches = (
            response.get("matches")
            if isinstance(response, dict)
            else getattr(response, "matches", [])
        )
        results: list[RetrievalHit] = []
        for match in matches or []:
            record = (
                match
                if isinstance(match, dict)
                else getattr(match, "to_dict", lambda: {})()
            )
            item_metadata = (
                record.get("metadata")
                if isinstance(record.get("metadata"), dict)
                else {}
            )
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
                    metadata=(
                        item_metadata.get("metadata", {}) if include_metadata else {}
                    ),
                )
            )
        return results
