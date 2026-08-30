from __future__ import annotations

import json

import chromadb

from server.contracts.node_catalog import VectorStoreCapabilities
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
    _coerce_metric,
    _matches_filter,
    _normalize_index_name,
    _point_attr,
    _resolve_vectorstore_root,
    _sanitize_metadata_entry,
    _score_from_metric,
    _score_semantics_for_metric,
    _store_attr,
)


###############################################################################
class ChromaVectorStoreAdapter(VectorStoreAdapter):
    backend = "chroma"
    capabilities = VectorStoreCapabilities(
        backend="chroma",
        supported_metrics=["cosine", "l2", "dot"],
        supported_search_modes=["vector"],
        supported_search_engines=["native"],
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
        supported_operations=[
            "insert",
            "upsert",
            "update",
            "delete_ids",
            "delete_document",
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
    def _build_client(self, *, storage_directory: str, endpoint_url: str):
        if endpoint_url:
            return chromadb.HttpClient(host=endpoint_url)
        root = _resolve_vectorstore_root(storage_directory)
        root.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(root / "chroma"))

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
        _ = api_key, database_name, provider_config
        client = self._build_client(
            storage_directory=storage_directory, endpoint_url=endpoint_url
        )
        _normalize_index_name(collection_name or index_name)
        client.heartbeat()

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
        id_conflict_policy: str = "reject",
        **_: Any,
    ) -> VectorStoreHandle:
        self.validate_write_capabilities(
            metric=metric,
            namespace=namespace,
            create_keyword_index=bool(_.get("create_keyword_index", False)),
        )
        _ = api_key, database_name, provider_config
        if not points:
            raise VectorStoreError(
                "Vector store write requires at least one vector point"
            )

        normalized_metric = _coerce_metric(metric)
        if normalized_metric not in {"cosine", "l2", "dot"}:
            raise VectorStoreError(f"Unsupported Chroma metric: {metric}")

        write_mode_normalized = write_mode.lower().strip()
        if write_mode_normalized not in {"overwrite", "append"}:
            raise VectorStoreError("write_mode must be either 'overwrite' or 'append'")

        collection = _normalize_index_name(collection_name or index_name)
        client = self._build_client(
            storage_directory=storage_directory, endpoint_url=endpoint_url
        )

        if write_mode_normalized == "overwrite":
            try:
                client.delete_collection(name=collection)
            except Exception as exc:  # Chroma has changed its not-found type.
                if "does not exist" not in str(exc).lower():
                    raise

        incoming_provider = str(_point_attr(points[0], "embedding_provider") or "")
        incoming_model = str(_point_attr(points[0], "embedding_model") or "")
        incoming_revision = str(_point_attr(points[0], "embedding_revision") or "")
        collection_metadata = {
            "hnsw:space": "ip" if normalized_metric == "dot" else normalized_metric,
            "dimension": len(_point_attr(points[0], "vector")),
            "embedding_provider": incoming_provider,
            "embedding_model": incoming_model,
            "embedding_revision": incoming_revision,
            "normalized": normalized_metric == "cosine",
        }
        coll = client.get_or_create_collection(
            name=collection, metadata=collection_metadata
        )
        existing_metadata = coll.metadata or {}
        mismatches = [
            field
            for field in (
                "dimension",
                "embedding_provider",
                "embedding_model",
                "embedding_revision",
                "normalized",
            )
            if existing_metadata.get(field) != collection_metadata.get(field)
        ]
        existing_metric = str(existing_metadata.get("hnsw:space", "cosine"))
        if existing_metric != collection_metadata["hnsw:space"]:
            mismatches.append("metric")
        if write_mode_normalized == "append" and mismatches:
            raise VectorStoreError(
                "Existing Chroma collection is incompatible: " + ", ".join(mismatches)
            )
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
                    "metadata_json": json.dumps(entry["metadata"], sort_keys=True),
                }
            )
        if len(ids) != len(set(ids)):
            raise VectorStoreConflictError(
                [item_id for item_id in ids if ids.count(item_id) > 1]
            )
        conflict_policy = id_conflict_policy.strip().lower()
        if conflict_policy not in {"reject", "upsert"}:
            raise VectorStoreError("id_conflict_policy must be 'reject' or 'upsert'")
        conflicts = set((coll.get(ids=ids).get("ids") or [])) if ids else set()
        if conflicts and conflict_policy == "reject":
            raise VectorStoreConflictError(list(conflicts))
        writer = coll.upsert if conflict_policy == "upsert" else coll.add
        writer(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

        return VectorStoreHandle(
            backend=self.backend,
            index_name=collection,
            artifact_path="",
            metric=normalized_metric,
            dimension=len(embeddings[0]),
            embedding_provider=str(_point_attr(points[0], "embedding_provider") or ""),
            embedding_model=str(_point_attr(points[0], "embedding_model") or ""),
            embedding_revision=incoming_revision,
            normalized=normalized_metric == "cosine",
            namespace=namespace,
            metadata={
                "storage_directory": storage_directory,
                "endpoint_url": endpoint_url,
                "collection_name": collection,
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
        self.validate_search_capabilities(
            store=store,
            search_mode=search_mode,
            search_engine=str(_.get("search_engine") or "native"),
            filter_spec=filter_spec,
            keyword_query=str(_.get("keyword_query") or "") or None,
        )

        metadata = (
            _store_attr(store, "metadata")
            if isinstance(_store_attr(store, "metadata"), dict)
            else {}
        )
        storage_directory = str(metadata.get("storage_directory") or "").strip()
        endpoint_url = str(metadata.get("endpoint_url") or "").strip()
        collection = str(
            metadata.get("collection_name") or _store_attr(store, "index_name") or ""
        ).strip()
        if not collection:
            raise VectorStoreError("Chroma search requires a collection name")

        client = self._build_client(
            storage_directory=storage_directory, endpoint_url=endpoint_url
        )
        coll = client.get_collection(name=collection)

        results = coll.query(
            query_embeddings=[[float(item) for item in query_vector]],
            n_results=min(max(1, top_k * 5), max(1, coll.count())),
        )
        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        payloads: list[RetrievalHit] = []
        for idx, item_id in enumerate(ids):
            meta = (
                metadatas[idx]
                if idx < len(metadatas) and isinstance(metadatas[idx], dict)
                else {}
            )
            entry_for_filter = {
                "metadata": json.loads(str(meta.get("metadata_json") or "{}")),
                "document_id": meta.get("document_id"),
                "chunk_id": meta.get("chunk_id"),
                "source_uri": meta.get("source_uri"),
                "text": documents[idx] if idx < len(documents) else "",
            }
            if not _matches_filter(entry_for_filter, filter_spec):
                continue
            raw = float(distances[idx]) if idx < len(distances) else 0.0
            metric = str(_store_attr(store, "metric") or "cosine")
            score = _score_from_metric(metric, raw, raw_semantics="distance")
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
                    score_semantics=_score_semantics_for_metric(metric),
                    metadata=(
                        json.loads(str(meta.get("metadata_json") or "{}"))
                        if include_metadata
                        else {}
                    ),
                )
            )
            if len(payloads) >= top_k:
                break
        return payloads

    # -------------------------------------------------------------------------
    def _collection(self, store: VectorStoreHandle | dict[str, Any]):
        metadata = _store_attr(store, "metadata") or {}
        client = self._build_client(
            storage_directory=str(metadata.get("storage_directory") or ""),
            endpoint_url=str(metadata.get("endpoint_url") or ""),
        )
        name = str(metadata.get("collection_name") or _store_attr(store, "index_name"))
        return client, client.get_collection(name=name)

    # -------------------------------------------------------------------------
    def inspect_collection(
        self, *, store: VectorStoreHandle | dict[str, Any]
    ) -> VectorCollectionInfo:
        _, collection = self._collection(store)
        metadata = collection.metadata or {}
        metric = str(metadata.get("hnsw:space", "cosine"))
        return VectorCollectionInfo(
            backend=self.backend,
            index_name=collection.name,
            exists=True,
            count=collection.count(),
            metric="dot" if metric == "ip" else metric,
            dimension=int(metadata.get("dimension", 0)),
            embedding_provider=str(metadata.get("embedding_provider", "")),
            embedding_model=str(metadata.get("embedding_model", "")),
            embedding_revision=str(metadata.get("embedding_revision", "")),
            normalized=bool(metadata.get("normalized", False)),
        )

    # -------------------------------------------------------------------------
    def delete_ids(
        self, *, store: VectorStoreHandle | dict[str, Any], ids: list[str], **_: Any
    ) -> VectorMutationResult:
        _, collection = self._collection(store)
        affected = list(collection.get(ids=ids).get("ids") or [])
        collection.delete(ids=ids)
        return VectorMutationResult(
            operation="delete_ids", affected_count=len(affected), affected_ids=affected
        )

    # -------------------------------------------------------------------------
    def update_points(
        self,
        *,
        store: VectorStoreHandle | dict[str, Any],
        points: list[VectorPoint | dict[str, Any]],
        **_: Any,
    ) -> VectorMutationResult:
        _, collection = self._collection(store)
        ids = [str(_point_attr(point, "id") or "") for point in points]
        existing = set(collection.get(ids=ids).get("ids") or [])
        missing = sorted(set(ids).difference(existing))
        if missing:
            raise VectorStoreError(
                "Cannot update missing vector record IDs: " + ", ".join(missing)
            )
        metadata = _store_attr(store, "metadata") or {}
        self.write_points(
            index_name=str(_store_attr(store, "index_name") or ""),
            storage_directory=str(metadata.get("storage_directory") or ""),
            endpoint_url=str(metadata.get("endpoint_url") or ""),
            metric=str(_store_attr(store, "metric") or "cosine"),
            write_mode="append",
            id_conflict_policy="upsert",
            points=points,
        )
        return VectorMutationResult(
            operation="update", affected_count=len(ids), affected_ids=sorted(ids)
        )

    # -------------------------------------------------------------------------
    def delete_document(
        self, *, store: VectorStoreHandle | dict[str, Any], document_id: str, **_: Any
    ) -> VectorMutationResult:
        _, collection = self._collection(store)
        affected = list(
            collection.get(where={"document_id": document_id}).get("ids") or []
        )
        collection.delete(where={"document_id": document_id})
        return VectorMutationResult(
            operation="delete_document",
            affected_count=len(affected),
            affected_ids=affected,
        )

    # -------------------------------------------------------------------------
    def delete_collection(
        self, *, store: VectorStoreHandle | dict[str, Any], **_: Any
    ) -> VectorMutationResult:
        client, collection = self._collection(store)
        affected = list(collection.get().get("ids") or [])
        client.delete_collection(name=collection.name)
        return VectorMutationResult(
            operation="delete_collection",
            affected_count=len(affected),
            affected_ids=affected,
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
                "metric": info.metric,
                "embedding_provider": info.embedding_provider,
                "embedding_model": info.embedding_model,
                "embedding_revision": info.embedding_revision,
                "normalized": info.normalized,
                "metadata": metadata,
            }
        )
