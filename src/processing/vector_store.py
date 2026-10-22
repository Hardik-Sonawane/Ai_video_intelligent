"""
Vector store management using ChromaDB.
Handles embedding generation and semantic search.
"""

import logging
import uuid
from typing import Optional
import chromadb
from chromadb.config import Settings

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from sentence_transformers import SentenceTransformer

from src.config import config

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Manages transcript storage in ChromaDB using sentence-transformers embeddings.
    Each chunk retains its source timestamp metadata for grounded answers.
    """

    def __init__(self):
        self._client = chromadb.PersistentClient(
            path=config.CHROMA_DB_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        self._collection: Optional[chromadb.Collection] = None
        self._current_video_id: Optional[str] = None

    # ── Collection management ────────────────────────────────────────────

    def get_or_create_collection(self, video_id: str) -> chromadb.Collection:
        """Get or create a ChromaDB collection for a given video."""
        collection_name = f"video_{video_id[:40]}"  # ChromaDB name limit
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._current_video_id = video_id
        return self._collection

    def collection_exists(self, video_id: str) -> bool:
        """Check if a collection already exists for this video."""
        try:
            collection_name = f"video_{video_id[:40]}"
            existing = [c.name for c in self._client.list_collections()]
            return collection_name in existing
        except Exception:
            return False

    def get_collection_count(self) -> int:
        if self._collection:
            return self._collection.count()
        return 0

    # ── Indexing ─────────────────────────────────────────────────────────

    def index_transcript(self, video_id: str, transcript_data: dict) -> int:
        """
        Split transcript segments into chunks, embed, and store in ChromaDB.
        Returns number of chunks stored.
        """
        self.get_or_create_collection(video_id)

        segments = transcript_data.get("segments", [])
        if not segments:
            logger.warning("No segments found in transcript.")
            return 0

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        documents, metadatas, ids = [], [], []

        # Chunk by grouping consecutive segments
        buffer_text = ""
        buffer_start = segments[0]["start"]
        buffer_end = segments[0]["end"]
        buffer_segments = []

        for seg in segments:
            buffer_text += " " + seg["text"]
            buffer_end = seg["end"]
            buffer_segments.append(seg)

            if len(buffer_text) >= config.CHUNK_SIZE:
                # Create chunk from buffer
                chunks = splitter.split_text(buffer_text.strip())
                for chunk in chunks:
                    if chunk.strip():
                        doc_id = str(uuid.uuid4())
                        documents.append(chunk)
                        metadatas.append({
                            "video_id": video_id,
                            "start_sec": float(buffer_start),
                            "end_sec": float(buffer_end),
                            "start_formatted": self._format_time(buffer_start),
                            "end_formatted": self._format_time(buffer_end),
                            "segment_count": len(buffer_segments),
                        })
                        ids.append(doc_id)

                # Reset buffer
                buffer_text = ""
                buffer_start = seg["end"]
                buffer_end = seg["end"]
                buffer_segments = []

        # Don't forget the last buffer
        if buffer_text.strip():
            chunks = splitter.split_text(buffer_text.strip())
            for chunk in chunks:
                if chunk.strip():
                    doc_id = str(uuid.uuid4())
                    documents.append(chunk)
                    metadatas.append({
                        "video_id": video_id,
                        "start_sec": float(buffer_start),
                        "end_sec": float(buffer_end),
                        "start_formatted": self._format_time(buffer_start),
                        "end_formatted": self._format_time(buffer_end),
                        "segment_count": len(buffer_segments),
                    })
                    ids.append(doc_id)

        if not documents:
            return 0

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(documents)} chunks...")
        embeddings = self._embed_model.encode(documents, show_progress_bar=False).tolist()

        # Batch upsert to ChromaDB
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            self._collection.upsert(
                documents=documents[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
                ids=ids[i : i + batch_size],
            )

        logger.info(f"Indexed {len(documents)} chunks for video {video_id}")
        return len(documents)

    # ── Search ───────────────────────────────────────────────────────────

    def search(self, query: str, video_id: str, top_k: int = None) -> list[dict]:
        """
        Semantic search over transcript chunks for a given video.
        Returns list of results with text, score, and timestamp.
        """
        k = top_k or config.TOP_K_RESULTS
        collection = self.get_or_create_collection(video_id)

        if collection.count() == 0:
            return []

        query_embedding = self._embed_model.encode([query]).tolist()
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            output.append({
                "text": doc,
                "start_sec": meta.get("start_sec", 0),
                "end_sec": meta.get("end_sec", 0),
                "start_formatted": meta.get("start_formatted", "00:00"),
                "end_formatted": meta.get("end_formatted", "00:00"),
                "relevance_score": round(1 - dist, 4),  # cosine similarity
            })

        return output

    def search_by_timestamp(
        self, timestamp_sec: float, video_id: str, window_sec: float = 60.0
    ) -> list[dict]:
        """Find transcript chunks near a specific timestamp."""
        collection = self.get_or_create_collection(video_id)
        if collection.count() == 0:
            return []

        lower = float(timestamp_sec - window_sec)
        upper = float(timestamp_sec + window_sec)

        try:
            # Use $and operator for ChromaDB >= 0.4
            results = collection.get(
                where={
                    "$and": [
                        {"start_sec": {"$lte": upper}},
                        {"end_sec": {"$gte": lower}},
                    ]
                },
                include=["documents", "metadatas"],
            )
        except Exception as e:
            logger.warning(f"Timestamp filter failed, falling back to full scan: {e}")
            # Fallback: get all and filter in Python
            results = collection.get(include=["documents", "metadatas"])

        output = []
        for doc, meta in zip(
            results.get("documents", []), results.get("metadatas", [])
        ):
            # Python-level filter as safety net
            start = meta.get("start_sec", 0)
            end = meta.get("end_sec", 0)
            if start <= upper and end >= lower:
                output.append({
                    "text": doc,
                    "start_sec": start,
                    "end_sec": end,
                    "start_formatted": meta.get("start_formatted", "00:00"),
                    "end_formatted": meta.get("end_formatted", "00:00"),
                })

        # Sort by proximity to the requested timestamp
        output.sort(key=lambda x: abs(x["start_sec"] - timestamp_sec))
        return output[:5]

    def delete_collection(self, video_id: str) -> bool:
        """Delete a collection for a given video."""
        try:
            collection_name = f"video_{video_id[:40]}"
            self._client.delete_collection(collection_name)
            self._collection = None
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_time(seconds: float) -> str:
        seconds = max(0, int(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
