"""Preparación de entregas del inventario de muestra."""


def etiqueta_entrega(pedido: dict) -> str:
    """Forma una etiqueta de envío con número de pedido y destinatario."""
    return f"Pedido {pedido['numero']} para {pedido['destinatario']}"
