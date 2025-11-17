"""Unit tests for finance agent tools."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.agents.supervisor.finance_agent.tools import (
    PLAID_REQUIRED_STATUS_PREFIX,
    FinanceDataAvailability,
    _validate_query_security,
    create_income_expense_summary_tool,
    create_net_worth_summary_tool,
    create_sql_db_query_tool,
    execute_financial_query,
)
from app.repositories.postgres.finance_repository import FinanceTables


class TestValidateQuerySecurity:
    """Test _validate_query_security function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = UUID("12345678-1234-5678-9012-123456789012")

    def test_valid_select_query_with_user_id_param(self):
        """Test valid SELECT query with :user_id parameter."""
        query = "SELECT * FROM transactions WHERE user_id = :user_id"
        result = _validate_query_security(query, self.user_id)
        assert result is None

    def test_valid_select_query_with_user_id_literal(self):
        """Test valid SELECT query with user_id literal."""
        query = f"SELECT * FROM transactions WHERE user_id = '{self.user_id}'"
        result = _validate_query_security(query, self.user_id)
        assert result is None

    def test_valid_select_query_with_where_user_id(self):
        """Test valid SELECT query with WHERE user_id pattern."""
        query = "SELECT * FROM transactions WHERE user_id = 'some-id' AND amount > 0"
        result = _validate_query_security(query, self.user_id)
        assert result is None

    def test_invalid_insert_query(self):
        """Test invalid INSERT query."""
        query = "INSERT INTO transactions VALUES (1, 2, 3)"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: INSERT" in result

    def test_invalid_update_query(self):
        """Test invalid UPDATE query."""
        query = "UPDATE transactions SET amount = 100"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: UPDATE" in result

    def test_invalid_delete_query(self):
        """Test invalid DELETE query."""
        query = "DELETE FROM transactions WHERE id = 1"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: DELETE" in result

    def test_invalid_drop_query(self):
        """Test invalid DROP query."""
        query = "DROP TABLE transactions"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: DROP" in result

    def test_invalid_locking_clause(self):
        """Test query with locking clause."""
        query = "SELECT * FROM transactions WHERE user_id = :user_id FOR SHARE"
        result = _validate_query_security(query, self.user_id)
        assert "Row-level locks are not allowed" in result

    def test_invalid_select_into(self):
        """Test SELECT INTO query."""
        query = "SELECT * INTO new_table FROM transactions WHERE user_id = :user_id"
        result = _validate_query_security(query, self.user_id)
        assert "SELECT INTO is not allowed" in result

    def test_invalid_data_modifying_cte(self):
        """Test data-modifying CTE."""
        query = "WITH cte AS (SELECT * FROM test WHERE user_id = :user_id) UPDATE test2 SET col = 1 FROM cte"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: UPDATE" in result

    def test_invalid_non_select_query(self):
        """Test non-SELECT top-level statement."""
        query = "CREATE VIEW test AS SELECT * FROM transactions"
        result = _validate_query_security(query, self.user_id)
        assert "Only SELECT queries" in result

    def test_query_without_user_id_filter(self):
        """Test query without user_id filter."""
        query = "SELECT * FROM transactions"
        result = _validate_query_security(query, self.user_id)
        assert "must include user_id filter" in result

    def test_valid_cte_query(self):
        """Test valid CTE query."""
        query = "WITH cte AS (SELECT * FROM transactions WHERE user_id = :user_id) SELECT * FROM cte"
        result = _validate_query_security(query, self.user_id)
        assert result is None

    def test_query_with_comments(self):
        """Test query with SQL comments."""
        query = """
        -- This is a comment
        SELECT * FROM transactions
        WHERE user_id = :user_id
        -- Another comment
        """
        result = _validate_query_security(query, self.user_id)
        assert result is None

    def test_connectivity_probe_select_1(self):
        """Test blocking SELECT 1 connectivity probe."""
        # This is handled separately in execute_financial_query, but test the pattern
        query = "SELECT 1"
        # This should pass validation since it's SELECT, but will be blocked later
        result = _validate_query_security(query, self.user_id)
        assert "must include user_id filter" in result

    def test_count_precheck_pattern(self):
        """Test COUNT(*) pre-check pattern."""
        # This is handled separately, but test validation
        query = "SELECT COUNT(*) AS cnt FROM transactions WHERE user_id = :user_id"
        result = _validate_query_security(query, self.user_id)
        assert result is None

    def test_invalid_alter_query(self):
        """Test invalid ALTER query."""
        query = "ALTER TABLE transactions ADD COLUMN new_col VARCHAR(255)"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: ALTER" in result

    def test_invalid_truncate_query(self):
        """Test invalid TRUNCATE query."""
        query = "TRUNCATE TABLE transactions"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: TRUNCATE" in result

    def test_invalid_replace_query(self):
        """Test invalid REPLACE query."""
        query = "REPLACE INTO transactions VALUES (1, 2, 3)"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: REPLACE" in result

    def test_invalid_merge_query(self):
        """Test invalid MERGE query."""
        query = "MERGE target_table t USING source_table s ON t.id = s.id WHEN MATCHED THEN UPDATE SET col = 1"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: UPDATE" in result

    def test_invalid_call_query(self):
        """Test invalid CALL query."""
        query = "CALL some_procedure()"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: CALL" in result

    def test_invalid_exec_query(self):
        """Test invalid EXEC query."""
        query = "EXEC some_procedure"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: EXEC" in result

    def test_invalid_grant_query(self):
        """Test invalid GRANT query."""
        query = "GRANT SELECT ON transactions TO user1"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: GRANT" in result

    def test_invalid_revoke_query(self):
        """Test invalid REVOKE query."""
        query = "REVOKE SELECT ON transactions FROM user1"
        result = _validate_query_security(query, self.user_id)
        assert "dangerous keyword: REVOKE" in result


