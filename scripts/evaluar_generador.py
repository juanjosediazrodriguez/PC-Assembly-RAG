"""
Evaluación del generador del manual con el modelo real (issue #23).

Genera el manual de 10 configuraciones compatibles con el modelo configurado en `.env`,
guarda las salidas y calcula métricas automáticas. Nada de lo que sale de aquí reemplaza
la revisión humana: el script solo marca sospechosos y prepara la hoja de revisión.

Qué hace
--------
1. Indexa el PDF del repo en una ChromaDB temporal (reproducible; no usa data/vectorstore).
2. Para cada configuración: valida compatibilidad, arma el plan y los pasos con contexto,
   y llama a `generar_manual` (el mismo camino que usa la interfaz).
3. Una "grabadora" sobre `redactar_paso` registra cada paso sin duplicar llamadas al modelo.
4. Calcula métricas por manual y globales, y escribe en
   data/processed/evaluacion_generador/<fecha-hora>/ (carpeta no versionada):
   - manual_<config>_r<n>.md     el manual generado
   - resultados.json             metadatos y registro por paso y por línea
   - resumen.md                  tabla de métricas y lista de sospechosos
   - muestra_revision.md         afirmaciones con cita para revisar a mano

Métricas automáticas (por manual y globales)
--------------------------------------------
- % de pasos con cita válida (entre los pasos que tienen manual).
- % de pasos en texto seguro ("no se pudo verificar").
- Citas inválidas (meta: 0), recomprobadas aquí de forma independiente.
- Pasos "sin manual" con pines, ranuras o cables específicos (meta: 0).
- Líneas del modelo sin ninguna cita (`validar_citas` no las detecta).
- Datos técnicos que no aparecen en el fragmento citado, y los que no aparecen en NADA de lo
  que el modelo recibió (sospechosos fuertes de invención).

Los datos técnicos se extraen con una expresión regular: es una heurística. Marca sospechosos
para revisar, no prueba por sí sola que haya una alucinación.

Uso:
    python scripts/evaluar_generador.py                  # 10 configuraciones, 1 corrida
    python scripts/evaluar_generador.py --solo 1,5       # solo algunas configuraciones
    python scripts/evaluar_generador.py --repeticiones 2 # mide la variación del modelo
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

from scripts.ingest_manuals import CARPETA_RAW, procesar_directorio  # noqa: E402
from src.catalogo import cargar_catalogo, construir_configuracion  # noqa: E402
from src.compatibilidad.validador import validar_compatibilidad  # noqa: E402
from src.llm import cargar_cliente, generar_manual  # noqa: E402
from src.llm import generador as gen  # noqa: E402
from src.pipeline import armar_pasos_con_contexto  # noqa: E402
from src.planificador.grafo import generar_plan_ensamble  # noqa: E402
from src.rag import buscador  # noqa: E402

CARPETA_SALIDA = RAIZ / "data" / "processed" / "evaluacion_generador"
SEMILLA_MUESTRA = 23  # número de la issue; fija la muestra de revisión

# ---------------------------------------------------------------------------
# Piezas reales del catálogo (nombres exactos; las mismas de tests/test_compatibilidad.py)
# ---------------------------------------------------------------------------
R5_7600X = "AMD Ryzen 5 7600X 4.7 GHz 6-Core Processor (100-100000593WOF)"
R5_5600X = "AMD Ryzen 5 5600X 3.7 GHz 6-Core Processor (100-100000065BOX)"
I5_13600K = "Intel Core i5-13600K 3.5 GHz 14-Core Processor (BX8071513600K)"
I5_12400 = "Intel Core i5-12400 2.5 GHz 6-Core Processor (BX8071512400)"
I7_9700K = "Intel Core i7-9700K 3.6 GHz 8-Core Processor (BX80684I79700K)"
PHENOM_965 = "AMD Phenom II X4 965 Black 3.4 GHz Quad-Core Processor (HDZ965FBGMBOX)"

B650_TUF = "Asus TUF GAMING B650-PLUS WIFI ATX AM5 Motherboard (TUF GAMING B650-PLUS WIFI)"  # única con manual
B550M_DS3H = "Gigabyte B550M DS3H Micro ATX AM4 Motherboard (B550M DS3H)"
Z790_ELITE = "Gigabyte Z790 AORUS ELITE AX ATX LGA1700 Motherboard (Z790 AORUS ELITE AX)"
B760M_DDR4 = "Gigabyte B760M DS3H DDR4 Micro ATX LGA1700 Motherboard (B760M DS3H DDR4)"
Z390_I = "Asus ROG STRIX Z390-I GAMING Mini ITX LGA1151 Motherboard (ROG STRIX Z390-I GAMING)"
M4A88TD = "Asus M4A88TD-V EVO/USB3 ATX AM3 Motherboard (M4A88TD-V EVO/USB3)"

RTX_4070 = "Asus TUF GAMING GeForce RTX 4070 12 GB Video Card (tuf-rtx4070-12g-gaming)"
RTX_3060 = "MSI GeForce RTX 3060 Ventus 2X 12G GeForce RTX 3060 12GB 12 GB Video Card (RTX3060Ventus2X12GOC)"
RX_6600 = "Gigabyte EAGLE Radeon RX 6600 8 GB Video Card (GV-R66EAGLE-8GD)"
GTX_1650 = "MSI D6 VENTUS XS OC GeForce GTX 1650 G6 4 GB Video Card (GTX 1650 D6 Ventus XS OC)"

DDR5_32GB = "Corsair Vengeance 32 GB (2 x 16 GB) DDR5-6000 CL36 Memory (CMK32GX5M2D6000C36)"
DDR4_16GB = "Corsair Vengeance LPX 16 GB (2 x 8 GB) DDR4-3200 CL16 Memory (CMK16GX4M2B3200C16)"
DDR3_8GB = "Corsair Vengeance 8 GB (2 x 4 GB) DDR3-1600 CL9 Memory (CMZ8GX3M2A1600C9)"

NVME_980PRO = "Samsung 980 Pro 1 TB M.2-2280 PCIe 4.0 X4 NVME Solid State Drive (MZ-V8P1T0B/AM)"
SATA_870EVO = 'Samsung 870 Evo 1 TB 2.5" Solid State Drive (MZ-77E1T0B/AM)'
HDD_BARRACUDA = 'Seagate BarraCuda 2 TB 3.5" 7200 RPM Internal Hard Drive (ST2000DM006)'

AIRE_212 = "Cooler Master Hyper 212 Black Edition 42 CFM CPU Cooler (RR-212S-20PK-R2)"
LIQUIDO_Z73 = "NZXT Kraken Z73 73.11 CFM Liquid CPU Cooler (RL-KRZ73-01)"

PSU_750_ATX = "Corsair RM750e (2023) 750 W 80+ Gold Certified Fully Modular ATX Power Supply (CP-9020262-NA)"
PSU_650_ATX = "Corsair CV650 650 W 80+ Bronze Certified ATX Power Supply (CP-9020236-NA)"
PSU_550_ATX = "Corsair CV550 550 W 80+ Bronze Certified ATX Power Supply (CP-9020210-NA)"
PSU_750_SFX = "Corsair SF750 750 W 80+ Platinum Certified Fully Modular SFX Power Supply (CP-9020186-NA)"
PSU_600_SFX = "Corsair SF600 600 W 80+ Platinum Certified Fully Modular SFX Power Supply (CP-9020182-NA)"

CASE_ATX_4000D = "Corsair 4000D Airflow ATX Mid Tower Case (CC-9011200-WW)"
CASE_ATX_H5 = "NZXT H5 Flow ATX Mid Tower Case (CC-H51FB-01)"
CASE_MATX_Q300L = "Cooler Master MasterBox Q300L MicroATX Mini Tower Case (MCB-Q300L-KANN-S00)"
CASE_ITX_NR200 = "Cooler Master MasterBox NR200 Mini ITX Desktop Case (MCB-NR200-KNNN-S00)"


def pc(cpu, motherboard, gpu, memory, storage, cooler, psu, case) -> dict[str, str]:
    return {
        "cpu": cpu, "motherboard": motherboard, "gpu": gpu, "memory": memory,
        "storage": storage, "cooler": cooler, "psu": psu, "case": case,
    }


# (id, descripción, piezas). 5 con la placa ASUS (hay manual) y 5 sin manual.
CONFIGURACIONES: list[tuple[int, str, dict[str, str]]] = [
    (1, "ASUS · NVMe · aire (ejemplo del contrato)",
     pc(R5_7600X, B650_TUF, RTX_4070, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_750_ATX, CASE_ATX_4000D)),
    (2, "ASUS · SATA · líquida",
     pc(R5_7600X, B650_TUF, RTX_4070, DDR5_32GB, SATA_870EVO, LIQUIDO_Z73, PSU_750_ATX, CASE_ATX_4000D)),
    (3, "ASUS · HDD · aire",
     pc(R5_7600X, B650_TUF, RTX_3060, DDR5_32GB, HDD_BARRACUDA, AIRE_212, PSU_650_ATX, CASE_ATX_H5)),
    (4, "ASUS · NVMe · líquida",
     pc(R5_7600X, B650_TUF, RTX_3060, DDR5_32GB, NVME_980PRO, LIQUIDO_Z73, PSU_750_ATX, CASE_ATX_H5)),
    (5, "ASUS · NVMe · aire · fuente SFX (con advertencia)",
     pc(R5_7600X, B650_TUF, RTX_3060, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_750_SFX, CASE_ATX_4000D)),
    (6, "Sin manual · AM4 B550M · HDD · aire",
     pc(R5_5600X, B550M_DS3H, RTX_3060, DDR4_16GB, HDD_BARRACUDA, AIRE_212, PSU_550_ATX, CASE_ATX_H5)),
    (7, "Sin manual · LGA 1700 Z790 · NVMe · líquida",
     pc(I5_13600K, Z790_ELITE, RTX_4070, DDR5_32GB, NVME_980PRO, LIQUIDO_Z73, PSU_750_ATX, CASE_ATX_4000D)),
    (8, "Sin manual · LGA 1700 B760M DDR4 · SATA · aire",
     pc(I5_12400, B760M_DDR4, RX_6600, DDR4_16GB, SATA_870EVO, AIRE_212, PSU_550_ATX, CASE_MATX_Q300L)),
    (9, "Sin manual · LGA 1151 ITX · NVMe · aire",
     pc(I7_9700K, Z390_I, GTX_1650, DDR4_16GB, NVME_980PRO, AIRE_212, PSU_600_SFX, CASE_ITX_NR200)),
    (10, "Sin manual · AM3 DDR3 · HDD · aire",
     pc(PHENOM_965, M4A88TD, GTX_1650, DDR3_8GB, HDD_BARRACUDA, AIRE_212, PSU_550_ATX, CASE_ATX_4000D)),
]

# ---------------------------------------------------------------------------
# Datos técnicos (heurística)
# ---------------------------------------------------------------------------
# Datos que un modelo suele inventar: pines, nombres de cabezales y ranuras, longitudes M.2, unidades.
PATRON_TECNICO = re.compile(
    r"(?i:\b\d+(?:-\d+)?\s*-?\s*pin(?:es)?\b)"        # 2-pin, 3-1 pin, 24 pines
    r"|(?i:\bpin(?:es)?\s+\d+(?:\s*(?:-|y|,)\s*\d+)*)"  # pin 1-2, pines 3 y 4
    r"|\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b"        # CPU_FAN, DIMM_A1, HDD_LED
    r"|\bM\.2(?:_\d)?"                                # M.2, M.2_1
    r"|\b[A-Z]{2,}\d+[A-Za-z0-9.]*"                   # DDR5, AM5
    r"|\b[A-Z]{4,}\b"                                 # PWRSW, RESET, SPEAKER
    r"|\b(?:2242|2260|2280|22110)\b"
    r"|\b\d+(?:[.,]\d+)?\s?(?:W|GB|MB|mm|cm|V|MHz)\b"
)
# Subconjunto para "pines, ranuras o cables específicos" en pasos sin manual.
PATRON_ESPECIFICO = re.compile(
    r"(?i:\b\d+(?:-\d+)?\s*-?\s*pin(?:es)?\b)"
    r"|(?i:\bpin(?:es)?\s+\d+(?:\s*(?:-|y|,)\s*\d+)*)"
    r"|\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b"
    r"|\bM\.2_\d"
)


def normalizar(texto: str) -> str:
    """Forma comparable: minúsculas, sin espacios, 'pines'->'pin', '2-pin'->'2pin', coma->punto."""
    t = texto.lower()
    t = re.sub(r"pines\b", "pin", t)
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"(\d)-pin", r"\1pin", t)
    return t.replace(",", ".")


def datos_tecnicos(frase: str, patron: re.Pattern = PATRON_TECNICO) -> set[str]:
    sin_citas = gen.PATRON_CITA.sub("", frase)
    return {normalizar(m.group(0)) for m in patron.finditer(sin_citas)}


def lineas_de(texto: str) -> list[str]:
    """Una línea por viñeta o párrafo, sin la marca de viñeta."""
    lineas = []
    for linea in texto.splitlines():
        limpia = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", linea).strip()
        if limpia:
            lineas.append(limpia)
    return lineas


def vio_el_modelo(paso_ctx) -> str:
    """Todo el texto que recibió el modelo para este paso, normalizado."""
    paso = paso_ctx.paso
    partes = [gen.recortar(f.texto, gen.MAX_PALABRAS_FRAGMENTO) for f in paso_ctx.fragmentos_rag]
    partes += [paso.titulo, paso.descripcion_base, *paso.componentes_involucrados]
    return normalizar(" ".join(partes))


# ---------------------------------------------------------------------------
# Evaluación de un paso
# ---------------------------------------------------------------------------
def evaluar_paso(paso_ctx, texto: str, usados: list, mensajes_log: list[str]) -> dict:
    paso, fragmentos = paso_ctx.paso, paso_ctx.fragmentos_rag
    tiene_manual = bool(fragmentos)
    texto_seguro = gen.TEXTO_NO_VERIFICADO in texto
    registro = {
        "id_paso": paso.id_paso,
        "orden": paso.orden,
        "titulo": paso.titulo,
        "tiene_manual": tiene_manual,
        "texto_seguro": texto_seguro,
        # Un texto que no termina en puntuación o cita suele estar cortado por max_tokens.
        "posible_truncado": tiene_manual
        and not texto_seguro
        and not re.search(r"[.!?)\]*_`»”\"]\s*$", texto.rstrip()),
        "texto": texto,
        "rechazos": sum("rechazado" in m for m in mensajes_log),
        "fallos_llamada": sum("Fallo la llamada" in m for m in mensajes_log),
        "citas": gen.etiquetas_citadas(texto),
        "citas_invalidas": gen.validar_citas(texto, fragmentos),
        "datos_especificos_sin_manual": [],
        "lineas": [],
    }

    if not tiene_manual:
        registro["datos_especificos_sin_manual"] = sorted(datos_tecnicos(texto, PATRON_ESPECIFICO))
        return registro
    if texto_seguro:
        return registro

    visto = vio_el_modelo(paso_ctx)
    for linea in lineas_de(texto):
        citas = gen.etiquetas_citadas(linea)
        citados = [f for f in fragmentos if gen.etiqueta_de(f) in citas]
        base_citada = normalizar(" ".join(gen.recortar(f.texto, gen.MAX_PALABRAS_FRAGMENTO) for f in citados))
        tokens = datos_tecnicos(linea)
        registro["lineas"].append({
            "texto": linea,
            "citas": citas,
            "con_cita": bool(citas),
            "datos": sorted(tokens),
            "fuera_del_fragmento": sorted(t for t in tokens if t not in base_citada),
            "fuera_del_contexto": sorted(t for t in tokens if t not in visto),
            "fragmentos_citados": [
                {
                    "etiqueta": gen.etiqueta_de(f),
                    "seccion": f.seccion,
                    "texto": gen.recortar(f.texto, gen.MAX_PALABRAS_FRAGMENTO),
                }
                for f in citados
            ],
        })
    return registro


# ---------------------------------------------------------------------------
# Corrida de una configuración con el modelo real
# ---------------------------------------------------------------------------
class Capturador(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.mensajes: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.mensajes.append(record.getMessage())


def correr_configuracion(cliente, modelo: str, catalogo: dict, cid: int, piezas: dict, rep: int) -> dict:
    config = construir_configuracion(catalogo, **piezas)
    compatibilidad = validar_compatibilidad(config)
    if not compatibilidad.compatible:
        raise RuntimeError(
            f"La configuración {cid} no es compatible: {[e.regla for e in compatibilidad.errores]}"
        )

    pasos = armar_pasos_con_contexto(generar_plan_ensamble(config))
    capturador = Capturador()
    logger = logging.getLogger("llm.generador")
    logger.addHandler(capturador)
    registros: list[dict] = []
    original = gen.redactar_paso

    def grabadora(cliente_, modelo_, paso_ctx):
        capturador.mensajes.clear()
        texto, usados = original(cliente_, modelo_, paso_ctx)
        registros.append(evaluar_paso(paso_ctx, texto, usados, list(capturador.mensajes)))
        return texto, usados

    def progreso(indice: int, total: int, titulo: str) -> None:
        print(f"    paso {indice + 1}/{total}: {titulo}", flush=True)

    gen.redactar_paso = grabadora  # generar_manual busca el nombre en el módulo en cada llamada
    try:
        manual = generar_manual(config, compatibilidad, pasos, cliente=cliente, modelo=modelo, progreso=progreso)
    finally:
        gen.redactar_paso = original
        logger.removeHandler(capturador)

    return {
        "config_id": cid,
        "repeticion": rep,
        "advertencias_compatibilidad": compatibilidad.advertencias,
        "manual_markdown": manual.manual_markdown,
        "pasos": registros,
    }


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def porcentaje(parte: int, total: int) -> float | None:
    return None if total == 0 else 100.0 * parte / total


def formato(valor: float | None) -> str:
    return "n/a" if valor is None else f"{valor:.0f} %"


def resumir(pasos: list[dict]) -> dict:
    con_manual = [p for p in pasos if p["tiene_manual"]]
    sin_manual = [p for p in pasos if not p["tiene_manual"]]
    seguros = [p for p in con_manual if p["texto_seguro"]]
    validos = [p for p in con_manual if not p["texto_seguro"] and p["citas"] and not p["citas_invalidas"]]
    lineas = [ln for p in con_manual if not p["texto_seguro"] for ln in p["lineas"]]
    return {
        "pasos": len(pasos),
        "pasos_con_manual": len(con_manual),
        "pasos_sin_manual": len(sin_manual),
        "pct_cita_valida": porcentaje(len(validos), len(con_manual)),
        "pct_texto_seguro": porcentaje(len(seguros), len(con_manual)),
        "pasos_posible_truncado": sum(1 for p in con_manual if p["posible_truncado"]),
        "citas_invalidas": sum(len(p["citas_invalidas"]) for p in pasos),
        "sin_manual_con_datos_especificos": sum(1 for p in sin_manual if p["datos_especificos_sin_manual"]),
        "lineas": len(lineas),
        "lineas_sin_cita": sum(1 for ln in lineas if not ln["con_cita"]),
        "lineas_con_datos_fuera_del_fragmento": sum(1 for ln in lineas if ln["fuera_del_fragmento"]),
        "lineas_con_datos_fuera_del_contexto": sum(1 for ln in lineas if ln["fuera_del_contexto"]),
        "rechazos": sum(p["rechazos"] for p in pasos),
        "fallos_llamada": sum(p["fallos_llamada"] for p in pasos),
    }


# ---------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------
def escribir_resumen(carpeta: Path, meta: dict, corridas: list[dict], descripciones: dict[int, str]) -> str:
    L = [
        "# Evaluación del generador del manual (issue #23)",
        "",
        f"- **Fecha:** {meta['fecha']}",
        f"- **Proveedor / modelo:** {meta['proveedor']} / `{meta['modelo']}`",
        f"- **Temperatura:** {meta['temperatura']} · **fragmentos por paso (top_k):** {meta['top_k']} "
        f"· **reintentos por paso:** {meta['max_reintentos']}",
        f"- **Corridas:** {len(corridas)} (repeticiones por configuración: {meta['repeticiones']})",
        "",
        "## Por manual",
        "",
        "| Config | Descripción | Pasos (con manual) | % cita válida | % texto seguro | Posible truncado | Citas inválidas "
        "| Sin manual con datos específicos | Líneas sin cita | Datos fuera del fragmento | Datos fuera del contexto | Reintentos |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    todos: list[dict] = []
    for c in corridas:
        r = resumir(c["pasos"])
        todos += c["pasos"]
        etiqueta = f"{c['config_id']}" + (f" (r{c['repeticion']})" if meta["repeticiones"] > 1 else "")
        L.append(
            f"| {etiqueta} | {descripciones[c['config_id']]} | {r['pasos']} ({r['pasos_con_manual']}) "
            f"| {formato(r['pct_cita_valida'])} | {formato(r['pct_texto_seguro'])} "
            f"| {r['pasos_posible_truncado']} | {r['citas_invalidas']} "
            f"| {r['sin_manual_con_datos_especificos']} | {r['lineas_sin_cita']}/{r['lineas']} "
            f"| {r['lineas_con_datos_fuera_del_fragmento']} | {r['lineas_con_datos_fuera_del_contexto']} "
            f"| {r['rechazos']} |"
        )
    g = resumir(todos)
    L += [
        "",
        "## Total",
        "",
        f"- Pasos: {g['pasos']} ({g['pasos_con_manual']} con manual, {g['pasos_sin_manual']} sin manual)",
        f"- **% de pasos con cita válida:** {formato(g['pct_cita_valida'])}",
        f"- **% de pasos en texto seguro:** {formato(g['pct_texto_seguro'])}",
        f"- **Pasos con posible truncado (el texto termina a mitad de frase):** {g['pasos_posible_truncado']} "
        f"de {g['pasos_con_manual']} con manual",
        f"- **Citas inválidas (meta 0):** {g['citas_invalidas']}",
        f"- **Pasos 'sin manual' con pines/ranuras/cables específicos (meta 0):** {g['sin_manual_con_datos_especificos']}",
        f"- Líneas del modelo sin cita: {g['lineas_sin_cita']} de {g['lineas']}",
        f"- Líneas con datos técnicos fuera del fragmento citado: {g['lineas_con_datos_fuera_del_fragmento']}",
        f"- **Líneas con datos técnicos fuera de todo lo que recibió el modelo (sospechosos fuertes):** "
        f"{g['lineas_con_datos_fuera_del_contexto']}",
        f"- Reintentos por citas inválidas: {g['rechazos']} · llamadas fallidas: {g['fallos_llamada']}",
        "",
        "> Los datos técnicos se detectan con una expresión regular: es una heurística. Cada sospechoso "
        "debe revisarse a mano; no es una prueba de alucinación por sí solo.",
    ]

    sospechosos, sin_cita, especificos = [], [], []
    for c in corridas:
        for p in c["pasos"]:
            for ln in p["lineas"]:
                donde = f"config {c['config_id']} · paso {p['orden']} ({p['id_paso']})"
                if ln["fuera_del_contexto"]:
                    sospechosos.append(f"- {donde}: `{ln['fuera_del_contexto']}` en «{ln['texto']}»")
                if not ln["con_cita"]:
                    sin_cita.append(f"- {donde}: «{ln['texto']}»")
            if p["datos_especificos_sin_manual"]:
                especificos.append(
                    f"- config {c['config_id']} · paso {p['orden']} ({p['id_paso']}): "
                    f"`{p['datos_especificos_sin_manual']}` en «{p['texto']}»"
                )
    L += ["", "## Sospechosos fuertes (dato técnico que no está en nada de lo que recibió el modelo)", ""]
    L += sospechosos or ["- Ninguno."]
    L += ["", "## Pasos 'sin manual' con datos específicos", ""] + (especificos or ["- Ninguno."])
    L += ["", "## Líneas del modelo sin cita (candidatas a afirmaciones no respaldadas)", ""]
    L += sin_cita or ["- Ninguna."]
    texto = "\n".join(L) + "\n"
    (carpeta / "resumen.md").write_text(texto, encoding="utf-8")
    return texto


def escribir_muestra(carpeta: Path, corridas: list[dict], n: int, semilla: int) -> int:
    """Hoja de revisión: afirmaciones con cita, sin repetidas, con el fragmento citado al lado."""
    candidatas, vistas = [], set()
    for c in corridas:
        for p in c["pasos"]:
            for ln in p["lineas"]:
                clave = normalizar(ln["texto"])
                if ln["con_cita"] and ln["fragmentos_citados"] and clave not in vistas:
                    vistas.add(clave)
                    candidatas.append((c["config_id"], p["orden"], p["id_paso"], ln))
    random.Random(semilla).shuffle(candidatas)
    muestra = sorted(candidatas[:n], key=lambda t: (t[0], t[1]))

    L = [
        "# Revisión manual de afirmaciones con cita (issue #23)",
        "",
        f"Muestra de {len(muestra)} afirmaciones (de {len(candidatas)} distintas con cita), semilla {semilla}.",
        "Para cada una, lee el fragmento citado y marca si el manual respalda la afirmación.",
        "Respaldada = lo que dice la frase está en el fragmento. Anota cualquier dato (pin, ranura, cable) que no esté.",
        "",
    ]
    for i, (cid, orden, id_paso, ln) in enumerate(muestra, start=1):
        L += [f"## {i}. Config {cid} · paso {orden} · `{id_paso}`", "", f"**Afirmación:** {ln['texto']}", ""]
        for f in ln["fragmentos_citados"]:
            L += [f"**Fragmento citado (pág. {f['etiqueta']}, sección: {f['seccion']}):**", ""]
            L += [f"> {parte}" for parte in f["texto"].splitlines() if parte.strip()]
            L.append("")
        if ln["fuera_del_fragmento"]:
            L += [f"_Datos técnicos que el script no halló en el fragmento: `{ln['fuera_del_fragmento']}`_", ""]
        L += ["**Veredicto:** [ ] respaldada  [ ] parcialmente  [ ] no respaldada", "", "**Notas:** ", "", "---", ""]
    (carpeta / "muestra_revision.md").write_text("\n".join(L), encoding="utf-8")
    return len(muestra)


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def indexar_manuales(base: Path) -> buscador.MotorVectorial:
    """Ingiere el PDF del repo en una ChromaDB temporal (no toca data/vectorstore)."""
    ruta_chunks = base / "manual_chunks.jsonl"
    total = procesar_directorio(CARPETA_RAW, ruta_salida=ruta_chunks)
    if total == 0:
        raise RuntimeError("La ingesta no generó fragmentos: revisa el PDF y la dependencia cryptography")
    motor = buscador.MotorVectorial(ruta_db=base / "vectorstore", nombre_coleccion="eval_generador")
    motor.cargar_chunks_jsonl(ruta_chunks)
    return motor


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluación del generador del manual (issue #23).")
    parser.add_argument("--solo", default="", help="ids de configuración separados por coma (por defecto, todas)")
    parser.add_argument("--repeticiones", type=int, default=1, help="corridas por configuración (por defecto 1)")
    parser.add_argument("--muestra", type=int, default=25, help="afirmaciones en la hoja de revisión (por defecto 25)")
    parser.add_argument("--salida", default=str(CARPETA_SALIDA), help="carpeta base de las salidas")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    for ruidoso in ("httpx", "openai", "chromadb", "ingest_manuals", "rag.buscador"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    elegidas = {int(x) for x in args.solo.split(",") if x.strip()} or {c[0] for c in CONFIGURACIONES}
    seleccion = [c for c in CONFIGURACIONES if c[0] in elegidas]
    if not seleccion:
        sys.exit(f"Ninguna configuración coincide con --solo={args.solo!r}")

    catalogo = cargar_catalogo()
    cliente, modelo = cargar_cliente()  # falla con un mensaje claro si falta la clave en .env
    ahora = datetime.now()
    carpeta = Path(args.salida) / ahora.strftime("%Y-%m-%d_%H%M%S")
    carpeta.mkdir(parents=True, exist_ok=True)
    print(f"Modelo: {modelo} · salidas en {carpeta}", flush=True)

    corridas: list[dict] = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        motor = indexar_manuales(Path(tmp))
        anterior = buscador._motor_global
        buscador._motor_global = motor  # buscar_contexto_paso usa el motor global
        try:
            for cid, descripcion, piezas in seleccion:
                for rep in range(1, args.repeticiones + 1):
                    print(f"[config {cid} · r{rep}] {descripcion}", flush=True)
                    corrida = correr_configuracion(cliente, modelo, catalogo, cid, piezas, rep)
                    corridas.append(corrida)
                    (carpeta / f"manual_{cid:02d}_r{rep}.md").write_text(corrida["manual_markdown"], encoding="utf-8")
        finally:
            buscador._motor_global = anterior

    meta = {
        "fecha": ahora.strftime("%Y-%m-%d %H:%M"),
        "proveedor": os.getenv("LLM_PROVIDER", "nvidia"),
        "modelo": modelo,
        "temperatura": 0.2,  # fijada en gen.redactar_paso
        "top_k": 2,          # valor por defecto de armar_pasos_con_contexto
        "max_reintentos": gen.MAX_REINTENTOS,
        "repeticiones": args.repeticiones,
    }
    descripciones = {cid: d for cid, d, _ in CONFIGURACIONES}
    resumen = escribir_resumen(carpeta, meta, corridas, descripciones)
    n = escribir_muestra(carpeta, corridas, args.muestra, SEMILLA_MUESTRA)
    with open(carpeta / "resultados.json", "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "corridas": corridas}, f, ensure_ascii=False, indent=2)

    g = resumir([p for c in corridas for p in c["pasos"]])
    print("\n" + "=" * 70)
    print(f"Citas inválidas: {g['citas_invalidas']} (meta 0)")
    print(f"Pasos sin manual con datos específicos: {g['sin_manual_con_datos_especificos']} (meta 0)")
    print(f"% pasos con cita válida: {formato(g['pct_cita_valida'])} · % texto seguro: {formato(g['pct_texto_seguro'])} · posible truncado: {g['pasos_posible_truncado']}")
    print(f"Líneas sin cita: {g['lineas_sin_cita']}/{g['lineas']} · sospechosos fuertes: {g['lineas_con_datos_fuera_del_contexto']}")
    print(f"Hoja de revisión con {n} afirmaciones: {carpeta / 'muestra_revision.md'}")
    print(f"Resumen: {carpeta / 'resumen.md'}")
    del resumen


if __name__ == "__main__":
    main()
