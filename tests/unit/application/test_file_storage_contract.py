import pytest

from app.application.errors import DependencyUnavailable
from tests.unit.application.fakes import FakeFileStorage


async def test_bytes_and_content_type_are_stored_by_distinct_opaque_keys():
    storage = FakeFileStorage()
    await storage.upload("opaque-one", b"first", "text/plain")
    await storage.upload("opaque-two", b"second", "application/octet-stream")
    assert storage.objects == {
        "opaque-one": (b"first", "text/plain"),
        "opaque-two": (b"second", "application/octet-stream"),
    }
    assert storage.calls == [("upload", "opaque-one"), ("upload", "opaque-two")]


async def test_delete_is_idempotent_and_records_attempts():
    storage = FakeFileStorage()
    await storage.upload("key", b"", "text/plain")
    await storage.delete("key")
    await storage.delete("key")
    assert storage.objects == {}
    assert storage.calls == [("upload", "key"), ("delete", "key"), ("delete", "key")]


async def test_failed_upload_creates_no_object():
    storage = FakeFileStorage(fail_upload=True)
    with pytest.raises(DependencyUnavailable):
        await storage.upload("key", b"private bytes", "text/plain")
    assert storage.objects == {}
    assert storage.calls == [("upload", "key")]


async def test_failed_delete_preserves_object():
    storage = FakeFileStorage()
    await storage.upload("key", b"private bytes", "text/plain")
    storage.fail_delete = True
    with pytest.raises(DependencyUnavailable):
        await storage.delete("key")
    assert storage.objects == {"key": (b"private bytes", "text/plain")}
    assert storage.calls[-1] == ("delete", "key")
    assert "private bytes" not in repr(storage)
