# Goal Progress History Internal API

**Base Path:** `/internal/goal-progress-history`

⚠️ **WARNING**: Estos endpoints NO requieren autenticación y están diseñados únicamente para comunicación servicio-a-servicio. En producción deben estar protegidos por políticas de red o reglas de API gateway.

---

## Endpoints Implementados

### 1. `GET /internal/goal-progress-history`
**Lista registros de historial de progreso con filtros opcionales**

**Query Parameters:**
- `user_id` (UUID, opcional): Filtrar por usuario
- `goal_id` (UUID, opcional): Filtrar por objetivo
- `is_current_period` (bool, opcional): Filtrar por acumuladores activos (True) o históricos (False)
- `period_type` (string, opcional): Filtrar por tipo de periodo (`day`, `week`, `month`, `quarter`, `year`)
- `from_date` (datetime, opcional): Filtrar registros con `period_start >= from_date`
- `to_date` (datetime, opcional): Filtrar registros con `period_start <= to_date`
- `limit` (int, 1-100, default 50): Máximo de registros a devolver
- `offset` (int, >=0, default 0): Registros a saltar (paginación)
- `order` (string, default `period_start_desc`): Orden de resultados
  - `period_start_desc`, `period_start_asc`, `created_at_desc`, `created_at_asc`

