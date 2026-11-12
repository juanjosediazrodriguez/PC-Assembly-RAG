"""
Pruebas del Módulo 1 — Validador de compatibilidad (issue #3).

20 escenarios con piezas reales de data/processed/hardware_catalog.json:
- 10 configuraciones compatibles (incluye casos al límite).
- 10 configuraciones incompatibles: 2 por regla + 2 con varios errores a la vez.

Cada prueba revisa:
1. Si la configuración es compatible o no.
2. Las reglas exactas que fallan (ni una más, ni una menos).
3. El consumo estimado y la potencia recomendada, calculados a mano con la
   fórmula del contrato:
       consumo     = CPU + GPU + 75 W
       recomendada = consumo + 150 W
4. La cantidad de advertencias.

Requisito: generar antes el catálogo con `python scripts/build_catalog.py`.
Ejecutar con: `pytest tests/test_compatibilidad.py -v`
"""

import json
from pathlib import Path

import pytest

from src.compatibilidad.validador import validar_compatibilidad
from src.esquemas import ConfiguracionPC

RUTA_CATALOGO = Path(__file__).resolve().parent.parent / "data" / "processed" / "hardware_catalog.json"

# ---------------------------------------------------------------------------
# Piezas reales del catálogo (nombre exacto)
# ---------------------------------------------------------------------------

# Procesadores
R5_7600X = "AMD Ryzen 5 7600X 4.7 GHz 6-Core Processor (100-100000593WOF)"         # AM5, 65 W
R5_5600X = "AMD Ryzen 5 5600X 3.7 GHz 6-Core Processor (100-100000065BOX)"         # AM4, 50 W
I5_13600K = "Intel Core i5-13600K 3.5 GHz 14-Core Processor (BX8071513600K)"       # LGA 1700, 80 W
I5_12400 = "Intel Core i5-12400 2.5 GHz 6-Core Processor (BX8071512400)"           # LGA 1700, 80 W
I5_10400 = "Intel Core i5-10400 2.9 GHz 6-Core Processor (BX8070110400)"           # LGA 1200, 65 W
I7_9700K = "Intel Core i7-9700K 3.6 GHz 8-Core Processor (BX80684I79700K)"         # LGA 1151, 65 W
I9_13900K = "Intel Core i9-13900K 3 GHz 24-Core Processor (BX8071513900K)"         # LGA 1700, 250 W
PHENOM_965 = "AMD Phenom II X4 965 Black 3.4 GHz Quad-Core Processor (HDZ965FBGMBOX)"  # AM3, 95 W

# Placas madre
B650_TUF = "Asus TUF GAMING B650-PLUS WIFI ATX AM5 Motherboard (TUF GAMING B650-PLUS WIFI)"  # AM5, ATX, DDR5
B550M_DS3H = "Gigabyte B550M DS3H Micro ATX AM4 Motherboard (B550M DS3H)"                    # AM4, MicroATX, DDR4
Z790_ELITE = "Gigabyte Z790 AORUS ELITE AX ATX LGA1700 Motherboard (Z790 AORUS ELITE AX)"    # LGA 1700, ATX, DDR5
B760M_DDR4 = "Gigabyte B760M DS3H DDR4 Micro ATX LGA1700 Motherboard (B760M DS3H DDR4)"      # LGA 1700, MicroATX, DDR4
B560M_MORTAR = "MSI MAG B560M MORTAR Micro ATX LGA1200 Motherboard (MAG B560M MORTAR)"       # LGA 1200, MicroATX, DDR4
Z390_I = "Asus ROG STRIX Z390-I GAMING Mini ITX LGA1151 Motherboard (ROG STRIX Z390-I GAMING)"  # LGA 1151, ITX, DDR4
M4A88TD = "Asus M4A88TD-V EVO/USB3 ATX AM3 Motherboard (M4A88TD-V EVO/USB3)"                 # AM3, ATX, DDR3

# Tarjetas gráficas
RTX_4090 = "Asus ROG STRIX GAMING OC GeForce RTX 4090 24 GB Video Card (ROG-STRIX-RTX4090-O24G-GAMING)"  # 450 W
RTX_4070 = "Asus TUF GAMING GeForce RTX 4070 12 GB Video Card (tuf-rtx4070-12g-gaming)"                  # 250 W
RTX_3060 = "MSI GeForce RTX 3060 Ventus 2X 12G GeForce RTX 3060 12GB 12 GB Video Card (RTX3060Ventus2X12GOC)"  # 170 W
RTX_2060 = "EVGA SC GAMING GeForce RTX 2060 6 GB Video Card (06G-P4-2062-KR)"                            # 160 W
RX_6600 = "Gigabyte EAGLE Radeon RX 6600 8 GB Video Card (GV-R66EAGLE-8GD)"                              # 150 W
GTX_1650 = "MSI D6 VENTUS XS OC GeForce GTX 1650 G6 4 GB Video Card (GTX 1650 D6 Ventus XS OC)"          # 75 W

