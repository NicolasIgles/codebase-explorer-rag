# Corrección de etiqueta en la evaluación reservada

La primera versión de `evaluacion/eval_heldout/casos.json` trataba «¿Qué pasarela autoriza las tarjetas de crédito?» como pregunta sin respuesta. Al revisar la respuesta híbrida, observamos que `evaluacion/eval_heldout/docs/operacion.txt` dice explícitamente que este proyecto no procesa cobros. La respuesta «Ninguna: el proyecto no registra datos de pago ni procesa cobros» cita esa fuente y está respaldada. La etiqueta inicial era incorrecta.

Se conserva la primera ejecución en `evaluacion/resultados/evaluacion_holdout_v1.json`. En la versión actual, `sin_pago` se cuenta como pregunta respondible y se agregó `sin_garantia` como negativa. No cambiaron las reglas de recuperación ni los prompts; cualquier variación entre ejecuciones puede deberse al modelo. Este conjunto ya fue inspeccionado durante el desarrollo y no debe presentarse como evaluación ciega futura.
