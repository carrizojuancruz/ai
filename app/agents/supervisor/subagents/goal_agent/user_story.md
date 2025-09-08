# Historia de Usuario: Gestión de Objetivos Financieros con VERA

## 📋 Resumen
**Como** usuario de VERA  
**Quiero** crear y gestionar mis objetivos financieros  
**Para** poder alcanzar mis metas de ahorro y controlar mis gastos con la ayuda de mi asistente financiero inteligente

---

## 🎯 Escenario Principal: Descubriendo las Capacidades de VERA

### **Contexto Inicial**
- Usuario: María, 28 años, empleada
- Situación: Ha estado usando VERA para consultas financieras básicas
- Descubrimiento: Se entera de que VERA puede ayudarla a crear y gestionar objetivos financieros
- Meta: Quiere ahorrar $5,000 para un viaje en 6 meses

### **Flujo de Interacción**

#### **Paso 1: Descubrimiento y Solicitud Inicial**
```
María: "Hola VERA, he estado pensando en ahorrar para un viaje que quiero hacer en 6 meses. ¿Puedes ayudarme con eso?"

VERA: "¡Por supuesto, María! Me encanta ayudarte con tus metas financieras. Puedo ayudarte a crear un objetivo de ahorro estructurado que te permita alcanzar tu meta de viaje. ¿Cuánto dinero necesitas ahorrar y en cuánto tiempo?"

María: "Necesito $5,000 para el viaje en 6 meses. ¿Cómo funciona esto de los objetivos?"

VERA: "Perfecto, María. Te explico: puedo crear un objetivo personalizado que incluya:
- Tu meta específica ($5,000 en 6 meses)
- Un plan de seguimiento automático
- Alertas cuando alcances hitos importantes
- Consejos personalizados según tu progreso

¿Te parece bien que creemos este objetivo juntas?"
```

#### **Paso 2: Procesamiento del Goal Agent**
VERA procesa internamente la solicitud:

1. **Análisis de Intención**: Identifica que María quiere crear un nuevo objetivo
2. **Verificación de Estado**: Usa `get_goal_requirements` para obtener campos requeridos
3. **Validación de Constraints**: Verifica que no hay objetivos "in_progress" activos
4. **Creación del Objetivo**: Usa `create_goal` con los datos proporcionados

#### **Paso 3: Respuesta de VERA**
```
VERA: "¡Excelente, María! He creado tu objetivo de ahorro personalizado. Aquí tienes todos los detalles:

🎯 **Tu Objetivo de Viaje**
• Meta: $5,000 en 6 meses
• Fecha objetivo: 15 de junio de 2024
• Categoría: Ahorro
• Tipo: Incremento de ahorros
• Seguimiento: Automático a través de tus cuentas vinculadas

📊 **Plan de Ahorro Sugerido**
• Ahorro mensual recomendado: ~$833
• Ahorro semanal recomendado: ~$192
• Esto te permitirá alcanzar tu meta cómodamente

¿Te gustaría activar este objetivo ahora para que comience el seguimiento automático, o prefieres hacer algún ajuste primero?"
```

#### **Paso 4: Activación del Objetivo**
```
María: "Sí, VERA, activa el objetivo por favor. Estoy emocionada de comenzar este plan de ahorro."

VERA: "¡Perfecto, María! Tu objetivo de viaje está ahora activo y comenzando el seguimiento automático. 

🎉 **¡Tu Objetivo Está Vivo!**
• Estado: En progreso y monitoreado
• Progreso actual: $0 de $5,000 (0%)
• Días restantes: 180 días
• Próxima revisión: Automática cada semana

💡 **Consejos para el Éxito:**
• Te enviaré actualizaciones semanales de tu progreso
• Recibirás alertas cuando alcances hitos importantes (25%, 50%, 75%)
• Si necesitas ajustar algo, solo dímelo y lo modificamos juntas

¡Estoy aquí para acompañarte en este viaje hacia tu meta de ahorro! ¿Hay algo más en lo que pueda ayudarte con tus finanzas?"
```

