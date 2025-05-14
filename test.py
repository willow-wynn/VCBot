# test_all.py
import pytest
import types
import sys
import os

from unittest.mock import MagicMock, AsyncMock, patch

import geminitools

# --- fixtures and setup ---
@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    # disable requests.get by default
    monkeypatch.setattr(geminitools.requests, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network disabled")))

@pytest.fixture
def fake_files(tmp_path, monkeypatch):
    files = {}
    for name in ["rules", "constitution"]:
        p = tmp_path / f"{name}.txt"
        p.write_text(f"{name} content")
        files[name] = str(p)
    monkeypatch.setattr("geminitools.KNOWLEDGE_FILES", files, raising=False)
    return files

@pytest.fixture
def fake_bill_storage(tmp_path, monkeypatch):
    # set up fake BILL_TXT_STORAGE
    bill_dir = tmp_path / "bills"
    bill_dir.mkdir()
    (bill_dir / "A.txt").write_text("this bill mentions FOOBAR", encoding="utf-8")
    (bill_dir / "B.txt").write_text("nothing here", encoding="utf-8")
    monkeypatch.setattr("geminitools.BILL_TXT_STORAGE", str(bill_dir), raising=False)
    return str(bill_dir)

# --- call_knowledge ---
def test_call_knowledge_happy(fake_files):
    out = geminitools.call_knowledge("rules")
    assert out == "rules content"

def test_call_knowledge_missing(fake_files):
    with pytest.raises(KeyError):
        geminitools.call_knowledge("nope")

# --- sanitize / sanitize_filename ---
@pytest.mark.parametrize("raw,expected", [
    ("@everyone", "@ everyone"),
    ("@here", "@ here"),
    ("<@&12345>", "< @&12345>"),
])
def test_sanitize(raw, expected):
    assert geminitools.sanitize(raw) == expected

@pytest.mark.parametrize("name,expected", [
    ("bad*file?.txt", "badfile.txt"),
    (" clean ", "clean")
])
def test_sanitize_filename(name, expected):
    assert geminitools.sanitize_filename(name) == expected

# --- fetch_public_gdoc_text ---
def test_fetch_public_gdoc_text_ok(monkeypatch):
    class DummyResp:
        status_code = 200
        text = "abc"
    monkeypatch.setattr(geminitools.requests, "get", lambda url: DummyResp())
    out = geminitools.fetch_public_gdoc_text("https://docs.google.com/document/d/abcdefg/view")
    assert out == "abc"

def test_fetch_public_gdoc_text_invalid_url():
    with pytest.raises(ValueError):
        geminitools.fetch_public_gdoc_text("https://notdocs.google.com/nope")

def test_fetch_public_gdoc_text_fail(monkeypatch):
    class DummyResp:
        status_code = 404
        text = ""
    monkeypatch.setattr(geminitools.requests, "get", lambda url: DummyResp())
    with pytest.raises(RuntimeError):
        geminitools.fetch_public_gdoc_text("https://docs.google.com/document/d/fakeid/view")

# --- bill_keyword_search ---
def test_bill_keyword_search_basic(fake_bill_storage):
    df = geminitools.bill_keyword_search("FOOBAR")
    assert not df.empty
    assert "A.txt" in df["filename"].values
    assert "B.txt" not in df["filename"].values

def test_bill_keyword_search_none(fake_bill_storage):
    df = geminitools.bill_keyword_search("nonexistentword")
    assert df.empty

# --- call_bill_search (big one, mock model and vector search) ---
def test_call_bill_search_empty_query(monkeypatch):
    out = geminitools.call_bill_search("", 5, False)
    assert isinstance(out, dict) and "error" in out

def test_call_bill_search_no_model(monkeypatch):
    monkeypatch.setattr(geminitools, "load_search_model", lambda *_: (_ for _ in ()).throw(FileNotFoundError("fail")))
    out = geminitools.call_bill_search("test", 3, False)
    assert "error" in out

def test_call_bill_search_vector_search(monkeypatch):
    monkeypatch.setattr(geminitools, "load_search_model", lambda *_: "dummy_model")
    monkeypatch.setattr(geminitools, "search_vectors_simple", lambda q, m, v, k=5: [{"text": "lorem", "metadata": {"source": "file1", "chunk_index_doc": 0}, "score": 0.9}])
    out = geminitools.call_bill_search("lorem", 5, True)
    assert isinstance(out, list)
    assert out[0]["source_bill"] == "file1"

# --- call_other_channel_context (async) ---
@pytest.mark.asyncio
async def test_call_other_channel_context(monkeypatch):
    # mock the Discord utils + channel history
    fake_msg = types.SimpleNamespace(content="foo")
    fake_channel = MagicMock()
    async def history(limit):
        yield fake_msg
    fake_channel.history = history
    fake_guild = types.SimpleNamespace(text_channels=[types.SimpleNamespace(name="bar"), fake_channel])
    class DummyClient: 
        def get_guild(self, gid): return fake_guild
    monkeypatch.setattr(geminitools, "client", DummyClient(), raising=False)
    monkeypatch.setattr(geminitools, "GUILD_ID", 1, raising=False)
    monkeypatch.setattr(geminitools.discord.utils, "get", lambda l, name: fake_channel)
    out = await geminitools.call_other_channel_context("whatever", 1)
    assert out and out[0].content == "foo"

# --- reconstruct_bills_from_chunks corner case ---
def test_call_bill_search_missing_metadata(monkeypatch):
    monkeypatch.setattr(geminitools, "load_search_model", lambda *_: "model")
    monkeypatch.setattr(geminitools, "search_vectors_simple", lambda *_, **__: [
        {"text": "txt1", "metadata": {}},  # missing source
        {"text": "txt2"}                    # missing metadata entirely
    ])
    out = geminitools.call_bill_search("anything", 2, True)
    assert isinstance(out, list) and len(out) == 0  # should skip all

# --- you would continue for other functions; just stub/mimic dependencies as above ---

# note: main.py-specific functions would be done in the same style, patching out actual Discord, Google, filesystem, etc.
# async def test_add_bill_to_db(monkeypatch, tmp_path): ... etc
if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__]))