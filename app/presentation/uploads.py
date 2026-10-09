"""Bound multipart parsing before spooling, then close every upload handle."""

from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from python_multipart.multipart import parse_options_header
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.domain.errors import FileTooLarge
from app.domain.validation import MAX_FILE_SIZE, validate_filename

CHUNK_SIZE = 64 * 1024
MAX_HEADER_BYTES = 16 * 1024
MAX_REQUEST_BYTES = MAX_FILE_SIZE + 64 * 1024


def invalid_upload() -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "loc": ("body", "file"),
                "msg": "One valid multipart file is required",
                "type": "value_error",
            }
        ]
    )


async def bounded_stream(request: Request) -> AsyncIterator[bytes]:
    received = 0
    async for chunk in request.stream():
        for start in range(0, len(chunk), CHUNK_SIZE):
            piece = chunk[start : start + CHUNK_SIZE]
            received += len(piece)
            if received > MAX_REQUEST_BYTES:
                raise FileTooLarge()
            yield piece


class BoundedMultipartParser(MultiPartParser):
    """The framework's max_part_size alone does not limit file parts."""

    def __init__(self, request: Request):
        super().__init__(
            request.headers,
            bounded_stream(request),
            max_files=1,
            max_fields=0,
            max_part_size=0,
        )
        self._file_bytes = 0
        self._header_bytes = 0
        self.complete = False

    def _count_header(self, start: int, end: int) -> None:
        self._header_bytes += end - start
        if self._header_bytes > MAX_HEADER_BYTES:
            raise MultiPartException("Multipart headers too large")

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self._count_header(start, end)
        super().on_header_field(data, start, end)

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._count_header(start, end)
        super().on_header_value(data, start, end)

    def on_headers_finished(self) -> None:
        super().on_headers_finished()
        if self._current_part.field_name != "file" or self._current_part.file is None:
            raise MultiPartException("One file field required")
        validate_filename(self._current_part.file.filename)

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            self._file_bytes += end - start
            if self._file_bytes > MAX_FILE_SIZE:
                raise FileTooLarge()
        super().on_part_data(data, start, end)

    def on_end(self) -> None:
        self.complete = True
        super().on_end()


async def read_upload(request: Request) -> tuple[str, bytes, str | None]:
    content_type, options = parse_options_header(request.headers.get("content-type"))
    if content_type != b"multipart/form-data":
        raise invalid_upload()
    boundary = options.get(b"boundary")
    if not boundary or len(boundary) > 200:
        raise invalid_upload()
    parser = BoundedMultipartParser(request)
    form = None
    try:
        form = await parser.parse()
        if not parser.complete or len(form.multi_items()) != 1:
            raise invalid_upload()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise invalid_upload()
        content = bytearray()
        while chunk := await upload.read(CHUNK_SIZE):
            if len(content) + len(chunk) > MAX_FILE_SIZE:
                raise FileTooLarge()
            content.extend(chunk)
        return upload.filename, bytes(content), upload.content_type
    except MultiPartException:
        raise invalid_upload() from None
    finally:
        if form is not None:
            await form.close()
        # Include incomplete parts not present in FormData. The locked parser
        # already closes these on exceptions; duplicate close is harmless.
        for handle in parser._files_to_close_on_error:
            handle.close()
