"""Planificador de ensamble de PC mediante un DAG de dependencias físicas."""

import networkx as nx

# El grafo base representa un ensamble con SSD NVMe y refrigeración por aire.
# Cada tarea contiene: fase, título, descripción y búsqueda técnica para RAG.
TAREAS_BASE = {
    "preparar_area": (
        "fuera_gabinete", "Preparar el área de trabajo",
        "Desconectar el equipo de la red eléctrica y preparar una superficie segura.",
        "precauciones de seguridad para instalar componentes de PC",
    ),
    "instalar_cpu": (
        "fuera_gabinete", "Instalar el procesador",
        "Colocar el procesador en el socket correcto sin forzar los contactos.",
        "instalación del procesador orientación socket y mecanismo de retención",
    ),
    "instalar_ram": (
        "fuera_gabinete", "Instalar la memoria RAM",
        "Instalar los módulos en las ranuras recomendadas para doble canal.",
        "ranuras DIMM recomendadas configuración dual channel memoria RAM",
    ),
    "instalar_almacenamiento": (
        "fuera_gabinete", "Instalar la unidad NVMe",
        "Montar la unidad M.2 en la placa antes de introducirla en el gabinete.",
        "instalación M.2 NVMe ranura y tornillo de fijación",
    ),
    "aplicar_pasta_termica": (
        "fuera_gabinete", "Aplicar pasta térmica",
        "Verificar si el disipador trae pasta preaplicada; si no, colocarla siguiendo las instrucciones del fabricante.",
        "pasta térmica instrucciones del fabricante disipador",
    ),
    "instalar_refrigeracion": (
        "fuera_gabinete", "Instalar disipador por aire",
        "Montar el disipador y su soporte según el socket, evitando obstrucciones.",
        "montaje de disipador por aire backplate y soporte de CPU",
    ),
    "preparar_gabinete": (
        "preparacion_gabinete", "Preparar el gabinete",
        "Abrir el gabinete, comprobar separadores y preparar el espacio para la placa.",
        "preparación de gabinete separadores motherboard standoffs",
    ),
    "instalar_fuente": (
        "preparacion_gabinete", "Instalar la fuente de poder",
        "Fijar la fuente en el gabinete, con el cable de corriente desconectado.",
        "montaje de fuente de poder PSU orientación y tornillos",
    ),
    "montar_placa": (
        "montaje_chasis", "Montar la placa madre",
        "Fijar la placa a los separadores del gabinete sin forzar los tornillos.",
        "montaje de placa madre en gabinete separadores tornillos",
    ),
    "conectar_alimentacion_placa": (
        "montaje_chasis", "Conectar alimentación de la placa",
        "Conectar los cables principales de alimentación ATX y CPU/EPS según el manual.",
        "conectores ATX 24 pin y CPU EPS 8 pin motherboard",
    ),
    "conectar_panel_frontal": (
        "montaje_chasis", "Conectar panel frontal",
        "Conectar botones, LEDs y puertos del gabinete siguiendo el diagrama oficial.",
        "diagrama pines system panel header power switch reset LED F_PANEL",
    ),
    "instalar_gpu": (
        "montaje_chasis", "Instalar la tarjeta gráfica",
        "Insertar la GPU en la ranura PCIe y fijarla al gabinete.",
        "instalación GPU ranura PCI Express y soporte gabinete",
    ),
    "conectar_alimentacion_gpu": (
        "cableado_y_cierre", "Conectar alimentación de la GPU",
        "Conectar los cables PCIe/12VHPWR requeridos por la tarjeta gráfica, si aplica.",
        "cable alimentación tarjeta gráfica PCIe 8 pin 12VHPWR instrucciones",
    ),
    "revisar_conexiones": (
        "cableado_y_cierre", "Revisar conexiones",
        "Comprobar conexiones, ventiladores, separadores y cables antes del cierre.",
        "lista de comprobación conectores alimentación ventiladores PC",
    ),
    "cerrar_gabinete": (
        "cableado_y_cierre", "Cerrar el gabinete",
        "Organizar los cables y volver a colocar los paneles del gabinete.",
        "cierre del gabinete organización de cables y paneles",
    ),
}

# Una arista (A, B) obliga a ejecutar A antes que B.
DEPENDENCIAS_BASE = (
    ("preparar_area", "instalar_cpu"),
    ("instalar_cpu", "instalar_ram"),
    ("instalar_cpu", "instalar_almacenamiento"),
    ("instalar_cpu", "aplicar_pasta_termica"),
    ("instalar_almacenamiento", "instalar_refrigeracion"),
    ("aplicar_pasta_termica", "instalar_refrigeracion"),
    ("instalar_ram", "preparar_gabinete"),
    ("instalar_almacenamiento", "preparar_gabinete"),
    ("instalar_refrigeracion", "preparar_gabinete"),
    ("preparar_gabinete", "instalar_fuente"),
    ("preparar_gabinete", "montar_placa"),
    ("instalar_ram", "montar_placa"),
    ("instalar_almacenamiento", "montar_placa"),
    ("instalar_refrigeracion", "montar_placa"),
    ("instalar_fuente", "conectar_alimentacion_placa"),
    ("montar_placa", "conectar_alimentacion_placa"),
    ("montar_placa", "conectar_panel_frontal"),
    ("conectar_alimentacion_placa", "instalar_gpu"),
    ("conectar_panel_frontal", "instalar_gpu"),
    ("instalar_gpu", "conectar_alimentacion_gpu"),
    ("instalar_fuente", "conectar_alimentacion_gpu"),
    ("conectar_alimentacion_gpu", "revisar_conexiones"),
    ("conectar_panel_frontal", "revisar_conexiones"),
    ("revisar_conexiones", "cerrar_gabinete"),
)


def crear_grafo_base() -> nx.DiGraph:
    """Crea y verifica el DAG base de instalación (NVMe y aire)."""
    grafo = nx.DiGraph()
    for id_paso, (fase, titulo, descripcion, consulta) in TAREAS_BASE.items():
        grafo.add_node(
            id_paso,
            fase=fase,
            titulo=titulo,
            descripcion_base=descripcion,
            consulta_base=consulta,
        )
    grafo.add_edges_from(DEPENDENCIAS_BASE)
    if not nx.is_directed_acyclic_graph(grafo):
        raise ValueError("El grafo base contiene un ciclo de dependencias")
    return grafo
