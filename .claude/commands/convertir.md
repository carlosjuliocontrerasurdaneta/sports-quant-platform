# /convertir

Convierte un documento externo a Markdown usando el skill markitdown.

Uso:
/convertir <ruta-del-archivo>

Pasos:
1. Verificar que el archivo existe.
2. Determinar tipo y carpeta de destino según tabla del skill markitdown.
3. Ejecutar conversión.
4. Confirmar ruta del `.md` generado.
5. Si es un input nuevo al pipeline, registrar en `architecture-log.md`.
