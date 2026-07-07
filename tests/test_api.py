from pathlib import Path

from fastapi.testclient import TestClient

from biome_rag.api import create_app


def test_api_endpoints_return_expected_shapes(tmp_path: Path):
    app = create_app(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed", storage_dir=tmp_path / "index")
    client = TestClient(app)

    (tmp_path / "raw").mkdir(parents=True, exist_ok=True)
    (tmp_path / "raw" / "sample.md").write_text("# Setup\n\nUse the API token.\n", encoding="utf-8")

    ingest_response = client.post(
        "/v1/ingest",
        json={"documents": [{"text": "Use the API token.", "source": "sample.md"}]},
    )
    assert ingest_response.status_code == 200

    ask_response = client.post("/v1/ask", json={"question": "What should I use?"})
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert "answer" in body
    assert "citations" in body
    assert "confidence" in body

    documents_response = client.get("/v1/documents")
    assert documents_response.status_code == 200
