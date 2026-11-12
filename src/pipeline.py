"""
Pegamento entre los modulos: arma los pasos del plan con el contexto de los manuales.

Lo usan la interfaz y la prueba de extremo a extremo, para no repetir esta logica.
"""

from src.esquemas import PasoConContexto, PasoEnsamble
from src.manuales import manual_id_de_pieza
from src.rag.buscador import buscar_contexto_paso


def consulta_para(paso: PasoEnsamble) -> PasoEnsamble:
    """
    Unico punto donde se decide la consulta que se envia al buscador.

    El planificador arma consulta_rag como "<consulta base> <nombres de las piezas>". Como
    la busqueda ya se limita al manual de la pieza (manual_id), los nombres no aportan y
    diluyen la consulta: en la prueba con el manual ASUS, el fragmento de "System Panel
    header" quedaba en la posicion 7 con ellos y en la 1 sin ellos. Aqui se quitan.
    Si la evaluacion de recuperacion (issue #9) indica otra cosa, el cambio va en esta funcion.
    """
    sufijo = " " + " ".join(paso.componentes_involucrados)
    return paso.model_copy(update={"consulta_rag": paso.consulta_rag.removesuffix(sufijo)})


def manual_id_del_paso(paso: PasoEnsamble) -> str | None:
    """manual_id del primer manual que cubra alguna de las piezas del paso, o None."""
    for nombre in paso.componentes_involucrados:
        manual_id = manual_id_de_pieza(nombre)
        if manual_id:
            return manual_id
    return None


def armar_pasos_con_contexto(plan: list[PasoEnsamble], top_k: int = 2) -> list[PasoConContexto]:
    """
    Para cada paso busca fragmentos solo en el manual de sus piezas.

    Si ninguna pieza del paso tiene manual, no busca: deja fragmentos_rag vacio
    (nunca se devuelve texto de un manual que no corresponde).
    """
    resultado = []
    for paso in plan:
        manual_id = manual_id_del_paso(paso)
        fragmentos = (
            buscar_contexto_paso(consulta_para(paso), top_k=top_k, manual_id=manual_id)
            if manual_id
            else []
        )
        resultado.append(PasoConContexto(paso=paso, fragmentos_rag=fragmentos))
    return resultado
