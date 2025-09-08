# Historia de Usuario: Gestión de Umbrales (Thresholds) en Objetivos Financieros con VERA

## 📋 Resumen
**Como** usuario de VERA  
**Quiero** configurar umbrales de alerta en mis objetivos financieros  
**Para** recibir notificaciones proactivas cuando mi progreso alcance ciertos puntos críticos y mantener mi motivación

---

## 🎯 Escenario Principal: Descubriendo los Umbrales de VERA

### **Contexto Inicial**
- Usuario: Carlos, 35 años, emprendedor
- Situación: Ha estado usando VERA para consultas financieras y ya creó un objetivo básico
- Descubrimiento: Se entera de que VERA puede configurar alertas personalizadas (umbrales)
- Meta: Quiere ahorrar $10,000 para un fondo de emergencia en 12 meses
- Requerimiento: Recibir alertas cuando alcance 70% y 90% del objetivo

### **Flujo de Interacción**

#### **Paso 1: Descubrimiento y Solicitud con Umbrales**
```
Carlos: "VERA, he estado pensando en mi objetivo de fondo de emergencia. ¿Hay alguna forma de que me avises cuando esté llegando a ciertos puntos importantes?"

VERA: "¡Excelente pregunta, Carlos! Sí, puedo configurar umbrales de alerta personalizados para tu objetivo. Esto significa que te notificaré automáticamente cuando alcances porcentajes específicos de tu meta.

Por ejemplo, puedo configurar alertas cuando alcances:
• 70% de tu objetivo (punto de advertencia)
• 90% de tu objetivo (punto crítico - ¡casi lo logras!)

¿Te gustaría que configure estos umbrales para tu objetivo de $10,000?"

Carlos: "¡Perfecto! Sí, quiero recibir alertas cuando alcance el 70% y 90% del objetivo. ¿Cómo funciona esto?"

VERA: "¡Genial! Te explico cómo funcionan los umbrales:

🔔 **Sistema de Alertas Inteligentes:**
• Alerta de Advertencia (70%): Te motiva cuando estás en el camino correcto
• Alerta Crítica (90%): Te celebra cuando estás muy cerca del éxito
• Cada alerta incluye tu progreso actual y consejos personalizados

¿Confirmas que quieres crear tu objetivo con estos umbrales configurados?"
```

#### **Paso 2: Procesamiento del Goal Agent**
VERA procesa internamente la solicitud:

1. **Análisis de Intención**: Identifica creación de objetivo con umbrales específicos
2. **Configuración de Thresholds**: Establece `warn_progress_pct: 70` y `alert_progress_pct: 90`
3. **Creación del Objetivo**: Usa `create_goal` con configuración de umbrales

#### **Paso 3: Respuesta de VERA**
```
Carlos: "Sí, confirma la creación con esos umbrales."

VERA: "¡Excelente, Carlos! He creado tu objetivo de fondo de emergencia con el sistema de alertas personalizado.

🎯 **Tu Objetivo de Fondo de Emergencia**
• Meta: $10,000 en 12 meses
• Fecha objetivo: 15 de diciembre de 2024
• Categoría: Ahorro
• Tipo: Incremento de ahorros
• Seguimiento: Automático a través de tus cuentas vinculadas

🔔 **Sistema de Alertas Configurado:**
• Alerta de Advertencia: 70% - Te notificaré cuando alcances $7,000
• Alerta Crítica: 90% - Te notificaré cuando alcances $9,000
• Cada alerta incluirá tu progreso actual y consejos motivacionales

📊 **Plan de Ahorro Sugerido:**
• Ahorro mensual recomendado: ~$833
• Ahorro semanal recomendado: ~$192

¿Te gustaría activar este objetivo ahora para que comience el seguimiento automático con alertas?"
```

