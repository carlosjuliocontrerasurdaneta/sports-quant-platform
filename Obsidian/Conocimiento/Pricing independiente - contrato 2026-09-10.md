# Pricing independiente — contrato 2026-09-10

El nuevo modo es opcional y offline. Una copia inmutable de los parámetros
deportivos, su versión y procedencia declarada produce un modelo antes de leer
precios. El freeze se persiste y queda identificado por SHA-256.

El mismo modelo admite distintas líneas posteriores; cambiar la cuota no cambia
las probabilidades. Los pushes devuelven stake, los cuartos se dividen entre
líneas adyacentes y EV se calcula como retorno esperado por unidad. No-vig exige
contrapartes del mismo book, mercado, línea normalizada, instante y fuente.

El motor recibe medias/sigmas o tasas ya estimadas; no obtiene por sí mismo
estadísticas avanzadas ni demuestra calibración. Count modela tiempo reglamentario;
no inventa OT. Normal usa corrección de continuidad para pushes y no proporciona
una distribución conjunta de marcadores. El output no asigna dinero.

Esto no cambia la política vigente que combina modelo y mercado en el diario.
No reemplaza los gates ni el ledger. Detalles técnicos en
`docs/INDEPENDENT-PRICING.md`; evidencia y límites en
`audit/optimization-20260910/VALIDATION.md`. Sesión: [[Bitácora/2026-09-10]].
