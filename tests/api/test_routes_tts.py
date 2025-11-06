"""Tests for TTS routes."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestTTSRoutes:
    """Test suite for TTS API routes."""

    def _make_mock_service(self):
        svc = MagicMock()
        # Properties / sync methods
        svc.get_provider_name.return_value = "openai"
        svc.get_available_voices.return_value = ["alloy", "ash"]
        svc.voice_id = "alloy"
        svc.get_config.return_value = {
            "provider": "openai",
            "voice_id": "alloy",
            "output_format": "mp3",
        }
        # Async methods
        svc.get_voice_info = AsyncMock(return_value={
            "provider": "openai",
            "voice_id": "alloy",
            "output_format": "mp3",
            "supported_formats": ["mp3"],
            "max_text_length": 4096,
            "supported_voices": ["alloy", "ash"],
        })
        svc.synthesize_speech = AsyncMock(return_value=b"abc")
        svc.test_connection = AsyncMock(return_value=True)
        return svc

    # /tts/health
    def test_tts_health_available(self, client: TestClient):
        mock_service = self._make_mock_service()
        with patch("app.api.routes_tts.is_tts_available", return_value=True), \
             patch("app.api.routes_tts.get_tts_service", return_value=mock_service), \
             patch("app.api.routes_tts.test_tts_service", new=AsyncMock(return_value=True)):
            resp = client.get("/tts/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["provider"] == "openai"
        assert isinstance(data.get("voice_info"), dict)

    def test_tts_health_unavailable(self, client: TestClient):
        with patch("app.api.routes_tts.is_tts_available", return_value=False):
            resp = client.get("/tts/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "error" in data

    # /tts/test
    def test_tts_test_synthesis_success(self, client: TestClient):
        mock_service = self._make_mock_service()
        mock_service.synthesize_speech = AsyncMock(return_value=b"audio_bytes")
        with patch("app.api.routes_tts.is_tts_available", return_value=True), \
             patch("app.api.routes_tts.get_tts_service", return_value=mock_service):
            resp = client.post("/tts/test", json={"text": "Hello world"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "TTS synthesis successful"
        # Validate base64 encoding of audio
        assert data["audio_data"] == base64.b64encode(b"audio_bytes").decode()
        assert data["size_bytes"] == len(b"audio_bytes")
        assert isinstance(data.get("voice_info"), dict)

    def test_tts_test_empty_text(self, client: TestClient):
        mock_service = self._make_mock_service()
        with patch("app.api.routes_tts.is_tts_available", return_value=True), \
             patch("app.api.routes_tts.get_tts_service", return_value=mock_service):
            resp = client.post("/tts/test", json={"text": "   "})
        assert resp.status_code == 400
        data = resp.json()
        assert "Text cannot be empty" in data["detail"]

    def test_tts_test_unavailable_service(self, client: TestClient):
        with patch("app.api.routes_tts.is_tts_available", return_value=False):
            resp = client.post("/tts/test", json={"text": "Hello"})
        assert resp.status_code == 503
        data = resp.json()
        assert "TTS service not available" in data["detail"]

    def test_tts_test_internal_error(self, client: TestClient):
        mock_service = self._make_mock_service()
        mock_service.synthesize_speech = AsyncMock(side_effect=Exception("boom"))
        with patch("app.api.routes_tts.is_tts_available", return_value=True), \
             patch("app.api.routes_tts.get_tts_service", return_value=mock_service):
            resp = client.post("/tts/test", json={"text": "Hello"})
        assert resp.status_code == 500
        data = resp.json()
        assert "TTS synthesis failed" in data["detail"]

    # /tts/voices
    def test_tts_voices_success(self, client: TestClient):
        mock_service = self._make_mock_service()
        with patch("app.api.routes_tts.is_tts_available", return_value=True), \
             patch("app.api.routes_tts.get_tts_service", return_value=mock_service):
            resp = client.get("/tts/voices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "openai"
        assert data["current_voice"] == "alloy"
        assert data["available_voices"] == ["alloy", "ash"]
        assert isinstance(data.get("voice_info"), dict)

    def test_tts_voices_unavailable(self, client: TestClient):
        with patch("app.api.routes_tts.is_tts_available", return_value=False):
            resp = client.get("/tts/voices")
        assert resp.status_code == 503
        data = resp.json()
        assert "TTS service not available" in data["detail"]

    # /tts/config
    def test_tts_config_success(self, client: TestClient):
        mock_service = self._make_mock_service()
        with patch("app.api.routes_tts.is_tts_available", return_value=True), \
             patch("app.api.routes_tts.get_tts_service", return_value=mock_service):
            resp = client.get("/tts/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data == mock_service.get_config.return_value

    def test_tts_config_unavailable(self, client: TestClient):
        with patch("app.api.routes_tts.is_tts_available", return_value=False):
            resp = client.get("/tts/config")
        assert resp.status_code == 500
        data = resp.json()
        assert "TTS service not available" in data["detail"]
