# Test Architecture - Verde AI (FOS AI)

## 📋 Tabla de Contenidos

- [Visión General](#visión-general)
- [Estructura de Directorios](#estructura-de-directorios)
- [Tipos de Tests](#tipos-de-tests)
- [Convenciones de Nombres](#convenciones-de-nombres)
- [Fixtures y Configuración](#fixtures-y-configuración)
- [Organización por Módulo](#organización-por-módulo)
- [Mejores Prácticas](#mejores-prácticas)
- [Ejemplos](#ejemplos)

---

## 🎯 Visión General

Este proyecto utiliza **pytest** como framework de testing con una arquitectura organizada que separa tests unitarios, de integración, y end-to-end. La estructura refleja la arquitectura del código fuente (`app/`) para facilitar la navegación y mantenimiento.

### Principios de Testing

1. **Determinismo**: Tests unitarios no dependen de servicios externos, LLMs, o variables de entorno
2. **Aislamiento**: Cada test es independiente y puede ejecutarse en cualquier orden
3. **Rapidez**: Tests unitarios deben ejecutarse en < 1 segundo cada uno
4. **Claridad**: Nombres descriptivos y estructura AAA (Arrange-Act-Assert)
5. **Cobertura**: Priorizar funciones críticas de negocio y utilidades reutilizables

---

## 📁 Estructura de Directorios

```
tests/
├── conftest.py                    # Configuración global de pytest
├── ARCHITECTURE.md                # Este documento
├── __init__.py
│
├── unit/                          # ✅ Tests unitarios (sin dependencias externas)
│   ├── agents/                    # Tests de agentes LangGraph
│   │   ├── __init__.py
│   │   ├── financial/             # Finance agent tests
│   │   │   ├── __init__.py
│   │   │   ├── test_agent.py
│   │   │   ├── test_business_rules.py
│   │   │   ├── test_helpers.py
│   │   │   ├── test_procedural_templates.py
│   │   │   ├── test_subgraph.py
│   │   │   └── test_tools.py
│   │   │
│   │   ├── goal_agent/            # Goal agent tests
│   │   │   ├── __init__.py
│   │   │   ├── test_agent.py
│   │   │   ├── test_helpers.py
│   │   │   ├── test_models.py
│   │   │   ├── test_subgraph.py
│   │   │   ├── test_tools.py
│   │   │   └── test_utils.py
│   │   │
│   │   ├── guest/                 # Guest agent tests
│   │   │   ├── conftest.py
│   │   │   └── test_guest_agent.py
│   │   │
│   │   ├── onboarding/            # Onboarding agent tests
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── test_events.py
│   │   │   ├── test_flow_definitions.py
│   │   │   └── test_onboarding_agent.py
│   │   │
│   │   ├── supervisor/            # Supervisor agent tests
│   │   │   ├── conftest.py
│   │   │   ├── test_agent_supervisor.py
│   │   │   ├── test_handoff.py
│   │   │   ├── test_hotpath.py    # ✨ Ejemplo completo (68 tests)
│   │   │   ├── test_i18n.py
│   │   │   ├── test_memory_tools.py
│   │   │   ├── test_summarizer.py
│   │   │   ├── test_tools_supervisor.py
│   │   │   └── test_workers.py
│   │   │
│   │   └── wealth_agent/          # Wealth agent tests
│   │       ├── conftest.py
│   │       ├── test_agent.py
│   │       ├── test_helpers.py
│   │       ├── test_subgraph.py
│   │       └── test_tools.py
│   │
│   ├── core/                      # Tests de configuración core
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_app_state.py
│   │   ├── test_aws_config.py
│   │   └── test_config.py
│   │
│   ├── db/                        # Tests de base de datos
│   │   ├── conftest.py
│   │   ├── test_session.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── conftest.py
│   │       └── test_user.py
│   │
│   ├── repositories/              # Tests de capa de datos
│   │   ├── conftest.py
│   │   ├── test_database_service.py
│   │   ├── test_finance_repository.py
│   │   ├── test_s3_vectors_store.py
│   │   ├── test_session_store.py
│   │   └── test_user_repository.py
│   │
│   └── summarizer/                # Tests de componentes específicos
│       ├── __init__.py
│       └── test_conversation_summarizer.py
│
├── agents/                        # 🔄 Tests de integración de agentes
│   └── supervisor/
│       └── memory/
│           ├── __init__.py
│           └── test_hotpath.py    # Ejemplo de tests con mocks
│
├── api/                           # 🌐 Tests de API (FastAPI routes)
│   ├── conftest.py
│   ├── test_routes.py
│   ├── test_routes_admin.py
│   ├── test_routes_crawl.py
│   ├── test_routes_cron.py
│   ├── test_routes_guest.py
│   ├── test_routes_knowledge.py
│   ├── test_routes_nudge_eval.py
│   ├── test_routes_supervisor.py
│   └── test_routes_title_gen.py
│
├── knowledge/                     # 📚 Tests del sistema de knowledge
│   ├── conftest.py
│   ├── crawler/
│   ├── management/
│   ├── sources/
│   ├── vector_store/
│   ├── test_crawl_logger.py
│   ├── test_document_service.py
│   ├── test_knowledge_service.py
│   ├── test_models.py
│   └── test_sync_service.py
│
└── summarizer/                    # 📝 Tests de servicios de summarización
    ├── __init__.py
    └── test_conversation_summarizer.py
```

---

## 🔬 Tipos de Tests

### 1. Tests Unitarios (`tests/unit/`)

**Características:**
- ✅ **Rápidos** (< 1 segundo por test)
- ✅ **Deterministas** (mismo input = mismo output)
- ✅ **Sin dependencias externas** (no DB, no LLM, no API calls)
- ✅ **Focalizados** en funciones/métodos individuales

**Qué testear:**
- Funciones puras de transformación de datos
- Modelos Pydantic y validaciones
- Utilidades y helpers
- Lógica de negocio aislada
- Funciones de parseo y formateo
- Reglas de negocio (business rules)

**Ejemplo:**
```python
# tests/unit/agents/supervisor/test_hotpath.py
def test_sanitize_semantic_time_phrases():
    """Remove temporal phrases from text."""
    text = "User went to gym today"
    result = _sanitize_semantic_time_phrases(text)
    assert "today" not in result.lower()
    assert "gym" in result.lower()
```

### 2. Tests de Integración (`tests/agents/`, `tests/api/`)

**Características:**
- 🔄 **Moderados** (1-5 segundos por test)
- 🔄 **Con mocks** para servicios externos
- 🔄 **Testean interacciones** entre componentes

**Qué testear:**
- Flujos de agentes LangGraph
- Endpoints de API
- Integración entre servicios
- Workflows completos

**Ejemplo:**
```python
# tests/api/test_routes_guest.py
def test_guest_chat_endpoint(client, mock_bedrock):
    response = client.post("/guest/chat", json={"message": "Hello"})
    assert response.status_code == 200
```

### 3. Tests End-to-End (E2E) - Futuro

**Características:**
- 🐢 **Lentos** (> 5 segundos)
- 🐢 **Con servicios reales** (DB, LLM en staging)
- 🐢 **Flujos completos** de usuario

---

## 📝 Convenciones de Nombres

### Archivos de Test

```
test_<module_name>.py        # Archivo de tests para un módulo
conftest.py                  # Fixtures compartidas en el directorio
__init__.py                  # Marca el directorio como paquete Python
```

### Clases de Test

```python
class Test<FunctionName>:
    """Test cases for <function_name> function."""
    
class Test<ClassName>:
    """Test cases for <ClassName> class."""
    
class Test<Feature>EdgeCases:
    """Edge cases for <feature>."""
```

### Funciones de Test

```python
def test_<what_is_being_tested>():
    """Docstring explaining the test."""
    
def test_<function>_with_<condition>():
    """Test function with specific condition."""
    
def test_<function>_returns_<expected>():
    """Test function returns expected value."""
    
def test_<function>_raises_<exception>():
    """Test function raises specific exception."""
```

### Ejemplos Reales

```python
# ✅ Buenos nombres
def test_collect_recent_user_texts_empty_messages()
def test_normalize_summary_text_smart_quotes_replacement()
def test_derive_nudge_metadata_finance_subscription()
def test_has_min_token_overlap_case_insensitive()

# ❌ Malos nombres
def test_function()
def test_1()
def test_edge_case()
```

---

## 🔧 Fixtures y Configuración

### Jerarquía de `conftest.py`

1. **`tests/conftest.py`** (Root) - Configuración global
   - Mock de módulos AWS (boto3, botocore)
   - Variables de entorno globales
   - Path configuration

2. **`tests/unit/<module>/conftest.py`** - Fixtures específicas del módulo
   - Fixtures compartidas entre tests del módulo
   - Mocks específicos del dominio

3. **`tests/<type>/conftest.py`** - Fixtures por tipo de test
   - Fixtures de integración
   - Clientes HTTP mock
   - Configuración de base de datos de prueba

### Ejemplo de Fixtures Comunes

```python
# tests/unit/agents/supervisor/conftest.py

import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_bedrock_client(mocker):
    """Mock AWS Bedrock client."""
    mock = mocker.patch("app.core.app_state.get_bedrock_runtime_client")
    mock_client = MagicMock()
    # ... configuración del mock
    return mock_client

@pytest.fixture
def sample_messages():
    """Sample LangChain messages for testing."""
    return [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi there!")
    ]

@pytest.fixture
def mock_user_context():
    """Mock user context dictionary."""
    return {
        "user_id": "test-user-123",
        "profile": {"name": "Test User"},
        "preferences": {}
    }
```

---

## 🗂️ Organización por Módulo

### Mapeo: Código Fuente → Tests

La estructura de tests **refleja la estructura del código**:

```
app/agents/supervisor/memory/hotpath.py
→ tests/unit/agents/supervisor/test_hotpath.py

app/agents/supervisor/goal_agent/helpers.py
→ tests/unit/agents/goal_agent/test_helpers.py

app/api/routes_guest.py
→ tests/api/test_routes_guest.py

app/knowledge/crawler/service.py
→ tests/knowledge/crawler/test_service.py
```

### Regla General

```
app/<path>/<module>.py → tests/unit/<path>/test_<module>.py
```

---

## ✅ Mejores Prácticas

### 1. Patrón AAA (Arrange-Act-Assert)

```python
def test_create_error_command_structure():
    # Arrange - Preparar datos de prueba
    error_message = "Test error message"
    
    # Act - Ejecutar la función
    result = create_error_command(error_message)
    
    # Assert - Verificar resultados
    assert result is not None
    assert result.goto == "supervisor"
```

### 2. Tests Descriptivos

```python
# ✅ Bueno - Se entiende qué se está testeando
def test_sanitize_removes_today_phrase():
    text = "User went to gym today"
    result = _sanitize_semantic_time_phrases(text)
    assert "today" not in result.lower()

# ❌ Malo - No se entiende el propósito
def test_sanitize():
    result = func("text")
    assert result
```

### 3. Un Assert por Concepto

```python
# ✅ Bueno - Agrupa asserts relacionados
def test_user_model_validation():
    user = User(name="John", email="john@example.com")
    
    # Validar estructura básica
    assert user.name == "John"
    assert user.email == "john@example.com"
    
    # Validar métodos derivados
    assert user.display_name() == "John"

# ❌ Malo - Muchos conceptos mezclados
def test_everything():
    assert user.name == "John"
    assert db.save(user)  # Concepto diferente
    assert api.send(user)  # Otro concepto diferente
```

### 4. Usar Fixtures para Datos Reutilizables

```python
# ✅ Bueno - Fixture reutilizable
@pytest.fixture
def sample_user():
    return {"user_id": "123", "name": "Test User"}

def test_process_user(sample_user):
    result = process_user(sample_user)
    assert result["name"] == "Test User"

# ❌ Malo - Datos duplicados en cada test
def test_process_user():
    user = {"user_id": "123", "name": "Test User"}
    result = process_user(user)
    # ...
```

### 5. Tests Deterministas

```python
# ✅ Bueno - Resultado predecible
def test_calculate_total():
    items = [{"price": 10}, {"price": 20}]
    assert calculate_total(items) == 30

# ❌ Malo - Depende de estado externo
def test_get_current_time():
    # Este test fallará en diferentes momentos
    assert get_current_time() == "14:30"
```

### 6. Organizar Tests en Clases

```python
class TestUserValidation:
    """Tests for user input validation."""
    
    def test_valid_email(self):
        assert validate_email("user@example.com")
    
    def test_invalid_email_format(self):
        assert not validate_email("invalid-email")
    
    def test_empty_email(self):
        assert not validate_email("")

class TestUserTransformations:
    """Tests for user data transformations."""
    
    def test_normalize_name(self):
        assert normalize_name("  JOHN  ") == "John"
```

### 7. Tests de Edge Cases

```python
class TestSanitizeSemanticTimePhrases:
    """Test time phrase sanitization."""
    
    # Caso normal
    def test_removes_today(self):
        text = "User went to gym today"
        result = _sanitize_semantic_time_phrases(text)
        assert "today" not in result.lower()
    
    # Edge cases
    def test_empty_string(self):
        assert _sanitize_semantic_time_phrases("") == ""
    
    def test_non_string_input(self):
        assert _sanitize_semantic_time_phrases(None) == ""
    
    def test_multiple_time_phrases(self):
        text = "today and yesterday"
        result = _sanitize_semantic_time_phrases(text)
        assert "today" not in result
        assert "yesterday" not in result
```

---

## 📚 Ejemplos Completos

### Ejemplo 1: Test Unitario Simple

```python
# tests/unit/agents/goal_agent/test_helpers.py

from app.agents.supervisor.goal_agent.helpers import create_error_command

class TestCreateErrorCommand:
    """Test cases for create_error_command function."""

    def test_create_error_command_structure(self):
        """Test that create_error_command returns proper Command structure."""
        # Arrange
        error_message = "Test error message"

        # Act
        result = create_error_command(error_message)

        # Assert
        assert result is not None
        assert hasattr(result, 'update')
        assert hasattr(result, 'goto')
        
        # Check update structure
        update_data = result.update
        assert "messages" in update_data
        assert len(update_data["messages"]) == 2
        
        # Check first message (error message)
        error_msg = update_data["messages"][0]
        assert error_msg["role"] == "assistant"
        assert error_msg["content"] == error_message
        
        # Check goto
        assert result.goto == "supervisor"
```

### Ejemplo 2: Test con Fixtures

```python
# tests/unit/agents/financial/test_helpers.py

import pytest
from langchain_core.messages import HumanMessage, AIMessage

class TestGetLastUserMessageText:
    """Test get_last_user_message_text function."""

    @pytest.fixture
    def mixed_messages(self):
        """Fixture with mixed message types."""
        return [
            HumanMessage(content="First message"),
            AIMessage(content="AI response"),
            HumanMessage(content="Last message"),
        ]

    def test_get_last_human_message(self, mixed_messages):
        """Test getting text from last HumanMessage."""
        result = get_last_user_message_text(mixed_messages)
        assert result == "Last message"
    
    def test_empty_messages_list(self):
        """Test with empty messages list."""
        result = get_last_user_message_text([])
        assert result == ""
```

### Ejemplo 3: Test de Modelo Pydantic

```python
# tests/unit/agents/goal_agent/test_models.py

import pytest
from pydantic import ValidationError
from app.agents.supervisor.goal_agent.models import GoalCreate

class TestGoalCreate:
    """Test GoalCreate model validation."""

    def test_valid_goal_creation(self):
        """Test creating a valid goal."""
        goal = GoalCreate(
            title="Save for vacation",
            target_amount=5000,
            category="travel"
        )
        assert goal.title == "Save for vacation"
        assert goal.target_amount == 5000
        assert goal.category == "travel"

    def test_missing_required_field(self):
        """Test validation error with missing field."""
        with pytest.raises(ValidationError) as exc_info:
            GoalCreate(title="Save for vacation")
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("target_amount",) for e in errors)

    def test_invalid_amount_type(self):
        """Test validation error with invalid amount type."""
        with pytest.raises(ValidationError):
            GoalCreate(
                title="Test",
                target_amount="not a number",
                category="savings"
            )
```

### Ejemplo 4: Test Completo con Multiple Casos

```python
# tests/unit/agents/supervisor/test_hotpath.py

from app.agents.supervisor.memory.hotpath import (
    _sanitize_semantic_time_phrases,
    _has_min_token_overlap,
    _derive_nudge_metadata
)

class TestSanitizeSemanticTimePhrases:
    """Test _sanitize_semantic_time_phrases function."""

    def test_removes_today(self):
        text = "User went to gym today"
        result = _sanitize_semantic_time_phrases(text)
        assert "today" not in result.lower()
        assert "gym" in result.lower()

    def test_removes_yesterday(self):
        text = "Yesterday I bought groceries"
        result = _sanitize_semantic_time_phrases(text)
        assert "yesterday" not in result.lower()
        assert "bought" in result.lower()

    def test_preserves_timeless_facts(self):
        text = "User's cat is named Luna"
        result = _sanitize_semantic_time_phrases(text)
        assert result == text

    def test_empty_string(self):
        result = _sanitize_semantic_time_phrases("")
        assert result == ""

    def test_non_string_input(self):
        result = _sanitize_semantic_time_phrases(None)
        assert result == ""


class TestDeriveNudgeMetadata:
    """Test _derive_nudge_metadata function."""

    def test_finance_subscription(self):
        result = _derive_nudge_metadata("Finance", "User has monthly subscription", 3)
        assert result["topic_key"] == "subscription"
        assert result["importance_bin"] == "med"

    def test_goals_active(self):
        result = _derive_nudge_metadata("Goals", "Saving for vacation", 5)
        assert result["topic_key"] == "goal_active"
        assert result["importance_bin"] == "high"

    def test_importance_boundary_values(self):
        result_high = _derive_nudge_metadata("Finance", "test", 4)
        assert result_high["importance_bin"] == "high"
        
        result_med = _derive_nudge_metadata("Finance", "test", 3)
        assert result_med["importance_bin"] == "med"
        
        result_low = _derive_nudge_metadata("Finance", "test", 1)
        assert result_low["importance_bin"] == "low"
```

---

## 🚀 Ejecutar Tests

### Comandos Básicos

```bash
# Todos los tests
poetry run pytest

# Solo tests unitarios
poetry run pytest tests/unit/

# Tests de un módulo específico
poetry run pytest tests/unit/agents/supervisor/

# Un archivo específico
poetry run pytest tests/unit/agents/supervisor/test_hotpath.py

# Una clase específica
poetry run pytest tests/unit/agents/supervisor/test_hotpath.py::TestSanitizeSemanticTimePhrases

# Un test específico
poetry run pytest tests/unit/agents/supervisor/test_hotpath.py::TestSanitizeSemanticTimePhrases::test_removes_today
```

### Con Opciones Útiles

```bash
# Con output verbose
poetry run pytest -v

# Con coverage
poetry run pytest --cov=app --cov-report=html

# Tests que fallaron la última vez
poetry run pytest --lf

# Solo tests rápidos (< 1s)
poetry run pytest -m "not slow"

# Con output detallado de prints
poetry run pytest -s

# Detener en el primer fallo
poetry run pytest -x

# Modo watch (requiere pytest-watch)
poetry run ptw
```

---

## 📊 Métricas de Calidad

### Objetivos de Cobertura

| Categoría | Objetivo | Prioridad |
|-----------|----------|-----------|
| Utilidades y Helpers | 90%+ | Alta |
| Modelos de Datos | 80%+ | Alta |
| Lógica de Negocio | 80%+ | Alta |
| Agentes LangGraph | 60%+ | Media |
| API Routes | 70%+ | Media |
| Scripts y CLI | 40%+ | Baja |

### Estado Actual (Ejemplo)

```
app/agents/supervisor/memory/hotpath.py    26% → 🎯 Target: 60%
app/agents/supervisor/goal_agent/*.py       0% → 🎯 Target: 50%
app/api/routes*.py                          0% → 🎯 Target: 70%
```

---

## 🔄 Flujo de Trabajo

### 1. Antes de Escribir el Código (TDD Opcional)

```python
# Escribir el test primero
def test_calculate_discount():
    assert calculate_discount(100, 0.2) == 80

# Implementar la función
def calculate_discount(price, discount):
    return price * (1 - discount)
```

### 2. Desarrollo Normal

1. Implementar funcionalidad
2. Escribir tests para funciones críticas
3. Ejecutar tests: `poetry run pytest`
4. Verificar cobertura: `poetry run pytest --cov=app`
5. Refactorizar con confianza

### 3. Pull Request

1. Todos los tests pasan ✅
2. Cobertura no disminuye ✅
3. Tests para nuevo código ✅

---

## 📖 Referencias

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)
- [Testing Best Practices - Real Python](https://realpython.com/pytest-python-testing/)
- [LangChain Testing Guide](https://python.langchain.com/docs/contributing/testing)

---

## 🤝 Contribuir

Al agregar tests nuevos:

1. ✅ Seguir la estructura de directorios establecida
2. ✅ Usar convenciones de nombres consistentes
3. ✅ Documentar con docstrings claros
4. ✅ Organizar en clases por funcionalidad
5. ✅ Incluir edge cases
6. ✅ Mantener tests deterministas y rápidos
7. ✅ Actualizar este documento si es necesario

---

**Última actualización**: Octubre 2025  
**Mantenido por**: Verde AI Team  
**Preguntas**: Consultar en Slack #engineering-tests
