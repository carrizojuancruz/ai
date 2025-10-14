"""Unit tests for app.db.session module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.db import session as session_module


class TestHealthCheckConnection:
    """Tests for _health_check_connection function."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_engine, mock_config):
        """Test successful health check."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        async_cm = AsyncMock()
        async_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        async_cm.__aexit__ = AsyncMock(return_value=None)
        mock_engine.begin = Mock(return_value=async_cm)

        result = await session_module._health_check_connection(mock_engine)

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_engine, mock_config):
        """Test failed health check."""
        mock_engine.begin.side_effect = Exception("Connection failed")

        result = await session_module._health_check_connection(mock_engine)

        assert result is False


class TestReconnectEngine:
    """Tests for _reconnect_engine function."""

    @pytest.mark.asyncio
    async def test_reconnect_engine_success(self, reset_db_globals, mock_engine, mock_config, mock_create_async_engine):
        """Test successful engine reconnection."""
        new_engine = Mock()
        new_engine.dispose = AsyncMock()
        mock_create_async_engine.return_value = new_engine

        session_module._engine = mock_engine

        with (
            patch('app.db.session._health_check_connection', return_value=True),
            patch('app.db.session.async_sessionmaker')
        ):
            await session_module._reconnect_engine()

            mock_engine.dispose.assert_called_once()
            mock_create_async_engine.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_engine_health_check_fails(self, reset_db_globals, mock_engine, mock_config, mock_create_async_engine):
        """Test reconnection when health check fails."""
        new_engine = Mock()
        new_engine.dispose = AsyncMock()
        mock_create_async_engine.return_value = new_engine

        session_module._engine = mock_engine

        with (
            patch('app.db.session._health_check_connection', return_value=False),
            patch('app.db.session.async_sessionmaker')
        ):
            await session_module._reconnect_engine()

            mock_create_async_engine.assert_called_once()


    @pytest.mark.asyncio
    async def test_reconnect_engine_raises_on_error(self, reset_db_globals, mock_config, mock_create_async_engine):
        """Test reconnection raises exception on error."""
        mock_create_async_engine.side_effect = Exception("Engine creation failed")

        session_module._engine = Mock()
        session_module._engine.dispose = AsyncMock()

        with pytest.raises(Exception, match="Engine creation failed"):
            await session_module._reconnect_engine()


class TestGetEngine:
    """Tests for _get_engine and get_engine functions."""

    def test_get_engine_creates_and_caches(self, reset_db_globals, mock_config, mock_create_async_engine):
        """Test that get_engine creates a new engine and caches it."""
        mock_engine = Mock()
        mock_create_async_engine.return_value = mock_engine

        with patch('asyncio.create_task'):
            result = session_module._get_engine()
            assert result == mock_engine
            mock_create_async_engine.assert_called_once()

            result2 = session_module._get_engine()
            assert result2 == mock_engine
            mock_create_async_engine.assert_called_once()

    def test_get_engine_handles_error(self, reset_db_globals, mock_config, mock_create_async_engine):
        """Test get_engine handles creation errors."""
        mock_create_async_engine.side_effect = Exception("Creation failed")

        with pytest.raises(Exception, match="Creation failed"):
            session_module._get_engine()


class TestGetSessionFactory:
    """Tests for _get_session_factory function."""

    def test_get_session_factory_creates_and_caches(self, reset_db_globals, mock_config, mock_create_async_engine, mock_async_sessionmaker):
        """Test that session factory is created and cached."""
        mock_engine = Mock()
        mock_create_async_engine.return_value = mock_engine
        mock_factory = Mock()
        mock_async_sessionmaker.return_value = mock_factory

        with patch('asyncio.create_task'):
            result = session_module._get_session_factory()
            assert result == mock_factory
            mock_async_sessionmaker.assert_called_once()

            result2 = session_module._get_session_factory()
            assert result2 == mock_factory
            mock_async_sessionmaker.assert_called_once()


class TestCreateSessionWithRetry:
    """Tests for _create_session_with_retry function."""

    @pytest.mark.asyncio
    async def test_create_session_success_first_try(self, reset_db_globals, mock_session, mock_session_factory, mock_config, mock_create_async_engine, mock_async_sessionmaker):
        """Test successful session creation on first try."""
        mock_engine = Mock()
        mock_create_async_engine.return_value = mock_engine
        mock_async_sessionmaker.return_value = mock_session_factory

        with patch('asyncio.create_task'):
            session = await session_module._create_session_with_retry()

            assert session == mock_session
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_retry_on_operational_error(self, reset_db_globals, mock_session, mock_session_factory, mock_config, mock_create_async_engine, mock_async_sessionmaker):
        """Test session creation retries on database errors."""
        mock_engine = Mock()
        mock_create_async_engine.return_value = mock_engine
        mock_async_sessionmaker.return_value = mock_session_factory

        mock_session.execute.side_effect = [OperationalError("", "", ""), None]

        with patch('asyncio.create_task'), patch('asyncio.sleep', new_callable=AsyncMock):
            session = await session_module._create_session_with_retry()

            assert session == mock_session
            assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_create_session_fails_after_max_retries(self, reset_db_globals, mock_session, mock_session_factory, mock_config, mock_create_async_engine, mock_async_sessionmaker):
        """Test session creation fails after max retries."""
        mock_engine = Mock()
        mock_create_async_engine.return_value = mock_engine
        mock_async_sessionmaker.return_value = mock_session_factory

        mock_session.execute.side_effect = OperationalError("", "", "")

        with (
            patch('asyncio.create_task'),
            patch('asyncio.sleep', new_callable=AsyncMock),
            pytest.raises(OperationalError)
        ):
            await session_module._create_session_with_retry(max_retries=3)


class TestGetRobustSession:
    """Tests for get_robust_session context manager."""

    @pytest.mark.asyncio
    async def test_get_robust_session_success(self, reset_db_globals, mock_session, mock_session_factory, mock_config, mock_create_async_engine, mock_async_sessionmaker):
        """Test successful robust session creation and cleanup."""
        mock_engine = Mock()
        mock_create_async_engine.return_value = mock_engine
        mock_async_sessionmaker.return_value = mock_session_factory

        with patch('asyncio.create_task'):
            async with session_module.get_robust_session() as session:
                assert session == mock_session

            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_robust_session_closes_on_exception(self, reset_db_globals, mock_session, mock_session_factory, mock_config, mock_create_async_engine, mock_async_sessionmaker):
        """Test robust session closes even on exception."""
        mock_engine = Mock()
        mock_create_async_engine.return_value = mock_engine
        mock_async_sessionmaker.return_value = mock_session_factory

        with patch('asyncio.create_task'):
            with pytest.raises(ValueError):
                async with session_module.get_robust_session():
                    raise ValueError("Test error")

            mock_session.close.assert_called_once()


class TestGetAsyncSession:
    """Tests for get_async_session function."""

    @pytest.mark.asyncio
    async def test_get_async_session_yields_session(self, reset_db_globals, mock_session, mock_session_factory, mock_config, mock_create_async_engine, mock_async_sessionmaker):
        """Test get_async_session yields session."""
        mock_engine = Mock()
        mock_create_async_engine.return_value = mock_engine
        mock_async_sessionmaker.return_value = mock_session_factory
        mock_session.close = AsyncMock()

        with patch('asyncio.create_task'):
            gen = session_module.get_async_session()
            session = await anext(gen)
            assert session is mock_session
            await gen.aclose()


class TestDisposeEngine:
    """Tests for dispose_engine function."""

    @pytest.mark.asyncio
    async def test_dispose_engine_cleanup(self, reset_db_globals, mock_engine):
        """Test dispose_engine cleans up resources."""
        mock_engine.dispose = AsyncMock()
        session_module._engine = mock_engine

        await session_module.dispose_engine()

        assert session_module._engine is None


class TestGetConnectionStats:
    """Tests for get_connection_stats function."""

    def test_get_connection_stats_returns_pool_info(self, reset_db_globals, mock_engine):
        """Test connection stats returns pool information."""
        session_module._engine = mock_engine

        stats = session_module.get_connection_stats()

        assert stats is not None
        assert 'pool_size' in stats
        assert 'checked_in' in stats