---

## 🔄 Escenario Secundario: Modificar Objetivo Existente

### **Contexto**
- María ya tiene un objetivo "in_progress" activo
- Después de 2 semanas, se da cuenta de que $5,000 es muy ambicioso
- Quiere ajustar el monto objetivo a algo más realista

#### **Interacción**
```
María: "VERA, he estado pensando en mi objetivo de viaje. Creo que $5,000 es demasiado ambicioso para 6 meses. ¿Puedo cambiarlo a $4,000?"

VERA: "¡Por supuesto, María! Es muy inteligente ajustar tus objetivos para que sean alcanzables. Cambiar de $5,000 a $4,000 es una decisión muy sensata.

📊 **Impacto del Cambio:**
• Nuevo ahorro mensual: ~$667 (en lugar de $833)
• Nuevo ahorro semanal: ~$154 (en lugar de $192)
• Esto te dará más flexibilidad en tu presupuesto mensual

¿Confirmas que quieres cambiar tu objetivo a $4,000? Esto actualizará automáticamente tu plan de seguimiento."
```

#### **Procesamiento y Confirmación**
```
María: "Sí, confirma el cambio. Me siento más cómoda con $4,000."

VERA: "¡Perfecto! He actualizado tu objetivo de viaje. 

✅ **Objetivo Actualizado:**
• Nueva meta: $4,000 (reducido de $5,000)
• Ahorro mensual ajustado: ~$667
• Tu progreso actual se mantiene: $0 de $4,000 (0%)
• Fecha objetivo: Sigue siendo 15 de junio de 2024

¡Ahora tu objetivo es más alcanzable y realista! Te seguiré acompañando en este viaje hacia tu meta ajustada."
```

---

## ⚠️ Escenario de Error: Múltiples Objetivos Activos

### **Contexto**
- María intenta crear un segundo objetivo mientras tiene uno "in_progress"
- Se siente motivada por el éxito de su primer objetivo y quiere agregar otro

#### **Interacción**
```
María: "VERA, me está yendo tan bien con mi objetivo de viaje que quiero crear otro objetivo para reducir mis gastos en restaurantes. ¿Puedes ayudarme?"

VERA: "¡Me encanta tu entusiasmo, María! Es fantástico que te esté yendo tan bien con tu objetivo de viaje. Sin embargo, tengo que explicarte algo importante sobre cómo funcionan los objetivos en mi sistema.

⚠️ **Limitación del Sistema:**
Actualmente tienes un objetivo activo: 'Ahorro para viaje' ($4,000 en progreso)
Mi sistema está diseñado para que te enfoques en un objetivo a la vez para maximizar tus posibilidades de éxito.

🤔 **¿Qué prefieres hacer?**
1. **Pausar tu objetivo de viaje** y crear el nuevo objetivo de restaurantes
2. **Completar tu objetivo de viaje primero** y luego crear el nuevo objetivo
3. **Cancelar la nueva creación** y seguir enfocada en tu viaje

¿Cuál opción te parece mejor para tu situación actual?"
```

#### **Procesamiento y Respuesta**
```
María: "Tienes razón, VERA. Mejor me enfoco en completar mi viaje primero. ¿Puedes recordarme cuánto llevo ahorrado?"

VERA: "¡Excelente decisión, María! El enfoque es clave para el éxito financiero. 

📊 **Estado Actual de tu Objetivo de Viaje:**
• Progreso: $1,200 de $4,000 (30% completado)
• Tiempo transcurrido: 2 meses de 6
• Tiempo restante: 4 meses
• Ahorro mensual actual: $600 (¡vas muy bien!)

🎯 **Estás en el camino correcto!** Tu progreso del 30% en 2 meses significa que estás ahorrando a un ritmo excelente. ¡Sigue así y alcanzarás tu meta de viaje sin problemas!"
```

---

## ✅ Escenario de Éxito: Completar Objetivo

### **Contexto**
- María ha alcanzado su meta de $4,000 antes de lo esperado
- El sistema detecta automáticamente el logro y celebra el éxito

