# Manual de inventario

## Reserva

Una reserva solo es posible si la cantidad solicitada es positiva y no supera las unidades disponibles. `puede_reservar` usa `unidades_disponibles` para consultar los lotes activos del SKU.

## Recuento

El equipo revisa los lotes activos cada lunes. Los lotes inactivos no se cuentan como unidades disponibles.

## Entrega

La etiqueta contiene el número de pedido y el nombre del destinatario. Se imprime al preparar la entrega; este ejemplo no realiza el transporte.