**Response:** `GoalProgressHistoryListResponse`
```json
{
  "records": [...],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

**Uso típico:**
- Auditoría cruzada de progresos por usuario o objetivo
- Exportación masiva de datos históricos
- Monitoreo de acumuladores activos

---

### 2. `GET /internal/goal-progress-history/by-goal/{goal_id}`
**Obtiene el acumulador activo y registros históricos de un objetivo específico**

**Path Parameters:**
- `goal_id` (UUID, requerido): Identificador del objetivo

**Query Parameters:**
- `limit` (int, 1-50, default 10): Máximo de registros históricos a devolver

**Response:** `GoalProgressHistoryByGoalResponse`
```json
{
  "goal_id": "123e4567-e89b-12d3-a456-426614174000",
  "current_accumulator": { ... },  // o null si no hay acumulador activo
  "historical_records": [...],
  "total_historical": 5
}
```

**Uso típico:**
- Obtener el estado actual y pasado de un objetivo para herramientas/dashboards
- Consulta rápida del progreso sin filtros complejos

---

### 3. `GET /internal/goal-progress-history/{record_id}`
**Obtiene un registro individual por ID**

**Path Parameters:**
- `record_id` (UUID, requerido): Identificador del registro

**Response:** `GoalProgressHistoryRead`

**Error 404** si no se encuentra el registro.

**Uso típico:**
- Depuración de registros específicos
- Verificación de valores tras creación/actualización

---

### 4. `POST /internal/goal-progress-history`
**Crea un nuevo registro de historial de progreso**

**Request Body:** `GoalProgressHistoryCreate`

**Campos requeridos:**
- `goal_id` (UUID): Identificador del objetivo
- `user_id` (UUID): Identificador del usuario
- `period_start` (datetime): Inicio del periodo
- `period_end` (datetime): Fin del periodo (debe ser > `period_start`)
- `period_type` (string): Tipo de periodo (`day`, `week`, `month`, `quarter`, `year`)

**Campos opcionales:**
- `final_value` (Decimal)
- `target_value` (Decimal)
- `percent_complete` (Decimal)
- `was_completed` (bool, default `False`)
- `reset_timestamp` (datetime, auto-set si no provisto y `is_current_period=False`)
- `goal_status_at_reset` (string)
- `is_current_period` (bool, default `False`)
- `last_updated` (datetime, auto-set si `is_current_period=True`)
- `update_count` (int, default 0)

**Comportamiento de close-and-replace:**
- Si `is_current_period=True` y ya existe otro acumulador activo para el mismo `goal_id`:
  - El acumulador previo se marca como histórico (`is_current_period=False`)
  - Se establece su `reset_timestamp` a now si no estaba definido
  - Se crea el nuevo acumulador activo

**Response:** `GoalProgressHistoryCreateResponse`
```json
{
  "success": true,
  "record": { ... },
  "closed_previous": "uuid-del-acumulador-cerrado",  // o null
  "message": "Goal progress history record created successfully (closed previous accumulator ...)"
}
```

**Validaciones:**
- `period_type` debe estar en `{day, week, month, quarter, year}`
- `period_end` debe ser mayor que `period_start`

**Uso típico:**
- Creación manual de registros históricos
- Migración de datos desde sistemas legacy
- Creación forzada de nuevos periodos (reemplazando acumulador activo)

---

### 5. `PATCH /internal/goal-progress-history/{record_id}`
**Actualiza un registro existente de historial de progreso**

**Path Parameters:**
- `record_id` (UUID, requerido): Identificador del registro a actualizar

**Request Body:** `GoalProgressHistoryUpdate` (todos los campos opcionales)

**Campos actualizables:**
- `final_value` (Decimal)
- `target_value` (Decimal)
- `percent_complete` (Decimal)
- `was_completed` (bool)
- `goal_status_at_reset` (string)
- `is_current_period` (bool) - **ver reglas especiales abajo**
- `last_updated` (datetime, auto-set a now si no provisto)
- `update_count` (int, auto-incrementa si no provisto)

**Campos NO actualizables:**
- `goal_id`, `user_id`, `period_start`, `period_end`, `period_type` (identidad del registro)

**Reglas especiales para `is_current_period`:**
- **True → False**: Se establece `reset_timestamp=now` si no estaba definido
- **False → True**: Se valida que no exista otro acumulador activo para el mismo `goal_id` (error 409 si existe)

**Response:** `GoalProgressHistoryUpdateResponse`
```json
{
  "success": true,
  "record": { ... },
  "message": "Goal progress history record updated successfully"
}
```

**Error 404** si no se encuentra el registro.  
**Error 409** si se intenta activar (`is_current_period=True`) pero ya existe otro acumulador activo para el goal.

**Uso típico:**
- Corrección de valores incorrectos en histórico
- Ajuste manual de progreso de acumulador activo
- Transición manual de estados (activo ↔ histórico)

---

## Schemas Pydantic

### `GoalProgressHistoryRead`
Representación completa de un registro (incluye todos los campos del modelo).

### `GoalProgressHistoryCreate`
Schema para crear registros (campos requeridos + opcionales con defaults).

### `GoalProgressHistoryUpdate`
Schema para actualizar registros (todos los campos opcionales, solo progreso/estado).

### `GoalProgressHistoryListResponse`
Lista paginada de registros con metadatos de paginación.

### `GoalProgressHistoryByGoalResponse`
Vista del progreso de un objetivo: acumulador activo + histórico reciente.

### `GoalProgressHistoryCreateResponse`
Respuesta de creación con información de cierre de acumulador previo (si aplicó).

### `GoalProgressHistoryUpdateResponse`
Respuesta de actualización con registro modificado.

---

## Casos de Uso

### 1. Auditoría de acumuladores activos
```http
GET /internal/goal-progress-history?is_current_period=true&limit=100
```

### 2. Exportar historial completo de un usuario
```http
GET /internal/goal-progress-history?user_id=<uuid>&limit=100&order=period_start_asc
```

### 3. Consultar progreso de un objetivo específico
```http
GET /internal/goal-progress-history/by-goal/<goal_id>?limit=20
```

### 4. Crear acumulador activo para un nuevo periodo (close-and-replace automático)
```http
POST /internal/goal-progress-history
{
  "goal_id": "...",
  "user_id": "...",
  "period_start": "2025-11-01T00:00:00Z",
  "period_end": "2025-11-30T23:59:59Z",
  "period_type": "month",
  "is_current_period": true,
  "final_value": 0,
  "target_value": 1000
}
```

### 5. Corregir valor final de un registro histórico
```http
PATCH /internal/goal-progress-history/<record_id>
{
  "final_value": 850.50,
  "percent_complete": 85.05
}
```

### 6. Cerrar manualmente un acumulador activo
```http
PATCH /internal/goal-progress-history/<record_id>
{
  "is_current_period": false
}
```

---

## Consideraciones de Seguridad

1. **Sin autenticación**: Estos endpoints NO validan usuario autenticado.
2. **Protección de red**: Deben estar bloqueados en el API Gateway para tráfico externo.
3. **Validación de datos**: Todas las schemas tienen validación Pydantic (tipos, rangos, coherencia).
4. **Transacciones**: Operaciones de escritura usan transacciones DB con rollback en caso de error.
5. **Conflictos**: La lógica de close-and-replace y validación de unicidad previene estados inconsistentes.

---

## Interacción con el Sistema Existente

- **Scheduler de periodos** (`POST /goals/process-periods`): Cierra acumuladores automáticamente cuando cambia el periodo. Los endpoints internos permiten hacer esto manualmente o corregir si el scheduler falla.
- **Endpoint autenticado** (`GET /goals/{goal_id}/history`): Lee el historial público para usuarios. Los endpoints internos ofrecen control total sin restricciones de usuario.
- **Services**: `goals_service.py` crea y actualiza acumuladores durante operaciones de goal. Los endpoints internos permiten operaciones CRUD directas sin lógica de negocio adicional.

---

## Archivos Creados/Modificados

- ✅ `api/schemas/goal_progress_history_internal.py` - Schemas Pydantic para la API interna
- ✅ `api/routers/internal_goal_history.py` - Router con los 5 endpoints para Goal Progress History
- ✅ `api/main.py` - Registro del router con prefix `/internal/goal-progress-history`
- ✅ `docs/GOAL_PROGRESS_HISTORY_INTERNAL_API.md` - Esta documentación

---

## Testing Recomendado

1. Crear acumulador activo para un goal nuevo
2. Crear segundo acumulador activo para el mismo goal → verificar close-and-replace
3. Actualizar valores del acumulador activo
4. Cambiar acumulador de activo a histórico (verificar `reset_timestamp`)
5. Listar con filtros variados (user_id, goal_id, period_type, rangos de fecha)
6. Consultar progreso por goal_id (verificar separación de activo/histórico)
7. Validar errores 404, 409, y 500 en casos límite
