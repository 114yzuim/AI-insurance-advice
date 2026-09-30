"""Content-addressed object storage for crawled documents/snapshots/parse
artifacts, with a swappable backend (local file today, S3-compatible later).

Concept borrowed from `FileArtifactStore`/`ArtifactStore` in
C:/Users/rabbi/OneDrive/桌面/final/repo-manager/manager/services/artifact_store.py
(remote YZU1507A/test-yzuqa-manager) -- the atomic-write-then-rename pattern
(a crash never leaves a reader looking at a half-written file) and the
path-traversal guard on every read/write.

What's deliberately NOT carried over from that source: `yzu_contracts`
(`ArtifactLayout`/`PageArtifact`/`CrawlRunManifest` -- YZU-specific pydantic
contracts this project has no equivalent of and shouldn't runtime-depend
on), the GCS-only cloud backend (`google-cloud-storage` isn't a dependency
of this project and Railway's own object storage is S3-compatible, so an
S3-compatible backend is the one worth having an interface for), and
`InMemoryArtifactStore` (this project's tests use real temp directories via
FileObjectStore instead -- one less code path to keep in sync with the real
one).

This store is deliberately generic -- "put these bytes under this key,
give me an ObjectRef back" -- unlike the source repo's store, which only
ever stores whole PageArtifact/CrawlRunManifest JSON documents. Callers
(scripts/download_ib_documents.py etc) decide the key layout; see this
module's KEY LAYOUT CONVENTIONS section below for the agreed one.

KEY LAYOUT CONVENTIONS (callers should follow these, not required by the
store itself):
    sources/{source}/documents/{checksum[:2]}/{checksum}.{ext}
    sources/{source}/html/{yyyymmdd}/{hash}.html
    parse_artifacts/{source}/{document_id}/{parser_name}.json

Usage:
    store = FileObjectStore(Path("backend/data/object_store"))
    ref = store.put_bytes("sources/ib_disclosure/documents/ab/ab12....pdf", data, content_type="application/pdf")
    data_back = store.get_bytes(ref.key)
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_KEY_SEGMENT_RE_INVALID = ("..", "\x00")


@dataclass(frozen=True)
class ObjectRef:
    scheme: str  # "file" | "s3"
    bucket: str
    key: str
    uri: str
    content_type: str | None
    size_bytes: int
    checksum_sha256: str


class ObjectStore(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> ObjectRef: ...

    def get_bytes(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


def _validate_key(key: str) -> str:
    """A key is a POSIX-style relative path -- never absolute, never
    containing `..` (path traversal) or a NUL byte. Raises ValueError
    rather than silently sanitizing, so a caller building a bad key finds
    out immediately instead of writing to a surprising location.
    """
    if not key or key.startswith("/") or key.startswith("\\"):
        raise ValueError(f"object key must be a relative path: {key!r}")
    for marker in _KEY_SEGMENT_RE_INVALID:
        if marker in key:
            raise ValueError(f"object key contains a disallowed sequence {marker!r}: {key!r}")
    return key


class FileObjectStore:
    """Local-filesystem-backed ObjectStore. The default backend -- durable,
    zero external dependencies, and the natural stand-in for the S3-
    compatible backend this project will eventually point at Railway's own
    bucket (see OBJECT_STORE_BACKEND in this module's docstring / .env
    convention).
    """

    scheme = "file"

    def __init__(self, root: Path | str, *, bucket: str = "local") -> None:
        self.root = Path(root).resolve()
        self.bucket = bucket
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        _validate_key(key)
        path = (self.root / key).resolve()
        # Belt-and-suspenders on top of _validate_key's string-level check:
        # confirm the resolved path is actually still under root (catches
        # e.g. a key that resolves through a symlink, or platform-specific
        # path quirks _validate_key's simple string check might miss).
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"object key escapes the store root: {key!r}") from exc
        return path

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> ObjectRef:
        path = self._resolve(key)
        checksum = hashlib.sha256(data).hexdigest()
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: write to a per-process temp file in the same
            # directory (so os.replace is a same-filesystem rename, not a
            # copy), then rename over the final name -- a reader never sees
            # a partially-written file, and a crash mid-write leaves only
            # an orphaned .tmp-* file, never a corrupt object at `path`.
            tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}")
            with open(tmp_path, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        # Duplicate-checksum idempotency: if content already exists at this
        # exact key (a caller keying by checksum, as the KEY LAYOUT
        # CONVENTIONS above recommend, re-puts the same bytes), skip the
        # write entirely rather than re-writing identical bytes.
        return ObjectRef(
            scheme=self.scheme,
            bucket=self.bucket,
            key=key,
            uri=f"file://{path.as_posix()}",
            content_type=content_type,
            size_bytes=len(data),
            checksum_sha256=checksum,
        )

    def get_bytes(self, key: str) -> bytes:
        path = self._resolve(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).exists()
        except ValueError:
            return False


class S3CompatibleObjectStore:
    """S3-compatible backend (AWS S3, Cloudflare R2, Railway Bucket -- all
    speak the same S3 API). NOT wired up with real credentials by this
    phase -- see Task 5's report for why -- but the interface and env var
    names are final so switching backends later is a config change, not a
    code change.

    Requires `boto3` (not currently a dependency of this project -- only
    imported lazily, inside __init__, so importing this module doesn't
    require installing it until a caller actually constructs one).
    """

    scheme = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client=None,
    ) -> None:
        if not bucket:
            raise ValueError("bucket is required")
        self.bucket = bucket
        if client is not None:
            self._client = client
        else:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - packaging guard
                raise RuntimeError(
                    "boto3 is required for S3CompatibleObjectStore -- pip install boto3, "
                    "or use FileObjectStore for local/dev storage"
                ) from exc
            self._client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> ObjectRef:
        _validate_key(key)
        checksum = hashlib.sha256(data).hexdigest()
        extra_args = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra_args)
        return ObjectRef(
            scheme=self.scheme,
            bucket=self.bucket,
            key=key,
            uri=f"s3://{self.bucket}/{key}",
            content_type=content_type,
            size_bytes=len(data),
            checksum_sha256=checksum,
        )

    def get_bytes(self, key: str) -> bytes:
        _validate_key(key)
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        _validate_key(key)
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


def object_store_from_env() -> ObjectStore:
    """Build the configured backend from environment variables:

        OBJECT_STORE_BACKEND=file|s3   (default: file)
        OBJECT_STORE_ROOT              (file backend; default backend/data/object_store)
        OBJECT_STORE_BUCKET
        OBJECT_STORE_ENDPOINT
        OBJECT_STORE_ACCESS_KEY_ID
        OBJECT_STORE_SECRET_ACCESS_KEY

    Kept as one function so callers (e.g. download_ib_documents.py) don't
    each re-read these variables their own way.
    """
    backend = os.environ.get("OBJECT_STORE_BACKEND", "file").strip().lower()
    if backend == "s3":
        return S3CompatibleObjectStore(
            bucket=os.environ.get("OBJECT_STORE_BUCKET", ""),
            endpoint_url=os.environ.get("OBJECT_STORE_ENDPOINT"),
            access_key_id=os.environ.get("OBJECT_STORE_ACCESS_KEY_ID"),
            secret_access_key=os.environ.get("OBJECT_STORE_SECRET_ACCESS_KEY"),
        )
    root = os.environ.get("OBJECT_STORE_ROOT")
    if root:
        return FileObjectStore(Path(root), bucket=os.environ.get("OBJECT_STORE_BUCKET", "local"))
    default_root = Path(__file__).resolve().parent.parent / "backend" / "data" / "object_store"
    return FileObjectStore(default_root, bucket=os.environ.get("OBJECT_STORE_BUCKET", "local"))


def document_key(source: str, checksum: str, ext: str) -> str:
    """sources/{source}/documents/{checksum[:2]}/{checksum}.{ext} -- see
    module docstring's KEY LAYOUT CONVENTIONS.
    """
    ext = ext if ext.startswith(".") else f".{ext}" if ext else ""
    return f"sources/{source}/documents/{checksum[:2]}/{checksum}{ext}"
