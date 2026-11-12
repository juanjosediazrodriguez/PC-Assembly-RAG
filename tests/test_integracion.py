"""
Prueba de integracion de extremo a extremo (issue #12).

Recorre el flujo completo sin la interfaz:
catalogo -> configuracion -> validacion -> plan -> RAG -> generador.

- El RAG es real: la fixture ingiere el PDF de ASUS que va en el repo y lo indexa en
  una ChromaDB temporal. La primera vez, ChromaDB descarga el modelo de embeddings
  (unos 80 MB) y la prueba tarda mas; despues queda en cache.
- El modelo de lenguaje es simulado, para que la prueba sea rapida y no use la red.
  La prueba con el modelo real esta al final y solo corre con PROBAR_LLM_REAL=1.
"""

import os
import re
from types import SimpleNamespace

import pytest

from scripts.ingest_manuals import CARPETA_RAW, procesar_directorio
from src.catalogo import cargar_catalogo, construir_configuracion, nombres_por_tipo
from src.compatibilidad.validador import validar_compatibilidad
from src.llm import cargar_cliente, generar_manual, validar_citas
from src.llm.generador import TEXTO_NO_VERIFICADO, TEXTO_SIN_MANUAL, etiquetas_citadas, redactar_paso
from src.manuales import manual_id_de_pieza
from src.pipeline import armar_pasos_con_contexto
from src.planificador.grafo import generar_plan_ensamble
from src.rag import buscador

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# Fragmento del nombre de cada pieza del ejemplo (el mismo que precarga la interfaz).
EJEMPLO = {
    "cpu": "Ryzen 5 7600X", "motherboard": "TUF GAMING B650-PLUS WIFI",
    "gpu": "RTX 4070 12 GB", "memory": "Vengeance 32 GB (2 x 16 GB) DDR5-6000 CL36",
    "storage": "980 Pro 1 TB", "cooler": "Hyper 212 Black Edition",
    "psu": "RM750e (2023)", "case": "4000D Airflow ATX",
}


# ---------------------------------------------------------------------------
# Fixtures y ayudas
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def catalogo():
    return cargar_catalogo()


def armar_config(catalogo, **cambios):
    """ConfiguracionPC del ejemplo; `cambios` reemplaza el nombre exacto de alguna pieza."""
    nombres = nombres_por_tipo(catalogo)
    piezas = {tipo: next(n for n in nombres[tipo] if frag in n) for tipo, frag in EJEMPLO.items()}
    piezas.update(cambios)
    return construir_configuracion(catalogo, **piezas)


def nombre_placa_asus(catalogo):
    """Nombre completo de la placa del ejemplo, la unica con manual."""
    return next(n for n in nombres_por_tipo(catalogo)["motherboard"] if EJEMPLO["motherboard"] in n)


@pytest.fixture(scope="module")
def config_ejemplo(catalogo):
    return armar_config(catalogo)


@pytest.fixture(scope="module")
def motor(tmp_path_factory):
    """Ingiere el PDF del repo y lo indexa en una ChromaDB temporal (no toca data/vectorstore)."""
    base = tmp_path_factory.mktemp("rag")
    ruta_chunks = base / "manual_chunks.jsonl"
    total = procesar_directorio(CARPETA_RAW, ruta_salida=ruta_chunks)
    assert total > 0, "La ingesta no genero fragmentos: revisa el PDF y la dependencia cryptography"

    instancia = buscador.MotorVectorial(ruta_db=base / "vectorstore", nombre_coleccion="prueba_e2e")
    instancia.cargar_chunks_jsonl(ruta_chunks)

    anterior = buscador._motor_global
    buscador._motor_global = instancia  # buscar_contexto_paso usa el motor global
    yield instancia
    buscador._motor_global = anterior


class ModeloSimulado:
    """Misma interfaz que el cliente de OpenAI: cita la primera pagina permitida del prompt."""

    def __init__(self):
        self.llamadas = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **kwargs):
        self.llamadas += 1
        cita = re.search(r"Cita: (\[[^\]]+\])", kwargs["messages"][1]["content"]).group(1)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=f"- Paso redactado. {cita}"))])


# ---------------------------------------------------------------------------
# Ingesta y buscador
# ---------------------------------------------------------------------------
def test_la_ingesta_deja_etiqueta_impresa_y_tipo_de_pieza(motor, catalogo):
    registros = motor.coleccion.get(include=["metadatas"])["metadatas"]
    assert len(registros) > 50
    assert all(r["pagina_etiqueta"] for r in registros), "Todos los fragmentos del ASUS tienen etiqueta"
    assert {r["componente_tipo"] for r in registros} == {"motherboard"}
    assert {r["manual_id"] for r in registros} == {manual_id_de_pieza(nombre_placa_asus(catalogo))}


def test_buscador_con_manual_inexistente_devuelve_vacio(motor, config_ejemplo):
    paso = generar_plan_ensamble(config_ejemplo)[0]
    assert buscador.buscar_contexto_paso(paso, top_k=3, manual_id="otro_manual") == []