#### **Procesamiento Automático y Celebración**
```
VERA: "🎉 ¡MARÍA, ¡LO LOGASTE! 🎉

¡Felicitaciones! Has alcanzado tu objetivo de ahorro de $4,000 para tu viaje. ¡Tu viaje está completamente financiado!

🏆 **¡MISIÓN CUMPLIDA!**
• Objetivo: $4,000 ✅ COMPLETADO
• Tiempo: 5 meses (¡1 mes antes de lo planeado!)
• Progreso final: 100% (4,000 de 4,000)
• Fecha de logro: 20 de mayo de 2024

🌟 **Lo que lograste:**
• Ahorraste consistentemente $800 por mes
• Superaste tu meta original en tiempo récord
• Demostraste disciplina financiera excepcional

🎯 **¿Qué sigue?**
Ahora que has completado este objetivo, puedes:
• Crear un nuevo objetivo financiero (como reducir gastos en restaurantes)
• Disfrutar tu viaje sin preocupaciones financieras
• Aplicar las estrategias de ahorro que aprendiste

¡Estoy muy orgullosa de tu logro, María! ¿Te gustaría que creemos tu próximo objetivo financiero?"
```

#### **Respuesta de María**
```
María: "¡VERA, no puedo creerlo! ¡Gracias por acompañarme en este proceso! Ahora sí quiero crear ese objetivo para reducir mis gastos en restaurantes."

VERA: "¡Por supuesto, María! Ahora que has demostrado que puedes ahorrar exitosamente, es el momento perfecto para crear tu próximo objetivo. 

¿Cuánto te gustaría reducir tus gastos mensuales en restaurantes y en cuánto tiempo?"
```

---

## 🛠️ Herramientas Utilizadas

| Herramienta | Propósito | Cuándo se usa |
|-------------|-----------|---------------|
| `get_goal_requirements` | Obtener campos requeridos | Al crear objetivos |
| `get_in_progress_goal` | Verificar objetivos activos | Antes de crear/activar |
| `create_goal` | Crear nuevo objetivo | Solicitud inicial |
| `update_goal` | Modificar objetivo existente | Cambios solicitados |
| `switch_goal_status` | Cambiar estado del objetivo | Activación/completado |
| `delete_goal` | Eliminar objetivo | Solicitud de eliminación |

---

## 📊 Estados del Objetivo

| Estado | Descripción | Transiciones Posibles |
|--------|-------------|----------------------|
| `pending` | Objetivo creado, no activo | → `in_progress`, `deleted` |
| `in_progress` | Objetivo activo y monitoreado | → `completed`, `error`, `paused`, `off_track` |
| `completed` | Objetivo alcanzado exitosamente | → `deleted` |
| `error` | Problema técnico en monitoreo | → `in_progress`, `deleted` |
| `paused` | Objetivo pausado temporalmente | → `in_progress`, `deleted` |
| `off_track` | Objetivo no va según plan | → `in_progress`, `paused`, `deleted` |
| `deleted` | Objetivo eliminado (soft delete) | - |

---

## 🎯 Criterios de Aceptación

- ✅ El usuario puede crear objetivos con todos los campos requeridos
- ✅ Solo se permite un objetivo "in_progress" a la vez
- ✅ Se solicita confirmación para acciones destructivas
- ✅ Los estados se transicionan correctamente
- ✅ Se manejan errores y casos edge apropiadamente
- ✅ Las respuestas incluyen JSON estructurado
- ✅ Se respetan las restricciones de estado del sistema

---

## 🔍 Validación de Funcionamiento

Esta historia de usuario demuestra que el goal_agent:

1. **Comprende intenciones** del usuario correctamente
2. **Maneja estados** según las reglas definidas
3. **Valida constraints** antes de ejecutar acciones
4. **Proporciona feedback** claro y estructurado
5. **Maneja errores** de forma elegante
6. **Sigue el flujo** de decisión establecido en el prompt

El system prompt mejorado permite que el agente funcione de manera predecible y confiable para la gestión de objetivos financieros.
