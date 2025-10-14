"""Tests for FinanceRepository."""

from unittest.mock import MagicMock, patch

import pytest

from app.repositories.postgres.finance_repository import FinanceRepository, FinanceTables


class TestFinanceTables:
    """Test FinanceTables constants."""

    def test_finance_tables_constants(self):
        """Test that FinanceTables has correct table names."""
        assert FinanceTables.ACCOUNTS == "public.unified_accounts"
        assert FinanceTables.TRANSACTIONS == "public.unified_transactions"
        assert FinanceTables.ASSETS == "public.unified_assets"
        assert FinanceTables.LIABILITIES == "public.unified_liabilities"


class TestFinanceRepositoryInitialization:
    """Test FinanceRepository initialization."""

    def test_repository_initialization(self, mock_session):
        """Test that repository can be initialized with a session."""
        repo = FinanceRepository(mock_session)

        assert repo.session is mock_session
        assert isinstance(repo, FinanceRepository)


class TestUserHasAnyAccounts:
    """Test user_has_any_accounts method."""

    @pytest.mark.asyncio
    async def test_user_has_accounts_returns_true(self, mock_session, sample_user_id):
        """Test that user_has_any_accounts returns True when accounts exist."""
        mock_result = MagicMock()
        mock_result.first.return_value = (1,)
        mock_session.execute.return_value = mock_result

        repo = FinanceRepository(mock_session)
        result = await repo.user_has_any_accounts(sample_user_id)

        assert result is True
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert call_args[0][1] == {"user_id": str(sample_user_id)}

    @pytest.mark.asyncio
    async def test_user_has_no_accounts_returns_false(self, mock_session, sample_user_id):
        """Test that user_has_any_accounts returns False when no accounts exist."""
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result

        repo = FinanceRepository(mock_session)
        result = await repo.user_has_any_accounts(sample_user_id)

        assert result is False
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_has_accounts_handles_exception(self, mock_session, sample_user_id):
        """Test that user_has_any_accounts returns False on exception."""
        mock_session.execute.side_effect = Exception("Database error")

        with patch('app.repositories.postgres.finance_repository.logger') as mock_logger:
            repo = FinanceRepository(mock_session)
            result = await repo.user_has_any_accounts(sample_user_id)

            assert result is False
            mock_session.rollback.assert_called_once()
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert str(sample_user_id) in error_call

    @pytest.mark.asyncio
    async def test_user_has_accounts_converts_uuid_to_string(self, mock_session, sample_user_id):
        """Test that user_has_any_accounts converts UUID to string for query."""
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result

        repo = FinanceRepository(mock_session)
        await repo.user_has_any_accounts(sample_user_id)

        call_args = mock_session.execute.call_args
        assert call_args[0][1] == {"user_id": str(sample_user_id)}


class TestExecuteQuery:
    """Test execute_query method."""

    @pytest.mark.asyncio
    async def test_execute_query_returns_results(self, mock_session):
        """Test that execute_query returns formatted results."""
        # Mock database rows
        mock_row1 = MagicMock()
        mock_row1._mapping = {"id": 1, "name": "Account 1", "balance": 1000.00}
        mock_row2 = MagicMock()
        mock_row2._mapping = {"id": 2, "name": "Account 2", "balance": 2000.00}

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row1, mock_row2]
        mock_session.execute.return_value = mock_result

        repo = FinanceRepository(mock_session)
        result = await repo.execute_query(
            "SELECT * FROM accounts WHERE user_id = :user_id",
            user_id="test-user-123"
        )

        assert len(result) == 2
        assert result[0] == {"id": 1, "name": "Account 1", "balance": 1000.00}
        assert result[1] == {"id": 2, "name": "Account 2", "balance": 2000.00}

    @pytest.mark.asyncio
    async def test_execute_query_returns_empty_list_for_no_results(self, mock_session):
        """Test that execute_query returns empty list when no rows found."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = FinanceRepository(mock_session)
        result = await repo.execute_query("SELECT * FROM accounts WHERE id = -1")

        assert result == []

    @pytest.mark.asyncio
    async def test_execute_query_sets_transaction_read_only(self, mock_session):
        """Test that execute_query sets transaction to READ ONLY."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = FinanceRepository(mock_session)
        await repo.execute_query("SELECT * FROM accounts")

        assert mock_session.execute.call_count >= 2
        first_call = mock_session.execute.call_args_list[0]
        assert "READ ONLY" in str(first_call[0][0])

    @pytest.mark.asyncio
    async def test_execute_query_handles_readonly_failure(self, mock_session):
        """Test that execute_query continues even if SET TRANSACTION READ ONLY fails."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session.execute.side_effect = [
            Exception("Cannot set read only"),
            mock_result
        ]

        with patch('app.repositories.postgres.finance_repository.logger') as mock_logger:
            repo = FinanceRepository(mock_session)
            result = await repo.execute_query("SELECT * FROM accounts")

            assert result == []
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Failed to set transaction READ ONLY" in warning_call

    @pytest.mark.asyncio
    async def test_execute_query_with_multiple_parameters(self, mock_session):
        """Test that execute_query handles multiple parameters."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = FinanceRepository(mock_session)
        await repo.execute_query(
            "SELECT * FROM transactions WHERE user_id = :user_id AND amount > :min_amount",
            user_id="test-user",
            min_amount=100
        )

        call_args = mock_session.execute.call_args_list[1]
        assert call_args[0][1] == {"user_id": "test-user", "min_amount": 100}

    @pytest.mark.asyncio
    async def test_execute_query_raises_on_execution_error(self, mock_session):
        """Test that execute_query raises exception on SQL error."""
        mock_session.execute.side_effect = [
            MagicMock(),  # First call for SET TRANSACTION READ ONLY succeeds
            Exception("SQL syntax error")  # Second call fails
        ]

        with patch('app.repositories.postgres.finance_repository.logger') as mock_logger:
            repo = FinanceRepository(mock_session)

            with pytest.raises(Exception, match="SQL syntax error"):
                await repo.execute_query("INVALID SQL")

            mock_session.rollback.assert_called_once()
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "SQL execution error" in error_call

    @pytest.mark.asyncio
    async def test_execute_query_logs_execution_steps(self, mock_session):
        """Test that execute_query logs various execution steps."""
        mock_row = MagicMock()
        mock_row._mapping = {"id": 1}
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        with patch('app.repositories.postgres.finance_repository.logger') as mock_logger:
            repo = FinanceRepository(mock_session)
            query = "SELECT * FROM accounts"
            params = {"user_id": "test"}

            await repo.execute_query(query, **params)

            assert mock_logger.info.call_count >= 4
            info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("params" in call for call in info_calls)
            assert any("Successfully formatted" in call for call in info_calls)

    @pytest.mark.asyncio
    async def test_execute_query_handles_none_rows(self, mock_session):
        """Test that execute_query handles None from fetchall."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = None
        mock_session.execute.return_value = mock_result

        repo = FinanceRepository(mock_session)
        result = await repo.execute_query("SELECT * FROM accounts")

        assert result == []