#### **Paso 4: Activación y Monitoreo**
```
Carlos: "Sí, VERA, activa el objetivo. Estoy emocionado de ver cómo funcionan estas alertas."

VERA: "¡Perfecto, Carlos! Tu objetivo de fondo de emergencia está ahora activo con el sistema de alertas inteligentes.

🎉 **¡Tu Objetivo con Alertas Está Vivo!**
• Estado: En progreso y monitoreado con alertas
• Progreso actual: $0 de $10,000 (0%)
• Días restantes: 365 días
• Próxima revisión: Automática cada semana

🔔 **Sistema de Alertas Activo:**
• Te notificaré automáticamente cuando alcances el 70% ($7,000)
• Te celebraré cuando alcances el 90% ($9,000)
• Cada alerta incluirá consejos personalizados y motivación

💡 **Consejos para el Éxito:**
• Las alertas te mantendrán motivado en el camino
• Recibirás reconocimiento en cada hito importante
• Si necesitas ajustar los umbrales, solo dímelo

¡Estoy aquí para acompañarte y celebrar cada paso hacia tu fondo de emergencia! ¿Hay algo más en lo que pueda ayudarte?"
```

---

## 🔔 Escenario de Alerta: Alcanzar Umbral de Advertencia

### **Contexto**
- Carlos ha ahorrado $7,200 (72% del objetivo) después de 8 meses
- El sistema detecta automáticamente que superó el umbral de advertencia (70%)
- VERA envía una alerta motivacional personalizada

#### **Procesamiento Automático y Alerta de VERA**
```
VERA: "🎯 ¡CARLOS, ¡EXCELENTE PROGRESO! 🎯

¡Has alcanzado el 72% de tu objetivo de fondo de emergencia! Esto significa que has superado tu umbral de advertencia del 70%.

🏆 **¡HITO ALCANZADO!**
• Progreso actual: $7,200 de $10,000 (72%)
• Umbral superado: 70% ✅
• Tiempo transcurrido: 8 meses de 12
• Días restantes: 120 días

🌟 **Lo que has logrado:**
• Has ahorrado consistentemente $900 por mes
• Estás 2% por encima de tu umbral de advertencia
• Tu disciplina financiera es ejemplar

🎯 **Próximo hito:**
Tu siguiente alerta llegará cuando alcances el 90% ($9,000)
¡Solo te faltan $1,800 para llegar a ese punto!

💪 **Motivación:**
¡Vas muy bien! Solo te faltan $2,800 para completar tu fondo de emergencia. ¡El final está cerca!"
```

---

## 🚨 Escenario de Alerta Crítica: Alcanzar Umbral Crítico

### **Contexto**
- Carlos ha ahorrado $9,100 (91% del objetivo) después de 10 meses
- El sistema detecta automáticamente que superó el umbral crítico (90%)
- VERA envía una alerta de celebración especial

#### **Procesamiento Automático y Alerta Crítica de VERA**
```
VERA: "🚨 ¡CARLOS, ¡CASI LO LOGRAS! 🚨

¡Has alcanzado el 91% de tu objetivo de fondo de emergencia! Esto significa que has superado tu umbral crítico del 90%.

🏆 **¡HITO CRÍTICO ALCANZADO!**
• Progreso actual: $9,100 de $10,000 (91%)
• Umbral superado: 90% ✅
• Tiempo transcurrido: 10 meses de 12
• Días restantes: 60 días

🌟 **Lo que has logrado:**
• Has ahorrado consistentemente $910 por mes
• Estás 1% por encima de tu umbral crítico
• Tu dedicación financiera es extraordinaria

🎯 **¡El final está cerca!**
Tu próximo hito es la meta completa: $10,000
¡Solo te faltan $900 para completar tu fondo de emergencia!

💪 **Motivación final:**
¡Estás a solo $900 de completar tu fondo de emergencia! ¡El final está cerca! ¡Has demostrado una disciplina financiera excepcional!"
```

---

## ⏰ Escenario de Umbral Temporal: Días Restantes