# Memorias RAM
DDR5_32GB = "Corsair Vengeance 32 GB (2 x 16 GB) DDR5-6000 CL36 Memory (CMK32GX5M2D6000C36)"
DDR4_16GB = "Corsair Vengeance LPX 16 GB (2 x 8 GB) DDR4-3200 CL16 Memory (CMK16GX4M2B3200C16)"
DDR3_8GB = "Corsair Vengeance 8 GB (2 x 4 GB) DDR3-1600 CL9 Memory (CMZ8GX3M2A1600C9)"

# Almacenamiento
NVME_980PRO = "Samsung 980 Pro 1 TB M.2-2280 PCIe 4.0 X4 NVME Solid State Drive (MZ-V8P1T0B/AM)"
SATA_870EVO = 'Samsung 870 Evo 1 TB 2.5" Solid State Drive (MZ-77E1T0B/AM)'
HDD_BARRACUDA = 'Seagate BarraCuda 2 TB 3.5" 7200 RPM Internal Hard Drive (ST2000DM006)'

# Disipadores
AIRE_212 = "Cooler Master Hyper 212 Black Edition 42 CFM CPU Cooler (RR-212S-20PK-R2)"
LIQUIDO_Z73 = "NZXT Kraken Z73 73.11 CFM Liquid CPU Cooler (RL-KRZ73-01)"

# Fuentes de poder
PSU_1000_ATX = "Corsair RM1000x (2021) 1000 W 80+ Gold Certified Fully Modular ATX Power Supply (CP-9020201-NA)"
PSU_750_ATX = "Corsair RM750e (2023) 750 W 80+ Gold Certified Fully Modular ATX Power Supply (CP-9020262-NA)"
PSU_650_ATX = "Corsair CV650 650 W 80+ Bronze Certified ATX Power Supply (CP-9020236-NA)"
PSU_550_ATX = "Corsair CV550 550 W 80+ Bronze Certified ATX Power Supply (CP-9020210-NA)"
PSU_450_ATX = "Corsair CV450 450 W 80+ Bronze Certified ATX Power Supply (CP-9020209-NA)"
PSU_750_SFX = "Corsair SF750 750 W 80+ Platinum Certified Fully Modular SFX Power Supply (CP-9020186-NA)"
PSU_600_SFX = "Corsair SF600 600 W 80+ Platinum Certified Fully Modular SFX Power Supply (CP-9020182-NA)"

