"""Tests for STT routes."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestSTTRoutes:
    def _make_mock_service(self):
        svc = MagicMock()
        svc.get_provider_name.return_value = "openai"
        svc.get_config.return_value = {
            "provider": "openai",
            "model": "whisper-1",
            "language": "en",
            "sample_rate": 16000,
        }
        svc.transcribe = AsyncMock(return_value={
            "text": "hello world",
            "provider": "openai",
            "model": "whisper-1",
        })
        svc.get_model_info = AsyncMock(return_value={"model": "whisper-1", "provider": "openai"})
        return svc

    def test_transcribe_disabled(self, client: TestClient):
        with patch("app.api.routes_stt.is_stt_available", return_value=False):
            files = {"file": ("a.wav", b"123", "audio/wav")}
            resp = client.post("/stt/transcribe", files=files)
        assert resp.status_code == 503
        data = resp.json()
        assert "STT service not available" in data["detail"]

    def test_transcribe_openai_success(self, client: TestClient):
        mock_service = self._make_mock_service()
        with patch("app.api.routes_stt.is_stt_available", return_value=True), \
             patch("app.api.routes_stt.get_stt_service", return_value=mock_service):
            files = {"file": ("a.wav", b"123", "audio/wav")}
            resp = client.post("/stt/transcribe", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "hello world"
        assert data["provider"] == "openai"

    def test_transcribe_internal_error(self, client: TestClient):
        mock_service = self._make_mock_service()
        mock_service.transcribe = AsyncMock(side_effect=Exception("boom"))
        with patch("app.api.routes_stt.is_stt_available", return_value=True), \
             patch("app.api.routes_stt.get_stt_service", return_value=mock_service):
            files = {"file": ("a.wav", b"123", "audio/wav")}
            resp = client.post("/stt/transcribe", files=files)
        assert resp.status_code == 500
        data = resp.json()
        assert "STT transcription failed" in data["detail"]
