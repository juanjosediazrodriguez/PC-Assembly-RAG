"""
Construye el catálogo limpio de hardware a partir de los CSVs crudos de PCPartPicker.

Entrada:  data/raw/specs/*.csv (8 CSVs + correcciones_ram_lga1700.csv)
Salida:   data/processed/hardware_catalog.json

Correcciones que aplica:
1. Tamaño de placa madre: se toma del nombre, porque la columna `size` del CSV
   marca como "ATX" a la mayoría de placas Micro ATX.
2. Tipo de RAM de la placa madre: el CSV no trae esta columna. Se deduce por el
   nombre (si dice DDR3/DDR4/D4/DDR5/D5) o por el socket. Para LGA 1700, que
   existe en DDR4 y DDR5, se usa el archivo de correcciones hecho por el equipo.
3. Se eliminan registros con errores conocidos en el dataset.

Uso:
    python scripts/build_catalog.py
"""

import json
import re
from pathlib import Path

import pandas as pd

# Rutas relativas a la raíz del repositorio
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CRUDOS = RAIZ / "data" / "raw" / "specs"
ARCHIVO_CORRECCIONES_RAM = CARPETA_CRUDOS / "correcciones_ram_lga1700.csv"
ARCHIVO_SALIDA = RAIZ / "data" / "processed" / "hardware_catalog.json"

# Registros con errores conocidos que se eliminan del catálogo
NOMBRES_EXCLUIDOS = {
    # Chipset A620 es de AMD (socket AM5), pero el dataset lo marca como LGA 1700
    "Biostar A620MT Micro ATX LGA1700 Motherboard (A620MT)",
}

# Tipo de RAM según socket, para los sockets que solo soportan una generación
RAM_POR_SOCKET = {
    "AM3": "DDR3",
    "AM4": "DDR4",
    "AM5": "DDR5",
    "LGA 1151": "DDR4",
    "LGA 1200": "DDR4",
    "X399": "DDR4",
    "TRX40": "DDR4",
}

# Sockets donde la RAM deducida solo por el socket puede estar mal: LGA 1151 tiene
# placas DDR3 cuyo nombre no lo dice. Esas placas quedan con confianza "media".
SOCKETS_RAM_AMBIGUA = {"LGA 1151"}

# Columnas que se conservan por componente y su nombre final (según docs/contratos.md)
COLUMNAS = {
    "cpu": {
        "archivo": "CPU.csv",
        "columnas": {
            "name": "name", "brand": "brand", "socket": "socket", "speed": "speed",
            "coreCount": "core_count", "threadCount": "thread_count", "power": "power",
        },
    },
    "motherboard": {
        "archivo": "Motherboard.csv",
        "columnas": {"name": "name", "brand": "brand", "socket": "socket", "size": "size"},
    },
    "gpu": {
        "archivo": "GPU.csv",
        "columnas": {
            "name": "name", "brand": "brand", "VRAM": "vram",
            "resolution": "resolution", "power": "power",
        },
    },
    "memory": {
        "archivo": "Memory.csv",
        "columnas": {"name": "name", "type": "type", "size": "size"},
    },
    "storage": {
        "archivo": "Storage.csv",
        "columnas": {"name": "name", "type": "type", "space": "space"},
    },
    "cooler": {
        "archivo": "Cooler.csv",
        "columnas": {"name": "name", "type": "type"},
    },
    "psu": {
        "archivo": "PSU.csv",
        "columnas": {"name": "name", "power": "power", "size": "size"},
    },
    "case": {
        "archivo": "Case.csv",
        "columnas": {"name": "name", "size": "size"},
    },
}

# Valores permitidos por campo (según docs/contratos.md)
VALORES_PERMITIDOS = {
    "socket": {"LGA 1151", "LGA 1200", "LGA 1700", "AM3", "AM4", "AM5", "X399", "TRX40"},
    "size_placa": {"ATX", "MicroATX", "ITX"},
    "memory_type": {"DDR3", "DDR4", "DDR5"},
    "cooler_type": {"air", "liquid"},
    "storage_type": {"NVME", "SATA", "HDD"},
    "psu_size": {"ATX", "SFX"},
}


def inferir_tamano_placa(nombre: str) -> str:
    """Saca el factor de forma de la placa desde su nombre comercial."""
    if "ITX" in nombre:
        return "ITX"
    if "Micro ATX" in nombre:
        return "MicroATX"
    return "ATX"


