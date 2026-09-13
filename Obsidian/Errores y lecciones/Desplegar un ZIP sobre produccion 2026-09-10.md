# Desplegar un ZIP sobre producción se lleva lo que `.gitignore` excluye

**Fecha**: 2026-09-10 · **Coste**: un run diario perdido y dos días de dudas
sobre qué estaba pasando.

## Qué pasó

El paquete de optimización se desplegó sobre `C:\dev\3\sports-quant-platform`,
que **es** el directorio al que apuntan las 5 tareas del Programador. El ZIP se
construye excluyendo lo que `.gitignore` excluye — por buenas razones: no
distribuir datos privados ni la clave de API. La consecuencia no buscada es que
el directorio quedó con el código nuevo y **sin el estado que ese código
necesita**: `data/` con 2 `.gitkeep` y sin `.env`.

`SQP_Diario_Completo_Cdev` falló a las 12:00:01 con `Último resultado: 1`.

## Por qué ningún control lo impidió

`DIARIO_COMPLETO.bat` tiene un guard de árbol limpio precisamente para que
producción no ejecute código sin registrar. Falla ABIERTO por diseño —«no se
puede comprobar» no es «está sucio»— y una extracción de ZIP **no trae `.git`**,
así que el guard se saltaba en cada ejecución. `IMPLEMENTACION.md` ofrecía ese
guard como garantía de integración. La garantía no existía en el formato
entregado.

## Lecciones

1. **Un guard que falla abierto no protege el escenario en que su premisa
   desaparece.** Aquí la premisa era «hay un repositorio git»; el despliegue por
   ZIP la elimina, y es justo el despliegue más arriesgado.
2. **Distribuir por ZIP y desplegar por ZIP son cosas distintas.** El parche
   (`OPTIMIZATION.diff`) se aplica sobre un checkout con Git, que conserva el
   estado no versionado. Extraer el ZIP encima es lo que lo borra.
3. **Antes de desplegar: copia de `data/` y `.env`.** Ya está escrito en
   `IMPLEMENTACION.md` desde hoy.
4. Durante la auditoría escribí que el árbol «parece un paquete entregado, no la
   copia de trabajo de producción» y lo registré como limitación de alcance. Era
   una **inferencia sin comprobar**, y comprobarla costaba una consulta
   (`schtasks /query ... | Iniciar en`). Un dato de inventario que cambia la
   severidad de todo lo demás merece verificarse, no suponerse.

Relacionado: [[Bitácora/2026-09-10]], AUD-MED-019.
