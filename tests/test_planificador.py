"""Pruebas de precedencia física y planificación adaptativa del ensamble."""

import networkx as nx
import pytest

from src.esquemas import ConfiguracionPC
from src.planificador.grafo import (
    crear_grafo_adaptativo,
    crear_grafo_base,
    generar_plan_ensamble,
)


@pytest.fixture
def configuracion() -> ConfiguracionPC:
    """Configuración AM5 válida basada en el contrato del proyecto."""
    return ConfiguracionPC.model_validate({
        "cpu": {
            "name": "AMD Ryzen 5 7600X", "brand": "AMD", "socket": "AM5",
            "speed": 4.7, "core_count": 6, "thread_count": 12, "power": 105,
        },
        "motherboard": {
            "name": "Asus TUF GAMING B650-PLUS WIFI", "brand": "AMD",
            "socket": "AM5", "size": "ATX", "memory_type": "DDR5",
        },
        "gpu": {
            "name": "RTX 4070", "brand": "NVIDIA", "vram": 12,
            "resolution": "1440p", "power": 200,
        },
        "memory": {"name": "DDR5 32 GB", "type": "DDR5", "size": 32},
        "storage": {"name": "SSD 1 TB", "type": "NVME", "space": 1000},
        "cooler": {"name": "Disipador CPU", "type": "air"},
        "psu": {"name": "PSU 750 W", "power": 750, "size": "ATX"},
        "case": {"name": "Gabinete ATX", "size": "ATX"},
    })


def cambiar(config: ConfiguracionPC, almacenamiento: str, refrigeracion: str) -> ConfiguracionPC:
    datos = config.model_dump()
    datos["storage"]["type"] = almacenamiento
    datos["cooler"]["type"] = refrigeracion
    return ConfiguracionPC.model_validate(datos)


def posiciones_de(config: ConfiguracionPC) -> dict[str, int]:
    return {p.id_paso: p.orden for p in generar_plan_ensamble(config)}


def test_grafo_base_acyclico():
    grafo = crear_grafo_base()
    assert isinstance(grafo, nx.DiGraph)
    assert nx.is_directed_acyclic_graph(grafo)
    assert grafo.has_edge("instalar_cpu", "aplicar_pasta_termica")
    assert grafo.has_edge("conectar_alimentacion_placa", "instalar_gpu")


@pytest.mark.parametrize("almacenamiento", ["NVME", "SATA", "HDD"])
@pytest.mark.parametrize("refrigeracion", ["air", "liquid"])
def test_grafos_adaptativos_aciclicos(configuracion, almacenamiento, refrigeracion):
    grafo = crear_grafo_adaptativo(cambiar(configuracion, almacenamiento, refrigeracion))
    assert nx.is_directed_acyclic_graph(grafo)


@pytest.mark.parametrize("almacenamiento", ["NVME", "SATA", "HDD"])
@pytest.mark.parametrize("refrigeracion", ["air", "liquid"])
def test_dependencias_respetadas(configuracion, almacenamiento, refrigeracion):
    config = cambiar(configuracion, almacenamiento, refrigeracion)
    grafo = crear_grafo_adaptativo(config)
    plan = generar_plan_ensamble(config)
    posiciones = {paso.id_paso: paso.orden for paso in plan}

    assert len(plan) == len(grafo.nodes)
    assert len(posiciones) == len(plan)
    assert [paso.orden for paso in plan] == list(range(1, len(plan) + 1))
    for anterior, siguiente in grafo.edges:
        assert posiciones[anterior] < posiciones[siguiente]
    for paso in plan:
        assert set(paso.dependencias_previas) == set(grafo.predecessors(paso.id_paso))
        assert paso.componentes_involucrados
        assert paso.consulta_rag.strip()


@pytest.mark.parametrize("almacenamiento", ["NVME", "SATA", "HDD"])
@pytest.mark.parametrize("refrigeracion", ["air", "liquid"])
def test_cpu_antes_de_pasta_y_refrigeracion(configuracion, almacenamiento, refrigeracion):
    posiciones = posiciones_de(cambiar(configuracion, almacenamiento, refrigeracion))
    assert posiciones["instalar_cpu"] < posiciones["aplicar_pasta_termica"]
    assert posiciones["aplicar_pasta_termica"] < posiciones["instalar_refrigeracion"]


@pytest.mark.parametrize("almacenamiento", ["NVME", "SATA", "HDD"])
@pytest.mark.parametrize("refrigeracion", ["air", "liquid"])
def test_gpu_despues_de_placa_y_cableado(configuracion, almacenamiento, refrigeracion):
    posiciones = posiciones_de(cambiar(configuracion, almacenamiento, refrigeracion))
    assert posiciones["montar_placa"] < posiciones["instalar_gpu"]
    assert posiciones["conectar_alimentacion_placa"] < posiciones["instalar_gpu"]
    assert posiciones["conectar_panel_frontal"] < posiciones["instalar_gpu"]
    assert posiciones["instalar_gpu"] < posiciones["conectar_alimentacion_gpu"]


def test_nvme_fuera_del_gabinete(configuracion):
    grafo = crear_grafo_adaptativo(configuracion)
    posiciones = posiciones_de(configuracion)
    assert "conectar_almacenamiento_sata" not in grafo
    assert grafo.nodes["instalar_almacenamiento"]["fase"] == "fuera_gabinete"
    assert posiciones["instalar_almacenamiento"] < posiciones["montar_placa"]


@pytest.mark.parametrize("tipo", ["SATA", "HDD"])
def test_almacenamiento_bahia_antes_de_gpu(configuracion, tipo):
    config = cambiar(configuracion, tipo, "air")
    grafo = crear_grafo_adaptativo(config)
    posiciones = posiciones_de(config)
    assert grafo.nodes["instalar_almacenamiento"]["fase"] == "preparacion_gabinete"
    assert posiciones["preparar_gabinete"] < posiciones["instalar_almacenamiento"]
    assert posiciones["instalar_almacenamiento"] < posiciones["conectar_almacenamiento_sata"]
    assert posiciones["conectar_almacenamiento_sata"] < posiciones["instalar_gpu"]


def test_disipador_aire_antes_de_placa(configuracion):
    posiciones = posiciones_de(configuracion)
    assert "instalar_radiador" not in posiciones
    assert posiciones["instalar_refrigeracion"] < posiciones["montar_placa"]


def test_refrigeracion_liquida_radiador_y_bloque(configuracion):
    config = cambiar(configuracion, "NVME", "liquid")
    grafo = crear_grafo_adaptativo(config)
    posiciones = posiciones_de(config)
    assert posiciones["preparar_gabinete"] < posiciones["instalar_radiador"]
    assert posiciones["instalar_radiador"] < posiciones["montar_placa"]
    assert posiciones["montar_placa"] < posiciones["aplicar_pasta_termica"]
    assert posiciones["aplicar_pasta_termica"] < posiciones["instalar_refrigeracion"]
    assert grafo.nodes["instalar_refrigeracion"]["fase"] == "montaje_chasis"


def test_consulta_rag_menciona_hardware_real(configuracion):
    pasos = generar_plan_ensamble(configuracion)
    paso_ram = next(p for p in pasos if p.id_paso == "instalar_ram")
    assert configuracion.motherboard.name in paso_ram.consulta_rag
    assert configuracion.memory.name in paso_ram.consulta_rag
    assert "dual channel" in paso_ram.consulta_rag
