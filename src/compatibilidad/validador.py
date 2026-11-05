"""
Módulo 1 — Validador de compatibilidad de PC-Assembly-RAG.

Recibe una ConfiguracionPC y aplica 4 reglas deterministas (sin IA) para
verificar que las piezas se puedan armar sin fallas físicas ni eléctricas.
Las reglas y la salida siguen lo definido en docs/contratos.md, sección 3.

Reglas:
1. Socket: el procesador debe encajar en la placa madre.
2. Memoria: la RAM debe ser del tipo que soporta la placa madre.
3. Factor de forma: el gabinete debe ser igual o más grande que la placa.
4. Potencia: la fuente debe cubrir el consumo estimado más un margen de picos.

El validador revisa todas las reglas y devuelve todos los errores juntos,
sin detenerse en el primero.
"""

from src.esquemas import (
    ConfiguracionPC,
    ErrorCompatibilidad,
    ResultadoCompatibilidad,
)

# Consumo fijo estimado de placa madre, RAM, disco y ventiladores (W)
CONSUMO_BASE_W = 75

# Margen extra para cubrir picos de consumo (W)
MARGEN_PICOS_W = 150

# Jerarquía de tamaños: un número mayor significa una pieza más grande
JERARQUIA_TAMANO = {"ITX": 1, "MicroATX": 2, "ATX": 3}


def calcular_consumo_estimado(config: ConfiguracionPC) -> int:
    """Consumo estimado = CPU + GPU + consumo base del resto de piezas."""
    return config.cpu.power + config.gpu.power + CONSUMO_BASE_W


def calcular_potencia_recomendada(consumo_estimado: int) -> int:
    """Potencia mínima recomendada = consumo estimado + margen de picos."""
    return consumo_estimado + MARGEN_PICOS_W


def revisar_socket(config: ConfiguracionPC) -> ErrorCompatibilidad | None:
    """Regla 1: el socket del procesador debe coincidir con el de la placa madre."""
    cpu, placa = config.cpu, config.motherboard
    if cpu.socket == placa.socket:
        return None
    return ErrorCompatibilidad(
        regla="socket",
        mensaje=(
            f"El procesador usa socket {cpu.socket} y la placa madre usa socket "
            f"{placa.socket}. El procesador no encaja físicamente en la placa."
        ),
        componentes_afectados=[cpu.name, placa.name],
    )


def revisar_memoria(config: ConfiguracionPC) -> ErrorCompatibilidad | None:
    """Regla 2: el tipo de RAM debe ser el que soporta la placa madre."""
    ram, placa = config.memory, config.motherboard
    if ram.type == placa.memory_type:
        return None
    return ErrorCompatibilidad(
        regla="memoria",
        mensaje=(
            f"La memoria es {ram.type} y la placa madre solo soporta "
            f"{placa.memory_type}. Las ranuras no son compatibles físicamente."
        ),
        componentes_afectados=[ram.name, placa.name],
    )


def revisar_factor_forma(config: ConfiguracionPC) -> ErrorCompatibilidad | None:
    """Regla 3: el gabinete debe ser igual o más grande que la placa madre."""
    gabinete, placa = config.case, config.motherboard
    if JERARQUIA_TAMANO[gabinete.size] >= JERARQUIA_TAMANO[placa.size]:
        return None
    return ErrorCompatibilidad(
        regla="factor_forma",
        mensaje=(
            f"La placa madre es {placa.size} y el gabinete es {gabinete.size}. "
            f"La placa no cabe dentro del gabinete."
        ),
        componentes_afectados=[placa.name, gabinete.name],
    )


def revisar_potencia(
    config: ConfiguracionPC, potencia_recomendada: int
) -> ErrorCompatibilidad | None:
    """Regla 4: la fuente debe ser igual o mayor a la potencia recomendada."""
    fuente = config.psu
    if fuente.power >= potencia_recomendada:
        return None
    return ErrorCompatibilidad(
        regla="potencia_psu",
        mensaje=(
            f"La fuente de {fuente.power} W es insuficiente. Se recomienda una "
            f"fuente de al menos {potencia_recomendada} W para cubrir picos de consumo."
        ),
        componentes_afectados=[fuente.name, config.gpu.name],
    )


def revisar_advertencias(config: ConfiguracionPC) -> list[str]:
    """Detecta situaciones que no impiden el armado pero que el usuario debe saber."""
    advertencias = []
    if config.psu.size == "SFX" and config.case.size == "ATX":
        advertencias.append(
            f"La fuente {config.psu.name} es SFX y el gabinete {config.case.name} "
            f"es ATX. Funciona, pero necesitas un adaptador de SFX a ATX para montarla."
        )
    return advertencias


def validar_compatibilidad(config: ConfiguracionPC) -> ResultadoCompatibilidad:
    """Evalúa las 4 reglas deterministas y retorna el diagnóstico completo."""
    consumo_estimado = calcular_consumo_estimado(config)
    potencia_recomendada = calcular_potencia_recomendada(consumo_estimado)

    resultados = [
        revisar_socket(config),
        revisar_memoria(config),
        revisar_factor_forma(config),
        revisar_potencia(config, potencia_recomendada),
    ]
    errores = [error for error in resultados if error is not None]

    return ResultadoCompatibilidad(
        compatible=len(errores) == 0,
        consumo_estimado_w=consumo_estimado,
        potencia_recomendada_w=potencia_recomendada,
        errores=errores,
        advertencias=revisar_advertencias(config),
    )