### **Contexto**
- Carlos quiere recibir alertas cuando queden 30 y 7 días para el objetivo
- Se da cuenta de que puede configurar alertas temporales además de las de progreso
- VERA le explica las opciones de umbrales temporales

#### **Solicitud de Configuración**
```
Carlos: "VERA, me gusta mucho cómo funcionan estas alertas. ¿También puedes avisarme cuando queden pocos días para completar el objetivo?"

VERA: "¡Por supuesto, Carlos! Puedo configurar alertas temporales además de las de progreso. Esto te ayudará a mantener el enfoque en el tiempo restante.

⏰ **Alertas Temporales Disponibles:**
• Alerta de 30 días restantes: Te recuerda el tiempo que queda
• Alerta de 7 días restantes: Te motiva para el sprint final
• Estas se combinan perfectamente con tus alertas de progreso

¿Te gustaría que configure estas alertas temporales para tu objetivo?"
```

#### **Actualización de Umbrales**
```
Carlos: "Sí, configura las alertas de 30 y 7 días. Quiero estar bien preparado."

VERA: "¡Perfecto, Carlos! He actualizado tu objetivo con el sistema completo de alertas.

✅ **Sistema de Alertas Completo:**
• Alerta de Progreso: 70% ($7,000) ✅
• Alerta Crítica: 90% ($9,000) ✅
• Alerta Temporal: 30 días restantes ✅
• Alerta Final: 7 días restantes ✅

🔔 **Ahora recibirás:**
• Alertas cuando alcances hitos de progreso
• Recordatorios cuando se acerque la fecha límite
• Motivación constante durante todo el proceso

¡Tu objetivo ahora tiene el sistema de alertas más completo! Te acompañaré en cada paso del camino."
```

#### **Alerta Temporal - 30 Días Restantes**
```
VERA: "⏰ ¡CARLOS, RECORDATORIO IMPORTANTE! ⏰

¡Te quedan exactamente 30 días para completar tu objetivo de fondo de emergencia!

📅 **Estado Actual:**
• Progreso: $8,500 de $10,000 (85% completado)
• Días restantes: 30 días
• Tiempo transcurrido: 11 meses de 12

🎯 **Análisis de Situación:**
• Necesitas ahorrar $1,500 en 30 días
• Esto equivale a $50 por día o $350 por semana
• Tu progreso actual del 85% es excelente

💡 **Recomendación:**
Si necesitas alcanzar los $10,000 en el tiempo restante, considera:
• Aumentar tu ahorro diario a $50
• O ajustar tu meta a $8,500 (que ya tienes)
• O extender la fecha límite por 1 mes

¿Te gustaría que ajustemos algo en tu plan para asegurar el éxito?"
```

---

## 🔧 Escenario de Modificación de Umbrales

### **Contexto**
- Carlos quiere cambiar los umbrales de progreso a 60% y 85%
- Se siente más cómodo con alertas más tempranas para mantenerse motivado

#### **Solicitud de Modificación**
```
Carlos: "VERA, me gustaría cambiar mis alertas para que me avisen más temprano. ¿Puedo cambiarlas al 60% y 85% en lugar de 70% y 90%?"

VERA: "¡Por supuesto, Carlos! Es muy inteligente ajustar tus umbrales para que se adapten mejor a tu estilo de motivación. Cambiar a alertas más tempranas puede ayudarte a mantener el impulso.

📊 **Impacto del Cambio:**
• Nueva alerta de advertencia: 60% ($6,000) - más temprana
• Nueva alerta crítica: 85% ($8,500) - más temprana
• Las alertas temporales se mantienen igual

¿Confirmas que quieres cambiar tus umbrales a 60% y 85%?"
```

