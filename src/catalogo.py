"""
Acceso al catálogo de hardware (data/processed/hardware_catalog.json).

Lo usan la interfaz (selectores de piezas) y las pruebas de extremo a extremo para
armar una ConfiguracionPC a partir de los nombres exactos de las piezas.

Requisito: generar antes el catálogo con `python scripts/build_catalog.py`.
"""

import json
from pathlib import Path

from src.esquemas import ConfiguracionPC

RUTA_CATALOGO = Path(__file__).resolve().parent.parent / "data" / "processed" / "hardware_catalog.json"

# Tipos de pieza que componen una ConfiguracionPC (mismos nombres que sus campos)
TIPOS_PIEZA = ("cpu", "motherboard", "gpu", "memory", "storage", "cooler", "psu", "case")


def cargar_catalogo(ruta: Path = RUTA_CATALOGO) -> dict[str, list[dict]]:
    """Lee el catálogo: un diccionario tipo de pieza -> lista de piezas."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe el catálogo en {ruta}. Genéralo con: python scripts/build_catalog.py"
        )
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def nombres_por_tipo(catalogo: dict[str, list[dict]]) -> dict[str, list[str]]:
    """Nombres de las piezas de cada tipo, ordenados, para llenar los selectores de la interfaz."""
    return {tipo: sorted(pieza["name"] for pieza in catalogo[tipo]) for tipo in TIPOS_PIEZA}


def construir_configuracion(
    catalogo: dict[str, list[dict]], **nombres: str
) -> ConfiguracionPC:
    """Arma una ConfiguracionPC buscando cada pieza por su nombre exacto.

    Uso: construir_configuracion(catalogo, cpu="...", motherboard="...", gpu="...",
    memory="...", storage="...", cooler="...", psu="...", case="...").
    Lanza ValueError si falta un tipo o si un nombre no está en el catálogo.
    """
    faltantes = [tipo for tipo in TIPOS_PIEZA if tipo not in nombres]
    sobrantes = [tipo for tipo in nombres if tipo not in TIPOS_PIEZA]
    if faltantes or sobrantes:
        raise ValueError(f"Tipos de pieza faltantes: {faltantes}; desconocidos: {sobrantes}")

    piezas = {}
    for tipo in TIPOS_PIEZA:
        encontradas = [p for p in catalogo[tipo] if p["name"] == nombres[tipo]]
        if not encontradas:
            raise ValueError(f"La pieza '{nombres[tipo]}' no está en el catálogo de {tipo}")
        piezas[tipo] = encontradas[0]
    return ConfiguracionPC.model_validate(piezas)
