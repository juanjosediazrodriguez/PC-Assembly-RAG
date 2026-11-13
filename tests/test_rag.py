"""
Evaluación de la recuperación (issue #9): Recall@3 sobre el manual de la placa ASUS.

Qué mide
--------
Para cada una de 10 preguntas técnicas se busca en el manual y se revisan los 3 primeros
fragmentos. Se reportan dos métricas, porque el criterio de la issue ("la página real debe
estar en el top 3") y el objetivo del README ("recuperar el fragmento correcto") no son
exactamente lo mismo:

- Por contenido: algún fragmento del top 3 contiene la `ancla` de la pregunta, una frase
  copiada del manual que prueba la respuesta.
- Por página: la `pagina_etiqueta` de algún fragmento del top 3 es una de las páginas donde
  el dato está físicamente impreso (`paginas_validas`).

Las dos pueden diferir porque la ingesta etiqueta cada fragmento con la página donde EMPIEZA
su sección. Una sección que ocupa dos páginas puede devolver el contenido correcto citando la
primera.

Independencia de la verdad
--------------------------
Las páginas y las anclas salen de leer el texto del PDF con pypdf, NO de ejecutar el buscador.
Si salieran del buscador, la prueba mediría al buscador contra sí mismo.

Líneas base (solo se imprimen): consulta con el nombre de la pieza pegado (como armaba el
planificador antes de `consulta_para`) y búsqueda por palabras clave sin embeddings.

Ejecutar con: `python -m pytest tests/test_rag.py -v -s`
La primera vez, ChromaDB descarga el modelo de embeddings (~80 MB).
"""

import json
import os
import re
from dataclasses import dataclass

import pytest

from scripts.ingest_manuals import CARPETA_RAW, extraer_paginas_pdf, procesar_directorio
from src.rag import buscador

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

K = 3
META_RECALL = 0.90
NOMBRE_PLACA = "Asus TUF GAMING B650-PLUS WIFI ATX AM5 Motherboard (TUF GAMING B650-PLUS WIFI)"


# ---------------------------------------------------------------------------
# Banco de 10 preguntas (en inglés: el manual y el modelo de embeddings lo están)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Caso:
    id: str
    consulta: str
    paginas_validas: frozenset[str]  # numeración impresa (pagina_etiqueta) donde está el dato
    ancla: str                       # frase del manual que prueba la respuesta