class TestToolCreation:
    """Test tool creation functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = UUID("12345678-1234-5678-9012-123456789012")

    def test_create_sql_db_query_tool(self):
        """Test creating SQL DB query tool."""
        tool = create_sql_db_query_tool(self.user_id, lambda: None)
        assert tool is not None
        assert hasattr(tool, 'name')
        assert hasattr(tool, 'description')

    def test_create_net_worth_summary_tool(self):
        """Test creating net worth summary tool."""
        tool = create_net_worth_summary_tool(self.user_id)
        assert tool is not None
        assert hasattr(tool, 'name')
        assert hasattr(tool, 'description')

    def test_create_income_expense_summary_tool(self):
        """Test creating income expense summary tool."""
        tool = create_income_expense_summary_tool(self.user_id)
        assert tool is not None
        assert hasattr(tool, 'name')
        assert hasattr(tool, 'description')

    @pytest.mark.asyncio
    async def test_net_worth_tool_requires_plaid_accounts(self):
        """Net worth tool should emit plaid status when accounts missing."""
        availability = FinanceDataAvailability(has_plaid_accounts=False)
        tool = create_net_worth_summary_tool(self.user_id, lambda: availability)
        result = await tool.ainvoke({})
        assert PLAID_REQUIRED_STATUS_PREFIX in result

    @pytest.mark.asyncio
    async def test_income_expense_tool_requires_plaid_accounts(self):
        """Income/expense tool should emit plaid status when accounts missing."""
        availability = FinanceDataAvailability(has_plaid_accounts=False)
        tool = create_income_expense_summary_tool(self.user_id, lambda: availability)
        result = await tool.ainvoke({})
        assert PLAID_REQUIRED_STATUS_PREFIX in result


class TestExecuteFinancialQuery:
    """Test execute_financial_query function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = UUID("12345678-1234-5678-9012-123456789012")

    @patch('app.agents.supervisor.finance_agent.tools.get_database_service')
    @pytest.mark.asyncio
    async def test_execute_financial_query_success(self, mock_get_db_service):
        """Test successful query execution."""
        # Mock the database service and repository
        mock_repo = AsyncMock()
        mock_repo.execute_query.return_value = "Query result"
        mock_session = AsyncMock()
        mock_db_service = MagicMock()
        mock_db_service.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_service.get_session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_db_service.get_finance_repository.return_value = mock_repo
        mock_get_db_service.return_value = mock_db_service

        result = await execute_financial_query("SELECT * FROM test WHERE user_id = :user_id", self.user_id)
        assert "Query result" in result

    @patch('app.agents.supervisor.finance_agent.tools.get_database_service')
    @pytest.mark.asyncio
    async def test_execute_financial_query_connectivity_probe(self, mock_get_db_service):
        """Test blocking connectivity probe."""
        mock_db_service = MagicMock()
        mock_get_db_service.return_value = mock_db_service

        result = await execute_financial_query("SELECT 1", self.user_id)
        assert "Connectivity probes are forbidden" in result

    @patch('app.agents.supervisor.finance_agent.tools.get_database_service')
    @pytest.mark.asyncio
    async def test_execute_financial_query_count_precheck(self, mock_get_db_service):
        """Test blocking COUNT(*) pre-check."""
        mock_db_service = MagicMock()
        mock_get_db_service.return_value = mock_db_service

        result = await execute_financial_query("SELECT COUNT(*) AS cnt FROM transactions", self.user_id)
        assert "Pre-check COUNT(*) queries are forbidden" in result

    @patch('app.agents.supervisor.finance_agent.tools.get_database_service')
    @pytest.mark.asyncio
    async def test_execute_financial_query_security_error(self, mock_get_db_service):
        """Test query security error."""
        mock_db_service = MagicMock()
        mock_get_db_service.return_value = mock_db_service

        result = await execute_financial_query("SELECT * FROM transactions", self.user_id)
        assert "ERROR:" in result

    @patch('app.agents.supervisor.finance_agent.tools.get_database_service')
    @pytest.mark.asyncio
    async def test_execute_financial_query_execution_error(self, mock_get_db_service):
        """Test query execution error."""
        # Mock the database service and repository to raise an exception
        mock_repo = AsyncMock()
        mock_repo.execute_query.side_effect = Exception("Database error")
        mock_session = AsyncMock()
        mock_db_service = MagicMock()
        mock_db_service.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_service.get_session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_db_service.get_finance_repository.return_value = mock_repo
        mock_get_db_service.return_value = mock_db_service

        result = await execute_financial_query("SELECT * FROM test WHERE user_id = :user_id", self.user_id)
        assert "Error executing query" in result

    @patch('app.agents.supervisor.finance_agent.tools.get_database_service')
    @pytest.mark.asyncio
    async def test_execute_financial_query_requires_plaid(self, mock_get_db_service):
        """Test plaid-only queries emit status when accounts missing."""
        mock_db_service = MagicMock()
        mock_get_db_service.return_value = mock_db_service

        availability = FinanceDataAvailability(has_plaid_accounts=False)
        query = f"SELECT * FROM {FinanceTables.TRANSACTIONS} WHERE user_id = :user_id"
        result = await execute_financial_query(query, self.user_id, availability)
        assert PLAID_REQUIRED_STATUS_PREFIX in result

    @patch('app.agents.supervisor.finance_agent.tools.get_database_service')
    @pytest.mark.asyncio
    async def test_execute_financial_query_no_data(self, mock_get_db_service):
        """Test query with no data returned."""
        # Mock the database service and repository
        mock_repo = AsyncMock()
        mock_repo.execute_query.return_value = None
        mock_session = AsyncMock()
        mock_db_service = MagicMock()
        mock_db_service.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_service.get_session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_db_service.get_finance_repository.return_value = mock_repo
        mock_get_db_service.return_value = mock_db_service

        result = await execute_financial_query("SELECT * FROM test WHERE user_id = :user_id", self.user_id)
        assert "No data found" in result
