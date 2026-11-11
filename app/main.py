"""Interfaz Streamlit de PC-Assembly-RAG (issue #11).

Conecta el catálogo, el validador de compatibilidad y el planificador de ensamble.
Pendiente: el manual redactado por el LLM y las citas (issues #8 y #10).
"""

import sys
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
from src.esquemas import ConfiguracionPC, ResultadoCompatibilidad  # noqa: E402
from src.planificador.grafo import generar_plan_ensamble  # noqa: E402

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


def mostrar_pasos(config: ConfiguracionPC) -> None:
    st.subheader("Orden de montaje")
    for paso in generar_plan_ensamble(config):
        with st.expander(f"{paso.orden}. {paso.titulo}  ·  {FASES[paso.fase]}"):
            st.write(paso.descripcion_base)
            previas = ", ".join(paso.dependencias_previas) or "ninguna"
            st.caption(f"Después de: {previas}")
            # TODO (#8 y #10): texto del LLM y citas del manual con página.
    st.info("El manual redactado con citas del fabricante llegará con el RAG y el generador LLM.")


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

    if mostrar_compatibilidad(config).compatible:
        mostrar_pasos(config)
    else:
        st.warning("Corrige los errores para ver el orden de montaje.")


main()