#### **Procesamiento y Confirmación**
```
Carlos: "Sí, confirma el cambio. Me siento más motivado con alertas más tempranas."

VERA: "¡Perfecto, Carlos! He actualizado tu sistema de alertas con los nuevos umbrales.

✅ **Umbrales Actualizados:**
• Alerta de Advertencia: 60% - Te notificaré cuando alcances $6,000
• Alerta Crítica: 85% - Te notificaré cuando alcances $8,500
• Alertas Temporales: 30 y 7 días restantes (sin cambios)

🔔 **Beneficios del Cambio:**
• Recibirás motivación más temprana en tu proceso
• Te mantendrás más enfocado desde el inicio
• Las alertas se adaptan mejor a tu estilo de trabajo

¡Ahora tu sistema de alertas está perfectamente personalizado para ti!"
```

---

## 📊 Tipos de Umbrales Soportados

| Tipo de Umbral | Campo | Descripción | Ejemplo |
|----------------|-------|-------------|---------|
| **Progreso - Advertencia** | `warn_progress_pct` | Porcentaje para alerta de advertencia | 70% |
| **Progreso - Crítico** | `alert_progress_pct` | Porcentaje para alerta crítica | 90% |
| **Temporal - Días** | `warn_days_remaining` | Días restantes para alerta | 30 días |

---

## 🎯 Casos de Uso de Umbrales

### **1. Objetivos de Ahorro**
```json
{
  "thresholds": {
    "warn_progress_pct": 50,
    "alert_progress_pct": 80,
    "warn_days_remaining": 60
  }
}
```

### **2. Reducción de Deudas**
```json
{
  "thresholds": {
    "warn_progress_pct": 60,
    "alert_progress_pct": 85,
    "warn_days_remaining": 45
  }
}
```

### **3. Objetivos de Inversión**
```json
{
  "thresholds": {
    "warn_progress_pct": 75,
    "alert_progress_pct": 95,
    "warn_days_remaining": 30
  }
}
```

---

## 🔍 Validación de Funcionamiento

Esta historia de usuario demuestra que el goal_agent con thresholds:

1. **Configura umbrales** durante la creación de objetivos
2. **Monitorea progreso** en tiempo real
3. **Dispara alertas** cuando se alcanzan umbrales
4. **Permite modificación** de umbrales existentes
5. **Maneja múltiples tipos** de umbrales (progreso y temporal)
6. **Proporciona contexto** relevante en cada alerta
7. **Mantiene consistencia** en el estado del objetivo

---

## 🛠️ Herramientas Utilizadas para Thresholds

| Herramienta | Propósito | Cuándo se usa |
|-------------|-----------|---------------|
| `create_goal` | Crear objetivo con umbrales | Solicitud inicial con thresholds |
| `update_goal` | Modificar umbrales existentes | Cambio de configuración |
| `get_goal_requirements` | Obtener campos de umbrales | Validación de configuración |

---

## 📋 Criterios de Aceptación para Thresholds

- ✅ Usuario puede configurar umbrales de progreso (warn_progress_pct, alert_progress_pct)
- ✅ Usuario puede configurar umbrales temporales (warn_days_remaining)
- ✅ Sistema dispara alertas automáticamente al alcanzar umbrales
- ✅ Usuario puede modificar umbrales en objetivos existentes
- ✅ Alertas incluyen contexto relevante del progreso
- ✅ Sistema mantiene consistencia entre umbrales y progreso real
- ✅ Múltiples tipos de umbrales funcionan simultáneamente

---

## 🎯 Beneficios de los Thresholds

1. **Proactividad**: El usuario recibe alertas antes de problemas
2. **Motivación**: Celebración de hitos importantes
3. **Flexibilidad**: Configuración personalizada según necesidades
4. **Contexto**: Información relevante en cada alerta
5. **Adaptabilidad**: Modificación de umbrales según cambien las circunstancias

Los thresholds transforman los objetivos financieros de entidades pasivas a sistemas proactivos de coaching financiero que guían al usuario hacia el éxito.
