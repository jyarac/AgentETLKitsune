## Riesgos identificados

### 1. Exposición de información personal
Si en algún momento incluyéramos datos de autores o colaboradores (nombres, afiliaciones, correos), estaríamos mostrando información que, aunque suele ser pública en el contexto académico, puede considerarse sensible en otros escenarios. Además, existe la posibilidad de que la API de origen cambie y exponga información no prevista, lo que incrementaría el riesgo.

### 2. Mal uso de la API (endpoints inseguros)
Un endpoint de actualización abierto sin protección podría ser usado de forma indebida, generando llamadas masivas que sobrecarguen tanto nuestra base de datos como la API externa (riesgo de DoS). Sin controles adicionales, también se facilita la extracción de datos a gran escala (scraping).

### 3. Exposición de credenciales
El almacenamiento inadecuado de credenciales (base de datos, claves de API como la de OpenAI) representa un riesgo significativo. Una filtración accidental en el repositorio o en los logs podría comprometer el sistema.

---

## Medidas de mitigación propuestas

### Control de acceso
Actualmente se implementó un token simple para proteger el endpoint de actualización (`/update`). Como mejora, se recomienda migrar hacia un esquema más robusto:
- Uso de OAuth2 o JWT para autenticación/autorización.
- Manejo de API Keys seguras, siempre almacenadas en variables de entorno o un gestor de secretos, nunca hardcodeadas en el código.
- Aplicar autenticación también en endpoints de lectura si es necesario limitar el acceso.

### Anonimización y limitación de datos

En caso de manejar información sensible (por ejemplo, correos de autores), se debería:
- Anonimizar (usar iniciales en lugar de nombres completos).
- Exponer únicamente los datos estrictamente necesarios.
- Revisar las políticas de uso de la fuente de datos para asegurar cumplimiento legal.

En esta prueba, solo se maneja información de publicaciones, lo cual reduce este riesgo, pero la recomendación sigue vigente para entornos productivos.

### Rate limiting y uso de recursos

Para prevenir abusos a la API:
- Implementar límites de tasa (rate limiting) en endpoints críticos como `/update` y en las búsquedas.
- Establecer mecanismos de logging y monitoreo para detectar patrones de uso anómalos.

### Protección de credenciales
- Mantener todas las credenciales fuera del repositorio, usando `.env`, archivos de configuración seguros o un gestor de secretos (ej. Vault, AWS Secrets Manager).
- Asegurar que la API corra bajo **HTTPS** en producción, evitando el envío de tokens o credenciales en texto plano.
- Validar periódicamente la rotación de claves.

