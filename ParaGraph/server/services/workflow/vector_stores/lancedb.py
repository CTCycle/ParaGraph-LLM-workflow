from __future__ import annotations

from ParaGraph.server.services.workflow.vector_stores.base import (
    Any,
    RetrievalHit,
    VectorPoint,
    VectorStoreAdapter,
    VectorStoreError,
    VectorStoreHandle,
    _import_lancedb_module,
    _matches_filter,
    _materialize_lancedb_rows,
    _normalize_index_name,
    _point_attr,
    _resolve_vectorstore_root,
    _sanitize_metadata_entry,
    _score_from_metric,
    _store_attr,
)

class LanceDbVectorStoreAdapter(VectorStoreAdapter):
    backend = "lancedb"
    supports_faiss_augmentation = False

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

        rows = [
            _sanitize_metadata_entry(point)
            | {"vector": [float(item) for item in _point_attr(point, "vector")]}
            for point in points
        ]
        db = lancedb.connect(str(root_path))
        table_names = set(db.table_names())

        if write_mode_normalized == "append" and normalized_index_name in table_names:
            table = db.open_table(normalized_index_name)
            current_rows = _materialize_lancedb_rows(table)
            if current_rows:
                existing_vector = (
                    current_rows[0].get("vector")
                    if isinstance(current_rows[0], dict)
                    else None
                )
                if (
                    not isinstance(existing_vector, list)
                    or len(existing_vector) != dimension
                ):
                    raise VectorStoreError(
                        "Existing LanceDB table dimension does not match incoming vectors"
                    )
                existing_provider = (
                    str(current_rows[0].get("embedding_provider", ""))
                    if isinstance(current_rows[0], dict)
                    else ""
                )
                existing_model = (
                    str(current_rows[0].get("embedding_model", ""))
                    if isinstance(current_rows[0], dict)
                    else ""
                )
                incoming_provider = str(
                    _point_attr(points[0], "embedding_provider") or ""
                )
                incoming_model = str(_point_attr(points[0], "embedding_model") or "")
                if existing_provider.lower() != incoming_provider.lower():
                    raise VectorStoreError(
                        "Existing LanceDB table embedding provider does not match incoming vectors"
                    )
                if existing_model != incoming_model:
                    raise VectorStoreError(
                        "Existing LanceDB table embedding model does not match incoming vectors"
                    )
            table.add(rows)
        else:
            table = db.create_table(normalized_index_name, data=rows, mode="overwrite")

        if create_vector_index:
            try:
                table.create_index(
                    vector_column_name="vector",
                    metric=metric_normalized,
                    num_partitions=max(1, nlist),
                )
            except TypeError:
                try:
                    table.create_index(
                        "vector", metric=metric_normalized, num_partitions=max(1, nlist)
                    )
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
            raise VectorStoreError(
                f"Search mode '{search_mode}' is not supported by backend '{self.backend}'"
            )
        lancedb = self._load_lancedb()
        store_metadata = (
            _store_attr(store, "metadata")
            if isinstance(_store_attr(store, "metadata"), dict)
            else {}
        )
        root_path = _resolve_vectorstore_root(
            store_metadata.get("storage_directory")
            if isinstance(store_metadata, dict)
            else None
        )
        db = lancedb.connect(str(root_path))
        table_name = str(
            (
                store_metadata.get("table_name")
                if isinstance(store_metadata, dict)
                else None
            )
            or _store_attr(store, "index_name")
            or ""
        ).strip()
        if not table_name:
            raise VectorStoreError("LanceDB search requires a table name")
        table = db.open_table(table_name)
        search_payload = table.search(query_vector).limit(
            max(1, top_k * 5, int(ann_search_depth))
        )
        rows = _materialize_lancedb_rows(search_payload)

        results: list[RetrievalHit] = []
        for entry in rows:
            if not isinstance(entry, dict) or not _matches_filter(entry, filter_spec):
                continue
            raw_score = float(entry.get("_distance", 0.0))
            score = _score_from_metric(
                str(_store_attr(store, "metric") or "cosine"), raw_score
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
                    metadata=entry.get("metadata", {}) if include_metadata else {},
                )
            )
            if len(results) >= top_k:
                break
        return results
