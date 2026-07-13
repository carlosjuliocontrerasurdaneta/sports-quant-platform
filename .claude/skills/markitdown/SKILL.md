---
name: markitdown
description: >
  Convierte documentos a Markdown usando Microsoft MarkItDown cuando el usuario
  lo pide explícitamente ("convierte a Markdown", "usa MarkItDown", "importa
  este documento como Markdown") o cuando se necesita ingestar documentación
  (PDF/DOCX/XLSX/PPTX/HTML) como texto plano trazable para un pipeline. NO usar
  para lectura o análisis normal de archivos: Claude lee PDFs e imágenes de
  forma nativa y existen skills dedicados (pdf, docx, xlsx, pptx) con mayor
  fidelidad.
---

# MarkItDown

## Cuándo usar (y cuándo no)

Usar SOLO cuando:
- El usuario pide explícitamente conversión a Markdown o menciona MarkItDown.
- Se ingesta documentación al proyecto y se necesita una versión Markdown
  trazable (ej. `docs/` del repositorio SQP).
- Hay que extraer texto masivo de varios documentos Office/HTML para procesarlo
  como texto.

NO usar cuando:
- El usuario solo quiere leer, resumir o analizar un archivo: usar la lectura
  nativa (visión para imágenes/PDF) o los skills pdf/docx/xlsx/pptx, que
  preservan mejor la estructura.
- El archivo es una imagen o un PDF escaneado con contenido visual relevante:
  la conversión pierde información que la visión nativa sí captura.

## Instalación

```bash
pip install 'markitdown[all]' --break-system-packages
```

Nota: la transcripción de audio (.mp3, .wav) requiere dependencias adicionales
de reconocimiento de voz que pueden no estar disponibles; si fallan, informarlo
y no fingir la transcripción.

## Flujo

1. Verificar que el formato es compatible (PDF, DOCX, XLSX, PPTX, HTML, XML,
   CSV, JSON, TXT, imágenes con OCR limitado).
2. Convertir: `markitdown archivo.ext > archivo.md` (o vía API de Python).
3. Conservar siempre el archivo original; nunca modificarlo ni reemplazarlo.
4. Registrar trazabilidad: nombre de origen, fecha de conversión y herramienta.
5. Si la conversión falla: mostrar el error, indicar la causa si está
   disponible y detener la conversión (el análisis puede continuar con la
   lectura nativa del original).
6. Nunca fabricar contenido que no se extrajo; reportar huecos de extracción.

## Salida

```text
Archivo recibido: informe.pdf
✓ Conversión completada → informe.md
Fuente Markdown generada; original conservado.
```