# Gabinetes
CASE_ATX_4000D = "Corsair 4000D Airflow ATX Mid Tower Case (CC-9011200-WW)"
CASE_ATX_H5 = "NZXT H5 Flow ATX Mid Tower Case (CC-H51FB-01)"
CASE_MATX_Q300L = "Cooler Master MasterBox Q300L MicroATX Mini Tower Case (MCB-Q300L-KANN-S00)"
CASE_ITX_NR200 = "Cooler Master MasterBox NR200 Mini ITX Desktop Case (MCB-NR200-KNNN-S00)"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalogo() -> dict[str, dict[str, dict]]:
    """Carga el catálogo una sola vez y lo indexa por tipo y nombre."""
    if not RUTA_CATALOGO.exists():
        pytest.fail("No existe el catálogo. Ejecuta antes: python scripts/build_catalog.py")
    with open(RUTA_CATALOGO, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    return {tipo: {pieza["name"]: pieza for pieza in piezas} for tipo, piezas in datos.items()}


def armar_pc(catalogo: dict, piezas: dict[str, str]) -> ConfiguracionPC:
    """Busca cada pieza por nombre en el catálogo y arma la ConfiguracionPC."""
    configuracion = {}
    for tipo, nombre in piezas.items():
        if nombre not in catalogo[tipo]:
            pytest.fail(f"La pieza '{nombre}' no existe en el catálogo ({tipo})")
        configuracion[tipo] = catalogo[tipo][nombre]
    return ConfiguracionPC(**configuracion)


def pc(cpu, motherboard, gpu, memory, storage, cooler, psu, case) -> dict[str, str]:
    """Agrupa los nombres de las 8 piezas en el orden del contrato."""
    return {
        "cpu": cpu, "motherboard": motherboard, "gpu": gpu, "memory": memory,
        "storage": storage, "cooler": cooler, "psu": psu, "case": case,
    }


# ---------------------------------------------------------------------------
# 10 configuraciones compatibles
# Formato: (id, piezas, consumo esperado, recomendada esperada, n.º de advertencias)
# ---------------------------------------------------------------------------

CASOS_COMPATIBLES = [
    (
        "C01_am5_ddr5_ejemplo_contrato",
        pc(R5_7600X, B650_TUF, RTX_4070, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_750_ATX, CASE_ATX_4000D),
        390, 540, 0,  # 65 + 250 + 75 = 390 | 390 + 150 = 540 <= 750
    ),
    (
        "C02_am4_placa_microatx_en_gabinete_atx",
        pc(R5_5600X, B550M_DS3H, RTX_3060, DDR4_16GB, HDD_BARRACUDA, AIRE_212, PSU_550_ATX, CASE_ATX_H5),
        295, 445, 0,  # 50 + 170 + 75 = 295 | 295 + 150 = 445 <= 550
    ),
    (
        "C03_lga1700_ddr5_refrigeracion_liquida",
        pc(I5_13600K, Z790_ELITE, RTX_4070, DDR5_32GB, NVME_980PRO, LIQUIDO_Z73, PSU_750_ATX, CASE_ATX_4000D),
        405, 555, 0,  # 80 + 250 + 75 = 405 | 405 + 150 = 555 <= 750
    ),
    (
        "C04_lga1700_ddr4_microatx_en_microatx",
        pc(I5_12400, B760M_DDR4, RX_6600, DDR4_16GB, SATA_870EVO, AIRE_212, PSU_550_ATX, CASE_MATX_Q300L),
        305, 455, 0,  # 80 + 150 + 75 = 305 | 305 + 150 = 455 <= 550
    ),
    (
        "C05_limite_fuente_justa",
        pc(I5_10400, B560M_MORTAR, RTX_2060, DDR4_16GB, NVME_980PRO, AIRE_212, PSU_450_ATX, CASE_MATX_Q300L),
        300, 450, 0,  # 65 + 160 + 75 = 300 | 300 + 150 = 450 == 450 (alcanza justo)
    ),
    (
        "C06_lga1151_itx_con_fuente_sfx",
        pc(I7_9700K, Z390_I, GTX_1650, DDR4_16GB, NVME_980PRO, AIRE_212, PSU_600_SFX, CASE_ITX_NR200),
        215, 365, 0,  # 65 + 75 + 75 = 215 | 215 + 150 = 365 <= 600 (SFX en ITX no advierte)
    ),
    (
        "C07_am3_ddr3",
        pc(PHENOM_965, M4A88TD, GTX_1650, DDR3_8GB, HDD_BARRACUDA, AIRE_212, PSU_550_ATX, CASE_ATX_4000D),
        245, 395, 0,  # 95 + 75 + 75 = 245 | 245 + 150 = 395 <= 550
    ),
    (
        "C08_placa_itx_en_gabinete_atx",
        pc(I7_9700K, Z390_I, RX_6600, DDR4_16GB, SATA_870EVO, AIRE_212, PSU_650_ATX, CASE_ATX_H5),
        290, 440, 0,  # 65 + 150 + 75 = 290 | 290 + 150 = 440 <= 650
    ),
    (
        "C09_advertencia_fuente_sfx_en_gabinete_atx",
        pc(R5_7600X, B650_TUF, RTX_3060, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_750_SFX, CASE_ATX_4000D),
        310, 460, 1,  # 65 + 170 + 75 = 310 | 310 + 150 = 460 <= 750 (SFX en ATX: 1 advertencia)
    ),
    (
        "C10_gama_alta_13900k_rtx4090",
        pc(I9_13900K, Z790_ELITE, RTX_4090, DDR5_32GB, NVME_980PRO, LIQUIDO_Z73, PSU_1000_ATX, CASE_ATX_4000D),
        775, 925, 0,  # 250 + 450 + 75 = 775 | 775 + 150 = 925 <= 1000
    ),
]


# ---------------------------------------------------------------------------
# 10 configuraciones incompatibles
# Formato: (id, piezas, reglas que deben fallar, consumo, recomendada, n.º de advertencias)
# ---------------------------------------------------------------------------

CASOS_INCOMPATIBLES = [
    # --- Socket ---
    (
        "I01_socket_cpu_am5_en_placa_am4",
        pc(R5_7600X, B550M_DS3H, RTX_3060, DDR4_16GB, NVME_980PRO, AIRE_212, PSU_650_ATX, CASE_ATX_H5),
        ["socket"], 310, 460, 0,  # 65 + 170 + 75 = 310 | 460 <= 650
    ),
    (
        "I02_socket_cpu_lga1700_en_placa_lga1200",
        pc(I5_13600K, B560M_MORTAR, RX_6600, DDR4_16GB, NVME_980PRO, AIRE_212, PSU_650_ATX, CASE_MATX_Q300L),
        ["socket"], 305, 455, 0,  # 80 + 150 + 75 = 305 | 455 <= 650
    ),
    # --- Memoria ---
    (
        "I03_memoria_ddr4_en_placa_ddr5",
        pc(R5_7600X, B650_TUF, RTX_4070, DDR4_16GB, NVME_980PRO, AIRE_212, PSU_750_ATX, CASE_ATX_4000D),
        ["memoria"], 390, 540, 0,  # 65 + 250 + 75 = 390 | 540 <= 750
    ),
    (
        "I04_memoria_ddr5_en_placa_ddr4",
        pc(I5_12400, B760M_DDR4, RX_6600, DDR5_32GB, SATA_870EVO, AIRE_212, PSU_550_ATX, CASE_MATX_Q300L),
        ["memoria"], 305, 455, 0,  # 80 + 150 + 75 = 305 | 455 <= 550
    ),
    # --- Factor de forma ---
    (
        "I05_tamano_placa_atx_en_gabinete_microatx",
        pc(I5_13600K, Z790_ELITE, RTX_4070, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_750_ATX, CASE_MATX_Q300L),
        ["factor_forma"], 405, 555, 0,  # 80 + 250 + 75 = 405 | 555 <= 750
    ),
    (
        "I06_tamano_placa_microatx_en_gabinete_itx",
        pc(R5_5600X, B550M_DS3H, GTX_1650, DDR4_16GB, NVME_980PRO, AIRE_212, PSU_600_SFX, CASE_ITX_NR200),
        ["factor_forma"], 200, 350, 0,  # 50 + 75 + 75 = 200 | 350 <= 600
    ),
    # --- Potencia ---
    (
        "I07_fuente_insuficiente_rtx4090",
        pc(R5_7600X, B650_TUF, RTX_4090, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_650_ATX, CASE_ATX_4000D),
        ["potencia_psu"], 590, 740, 0,  # 65 + 450 + 75 = 590 | 740 > 650 (faltan 90 W)
    ),
    (
        "I08_limite_fuente_corta_por_5w",
        pc(I5_13600K, Z790_ELITE, RTX_4070, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_550_ATX, CASE_ATX_4000D),
        ["potencia_psu"], 405, 555, 0,  # 80 + 250 + 75 = 405 | 555 > 550 (faltan 5 W)
    ),
    # --- Varios errores a la vez ---
    (
        "I09_combinado_socket_y_fuente",
        pc(I5_12400, B650_TUF, RTX_4070, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_450_ATX, CASE_ATX_4000D),
        ["socket", "potencia_psu"], 405, 555, 0,  # 80 + 250 + 75 = 405 | 555 > 450
    ),
    (
        "I10_combinado_las_cuatro_reglas",
        pc(R5_7600X, B760M_DDR4, RTX_4090, DDR5_32GB, NVME_980PRO, AIRE_212, PSU_450_ATX, CASE_ITX_NR200),
        ["socket", "memoria", "factor_forma", "potencia_psu"], 590, 740, 0,  # 65 + 450 + 75 = 590 | 740 > 450
    ),
]


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "piezas, consumo, recomendada, n_advertencias",
    [caso[1:] for caso in CASOS_COMPATIBLES],
    ids=[caso[0] for caso in CASOS_COMPATIBLES],
)
def test_configuraciones_compatibles(catalogo, piezas, consumo, recomendada, n_advertencias):
    resultado = validar_compatibilidad(armar_pc(catalogo, piezas))

    assert resultado.compatible is True
    assert resultado.errores == [], f"Falso positivo: {[e.regla for e in resultado.errores]}"
    assert resultado.consumo_estimado_w == consumo
    assert resultado.potencia_recomendada_w == recomendada
    assert len(resultado.advertencias) == n_advertencias


@pytest.mark.parametrize(
    "piezas, reglas_esperadas, consumo, recomendada, n_advertencias",
    [caso[1:] for caso in CASOS_INCOMPATIBLES],
    ids=[caso[0] for caso in CASOS_INCOMPATIBLES],
)
def test_configuraciones_incompatibles(
    catalogo, piezas, reglas_esperadas, consumo, recomendada, n_advertencias
):
    resultado = validar_compatibilidad(armar_pc(catalogo, piezas))
    reglas_detectadas = sorted(error.regla for error in resultado.errores)

    assert resultado.compatible is False
    assert reglas_detectadas == sorted(reglas_esperadas)
    assert resultado.consumo_estimado_w == consumo
    assert resultado.potencia_recomendada_w == recomendada
    assert len(resultado.advertencias) == n_advertencias
    for error in resultado.errores:
        assert error.mensaje, "Cada error debe traer un mensaje explicativo"
        assert len(error.componentes_afectados) >= 2, "Cada error debe nombrar las piezas involucradas"