def inferir_ram_por_nombre(nombre: str) -> str | None:
    """Busca el tipo de RAM escrito en el nombre de la placa (DDR3, D3, DDR4, D4, DDR5, D5...).

    El sufijo "D3" solo se toma como DDR3 fuera de Gigabyte: en Gigabyte "D3" es una
    gama de producto (Z370P D3, GA-Z270P-D3, D3H) y no indica el tipo de memoria.
    """
    sufijo_d3 = re.search(r"\bD3\b", nombre) and not nombre.startswith("Gigabyte")
    if "DDR3" in nombre or sufijo_d3:
        return "DDR3"
    if "DDR4" in nombre or re.search(r"\bD4\b", nombre):
        return "DDR4"
    if "DDR5" in nombre or re.search(r"\bD5\b", nombre):
        return "DDR5"
    return None


def cargar_correcciones_ram() -> dict[str, tuple[str, str]]:
    """Carga el CSV de correcciones de RAM: nombre -> (tipo de RAM, confianza)."""
    correcciones = pd.read_csv(ARCHIVO_CORRECCIONES_RAM)
    return {
        fila["name"]: (fila["memory_type"], "alta" if fila["confianza"] == "alta" else "media")
        for _, fila in correcciones.iterrows()
    }


def inferir_ram_placa(
    nombre: str, socket: str, correcciones: dict[str, tuple[str, str]]
) -> tuple[str, str]:
    """Decide el tipo de RAM de una placa y qué tan confiable es el dato.

    Prioridad: nombre > correcciones > socket. Retorna (tipo, confianza), donde la
    confianza es "alta" o "media". Es "media" cuando viene de una corrección con
    confianza media o del socket LGA 1151, que tiene placas DDR3 sin marca en el nombre.
    """
    por_nombre = inferir_ram_por_nombre(nombre)
    if por_nombre:
        return por_nombre, "alta"
    if nombre in correcciones:
        return correcciones[nombre]
    if socket in RAM_POR_SOCKET:
        confianza = "media" if socket in SOCKETS_RAM_AMBIGUA else "alta"
        return RAM_POR_SOCKET[socket], confianza
    raise ValueError(f"No se pudo deducir la RAM de la placa: {nombre} ({socket})")


def cargar_componente(tipo: str) -> pd.DataFrame:
    """Lee el CSV de un componente y deja solo las columnas del contrato."""
    config = COLUMNAS[tipo]
    df = pd.read_csv(CARPETA_CRUDOS / config["archivo"])
    df = df[list(config["columnas"].keys())].rename(columns=config["columnas"])
    df = df[~df["name"].isin(NOMBRES_EXCLUIDOS)]
    df = df.dropna().drop_duplicates(subset="name")
    return df.reset_index(drop=True)


def procesar_placas(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica las correcciones de tamaño (error 1) y tipo de RAM (error 2)."""
    correcciones = cargar_correcciones_ram()
    df["size"] = df["name"].apply(inferir_tamano_placa)
    ram = df.apply(
        lambda fila: inferir_ram_placa(fila["name"], fila["socket"], correcciones), axis=1
    )
    df["memory_type"] = ram.str[0]
    df["memory_type_confianza"] = ram.str[1]
    return df


def validar_valores(catalogo: dict[str, pd.DataFrame]) -> None:
    """Revisa que todos los valores categóricos estén dentro de lo permitido por el contrato."""
    revisiones = [
        ("cpu", "socket", "socket"),
        ("motherboard", "socket", "socket"),
        ("motherboard", "size", "size_placa"),
        ("motherboard", "memory_type", "memory_type"),
        ("memory", "type", "memory_type"),
        ("case", "size", "size_placa"),
        ("cooler", "type", "cooler_type"),
        ("storage", "type", "storage_type"),
        ("psu", "size", "psu_size"),
    ]
    for tipo, columna, regla in revisiones:
        invalidos = set(catalogo[tipo][columna]) - VALORES_PERMITIDOS[regla]
        if invalidos:
            raise ValueError(f"Valores inválidos en {tipo}.{columna}: {invalidos}")


def construir_catalogo() -> dict[str, list[dict]]:
    """Ejecuta todo el proceso y retorna el catálogo listo para guardar."""
    catalogo = {tipo: cargar_componente(tipo) for tipo in COLUMNAS}
    catalogo["motherboard"] = procesar_placas(catalogo["motherboard"])
    validar_valores(catalogo)
    return {tipo: df.to_dict(orient="records") for tipo, df in catalogo.items()}


def main() -> None:
    catalogo = construir_catalogo()
    ARCHIVO_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as archivo:
        json.dump(catalogo, archivo, ensure_ascii=False, indent=2)

    print(f"Catálogo guardado en {ARCHIVO_SALIDA.relative_to(RAIZ)}")
    for tipo, registros in catalogo.items():
        print(f"  {tipo:<12} {len(registros):>5} registros")


if __name__ == "__main__":
    main()
