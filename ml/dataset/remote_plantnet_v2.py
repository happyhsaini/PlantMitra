"""Fetch selected Pl@ntNet-300K-v2 image members via HTTP byte ranges."""

from __future__ import annotations

import io
import re
import urllib.request
import zipfile
from http.client import IncompleteRead

from PIL import Image

from .metadata import PlantImageRecord, load_records


class RangeRequestError(IOError):
    """The archive server did not honor a bounded HTTP Range request."""


class HttpRangeReader:
    """Seekable read-only file-like object backed exclusively by HTTP Range requests."""

    def __init__(self, url: str, timeout: float = 90, chunk_size: int = 8 * 1024 * 1024):
        self.url, self.timeout, self.chunk_size = url, timeout, chunk_size
        self.position = 0
        self.closed = False
        self.bytes_received = 0
        self.range_requests = 0
        self.size = self._discover_size()

    def _request_range(self, start: int, end: int) -> bytes:
        parts = bytearray()
        cursor = start
        attempts = 0
        while cursor <= end:
            request = urllib.request.Request(
                self.url,
                headers={"Range": f"bytes={cursor}-{end}", "Accept-Encoding": "identity",
                         "User-Agent": "PlantMitra-remote-dataset/1.0"},
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status != 206:
                    raise RangeRequestError(
                        f"Server ignored Range request (HTTP {response.status}); refusing full download"
                    )
                content_range = response.headers.get("Content-Range", "")
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", content_range)
                if not match or int(match.group(1)) != cursor or int(match.group(2)) > end:
                    raise RangeRequestError(f"Unexpected Content-Range: {content_range!r}")
                expected = int(match.group(2)) - cursor + 1
                try:
                    body = response.read()
                except IncompleteRead as error:
                    body = error.partial
                if not body:
                    attempts += 1
                    if attempts >= 5:
                        raise RangeRequestError(f"Repeated empty response at byte {cursor}")
                    continue
                parts.extend(body)
                cursor += len(body)
                attempts = attempts + 1 if len(body) < expected else 0
                if attempts >= 5:
                    raise RangeRequestError(f"Repeated incomplete range response at byte {cursor}")
        self.bytes_received += len(parts)
        self.range_requests += 1
        return bytes(parts)

    def _discover_size(self) -> int:
        request = urllib.request.Request(
            self.url, headers={"Range": "bytes=0-0", "Accept-Encoding": "identity",
                              "User-Agent": "PlantMitra-remote-dataset/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            content_range = response.headers.get("Content-Range", "")
            match = re.fullmatch(r"bytes 0-0/(\d+)", content_range)
            if response.status != 206 or not match:
                raise RangeRequestError("Remote server must support HTTP Range; refusing to download the archive")
            if len(response.read(2)) != 1:
                raise RangeRequestError("Invalid response to one-byte range probe")
            self.bytes_received = 1
            self.range_requests = 1
            return int(match.group(1))

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self.position + offset
        elif whence == io.SEEK_END:
            position = self.size + offset
        else:
            raise ValueError(f"Invalid whence value: {whence}")
        if position < 0:
            raise ValueError("negative seek position")
        self.position = position
        return position

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("I/O operation on closed range reader")
        if size is None or size < 0:
            size = self.size - self.position
        size = min(size, max(0, self.size - self.position))
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            count = min(remaining, self.chunk_size)
            start = self.position
            chunk = self._request_range(start, start + count - 1)
            chunks.append(chunk)
            self.position += len(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def close(self) -> None:
        self.closed = True


class RemotePlantNetV2:
    """Metadata-aware ZIP reader; only requested image members enter process memory."""

    def __init__(self, archive_url: str = "https://zenodo.org/records/10419064/files/images.zip",
                 allowed_licenses: tuple[str, ...] = ("cc-by-sa",), timeout: float = 90):
        self.archive_url = archive_url
        self.allowed_licenses = allowed_licenses
        self.timeout = timeout
        self.range_reader: HttpRangeReader | None = None
        self.archive: zipfile.ZipFile | None = None

    def load_metadata(self, scientific_names=None):
        return load_records(scientific_names, self.allowed_licenses)

    def open(self) -> "RemotePlantNetV2":
        if self.archive is None:
            self.range_reader = HttpRangeReader(self.archive_url, timeout=self.timeout)
            self.archive = zipfile.ZipFile(self.range_reader, mode="r")
        return self

    def fetch_bytes(self, record: PlantImageRecord) -> bytes:
        self.open()
        assert self.archive is not None
        return self.archive.read(record.zip_path)

    def fetch_image(self, record: PlantImageRecord) -> Image.Image:
        """Decode a selected image from memory as RGB; never writes the image to disk."""
        image_bytes = self.fetch_bytes(record)
        with Image.open(io.BytesIO(image_bytes)) as source:
            source.load()
            return source.convert("RGB")

    @property
    def bytes_received(self) -> int:
        return self.range_reader.bytes_received if self.range_reader else 0

    @property
    def range_requests(self) -> int:
        return self.range_reader.range_requests if self.range_reader else 0

    def close(self) -> None:
        if self.archive:
            self.archive.close()
            self.archive = None
        if self.range_reader:
            self.range_reader.close()
            self.range_reader = None

    def __enter__(self) -> "RemotePlantNetV2":
        return self.open()

    def __exit__(self, *_exc) -> None:
        self.close()
