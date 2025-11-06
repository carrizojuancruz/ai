import pytest

from app.core.config import config
from app.services.stt.base import STTServiceError
from app.services.stt.factory import (
    get_stt_service,
    reset_stt_service,
)


class TestSTTFactory:
    def setup_method(self):
        reset_stt_service()

    def teardown_method(self):
        reset_stt_service()

    def test_stt_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr(config, "AUDIO_ENABLED", False, raising=False)
        svc = get_stt_service()
        assert svc is None

    def test_openai_provider_initializes(self, monkeypatch):
        monkeypatch.setattr(config, "AUDIO_ENABLED", True, raising=False)
        monkeypatch.setattr(config, "STT_PROVIDER", "openai", raising=False)
        monkeypatch.setattr(config, "STT_MODEL", "whisper-1", raising=False)
        monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test", raising=False)
        svc = get_stt_service()
        assert svc is not None
        assert svc.get_provider_name() == "openai"

    def test_unsupported_provider_raises(self, monkeypatch):
        monkeypatch.setattr(config, "AUDIO_ENABLED", True, raising=False)
        monkeypatch.setattr(config, "STT_PROVIDER", "unknown", raising=False)
        with pytest.raises(STTServiceError):
            _ = get_stt_service()
