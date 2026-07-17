from __future__ import annotations

import lancedb

from server.services.workflow.vector_stores.base import (
    Any,
    RetrievalHit,
    VectorCollectionInfo,
    VectorMutationResult,
    VectorPoint,
    VectorStoreAdapter,
    VectorStoreConflictError,
    VectorStoreError,
    VectorStoreHandle,
    _matches_filter,
    _materialize_lancedb_rows,
    _normalize_index_name,
    _point_attr,
    _resolve_vectorstore_root,
    _sanitize_metadata_entry,
    _score_from_metric,
    _store_attr,
    _store_lock,
)

###############################################################################
class LanceDbVectorStoreAdapter(VectorStoreAdapter):
    backend = "lancedb"
    supports_faiss_augmentation = False
    supported_operations = frozenset(
        {"insert", "upsert", "update", "delete_ids", "delete_document", "delete_filter", "inspect", "delete_collection", "reload", "close"}
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
        create_vector_index: bool = True,
        id_conflict_policy: str = "reject",
        lock_timeout: float = 10.0,
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

        normalized_index_name = _normalize_index_name(collection_name or index_name)
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

        with _store_lock(root_path / normalized_index_name, lock_timeout):
            current_rows: list[dict[str, Any]] = []
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
                existing_ids = {str(row.get("id", "")) for row in current_rows}
                incoming_ids = [str(row.get("id", "")) for row in rows]
                duplicate_incoming = {
                    item_id for item_id in incoming_ids if incoming_ids.count(item_id) > 1
                }
                if duplicate_incoming:
                    raise VectorStoreConflictError(list(duplicate_incoming))
                conflicts = existing_ids.intersection(incoming_ids)
                policy = id_conflict_policy.strip().lower()
                if policy not in {"reject", "upsert"}:
                    raise VectorStoreError(
                        "id_conflict_policy must be 'reject' or 'upsert'"
                    )
                if conflicts and policy == "reject":
                    raise VectorStoreConflictError(list(conflicts))
                if conflicts:
                    current_rows = [
                        row for row in current_rows if str(row.get("id", "")) not in conflicts
                    ]
                rows = [*current_rows, *rows]
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
            embedding_revision=str(_point_attr(points[0], "embedding_revision") or ""),
            normalized=metric_normalized == "cosine",
            metadata={
                "index_type": index_type.lower().strip(),
                "count": len(_materialize_lancedb_rows(table)),
                "storage_directory": str(root_path),
                "table_name": normalized_index_name,
                "create_vector_index": bool(create_vector_index),
                "vector_index_status": "created" if create_vector_index else "skipped",
                "keyword_index_status": "unsupported",
                "num_partitions": max(1, nlist),
                "hnsw_m": hnsw_m,
            },
            collection_name=normalized_index_name,
            vector_index_status="created" if create_vector_index else "skipped",
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
        _ = keyword_query, vector_weight, keyword_weight
        if search_mode != "vector":
            raise VectorStoreError(
                f"Search mode '{search_mode}' is not supported by backend '{self.backend}'"
            )
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

    # -------------------------------------------------------------------------
    def _table(self, store: VectorStoreHandle | dict[str, Any]):
        metadata = _store_attr(store, "metadata") or {}
        root = _resolve_vectorstore_root(metadata.get("storage_directory"))
        name = str(metadata.get("table_name") or _store_attr(store, "index_name"))
        db = lancedb.connect(str(root))
        return db, db.open_table(name), root, name

    # -------------------------------------------------------------------------
    def inspect_collection(
        self, *, store: VectorStoreHandle | dict[str, Any]
    ) -> VectorCollectionInfo:
        _, table, _, name = self._table(store)
        rows = _materialize_lancedb_rows(table)
        first = rows[0] if rows else {}
        vector = first.get("vector") if isinstance(first.get("vector"), list) else []
        return VectorCollectionInfo(
            backend=self.backend,
            index_name=name,
            exists=True,
            count=len(rows),
            metric=str(_store_attr(store, "metric") or ""),
            dimension=len(vector),
            embedding_provider=str(first.get("embedding_provider", "")),
            embedding_model=str(first.get("embedding_model", "")),
            embedding_revision=str(first.get("embedding_revision", "")),
            normalized=bool(first.get("normalized", False)),
        )

    # -------------------------------------------------------------------------
    def _delete_matching(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        predicate: Any,
        operation: str,
        lock_timeout: float,
    ) -> VectorMutationResult:
        db, table, root, name = self._table(store)
        rows = _materialize_lancedb_rows(table)
        affected = [str(row.get("id", "")) for row in rows if predicate(row)]
        retained = [row for row in rows if not predicate(row)]
        with _store_lock(root / name, lock_timeout):
            if retained:
                db.create_table(name, data=retained, mode="overwrite")
            else:
                db.drop_table(name)
        return VectorMutationResult(
            operation=operation,
            affected_count=len(affected),
            affected_ids=sorted(affected),
        )

    # -------------------------------------------------------------------------
    def delete_ids(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        ids: list[str],
        lock_timeout: float = 10.0,
    ) -> VectorMutationResult:
        requested = set(ids)
        return self._delete_matching(
            store=store,
            predicate=lambda row: str(row.get("id", "")) in requested,
            operation="delete_ids",
            lock_timeout=lock_timeout,
        )

    # -------------------------------------------------------------------------
    def update_points(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        points: list[VectorPoint | dict[str, Any]],
        lock_timeout: float = 10.0,
    ) -> VectorMutationResult:
        _, table, root, name = self._table(store)
        existing = {str(row.get("id", "")) for row in _materialize_lancedb_rows(table)}
        ids = [str(_point_attr(point, "id") or "") for point in points]
        missing = sorted(set(ids).difference(existing))
        if missing:
            raise VectorStoreError(
                "Cannot update missing vector record IDs: " + ", ".join(missing)
            )
        self.write_points(
            index_name=name,
            storage_directory=str(root),
            metric=str(_store_attr(store, "metric") or "cosine"),
            write_mode="append",
            id_conflict_policy="upsert",
            points=points,
            create_vector_index=False,
            lock_timeout=lock_timeout,
        )
        return VectorMutationResult(
            operation="update", affected_count=len(ids), affected_ids=sorted(ids)
        )

    # -------------------------------------------------------------------------
    def delete_document(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        document_id: str,
        lock_timeout: float = 10.0,
    ) -> VectorMutationResult:
        return self._delete_matching(
            store=store,
            predicate=lambda row: str(row.get("document_id", "")) == document_id,
            operation="delete_document",
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
        return self._delete_matching(
            store=store,
            predicate=lambda row: _matches_filter(row, filter_spec),
            operation="delete_filter",
            lock_timeout=lock_timeout,
        )

    # -------------------------------------------------------------------------
    def delete_collection(
        self, *, store: VectorStoreHandle | dict[str, Any], **_: Any
    ) -> VectorMutationResult:
        db, table, _, name = self._table(store)
        ids = [str(row.get("id", "")) for row in _materialize_lancedb_rows(table)]
        db.drop_table(name)
        return VectorMutationResult(
            operation="delete_collection", affected_count=len(ids), affected_ids=ids
        )

    # -------------------------------------------------------------------------
    def reload(self, *, store: VectorStoreHandle | dict[str, Any]) -> VectorStoreHandle:
        info = self.inspect_collection(store=store)
        payload = store if isinstance(store, dict) else store.model_dump(mode="json")
        metadata = dict(payload.get("metadata") or {})
        metadata["count"] = info.count
        return VectorStoreHandle.model_validate(
            payload
            | {
                "dimension": info.dimension,
                "embedding_provider": info.embedding_provider,
                "embedding_model": info.embedding_model,
                "embedding_revision": info.embedding_revision,
                "normalized": info.normalized,
                "metadata": metadata,
            }
        )
