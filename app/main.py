"""Interfaz Streamlit de PC-Assembly-RAG (issue #11).

Conecta el catálogo, el validador de compatibilidad y el planificador de ensamble.
Pendiente: el manual redactado por el LLM y las citas (issues #8 y #10).
"""

import os
import sys
from datetime import date
from pathlib import Path

import streamlit as st

# Permite `streamlit run app/main.py` sin instalar el paquete: añade la raíz del repo.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.catalogo import (  # noqa: E402
    TIPOS_PIEZA, cargar_catalogo, construir_configuracion, nombres_por_tipo,
)
from src.compatibilidad.validador import validar_compatibilidad  # noqa: E402
from src.esquemas import ConfiguracionPC, PasoEnsamble, ResultadoCompatibilidad  # noqa: E402
from src.llm import cargar_cliente, generar_manual  # noqa: E402
from src.llm.generador import TEXTO_NO_VERIFICADO  # noqa: E402
from src.pipeline import armar_pasos_con_contexto  # noqa: E402
from src.rag.buscador import RUTA_CHUNKS_JSONL  # noqa: E402
from src.planificador.grafo import generar_plan_ensamble  # noqa: E402
from scripts.ingest_manuals import CARPETA_RAW, procesar_directorio  # noqa: E402

# Despliegue público (LIMITAR_GENERACIONES=1): la clave del modelo es del autor y gratuita,
# así que se limita cuántos manuales puede generar cada visitante y la demo completa por día.
MAX_POR_SESION = 2
MAX_POR_DIA = 30
RUTA_MANUAL_EJEMPLO = RAIZ / "docs" / "demo" / "manual_ejemplo.md"

ETIQUETAS = {
    "cpu": "Procesador", "motherboard": "Placa madre", "gpu": "Tarjeta gráfica",
    "memory": "Memoria RAM", "storage": "Almacenamiento", "cooler": "Refrigeración",
    "psu": "Fuente de poder", "case": "Gabinete",
}
FASES = {
    "fuera_gabinete": "Fuera del gabinete",
    "preparacion_gabinete": "Preparación del gabinete",
    "montaje_chasis": "Montaje en el chasis",
    "cableado_y_cierre": "Cableado y cierre",
}
# Fragmento del nombre que se busca para precargar un ejemplo compatible.
EJEMPLO = {
    "cpu": "Ryzen 5 7600X", "motherboard": "TUF GAMING B650-PLUS WIFI",
    "gpu": "RTX 4070 12 GB", "memory": "Vengeance 32 GB (2 x 16 GB) DDR5-6000 CL36",
    "storage": "980 Pro 1 TB", "cooler": "Hyper 212 Black Edition",
    "psu": "RM750e (2023)", "case": "4000D Airflow ATX",
}


@st.cache_data
def leer_catalogo() -> dict[str, list[dict]]:
    """El JSON pesa 2,4 MB: se lee una sola vez por sesión."""
    return cargar_catalogo()


def indice_inicial(opciones: list[str], fragmento: str) -> int:
    """Posición de la primera opción que contiene el fragmento (0 si no hay)."""
    return next((i for i, n in enumerate(opciones) if fragmento in n), 0)


def elegir_piezas(nombres: dict[str, list[str]]) -> dict[str, str]:
    """Un selector por tipo de pieza. Se puede escribir para filtrar la lista."""
    return {
        tipo: st.sidebar.selectbox(
            ETIQUETAS[tipo], nombres[tipo],
            index=indice_inicial(nombres[tipo], EJEMPLO[tipo]), key=tipo,
        )
        for tipo in TIPOS_PIEZA
    }


def mostrar_compatibilidad(config: ConfiguracionPC) -> ResultadoCompatibilidad:
    resultado = validar_compatibilidad(config)
    col1, col2, col3 = st.columns(3)
    col1.metric("Consumo estimado", f"{resultado.consumo_estimado_w} W")
    col2.metric("Fuente recomendada", f"{resultado.potencia_recomendada_w} W")
    col3.metric("Fuente elegida", f"{config.psu.power} W")

    if resultado.compatible:
        st.success("Configuración compatible.")
    for error in resultado.errores:
        st.error(f"**{error.regla}:** {error.mensaje}")
    for aviso in resultado.advertencias:
        st.warning(aviso)
    if config.motherboard.memory_type_confianza == "media":
        st.info(
            f"El tipo de RAM de esta placa ({config.motherboard.memory_type}) se dedujo "
            "por marca o socket, no figura en su nombre. Verifícalo antes de comprar."
        )
    return resultado


def mostrar_pasos(plan: list[PasoEnsamble]) -> None:
    st.subheader("Orden de montaje")
    for paso in plan:
        with st.expander(f"{paso.orden}. {paso.titulo}  ·  {FASES[paso.fase]}"):
            st.write(paso.descripcion_base)
            previas = ", ".join(paso.dependencias_previas) or "ninguna"
            st.caption(f"Después de: {previas}")


@st.cache_resource(show_spinner="Preparando el índice del manual (solo la primera vez)...")
def asegurar_ingesta() -> None:
    """En un servidor limpio manual_chunks.jsonl no existe (no está en Git): se genera desde el PDF."""
    if not RUTA_CHUNKS_JSONL.exists():
        procesar_directorio(CARPETA_RAW)


@st.cache_resource
def contador_global() -> dict:
    """Manuales generados hoy por todos los visitantes. Se reinicia si el servidor se reinicia."""
    return {"dia": date.today(), "n": 0}


