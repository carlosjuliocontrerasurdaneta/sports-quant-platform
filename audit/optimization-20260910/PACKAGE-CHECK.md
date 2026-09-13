# Comprobación del paquete

Ejecutada por Codex el 2026-09-10 en una extracción nueva del ZIP, fuera del
checkout de desarrollo. La carpeta extraída no contenía entorno virtual ni `.git`.

Comando utilizado desde la extracción:

```bash
python3 scripts/setup_local.py --verify
```

Resultado real: **exit 0**, mensaje final `READY`.

| Etapa | Resultado |
|---|---|
| Creación de `.venv` | Completada con Python 3.12.14 |
| Instalación editable mediante pip y constraints | Completada desde `requirements.lock` |
| `pip check` | No broken requirements found |
| Ruff | All checks passed |
| MyPy | Sin errores en 101 archivos fuente |
| Pytest sobre archivos extraídos | 1929 aprobadas, 2 omitidas; 41.95 s; exit 0 |

Omisiones preexistentes, sin añadir skips nuevos:

- `tests/test_codex_review.py:1780`: el shim de npm solo existe en Windows.
- `tests/test_review_v2.py:228`: severity es un enum cerrado, no texto libre.

También se verificó que `OPTIMIZATION.diff` pasa `git apply --check` sobre una
copia limpia del commit base. La integridad ZIP se comprobó mediante CRC.
`BUILD_INFO.json` contiene hashes SHA-256 para todos los archivos fuente y el parche.

Pruebas de fechas adicionales con `TZ=UTC`: 57 aprobadas, exit 0. La suite completa
también pasó con `TZ=Asia/Jakarta`, la zona del proceso de prueba original.

La demostración independiente utiliza cuatro cuotas sintéticas: se verificó que
el modelo persistido coincide con el modelo del informe, que las cuatro filas
tienen contrapartes compatibles, que no hay rechazos y que todos los stakes son cero.

No se ejecutó Windows/cmd.exe. El instalador Python y la demostración CLI se
ejecutaron realmente en Linux; los BAT se verificaron por contrato estático.
No se distribuyen `.git`, `.venv`, cachés de pruebas, `.env` operativo ni estado
privado. `requirements.lock` se conserva byte a byte respecto del commit base.

Las incorporaciones posteriores a la prueba de extracción son registros de esta
validación y notas de la sesión; se verifica que el código, BAT y configuración
del ZIP final coincidan con los probados.
