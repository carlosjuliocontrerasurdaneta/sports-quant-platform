# Sistema de Skills e instrucciones

Esta referencia contiene los controles especializados para Skills, prompts persistentes, agentes, loops, comandos, routing y archivos equivalentes.

---

## Sistema de Skills e instrucciones

Cuando el proyecto disponga de Skills, prompts persistentes, agentes, loops, comandos, routing u otros archivos que gobiernen el comportamiento de asistentes o automatizaciones, revisarlos como parte del proyecto.

Inventariar primero las Skills existentes y sus relaciones relevantes.

Revisar:

- estructura y ubicación de cada Skill;
- validez del frontmatter o metadatos equivalentes;
- coherencia entre nombre, descripción y propósito;
- condiciones o frases de activación;
- triggers demasiado amplios, demasiado estrechos o ambiguos;
- solapamientos y conflictos entre Skills;
- responsabilidades duplicadas o Skills redundantes;
- contradicciones internas;
- contradicciones con instrucciones de mayor prioridad aplicables al proyecto;
- referencias a archivos, agentes, loops, comandos, herramientas o recursos inexistentes;
- dependencias circulares o delegación circular;
- instrucciones obsoletas o incompatibles con la estructura actual del proyecto;
- límites de autorización para lectura, modificación y operaciones externas;
- criterios de salida, validación y finalización;
- coherencia entre Skill, routing, loop y consumidor real cuando exista esa arquitectura.

No asumir que una herramienta, agente, loop, comando o capacidad existe únicamente porque aparezca nombrado. Verificar su existencia o clasificarla como no verificable.

No reportar como defecto una preferencia de estilo o redacción sin efecto demostrable sobre activación, ejecución, seguridad, cobertura, trazabilidad o mantenibilidad.

Si el proyecto no utiliza un sistema de Skills o instrucciones equivalente, clasificar esta área como `NO_APLICABLE`.
