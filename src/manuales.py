"""
Mapa de manuales: que manual cubre que pieza del catalogo.

Lee data/processed/manuales.json. Lo usan la ingesta (para asignar manual_id y
tipo de componente a cada PDF) y el generador (para pedir al buscador solo los
fragmentos del manual de la pieza). Vive en src/ junto a catalogo.py, y no en
src/rag/, para no cargar ChromaDB cuando solo se necesita el mapa.
"""

import json
from pathlib import Path

RUTA_MANUALES = Path(__file__).resolve().parent.parent / "data" / "processed" / "manuales.json"


def cargar_manuales(ruta: Path = RUTA_MANUALES) -> dict[str, dict]:
    """Lee el mapa: manual_id -> {archivo, componente_tipo, piezas}. Vacio si no existe."""
    if not ruta.exists():
        return {}
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def manual_id_de_pieza(nombre_pieza: str, ruta: Path = RUTA_MANUALES) -> str | None:
    """manual_id del manual que cubre la pieza, o None si no hay manual para ella."""
    for manual_id, datos in cargar_manuales(ruta).items():
        if nombre_pieza in datos.get("piezas", []):
            return manual_id
    return None


def manual_por_archivo(nombre_archivo: str, ruta: Path = RUTA_MANUALES) -> tuple[str, str] | None:
    """(manual_id, componente_tipo) del PDF dado, o None si no esta en el mapa."""
    for manual_id, datos in cargar_manuales(ruta).items():
        if datos.get("archivo") == nombre_archivo:
            return manual_id, datos.get("componente_tipo", "general")
    return None
