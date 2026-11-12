"""
Ingesta y procesamiento de manuales tecnicos en formato PDF para PC-Assembly-RAG.

Este modulo implementa el procesamiento de manuales de hardware usando pypdf:
1. Extrae texto pagina por pagina, con el indice fisico (pagina) y la numeracion impresa (pagina_etiqueta).
2. Identifica secciones estructurales (mediante marcadores/outlines de PDF o patrones de encabezado).
3. Segmenta en fragmentos semanticos (~400 palabras) priorizando limites de seccion.
4. Asocia metadatos normalizados (chunk_id, manual_id, componente_tipo, pagina, pagina_etiqueta, seccion).
5. Vincula componentes contra data/processed/hardware_catalog.json si esta disponible.
6. Exporta el resultado a data/processed/manual_chunks.jsonl.

Uso:
    python scripts/ingest_manuals.py
    python scripts/ingest_manuals.py --input data/raw/manuals_pdf/mi_manual.pdf
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import pypdf
from pydantic import BaseModel, Field

# Configuracion de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ingest_manuals")

# Rutas estandar del repositorio
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.manuales import manual_por_archivo  # noqa: E402

CARPETA_RAW = RAIZ / "data" / "raw"
CARPETA_PROCESADOS = RAIZ / "data" / "processed"
CATALOGO_HARDWARE_PATH = CARPETA_PROCESADOS / "hardware_catalog.json"
SALIDA_CHUNKS_JSONL = CARPETA_PROCESADOS / "manual_chunks.jsonl"


# ---------------------------------------------------------------------------
# Modelo de datos para cada chunk (alineado con docs/contratos.md)
# ---------------------------------------------------------------------------
class ChunkManual(BaseModel):
    chunk_id: str = Field(description="Identificador unico del fragmento")
    manual_id: str = Field(description="Identificador canonico del manual")
    componente_tipo: str = Field(description="Categoria del componente (motherboard, cpu, etc.)")
    pagina: int = Field(description="Indice de la pagina en el PDF (base 1)")
    pagina_etiqueta: str = Field(default="", description="Numeracion impresa del manual, p. ej. '1-8'")
    seccion: str = Field(description="Titulo o nombre de la seccion identificada")
    texto: str = Field(description="Texto procesado del fragmento")


# ---------------------------------------------------------------------------
# Funciones auxiliares para catalogo y metadatos
# ---------------------------------------------------------------------------
def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparaciones eliminando caracteres especiales y mayusculas."""
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def cargar_catalogo_hardware(ruta_catalogo: Path = CATALOGO_HARDWARE_PATH) -> dict[str, list[dict[str, Any]]]:
    """Carga el catalogo de hardware procesado si existe."""
    if not ruta_catalogo.exists():
        logger.warning("No se encontro el archivo de catalogo en: %s", ruta_catalogo)
        return {}
    try:
        with open(ruta_catalogo, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as error:
        logger.warning("Error al cargar catalogo de hardware: %s", error)
        return {}


def vincular_con_catalogo(
    nombre_archivo: str,
    texto_muestra: str,
    catalogo: dict[str, list[dict[str, Any]]],
) -> tuple[str, str]:
    """
    Determina manual_id y componente_tipo buscando coincidencias con hardware_catalog.json.
    Si no encuentra coincidencia en el catalogo, deriva un slug limpio del nombre de archivo.
    """
    nombre_limpio = Path(nombre_archivo).stem
    nombre_norm = normalizar_texto(nombre_limpio)
    muestra_norm = normalizar_texto(texto_muestra[:2000])

    mejor_coincidencia = None
    mejor_puntaje = 0
    tipo_detectado = "desconocido"

    for tipo_componente, lista_items in catalogo.items():
        for item in lista_items:
            nombre_item = item.get("name", "")
            item_norm = normalizar_texto(nombre_item)
            if not item_norm:
                continue

            # Coincidencia directa con nombre de archivo
            if item_norm in nombre_norm or nombre_norm in item_norm:
                puntaje = len(item_norm)
                if puntaje > mejor_puntaje:
                    mejor_puntaje = puntaje
                    mejor_coincidencia = nombre_item
                    tipo_detectado = tipo_componente

            # Coincidencia con texto de portada / primeras paginas
            elif item_norm in muestra_norm:
                puntaje = len(item_norm) // 2
                if puntaje > mejor_puntaje:
                    mejor_puntaje = puntaje
                    mejor_coincidencia = nombre_item
                    tipo_detectado = tipo_componente

    if mejor_coincidencia:
        slug_manual = re.sub(r"[^a-z0-9]+", "_", mejor_coincidencia.lower()).strip("_")
        logger.info("Coincidencia encontrada en catalogo: %s (%s)", mejor_coincidencia, tipo_detectado)
        return slug_manual, tipo_detectado

    # Si no hubo coincidencia, generar slug desde el nombre de archivo
    slug_manual = re.sub(r"[^a-z0-9]+", "_", nombre_limpio.lower()).strip("_")
    logger.info("Sin coincidencia directa en catalogo. Usando slug derivado: %s", slug_manual)
    return slug_manual, "general"


# ---------------------------------------------------------------------------
# Extraccion de texto y numeracion oficial de paginas
# ---------------------------------------------------------------------------
def obtener_etiqueta_pagina(reader: pypdf.PdfReader, indice_cero: int) -> str:
    """
    Devuelve la numeracion impresa del manual para una pagina (p. ej. '1-8' o 'iv').

    Devuelve cadena vacia si el PDF no define etiquetas de pagina: en ese caso pypdf
    inventaria '1', '2', ... a partir del indice fisico, que no es la numeracion impresa.
    """
    try:
        if "/PageLabels" not in reader.trailer["/Root"]:
            return ""
        return str(reader.page_labels[indice_cero]).strip()
    except Exception:
        return ""


def extraer_marcadores_outline(outline: Any, reader: pypdf.PdfReader) -> list[tuple[int, str]]:
    """Extrae jerarquicamente los marcadores (bookmarks/outline) del PDF."""
    marcadores: list[tuple[int, str]] = []
    if not outline:
        return marcadores

    for elemento in outline:
        if isinstance(elemento, list):
            marcadores.extend(extraer_marcadores_outline(elemento, reader))
        else:
            try:
                pagina_destino = reader.get_destination_page_number(elemento)
                titulo = getattr(elemento, "title", str(elemento)).strip()
                if pagina_destino is not None and titulo:
                    marcadores.append((pagina_destino, titulo))
            except Exception:
                continue

    marcadores.sort(key=lambda item: item[0])
    return marcadores


def extraer_paginas_pdf(ruta_pdf: Path) -> tuple[list[dict[str, Any]], dict[int, str]]:
    """
    Extrae el texto de cada pagina del PDF junto con su numero oficial de pagina
    y el mapa de secciones derivado de los marcadores del PDF.
    """
    reader = pypdf.PdfReader(str(ruta_pdf))
    total_paginas = len(reader.pages)
    logger.info("Abriendo '%s' con %d paginas.", ruta_pdf.name, total_paginas)

    # Extraer marcadores de seccion si existen
    marcadores = []
    try:
        marcadores = extraer_marcadores_outline(reader.outline, reader)
    except Exception as error:
        logger.debug("No se pudieron leer marcadores del PDF: %s", error)

    # Construir mapa de pagina_fisica -> seccion desde los marcadores
    mapa_secciones_outline: dict[int, str] = {}
    if marcadores:
        for idx in range(len(marcadores)):
            pag_inicio, titulo = marcadores[idx]
            pag_fin = marcadores[idx + 1][0] if idx + 1 < len(marcadores) else total_paginas
            for p in range(pag_inicio, min(pag_fin, total_paginas)):
                mapa_secciones_outline[p] = titulo

    paginas_extraidas: list[dict[str, Any]] = []

    for indice_fisico, page in enumerate(reader.pages):
        try:
            texto = page.extract_text() or ""
        except Exception as error:
            logger.warning("Fallo al extraer texto de pagina %d: %s", indice_fisico + 1, error)
            texto = ""

        # Limpiar caracteres nulos y espacios redundantes
        texto_limpio = texto.replace("\x00", " ").strip()
        pagina = indice_fisico + 1
        etiqueta = obtener_etiqueta_pagina(reader, indice_fisico)
        seccion_outline = mapa_secciones_outline.get(indice_fisico, "")

        paginas_extraidas.append({
            "indice_fisico": indice_fisico,
            "pagina": pagina,
            "pagina_etiqueta": etiqueta,
            "texto": texto_limpio,
            "seccion_outline": seccion_outline,
        })

    return paginas_extraidas, mapa_secciones_outline


# ---------------------------------------------------------------------------
# Deteccion de secciones y segmentacion semantica (~400 palabras)
# ---------------------------------------------------------------------------
PATRON_SECCION = re.compile(
    r"^(?:(?:(?:\d+\.){1,3}\d*|[A-Z]\.|\d+)\s+[A-Z0-9].*|(?:Chapter|Capítulo|Section|Sección)\s+\d+.*)",
    re.MULTILINE,
)


def detectar_secciones_en_texto(texto: str) -> list[tuple[str, str]]:
    """
    Intenta dividir el texto de una pagina en bloques delimitados por titulos de seccion detectados por regex.
    Retorna pares (titulo_seccion, texto_del_bloque).
    """
    coincidencias = list(PATRON_SECCION.finditer(texto))
    if not coincidencias:
        return []

    bloques: list[tuple[str, str]] = []
    # Texto antes de la primera seccion encontrada
    if coincidencias[0].start() > 0:
        texto_previo = texto[:coincidencias[0].start()].strip()
        if texto_previo:
            bloques.append(("", texto_previo))

    for idx, match in enumerate(coincidencias):
        titulo = match.group(0).strip()
        inicio_texto = match.end()
        fin_texto = coincidencias[idx + 1].start() if idx + 1 < len(coincidencias) else len(texto)
        cuerpo = texto[inicio_texto:fin_texto].strip()
        bloques.append((titulo, cuerpo))

    return bloques


def dividir_texto_en_palabras(texto: str, palabras_por_chunk: int = 400, solapamiento: int = 50) -> list[str]:
    """
    Divide un texto largo en chunks de tamano aproximado en palabras con solapamiento continuo.
    Intenta respetar saltos de linea o parrafos cuando sea posible.
    """
    palabras = texto.split()
    if not palabras:
        return []

    if len(palabras) <= palabras_por_chunk + (palabras_por_chunk // 4):
        return [" ".join(palabras)]

    chunks = []
    paso = max(1, palabras_por_chunk - solapamiento)
    inicio = 0

    while inicio < len(palabras):
        fin = inicio + palabras_por_chunk
        fragmento = palabras[inicio:fin]
        chunks.append(" ".join(fragmento))
        if fin >= len(palabras):
            break
        inicio += paso

    return chunks


def segmentar_en_chunks(
    paginas: list[dict[str, Any]],
    manual_id: str,
    componente_tipo: str,
    palabras_objetivo: int = 400,
    solapamiento: int = 50,
) -> list[ChunkManual]:
    """
    Segmenta el manual respetando:
    1. Secciones del manual (outlines o deteccion regex de titulos).
    2. Tamano semantico objetivo (~400 palabras) con solapamiento.
    3. Si no hay secciones disponibles, aplica fallback deslizante de ~400 palabras.
    """
    # Fase 1: Agrupar unidades semanticas por seccion y pagina
    unidades: list[dict[str, Any]] = []
    seccion_actual = "Introducción"
    hay_secciones_detectadas = False

    for item_pag in paginas:
        texto_pag = item_pag["texto"]
        if not texto_pag:
            continue

        pagina = item_pag["pagina"]
        pagina_etiqueta = item_pag["pagina_etiqueta"]
        seccion_outline = item_pag.get("seccion_outline", "")

        if seccion_outline:
            seccion_actual = seccion_outline
            hay_secciones_detectadas = True

        # Verificar si dentro de la pagina hay encabezados adicionales
        bloques_regex = detectar_secciones_en_texto(texto_pag)
        if bloques_regex:
            hay_secciones_detectadas = True
            for titulo_bloque, contenido_bloque in bloques_regex:
                if titulo_bloque:
                    seccion_actual = titulo_bloque
                if contenido_bloque:
                    unidades.append({
                        "pagina": pagina,
                        "pagina_etiqueta": pagina_etiqueta,
                        "seccion": seccion_actual,
                        "texto": contenido_bloque,
                    })
        else:
            unidades.append({
                "pagina": pagina,
                "pagina_etiqueta": pagina_etiqueta,
                "seccion": seccion_actual,
                "texto": texto_pag,
            })

    # Fase 2: Segmentar segun presencia o ausencia de secciones
    chunks_resultado: list[ChunkManual] = []
    contador_chunk = 1

    if hay_secciones_detectadas:
        # Agrupacion por secciones continuas
        secciones_agrupadas: list[dict[str, Any]] = []
        grupo_actual: dict[str, Any] | None = None

        for unidad in unidades:
            if grupo_actual is None or grupo_actual["seccion"] != unidad["seccion"]:
                if grupo_actual is not None:
                    secciones_agrupadas.append(grupo_actual)
                grupo_actual = {
                    "seccion": unidad["seccion"],
                    "pagina": unidad["pagina"],
                    "pagina_etiqueta": unidad["pagina_etiqueta"],
                    "textos": [unidad["texto"]],
                }
            else:
                grupo_actual["textos"].append(unidad["texto"])

        if grupo_actual is not None:
            secciones_agrupadas.append(grupo_actual)

        # Generar chunks para cada grupo de seccion
        for sec in secciones_agrupadas:
            texto_completo = "\n\n".join(sec["textos"]).strip()
            num_palabras = len(texto_completo.split())

            if num_palabras == 0:
                continue

            # Si la seccion cabe comodamente en ~400 palabras (+ 30% de tolerancia), queda en un solo chunk
            if num_palabras <= (palabras_objetivo + 120):
                chunk_id = f"{manual_id}_p{sec['pagina']}_c{contador_chunk:02d}"
                chunks_resultado.append(
                    ChunkManual(
                        chunk_id=chunk_id,
                        manual_id=manual_id,
                        componente_tipo=componente_tipo,
                        pagina=sec["pagina"],
                        pagina_etiqueta=sec["pagina_etiqueta"],
                        seccion=sec["seccion"],
                        texto=texto_completo,
                    )
                )
                contador_chunk += 1
            else:
                # Subsegmentar secciones extensas manteniendo solapamiento
                subfragmentos = dividir_texto_en_palabras(
                    texto_completo,
                    palabras_por_chunk=palabras_objetivo,
                    solapamiento=solapamiento,
                )
                for subtexto in subfragmentos:
                    chunk_id = f"{manual_id}_p{sec['pagina']}_c{contador_chunk:02d}"
                    chunks_resultado.append(
                        ChunkManual(
                            chunk_id=chunk_id,
                            manual_id=manual_id,
                            componente_tipo=componente_tipo,
                            pagina=sec["pagina"],
                            pagina_etiqueta=sec["pagina_etiqueta"],
                            seccion=sec["seccion"],
                            texto=subtexto,
                        )
                    )
                    contador_chunk += 1

    else:
        # Fallback cuando no hay secciones identificables
        logger.info("No se discernieron secciones estructurales; aplicando chunking plano de ~%d palabras.", palabras_objetivo)
        for unidad in unidades:
            subfragmentos = dividir_texto_en_palabras(
                unidad["texto"],
                palabras_por_chunk=palabras_objetivo,
                solapamiento=solapamiento,
            )
            for subtexto in subfragmentos:
                chunk_id = f"{manual_id}_p{unidad['pagina']}_c{contador_chunk:02d}"
                chunks_resultado.append(
                    ChunkManual(
                        chunk_id=chunk_id,
                        manual_id=manual_id,
                        componente_tipo=componente_tipo,
                        pagina=unidad["pagina"],
                        pagina_etiqueta=unidad["pagina_etiqueta"],
                        seccion="General",
                        texto=subtexto,
                    )
                )
                contador_chunk += 1

    return chunks_resultado


# ---------------------------------------------------------------------------
# Procesamiento de archivos y exportacion
# ---------------------------------------------------------------------------
def exportar_chunks_jsonl(chunks: list[ChunkManual], ruta_salida: Path, sobrescribir: bool = False) -> int:
    """
    Exporta la lista de chunks al archivo JSONL especificado.
    Crea las carpetas padre automaticamente si no existen.
    """
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    modo = "w" if sobrescribir else "a"

    with open(ruta_salida, modo, encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json() + "\n")

    return len(chunks)


def procesar_un_manual(
    ruta_pdf: Path,
    catalogo: dict[str, list[dict[str, Any]]],
    palabras_objetivo: int = 400,
) -> list[ChunkManual]:
    """Procesa un manual PDF individual de extremo a extremo."""
    logger.info("Iniciando procesamiento de: %s", ruta_pdf.name)

    # 1. Extraer paginas y marcadores
    paginas, mapa_secciones = extraer_paginas_pdf(ruta_pdf)
    if not paginas:
        logger.warning("El archivo '%s' no contiene paginas legibles.", ruta_pdf.name)
        return []

    # 2. Tomar muestra de texto para correlacion con catalogo
    muestra_texto = " ".join([p["texto"] for p in paginas[:3]])
    registro = manual_por_archivo(ruta_pdf.name)
    if registro:
        manual_id, componente_tipo = registro
        logger.info("Manual encontrado en data/processed/manuales.json: %s (%s)", manual_id, componente_tipo)
    else:
        manual_id, componente_tipo = vincular_con_catalogo(ruta_pdf.name, muestra_texto, catalogo)

    # 3. Segmentar respetando secciones y conteo de palabras
    chunks = segmentar_en_chunks(
        paginas=paginas,
        manual_id=manual_id,
        componente_tipo=componente_tipo,
        palabras_objetivo=palabras_objetivo,
    )

    logger.info(
        "Finalizado '%s': %d paginas procesadas, %d chunks generados (manual_id='%s', tipo='%s').",
        ruta_pdf.name,
        len(paginas),
        len(chunks),
        manual_id,
        componente_tipo,
    )
    return chunks


def procesar_directorio(
    carpeta_origen: Path,
    ruta_salida: Path = SALIDA_CHUNKS_JSONL,
    ruta_catalogo: Path = CATALOGO_HARDWARE_PATH,
    palabras_objetivo: int = 400,
) -> int:
    """
    Busca de manera recursiva todos los PDFs en carpeta_origen, los procesa y
    guarda todos los chunks generados en ruta_salida.
    """
    catalogo = cargar_catalogo_hardware(ruta_catalogo)
    archivos_pdf = sorted(list(carpeta_origen.glob("**/*.pdf")))

    if not archivos_pdf:
        logger.warning("No se encontraron archivos .pdf en la ruta: %s", carpeta_origen)
        return 0

    logger.info("Se encontraron %d manual(es) PDF para procesar en %s.", len(archivos_pdf), carpeta_origen)

    # Sobrescribir archivo de salida para la ejecucion por lote completo
    if ruta_salida.exists():
        ruta_salida.unlink()

    total_chunks = 0
    for archivo_pdf in archivos_pdf:
        try:
            chunks = procesar_un_manual(
                ruta_pdf=archivo_pdf,
                catalogo=catalogo,
                palabras_objetivo=palabras_objetivo,
            )
            if chunks:
                escritos = exportar_chunks_jsonl(chunks, ruta_salida, sobrescribir=False)
                total_chunks += escritos
        except Exception as error:
            logger.error("Error al procesar el archivo '%s': %s", archivo_pdf.name, error, exc_info=True)

    logger.info("Proceso completado. Total de chunks exportados: %d en %s", total_chunks, ruta_salida)
    return total_chunks


# ---------------------------------------------------------------------------
# Punto de entrada CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Extractor y segmentador semantico de manuales tecnicos PDF para PC-Assembly-RAG."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Ruta a un archivo PDF especifico o a un directorio con manuales (por defecto busca en data/raw).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(SALIDA_CHUNKS_JSONL),
        help=f"Ruta del archivo de salida JSONL (por defecto: {SALIDA_CHUNKS_JSONL}).",
    )
    parser.add_argument(
        "--palabras",
        type=int,
        default=400,
        help="Tamano objetivo aproximado en palabras por chunk (por defecto: 400).",
    )
    args = parser.parse_args()

    ruta_salida = Path(args.output)
    catalogo = cargar_catalogo_hardware()

    total = 0
    if args.input:
        ruta_entrada = Path(args.input)
        if ruta_entrada.is_file() and ruta_entrada.suffix.lower() == ".pdf":
            chunks = procesar_un_manual(ruta_entrada, catalogo, palabras_objetivo=args.palabras)
            total = exportar_chunks_jsonl(chunks, ruta_salida, sobrescribir=True)
            logger.info("Exportados %d chunks a %s", total, ruta_salida)
        elif ruta_entrada.is_dir():
            total = procesar_directorio(ruta_entrada, ruta_salida, palabras_objetivo=args.palabras)
        else:
            logger.error("La ruta especificada no es un archivo PDF ni un directorio valido: %s", ruta_entrada)
            sys.exit(1)
    else:
        total = procesar_directorio(CARPETA_RAW, ruta_salida, palabras_objetivo=args.palabras)

    if total == 0:
        logger.error("No se genero ningun chunk. Revisa los errores anteriores.")
        sys.exit(1)


if __name__ == "__main__":
    main()