def limites_activos() -> bool:
    return os.getenv("LIMITAR_GENERACIONES", "") == "1"


def hay_cupo() -> tuple[bool, str]:
    """(puede generar, motivo si no puede). Solo aplica en el despliegue público."""
    if not limites_activos():
        return True, ""
    global_ = contador_global()
    if global_["dia"] != date.today():
        global_["dia"], global_["n"] = date.today(), 0
    if st.session_state.get("n_generaciones", 0) >= MAX_POR_SESION:
        return False, f"Ya generaste {MAX_POR_SESION} manuales en esta sesión."
    if global_["n"] >= MAX_POR_DIA:
        return False, "La demo alcanzó su cupo diario de manuales."
    return True, ""


def registrar_generacion() -> None:
    st.session_state["n_generaciones"] = st.session_state.get("n_generaciones", 0) + 1
    contador_global()["n"] += 1


def mostrar_ejemplo(motivo: str) -> None:
    """Respaldo del despliegue público: un manual real ya generado, sin llamar al modelo."""
    st.info(
        f"{motivo} Te muestro un manual de ejemplo ya generado con el modelo real para la "
        "configuración precargada (Ryzen 5 7600X + ASUS TUF B650). Es una salida sin editar: "
        "puede traer pasos cortados o marcados como no verificados."
    )
    if RUTA_MANUAL_EJEMPLO.exists():
        st.markdown(RUTA_MANUAL_EJEMPLO.read_text(encoding="utf-8"))


def generar_y_guardar(
    config: ConfiguracionPC, resultado: ResultadoCompatibilidad, plan: list[PasoEnsamble]
) -> None:
    """Llama al modelo (tarda decenas de segundos) y guarda el manual en la sesión."""
    puede, motivo = hay_cupo()
    if not puede:
        mostrar_ejemplo(motivo)
        return
    asegurar_ingesta()
    if not RUTA_CHUNKS_JSONL.exists():
        st.error("Falta la ingesta de los manuales. Corre: python scripts/ingest_manuals.py (con el entorno .venv activo)")
        return
    try:
        cliente, modelo = cargar_cliente()
    except (RuntimeError, ValueError) as error:
        if limites_activos():
            mostrar_ejemplo("El modelo no está disponible en este momento.")
        else:
            st.error(f"No se puede usar el modelo: {error}")
        return
    registrar_generacion()

    barra = st.progress(0.0, text="Buscando en los manuales...")
    pasos_con_contexto = armar_pasos_con_contexto(plan)

    def avanzar(indice: int, total: int, titulo: str) -> None:
        barra.progress(indice / total, text=f"Redactando el paso {indice + 1} de {total}: {titulo}")

    manual = generar_manual(
        config, resultado, pasos_con_contexto, cliente=cliente, modelo=modelo, progreso=avanzar
    )
    barra.empty()
    st.session_state["manual"] = {"firma": config.model_dump_json(), "datos": manual}


def mostrar_manual(
    config: ConfiguracionPC, resultado: ResultadoCompatibilidad, plan: list[PasoEnsamble]
) -> None:
    st.subheader("Manual con citas del fabricante")
    st.caption(
        "Lo redacta un modelo de lenguaje, pero solo con fragmentos de los manuales oficiales. "
        "El orden y la compatibilidad los calcula el código."
    )
    if st.button("Generar manual", key="generar", type="primary"):
        generar_y_guardar(config, resultado, plan)

    # Streamlit vuelve a ejecutar esta función con cada cambio de selector: el manual
    # se guarda en la sesión para no llamar de nuevo al modelo.
    guardado = st.session_state.get("manual")
    if not guardado:
        return
    if guardado["firma"] != config.model_dump_json():
        st.info("Cambiaste las piezas desde que se generó este manual. Genera uno nuevo para esta configuración.")
        return

    manual = guardado["datos"]
    sin_verificar = manual.manual_markdown.count(TEXTO_NO_VERIFICADO)
    if sin_verificar:
        st.warning(
            f"{sin_verificar} paso(s) no se pudieron respaldar con una cita del manual "
            "y muestran solo la descripción base."
        )
    st.markdown(manual.manual_markdown)
    with st.expander(f"Fuentes citadas ({len(manual.citas_manuales)})"):
        if not manual.citas_manuales:
            st.caption("Ningún paso quedó respaldado por una cita del manual.")
        for cita in manual.citas_manuales:
            pagina = cita["pagina_etiqueta"] or cita["pagina"]
            st.markdown(f"- **{cita['titulo']}**, pág. {pagina} · {cita['seccion']} · pasos: {', '.join(cita['pasos'])}")

def main() -> None:
    st.set_page_config(page_title="PC-Assembly-RAG", layout="wide")
    st.title("PC-Assembly-RAG")
    st.caption("Elige las 8 piezas en la barra lateral. Se valida la compatibilidad y se calcula el orden de montaje.")

    catalogo = leer_catalogo()
    st.sidebar.header("Tus piezas")
    elegidas = elegir_piezas(nombres_por_tipo(catalogo))

    try:
        config = construir_configuracion(catalogo, **elegidas)
    except ValueError as error:  # pydantic.ValidationError hereda de ValueError
        st.error(f"No se pudo armar la configuración: {error}")
        st.stop()

    resultado = mostrar_compatibilidad(config)
    if resultado.compatible:
        plan = generar_plan_ensamble(config)
        mostrar_pasos(plan)
        mostrar_manual(config, resultado, plan)
    else:
        st.warning("Corrige los errores para ver el orden de montaje.")


main()
