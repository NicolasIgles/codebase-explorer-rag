"""Proyecto independiente reservado para evaluar recuperación."""


def unidades_disponibles(productos: list[dict], sku: str) -> int:
    """Suma las unidades de lotes activos para un SKU."""
    return sum(
        lote["unidades"] for lote in productos
        if lote["sku"] == sku and lote["activo"]
    )


def puede_reservar(productos: list[dict], sku: str, cantidad: int) -> bool:
    """Permite reservar una cantidad positiva que no supera las existencias."""
    return cantidad > 0 and unidades_disponibles(productos, sku) >= cantidad
