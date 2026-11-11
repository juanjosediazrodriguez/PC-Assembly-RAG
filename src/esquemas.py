"""
Modelos de datos compartidos entre los 4 módulos de PC-Assembly-RAG.

Este archivo es la versión en código de docs/contratos.md. Cualquier cambio aquí
debe reflejarse también en el contrato, discutirse en equipo y enviarse en su
propio Pull Request con el título `docs(contratos): descripción del cambio`.
"""

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 1. Convenciones generales (contratos.md, sección 1)
# ---------------------------------------------------------------------------

SocketType = Literal[
    "LGA 1151", "LGA 1200", "LGA 1700",
    "AM3", "AM4", "AM5", "X399", "TRX40",
]
FormFactor = Literal["ATX", "MicroATX", "ITX"]
MemoryType = Literal["DDR3", "DDR4", "DDR5"]
CoolerType = Literal["air", "liquid"]
StorageType = Literal["NVME", "SATA", "HDD"]
PSUSize = Literal["ATX", "SFX"]


# ---------------------------------------------------------------------------
# 2. Entidad central: ConfiguracionPC (contratos.md, sección 2)
# ---------------------------------------------------------------------------

class CPU(BaseModel):
    name: str = Field(description="Nombre comercial completo")
    brand: Literal["Intel", "AMD"]
    socket: SocketType
    speed: float = Field(description="Frecuencia base en GHz")
    core_count: int
    thread_count: int
    power: int = Field(description="TDP o consumo en Watts")


class Motherboard(BaseModel):
    name: str
    brand: Literal["Intel", "AMD"]
    socket: SocketType
    size: FormFactor
    memory_type: MemoryType = Field(description="Generación de RAM soportada")
    memory_type_confianza: Literal["alta", "media"] = Field(
        default="alta",
        description="Confianza del tipo de RAM: 'media' si se dedujo por marca o por socket ambiguo",
    )


class GPU(BaseModel):
    name: str
    brand: Literal["NVIDIA", "AMD"]
    vram: int = Field(description="Memoria de video en GB")
    resolution: str
    power: int = Field(description="Consumo en Watts bajo carga")


class Memory(BaseModel):
    name: str
    type: MemoryType
    size: int = Field(description="Capacidad total en GB")


class Storage(BaseModel):
    name: str
    type: StorageType
    space: int = Field(description="Capacidad en GB")


class Cooler(BaseModel):
    name: str
    type: CoolerType


class PSU(BaseModel):
    name: str
    power: int = Field(description="Potencia nominal en Watts")
    size: PSUSize


class Case(BaseModel):
    name: str
    size: FormFactor


class ConfiguracionPC(BaseModel):
    cpu: CPU
    motherboard: Motherboard
    gpu: GPU
    memory: Memory
    storage: Storage
    cooler: Cooler
    psu: PSU
    case: Case


# ---------------------------------------------------------------------------
# 3. Módulo 1 — Validador de compatibilidad (contratos.md, sección 3)
# ---------------------------------------------------------------------------

class ErrorCompatibilidad(BaseModel):
    regla: Literal["socket", "memoria", "factor_forma", "potencia_psu"]
    mensaje: str
    componentes_afectados: list[str]


class ResultadoCompatibilidad(BaseModel):
    compatible: bool
    consumo_estimado_w: int
    potencia_recomendada_w: int
    errores: list[ErrorCompatibilidad]
    advertencias: list[str]  # Ej: PSU SFX en gabinete ATX (requiere adaptador)


# ---------------------------------------------------------------------------
# 4. Módulo 2 — Planificador con grafos (contratos.md, sección 4)
# ---------------------------------------------------------------------------

class PasoEnsamble(BaseModel):
    orden: int
    id_paso: str
    fase: Literal[
        "fuera_gabinete", "preparacion_gabinete", "montaje_chasis", "cableado_y_cierre"
    ]
    titulo: str
    descripcion_base: str
    componentes_involucrados: list[str]
    dependencias_previas: list[str]
    consulta_rag: str  # Query semántica EN INGLÉS lista para enviar al buscador de ChromaDB


# ---------------------------------------------------------------------------
# 5. Módulo 3 — Pipeline RAG y ChromaDB (contratos.md, sección 5)
# ---------------------------------------------------------------------------

class FragmentoManual(BaseModel):
    chunk_id: str
    manual_id: str
    pagina: int  # Índice de la página en el PDF (base 1)
    pagina_etiqueta: str = ""  # Numeración impresa del manual, ej. "1-6"
    seccion: str
    texto: str
    distancia: float  # Similitud calculada por ChromaDB (menor = más relevante)


# ---------------------------------------------------------------------------
# 6. Módulo 4 — Generador con LLM (contratos.md, sección 6)
# ---------------------------------------------------------------------------

class PasoConContexto(BaseModel):
    paso: PasoEnsamble
    fragmentos_rag: list[FragmentoManual]


class ManualFinal(BaseModel):
    compatible: bool
    resumen_compatibilidad: ResultadoCompatibilidad
    total_pasos: int
    manual_markdown: str  # Texto en Markdown listo para renderizar en Streamlit
    citas_manuales: list[dict]  # Lista de evidencias con manual_id y página