CASOS: list[Caso] = [
    Caso(
        "panel_frontal_boton_encendido",
        "How do I connect the chassis power button to the motherboard front panel header?",
        frozenset({"1-6"}),
        "Power Button/Soft-off Button header (PWRSW)",
    ),
    Caso(
        "memoria_canales_dimm",
        "Which DIMM sockets belong to channel A and channel B for dual channel memory?",
        frozenset({"1-12"}),
        "Channel A DIMM_A1 & DIMM_A2",
    ),
    Caso(
        "memoria_ddr5_muesca",
        "Can I install a DDR4 memory module in the DDR5 slot?",
        frozenset({"1-12"}),
        "DO NOT install a DDR, DDR2, DDR3 or DDR4 memory module to the DDR5 slot",
    ),
    Caso(
        "m2_instalar_2280",
        "How do I install an M.2 SSD of 2280 length using the Q-Latch?",
        frozenset({"1-14"}),
        "Rotate the M.2 Q-Latch clockwise to secure the M.2 in place",
    ),
    Caso(
        "m2_instalar_2242_2260",
        "How do I secure a 2242 or 2260 M.2 drive with the bundled screw stand?",
        frozenset({"1-15"}),
        "Install the bundled screw stand to the M.2 length screw hole",
    ),
    Caso(
        "m2_ranura_pcie5",
        "Which M.2 slot supports PCIe 5.0 x4 mode?",
        frozenset({"1-4"}),
        "M.2_1 slot supports PCIe 5.0 x4 mode",
    ),
    Caso(
        "cpu_orientacion_am5",
        "What precautions apply to the CPU orientation when installing it in the AM5 socket?",
        frozenset({"1-10"}),
        "DO NOT force the CPU into the socket",
    ),
    Caso(
        "limpiar_cmos",
        "How do I clear the CMOS RTC RAM using the jumper pins?",
        frozenset({"1-5"}),
        "Short-circuit pin 1-2 with a metal object or jumper cap",
    ),
    Caso(
        "alimentacion_cpu_8pin",
        "Which CPU power plugs must be connected to the power supply, the 8-pin or the 4-pin?",
        frozenset({"1-3"}),
        "Ensure to connect the 8-pin power plug, or connect both the 8-pin and 4-pin power plugs",
    ),
    Caso(
        "antena_wifi",
        "How do I connect the Wi-Fi antenna to the motherboard?",
        frozenset({"1-16"}),
        "Connect the bundled ASUS Wi-Fi moving antenna connector to the Wi-Fi ports",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def chunks(tmp_path_factory) -> list[dict]:
    """Ingiere el PDF del repo a un JSONL temporal (no toca data/processed)."""
    ruta = tmp_path_factory.mktemp("rag_eval") / "manual_chunks.jsonl"
    total = procesar_directorio(CARPETA_RAW, ruta_salida=ruta)
    assert total > 0, "La ingesta no generó fragmentos: revisa el PDF y la dependencia cryptography"
    with open(ruta, encoding="utf-8") as archivo:
        return [json.loads(linea) for linea in archivo if linea.strip()]


@pytest.fixture(scope="module")
def motor(chunks, tmp_path_factory):
    """ChromaDB temporal con los fragmentos (no toca data/vectorstore)."""
    base = tmp_path_factory.mktemp("rag_eval_db")
    ruta_chunks = base / "chunks.jsonl"
    with open(ruta_chunks, "w", encoding="utf-8") as archivo:
        for chunk in chunks:
            archivo.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    instancia = buscador.MotorVectorial(ruta_db=base / "vectorstore", nombre_coleccion="eval_recall")
    instancia.cargar_chunks_jsonl(ruta_chunks)
    return instancia


@pytest.fixture(scope="module")
def manual_id(chunks) -> str:
    ids = {c["manual_id"] for c in chunks}
    assert len(ids) == 1, f"Se esperaba un solo manual indexado y hay: {ids}"
    return ids.pop()


# ---------------------------------------------------------------------------
# Utilidades de evaluación
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    return " ".join(texto.split()).lower()


def etiqueta(fragmento) -> str:
    return fragmento.pagina_etiqueta or str(fragmento.pagina)


_VACIAS = frozenset(
    "a an the of to in on for is are be it how do i my can which what with and or by at as from this that when using".split()
)


def _tokens(texto: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_.]+", texto.lower()) if len(t) > 1 and t not in _VACIAS}


def buscar_por_palabras(chunks: list[dict], consulta: str, k: int) -> list[dict]:
    """Línea base sin embeddings: cuenta cuántas palabras de la consulta aparecen en cada fragmento."""
    q = _tokens(consulta)
    ordenados = sorted(chunks, key=lambda c: (-len(q & _tokens(c["texto"])), c["chunk_id"]))
    return ordenados[:k]


def evaluar(buscar, casos: list[Caso]) -> tuple[float, float, list[dict]]:
    """Devuelve (recall por contenido, recall por página, detalle por caso).

    `buscar(consulta)` debe devolver una lista de (etiqueta_de_pagina, texto) del top K.
    """
    ok_contenido = ok_pagina = 0
    detalle = []
    for caso in casos:
        resultados = buscar(caso.consulta)
        hit_contenido = any(normalizar(caso.ancla) in normalizar(texto) for _, texto in resultados)
        hit_pagina = any(pag in caso.paginas_validas for pag, _ in resultados)
        ok_contenido += hit_contenido
        ok_pagina += hit_pagina
        detalle.append({
            "id": caso.id,
            "contenido": hit_contenido,
            "pagina": hit_pagina,
            "esperadas": sorted(caso.paginas_validas),
            "obtenidas": [pag for pag, _ in resultados],
        })
    n = len(casos)
    return ok_contenido / n, ok_pagina / n, detalle


def imprimir(titulo: str, rc: float, rp: float, detalle: list[dict]) -> None:
    print(f"\n=== {titulo}: Recall@{K} contenido={rc:.0%}  página={rp:.0%}")
    for d in detalle:
        print(
            f"  {'OK ' if d['contenido'] else 'NO '}contenido | {'OK ' if d['pagina'] else 'NO '}página | "
            f"{d['id']:<32} esperada={d['esperadas']} obtenidas={d['obtenidas']}"
        )


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------
def test_la_verdad_del_banco_coincide_con_el_texto_del_pdf():
    """Guardia: cada ancla debe estar impresa en la página que el banco declara, según el PDF.

    Lee el PDF directamente (sin chunking ni embeddings), así la verdad de la evaluación
    no depende del sistema que se evalúa.
    """
    assert len(CASOS) == 10
    assert len({c.id for c in CASOS}) == 10, "Los ids de las preguntas deben ser únicos"

    pdfs = sorted((CARPETA_RAW / "manuals_pdf").glob("*.pdf"))
    assert pdfs, "No hay PDF en data/raw/manuals_pdf"
    paginas, _ = extraer_paginas_pdf(pdfs[0])
    texto_por_etiqueta = {p["pagina_etiqueta"]: normalizar(p["texto"]) for p in paginas}

    for caso in CASOS:
        assert caso.paginas_validas <= texto_por_etiqueta.keys(), f"{caso.id}: la página no existe en el PDF"
        assert any(
            normalizar(caso.ancla) in texto_por_etiqueta[pag] for pag in caso.paginas_validas
        ), f"{caso.id}: la ancla no está impresa en las páginas {sorted(caso.paginas_validas)}"


def test_recall_at_3_del_buscador(motor, manual_id, chunks):
    def buscar(consulta):
        frags = motor.buscar(consulta, top_k=K, manual_id=manual_id)
        return [(etiqueta(f), f.texto) for f in frags]

    rc, rp, detalle = evaluar(buscar, CASOS)
    imprimir("Buscador (embeddings, consulta sin nombres de pieza)", rc, rp, detalle)

    # Líneas base (informativas)
    def buscar_con_nombre(consulta):
        frags = motor.buscar(f"{consulta} {NOMBRE_PLACA}", top_k=K, manual_id=manual_id)
        return [(etiqueta(f), f.texto) for f in frags]

    def buscar_palabras(consulta):
        return [(c["pagina_etiqueta"] or str(c["pagina"]), c["texto"]) for c in buscar_por_palabras(chunks, consulta, K)]

    imprimir("Línea base: consulta con el nombre de la pieza", *evaluar(buscar_con_nombre, CASOS))
    imprimir("Línea base: palabras clave (sin embeddings)", *evaluar(buscar_palabras, CASOS))

    fallas = [d for d in detalle if not d["pagina"]]
    assert rp >= META_RECALL, (
        f"Recall@{K} por página = {rp:.0%} (meta {META_RECALL:.0%}). "
        f"Por contenido = {rc:.0%}. Fallaron por página: {[(d['id'], d['esperadas'], d['obtenidas']) for d in fallas]}"
    )
