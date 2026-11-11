"""Planificador de ensamble de PC mediante un DAG de dependencias físicas."""

import networkx as nx

from src.esquemas import ConfiguracionPC, PasoEnsamble

# El grafo base representa un ensamble con SSD NVMe y refrigeración por aire.
# Cada tarea contiene: fase, título, descripción y búsqueda técnica para RAG.
TAREAS_BASE = {
    "preparar_area": (
        "fuera_gabinete", "Preparar el área de trabajo",
        "Desconectar el equipo de la red eléctrica y preparar una superficie segura.",
        "safety precautions before installing PC components electrostatic discharge",
    ),
    "instalar_cpu": (
        "fuera_gabinete", "Instalar el procesador",
        "Colocar el procesador en el socket correcto sin forzar los contactos.",
        "CPU installation socket orientation alignment mark and retention bracket",
    ),
    "instalar_ram": (
        "fuera_gabinete", "Instalar la memoria RAM",
        "Instalar los módulos en las ranuras recomendadas para doble canal.",
        "recommended DIMM slots dual channel memory configuration",
    ),
    "instalar_almacenamiento": (
        "fuera_gabinete", "Instalar la unidad NVMe",
        "Montar la unidad M.2 en la placa antes de introducirla en el gabinete.",
        "M.2 NVMe SSD installation slot and retention screw",
    ),
    "aplicar_pasta_termica": (
        "fuera_gabinete", "Aplicar pasta térmica",
        "Verificar si el disipador trae pasta preaplicada; si no, colocarla siguiendo las instrucciones del fabricante.",
        "thermal paste application CPU cooler installation instructions",
    ),
    "instalar_refrigeracion": (
        "fuera_gabinete", "Instalar disipador por aire",
        "Montar el disipador y su soporte según el socket, evitando obstrucciones.",
        "air CPU cooler mounting bracket backplate and CPU_FAN header",
    ),
    "preparar_gabinete": (
        "preparacion_gabinete", "Preparar el gabinete",
        "Abrir el gabinete, comprobar separadores y preparar el espacio para la placa.",
        "chassis preparation motherboard standoffs and I/O shield",
    ),
    "instalar_fuente": (
        "preparacion_gabinete", "Instalar la fuente de poder",
        "Fijar la fuente en el gabinete, con el cable de corriente desconectado.",
        "power supply PSU mounting orientation and screws",
    ),
    "montar_placa": (
        "montaje_chasis", "Montar la placa madre",
        "Fijar la placa a los separadores del gabinete sin forzar los tornillos.",
        "motherboard installation in chassis standoffs and screws",
    ),
    "conectar_alimentacion_placa": (
        "montaje_chasis", "Conectar alimentación de la placa",
        "Conectar los cables principales de alimentación ATX y CPU/EPS según el manual.",
        "ATX 24-pin and CPU EPS 8-pin power connectors motherboard",
    ),
    "conectar_panel_frontal": (
        "montaje_chasis", "Conectar panel frontal",
        "Conectar botones, LEDs y puertos del gabinete siguiendo el diagrama oficial.",
        "System Panel header pin layout power switch reset switch HDD LED PLED F_PANEL",
    ),
    "instalar_gpu": (
        "montaje_chasis", "Instalar la tarjeta gráfica",
        "Insertar la GPU en la ranura PCIe y fijarla al gabinete.",
        "graphics card installation PCIe x16 slot and bracket screws",
    ),
    "conectar_alimentacion_gpu": (
        "cableado_y_cierre", "Conectar alimentación de la GPU",
        "Conectar los cables PCIe/12VHPWR requeridos por la tarjeta gráfica, si aplica.",
        "graphics card power connectors PCIe 8-pin 12VHPWR cable requirements",
    ),
    "revisar_conexiones": (
        "cableado_y_cierre", "Revisar conexiones",
        "Comprobar conexiones, ventiladores, separadores y cables antes del cierre.",
        "final checklist power connectors fans and front panel cables",
    ),
    "cerrar_gabinete": (
        "cableado_y_cierre", "Cerrar el gabinete",
        "Organizar los cables y volver a colocar los paneles del gabinete.",
        "cable management and closing chassis side panels",
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

# Componentes cuyos nombres contextualizan cada búsqueda en los manuales.
COMPONENTES_POR_PASO = {
    "preparar_area": ("case",),
    "instalar_cpu": ("cpu", "motherboard"),
    "instalar_ram": ("memory", "motherboard"),
    "instalar_almacenamiento": ("storage", "motherboard", "case"),
    "aplicar_pasta_termica": ("cpu", "cooler"),
    "instalar_refrigeracion": ("cooler", "motherboard", "case"),
    "preparar_gabinete": ("case",),
    "instalar_fuente": ("psu", "case"),
    "instalar_radiador": ("cooler", "case"),
    "montar_placa": ("motherboard", "case"),
    "conectar_alimentacion_placa": ("motherboard", "psu"),
    "conectar_panel_frontal": ("motherboard", "case"),
    "instalar_gpu": ("gpu", "motherboard", "case"),
    "conectar_alimentacion_gpu": ("gpu", "psu"),
    "conectar_almacenamiento_sata": ("storage", "motherboard", "psu"),
    "revisar_conexiones": ("motherboard", "psu", "gpu"),
    "cerrar_gabinete": ("case",),
}


def crear_grafo_adaptativo(config: ConfiguracionPC) -> nx.DiGraph:
    """Ajusta el grafo base según almacenamiento y refrigeración elegidos."""
    grafo = crear_grafo_base()

    if config.storage.type in ("SATA", "HDD"):
        # Esta unidad va en una bahía, no sobre la placa fuera del chasis.
        grafo.remove_edge("instalar_almacenamiento", "instalar_refrigeracion")
        grafo.remove_edge("instalar_almacenamiento", "preparar_gabinete")
        grafo.add_edge("preparar_gabinete", "instalar_almacenamiento")
        grafo.nodes["instalar_almacenamiento"].update(
            fase="preparacion_gabinete",
            titulo="Montar unidad SATA/HDD en una bahía",
            descripcion_base="Fijar la unidad en una bahía compatible del gabinete.",
            consulta_base="SATA drive or HDD installation in drive bay",
        )
        grafo.add_node(
            "conectar_almacenamiento_sata",
            fase="montaje_chasis",
            titulo="Conectar la unidad SATA/HDD",
            descripcion_base="Conectar datos SATA a la placa y alimentación SATA a la fuente.",
            consulta_base="SATA ports on motherboard and SATA power connector from power supply",
        )
        grafo.add_edges_from([
            ("instalar_almacenamiento", "conectar_almacenamiento_sata"),
            ("montar_placa", "conectar_almacenamiento_sata"),
            ("instalar_fuente", "conectar_almacenamiento_sata"),
            ("conectar_almacenamiento_sata", "instalar_gpu"),
            ("conectar_almacenamiento_sata", "revisar_conexiones"),
        ])

    if config.cooler.type == "liquid":
        # En refrigeración líquida, primero se prepara el chasis y se monta
        # el radiador; el bloque se instala tras fijar la placa madre.
        grafo.remove_edge("instalar_refrigeracion", "preparar_gabinete")
        grafo.remove_edge("instalar_refrigeracion", "montar_placa")
        grafo.add_node(
            "instalar_radiador",
            fase="preparacion_gabinete",
            titulo="Montar radiador en el gabinete",
            descripcion_base="Fijar el radiador AIO en la posición permitida por el gabinete.",
            consulta_base="AIO radiator mounting position and orientation in chassis",
        )
        grafo.add_edges_from([
            ("preparar_gabinete", "instalar_radiador"),
            ("instalar_radiador", "montar_placa"),
            ("montar_placa", "aplicar_pasta_termica"),
            ("instalar_radiador", "instalar_refrigeracion"),
            ("instalar_refrigeracion", "conectar_alimentacion_placa"),
        ])
        grafo.nodes["aplicar_pasta_termica"]["fase"] = "montaje_chasis"
        grafo.nodes["instalar_refrigeracion"].update(
            fase="montaje_chasis",
            titulo="Montar bloque de refrigeración líquida",
            descripcion_base="Fijar el bloque al CPU y conectar bomba y ventiladores según el fabricante.",
            consulta_base="AIO pump block installation and AIO_PUMP CPU_FAN header connections",
        )

    if not nx.is_directed_acyclic_graph(grafo):
        raise ValueError("La configuración generó un ciclo de dependencias")
    return grafo


def generar_plan_ensamble(config: ConfiguracionPC) -> list[PasoEnsamble]:
    """Ordena el DAG y devuelve pasos compatibles con el contrato Pydantic."""
    grafo = crear_grafo_adaptativo(config)
    orden_topologico = list(nx.topological_sort(grafo))
    posiciones = {id_paso: i for i, id_paso in enumerate(orden_topologico)}
    plan = []

    for numero, id_paso in enumerate(orden_topologico, start=1):
        datos = grafo.nodes[id_paso]
        componentes = [
            getattr(config, campo).name
            for campo in COMPONENTES_POR_PASO[id_paso]
        ]
        dependencias = sorted(
            grafo.predecessors(id_paso), key=posiciones.__getitem__
        )
        plan.append(PasoEnsamble(
            orden=numero,
            id_paso=id_paso,
            fase=datos["fase"],
            titulo=datos["titulo"],
            descripcion_base=datos["descripcion_base"],
            componentes_involucrados=componentes,
            dependencias_previas=dependencias,
            consulta_rag=f"{datos['consulta_base']} {' '.join(componentes)}",
        ))

    return plan
