from __future__ import annotations

from ParaGraph.server.services.workflow.vector_stores.base import (
    Any,
    RetrievalHit,
    VectorPoint,
    VectorStoreAdapter,
    VectorStoreError,
    VectorStoreHandle,
    _coerce_metric,
    _import_chromadb_module,
    _matches_filter,
    _normalize_index_name,
    _point_attr,
    _resolve_vectorstore_root,
    _sanitize_metadata_entry,
    _score_from_metric,
    _store_attr,
)

class ChromaVectorStoreAdapter(VectorStoreAdapter):
    backend = "chroma"
    supports_faiss_augmentation = False

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
        client = self._build_client(
            storage_directory=storage_directory, endpoint_url=endpoint_url
        )
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
        coll.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

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
            raise VectorStoreError(
                "Hybrid search is not currently supported for Chroma in this runtime"
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
            n_results=max(1, top_k),
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
                "metadata": meta.get("metadata", {})
                if isinstance(meta.get("metadata"), dict)
                else {},
                "document_id": meta.get("document_id"),
                "chunk_id": meta.get("chunk_id"),
                "source_uri": meta.get("source_uri"),
                "text": documents[idx] if idx < len(documents) else "",
            }
            if not _matches_filter(entry_for_filter, filter_spec):
                continue
            raw = float(distances[idx]) if idx < len(distances) else 0.0
            score = _score_from_metric(
                str(_store_attr(store, "metric") or "cosine"), raw
            )
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