def test_el_panel_frontal_recupera_la_seccion_del_system_panel(motor, config_ejemplo):
    """Regresion: con los nombres de pieza en la consulta, esta seccion quedaba en la posicion 7."""
    pasos = armar_pasos_con_contexto(generar_plan_ensamble(config_ejemplo))
    panel = next(p for p in pasos if p.paso.id_paso == "conectar_panel_frontal")
    assert any(f.seccion.startswith("16. System Panel") for f in panel.fragmentos_rag)
    assert all(f.pagina_etiqueta for f in panel.fragmentos_rag)


# ---------------------------------------------------------------------------
# Flujo completo
# ---------------------------------------------------------------------------
def test_flujo_completo_con_configuracion_compatible(motor, config_ejemplo):
    compatibilidad = validar_compatibilidad(config_ejemplo)
    assert compatibilidad.compatible

    plan = generar_plan_ensamble(config_ejemplo)
    posicion = {p.id_paso: i for i, p in enumerate(plan)}
    for paso in plan:  # el orden respeta las precedencias del grafo
        assert all(posicion[previa] < posicion[paso.id_paso] for previa in paso.dependencias_previas)

    pasos = armar_pasos_con_contexto(plan)
    con_manual = [p for p in pasos if p.fragmentos_rag]
    sin_manual = [p for p in pasos if not p.fragmentos_rag]
    assert con_manual and sin_manual, "Con la placa ASUS, algunos pasos tienen manual y otros no"

    modelo = ModeloSimulado()
    manual = generar_manual(config_ejemplo, compatibilidad, pasos, cliente=modelo, modelo="simulado")

    assert manual.compatible
    assert manual.total_pasos == len(plan)
    assert modelo.llamadas == len(con_manual), "Solo los pasos con manual llaman al modelo"
    assert manual.manual_markdown.count(TEXTO_SIN_MANUAL) == len(sin_manual)
    assert TEXTO_NO_VERIFICADO not in manual.manual_markdown

    # toda cita del texto corresponde a un fragmento recuperado
    recuperadas = {f.pagina_etiqueta for p in con_manual for f in p.fragmentos_rag}
    assert set(etiquetas_citadas(manual.manual_markdown)) <= recuperadas
    assert manual.citas_manuales
    assert {c["manual_id"] for c in manual.citas_manuales} == {manual_id_de_pieza(config_ejemplo.motherboard.name)}


def test_configuracion_incompatible_no_llama_al_modelo(motor, catalogo):
    psu_corta = next(n for n in nombres_por_tipo(catalogo)["psu"] if "EVGA 400 N1 400 W" in n)
    config = armar_config(catalogo, psu=psu_corta)
    compatibilidad = validar_compatibilidad(config)
    assert not compatibilidad.compatible

    modelo = ModeloSimulado()
    pasos = armar_pasos_con_contexto(generar_plan_ensamble(config))
    manual = generar_manual(config, compatibilidad, pasos, cliente=modelo, modelo="simulado")

    assert not manual.compatible
    assert manual.total_pasos == 0
    assert modelo.llamadas == 0
    assert "potencia_psu" in manual.manual_markdown


def test_una_placa_sin_manual_no_recibe_texto_de_otro_manual(motor, catalogo):
    asus = nombre_placa_asus(catalogo)
    otra = next(
        p["name"] for p in catalogo["motherboard"]
        if p["socket"] == "AM5" and p["memory_type"] == "DDR5" and p["size"] == "ATX"
        and p["name"] != asus and p.get("memory_type_confianza", "alta") == "alta"
    )
    config = armar_config(catalogo, motherboard=otra)
    compatibilidad = validar_compatibilidad(config)
    assert compatibilidad.compatible

    pasos = armar_pasos_con_contexto(generar_plan_ensamble(config))
    assert all(not p.fragmentos_rag for p in pasos), "Ninguna pieza de esta configuracion tiene manual"

    modelo = ModeloSimulado()
    manual = generar_manual(config, compatibilidad, pasos, cliente=modelo, modelo="simulado")
    assert modelo.llamadas == 0
    assert manual.manual_markdown.count(TEXTO_SIN_MANUAL) == len(pasos)
    assert manual.citas_manuales == []


# ---------------------------------------------------------------------------
# Modelo real (opcional)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    os.getenv("PROBAR_LLM_REAL") != "1",
    reason="Usa el modelo real y la red. Activala con PROBAR_LLM_REAL=1 (necesita la clave en .env)",
)
def test_modelo_real_cita_solo_paginas_recuperadas(motor, config_ejemplo):
    cliente, modelo = cargar_cliente()
    pasos = armar_pasos_con_contexto(generar_plan_ensamble(config_ejemplo))
    panel = next(p for p in pasos if p.paso.id_paso == "conectar_panel_frontal")

    texto, citados = redactar_paso(cliente, modelo, panel)

    assert TEXTO_NO_VERIFICADO not in texto, "El modelo no logro citar pagina valida (revisa el modelo en .env)"
    assert citados
    assert validar_citas(texto, panel.fragmentos_rag) == []
