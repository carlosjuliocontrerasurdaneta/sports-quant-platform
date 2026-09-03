# Informe consolidado

## Contenidos

- Resumen ejecutivo
- Inventario
- Matriz de cobertura
- Hallazgos confirmados
- Hallazgos inferidos
- Hallazgos no verificables
- Detecciones por herramientas pendientes
- Falsos positivos descartados
- Validaciones
- Plan priorizado
- Limpieza y racionalización
- Riesgos pendientes

---
# Informe consolidado

Entregar obligatoriamente:

## 1. Resumen ejecutivo

- propósito;
- arquitectura;
- estado general;
- riesgos principales;
- conclusión;
- limitaciones.

## 2. Inventario

- componentes;
- tecnologías;
- puntos de entrada;
- dependencias;
- datos;
- pruebas;
- infraestructura;
- integraciones;
- áreas especiales.

## 3. Matriz de cobertura

Para cada área:

- prioridad;
- estado;
- componentes;
- método;
- validación;
- limitaciones.

## 4. Hallazgos confirmados

Ordenar por:

1. `CRITICAL`
2. `HIGH`
3. `MEDIUM`
4. `LOW`

## 5. Hallazgos inferidos

Mantenerlos separados de los confirmados.

## 6. Hallazgos no verificables

Indicar:

- qué falta;
- por qué impide verificar;
- qué evidencia sería necesaria.

## 7. Hallazgos detectados por herramientas pendientes de validación

No mezclarlos con defectos confirmados.

## 8. Falsos positivos descartados

Incluir los casos relevantes y la evidencia que los refutó.

## 9. Validaciones

Para cada comando:

- comando exacto;
- propósito;
- resultado;
- fallos;
- efectos observados;
- limitaciones.

## 10. Plan priorizado

Relacionar cada acción con:

- IDs;
- archivos;
- riesgos;
- pruebas;
- criterio de aceptación;
- orden.

## 11. Limpieza y racionalización

Cuando existan candidatos de limpieza, entregar una tabla separada con:

- ID;
- ruta;
- categoría;
- evidencia;
- tamaño o impacto cuando sea relevante;
- reemplazo o fuente canónica;
- riesgo;
- decisión propuesta: `CONSERVAR` o `PROPONER_ELIMINACIÓN`;
- validación requerida.

No incluir elementos `NO_VERIFICABLE` como eliminaciones recomendadas.

## 12. Riesgos pendientes

Indicar problemas que no puedan corregirse o verificarse y explicar la causa.
