from __future__ import annotations

import hashlib

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from tests import factories as f
from tests.conftest import register_and_login

pytestmark = pytest.mark.integration

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    name: str,
    data: bytes,
    title: str | None = None,
) -> httpx.Response:
    form = {"title": title} if title else None
    return await client.post(
        "/api/v1/documents", headers=headers, files={"file": (name, data)}, data=form
    )


async def test_upload_list_get_download_byte_identical(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    for name, data in [
        ("Report.docx", f.ooxml_bytes("docx")),
        ("Deck.pptx", f.ooxml_bytes("pptx")),
        ("Paper.pdf", f.pdf_bytes()),
    ]:
        r = await upload(client, headers, name, data)
        assert r.status_code == 201, r.text
        doc = r.json()
        assert doc["kind"] == name.rsplit(".", 1)[1].lower()
        assert doc["status"] == "ready" and doc["origin"] == "uploaded"
        v = doc["current_version"]
        assert v["number"] == 1 and v["created_by"] == "upload"
        assert v["sha256"] == hashlib.sha256(data).hexdigest()
        assert v["summary"]["analysis"] == "not_available"  # honest: parsing is Phase 2

        dl = await client.get(f"/api/v1/versions/{v['id']}/file", headers=headers)
        assert dl.status_code == 200
        assert dl.content == data  # byte-identical original
        assert dl.headers["x-content-sha256"] == v["sha256"]
        assert "attachment" in dl.headers["content-disposition"]
        assert dl.headers["x-content-type-options"] == "nosniff"

    r = await client.get("/api/v1/documents", headers=headers)
    assert [d["title"] for d in r.json()["items"]] == ["Paper", "Deck", "Report"]

    stats = (await client.get("/api/v1/documents/stats", headers=headers)).json()
    assert stats["documents"] == 3 and stats["versions"] == 3
    assert stats["by_kind"] == {"docx": 1, "pptx": 1, "pdf": 1}
    assert stats["stored_bytes"] > 0


async def test_custom_title_and_rename(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    doc = (await upload(client, headers, "a.docx", f.ooxml_bytes(), title="Thesis draft")).json()
    assert doc["title"] == "Thesis draft"
    r = await client.patch(
        f"/api/v1/documents/{doc['id']}", headers=headers, json={"title": "Final"}
    )
    assert r.status_code == 200 and r.json()["title"] == "Final"


async def test_filename_path_components_stripped(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    r = await upload(client, headers, "../../etc/evil.docx", f.ooxml_bytes())
    assert r.status_code == 201
    assert r.json()["original_filename"] == "evil.docx"


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("m.docx", f.ooxml_bytes(main_type=f.WORD_MACRO_MAIN), 415, "MACRO_ENABLED"),
        ("m.docm", f.ooxml_bytes(), 415, "MACRO_ENABLED"),
        ("fake.pdf", f.ooxml_bytes(), 415, "EXTENSION_MISMATCH"),
        ("x.txt", b"hello", 415, "UNSUPPORTED_EXTENSION"),
        ("enc.pdf", f.pdf_bytes(encrypted=True), 415, "ENCRYPTED_PDF"),
        ("t.docx", f.ooxml_bytes(extra_parts={"../x": b"1"}), 415, "UNSAFE_PATH"),
    ],
)
async def test_malicious_or_invalid_uploads_rejected(
    client: httpx.AsyncClient, name: str, data: bytes, status: int, code: str
) -> None:
    headers = await register_and_login(client)
    r = await upload(client, headers, name, data)
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    assert (await client.get("/api/v1/documents", headers=headers)).json()["items"] == []


async def test_oversized_upload_rejected(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    r = await upload(client, headers, "big.pdf", f.pdf_bytes() + b"0" * (6 * 1024 * 1024))
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_pdf_active_content_is_flagged(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    r = await upload(client, headers, "js.pdf", f.pdf_bytes(javascript=True))
    assert r.status_code == 201
    assert "pdf_active_content:javascript" in r.json()["safety_warnings"]


async def test_user_isolation_returns_404(client: httpx.AsyncClient) -> None:
    alice = await register_and_login(client, "alice@example.com", "Alice-secret-1")
    doc = (await upload(client, alice, "a.docx", f.ooxml_bytes())).json()
    vid = doc["current_version"]["id"]

    bob = await register_and_login(client, "bob@example.com", "Bob-secret-22")
    for method, path in [
        ("GET", f"/api/v1/documents/{doc['id']}"),
        ("GET", f"/api/v1/documents/{doc['id']}/versions"),
        ("GET", f"/api/v1/versions/{vid}/file"),
        ("DELETE", f"/api/v1/documents/{doc['id']}"),
    ]:
        r = await client.request(method, path, headers=bob)
        assert r.status_code == 404, (method, path)
    r = await client.patch(f"/api/v1/documents/{doc['id']}", headers=bob, json={"title": "pwned"})
    assert r.status_code == 404
    assert (await client.get("/api/v1/documents", headers=bob)).json()["items"] == []
    assert (await client.get(f"/api/v1/documents/{doc['id']}", headers=alice)).json()[
        "title"
    ] == "a"


async def test_soft_delete_hides_but_keeps_original(client: httpx.AsyncClient, settings) -> None:
    headers = await register_and_login(client)
    data = f.ooxml_bytes()
    doc = (await upload(client, headers, "a.docx", data)).json()
    r = await client.delete(f"/api/v1/documents/{doc['id']}", headers=headers)
    assert r.status_code == 204
    assert (await client.get(f"/api/v1/documents/{doc['id']}", headers=headers)).status_code == 404
    sha = doc["current_version"]["sha256"]
    blob = settings.storage_root / "sha256" / sha[:2] / sha[2:4] / sha
    assert blob.read_bytes() == data  # original never destroyed


async def test_identical_uploads_share_one_blob(client: httpx.AsyncClient, settings) -> None:
    headers = await register_and_login(client)
    data = f.pdf_bytes()
    a = (await upload(client, headers, "a.pdf", data)).json()
    b = (await upload(client, headers, "b.pdf", data)).json()
    assert a["id"] != b["id"]
    assert a["current_version"]["sha256"] == b["current_version"]["sha256"]
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        assert (await conn.execute(text("select count(*) from blobs"))).scalar_one() == 1
    await engine.dispose()


async def test_database_refuses_to_alter_originals(client: httpx.AsyncClient, settings) -> None:
    headers = await register_and_login(client)
    await upload(client, headers, "a.pdf", f.pdf_bytes())
    engine = create_async_engine(settings.database_url)
    for stmt in (
        "update blobs set size_bytes = 1",
        "delete from blobs",
        "update document_versions set source_blob = repeat('0', 64)",
    ):
        async with engine.connect() as conn:
            with pytest.raises(DBAPIError, match="immutable record"):
                await conn.execute(text(stmt))
    await engine.dispose()


async def test_pagination_and_search(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    for i in range(5):
        await upload(client, headers, f"doc{i}.pdf", f.pdf_bytes() + bytes([i]))
    await upload(client, headers, "100%_done.pdf", f.pdf_bytes() + b"x")
    page1 = (await client.get("/api/v1/documents?limit=4", headers=headers)).json()
    assert len(page1["items"]) == 4 and page1["next_cursor"]
    page2 = (
        await client.get(
            f"/api/v1/documents?limit=4&cursor={page1['next_cursor']}", headers=headers
        )
    ).json()
    assert len(page2["items"]) == 2 and page2["next_cursor"] is None
    ids = {d["id"] for d in page1["items"] + page2["items"]}
    assert len(ids) == 6
    hits = (await client.get("/api/v1/documents?q=100%25_", headers=headers)).json()["items"]
    assert [d["title"] for d in hits] == ["100%_done"]  # % and _ are literal, not wildcards
    assert (
        len((await client.get("/api/v1/documents?kind=docx", headers=headers)).json()["items"]) == 0
    )


async def test_audit_trail_records_actions(client: httpx.AsyncClient, settings) -> None:
    headers = await register_and_login(client)
    doc = (await upload(client, headers, "a.pdf", f.pdf_bytes())).json()
    await client.get(f"/api/v1/versions/{doc['current_version']['id']}/file", headers=headers)
    await upload(client, headers, "bad.docm", b"x")
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        actions = (
            (await conn.execute(text("select action from audit_events order by id")))
            .scalars()
            .all()
        )
    await engine.dispose()
    assert actions == [
        "auth.register",
        "auth.login",
        "document.uploaded",
        "document.downloaded",
        "document.upload_rejected",
    ]
