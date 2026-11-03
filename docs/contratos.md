# Contratos de datos — PC-Assembly-RAG

La forma y los esquemas de los datos que comparten los 4 módulos del proyecto. 

> **Regla de equipo:** Cambiar un contrato rompe el trabajo de otro compañero. Cualquier modificación aquí debe discutirse en equipo, notificarse y enviarse en su propio Pull Request con el título `docs(contratos): descripción del cambio`.

Cuando se empiece a escribir el código fuente, estos contratos pasarán a ser modelos formales de Pydantic en `src/esquemas.py`. Este documento es su especificación y explicación técnica.

---

## 1. Convenciones generales

| Concepto | Tipo en Python | Convención / Regla | Ejemplo |
|---|---|---|---|
| **Sockets** | `str` (Enum/Literal) | Nombre canónico de la plataforma | `"AM5"`, `"LGA 1700"`, `"AM4"` |
| **Factor de forma** | `str` (Enum/Literal) | Jerarquía física estricta | `"ITX"` < `"MicroATX"` < `"ATX"` |
| **Memoria RAM** | `str` (Enum/Literal) | Generación estándar de DDR | `"DDR4"`, `"DDR5"`, `"DDR3"` |
| **Potencias / Consumo** | `int` | Valores enteros en Watts (W) | `65`, `125`, `750` |
| **Almacenamiento** | `str` (Enum/Literal) | Interfaz de conexión | `"NVME"`, `"SATA"`, `"HDD"` |
| **Disipador** | `str` (Enum/Literal) | Tipo de refrigeración física | `"air"`, `"liquid"` |
| **Rutas relativas** | `str` / `Path` | Siempre relativas a la raíz del repo | `"data/processed/hardware_catalog.json"` |

---

## 2. Entidad Central: `ConfiguracionPC`

Es la entrada que genera la interfaz de usuario (Streamlit) y que viaja por todo el pipeline. Representa el computador que el usuario desea armar con sus 8 componentes seleccionados.

### Explicación en lenguaje natural
Cada componente proviene del catálogo procesado (`data/processed/hardware_catalog.json`). No contiene URLs largas ni datos innecesarios de tiendas: únicamente las métricas que afectan la compatibilidad física y eléctrica, y las instrucciones de montaje.

### Especificación en código (Pydantic / Python)

```python
from typing import Literal
from pydantic import BaseModel, Field

SocketType = Literal[
    "LGA 1151", "LGA 1200", "LGA 1700",
    "AM3", "AM4", "AM5", "X399", "TRX40"
]
FormFactor = Literal["ATX", "MicroATX", "ITX"]
MemoryType = Literal["DDR3", "DDR4", "DDR5"]
CoolerType = Literal["air", "liquid"]
StorageType = Literal["NVME", "SATA", "HDD"]
PSUSize = Literal["ATX", "SFX"]

class CPU(BaseModel):
    name: str = Field(description="Nombre comercial completo")
    brand: Literal["Intel", "AMD"]
    socket: SocketType
    speed: float = Field(description="Frecuencia base en GHz")
    core_count: int
    thread_count: int
    power: int = Field(description="TDP o consumo en Watts")

class Motherboard(BaseModel):
    name: str
    brand: Literal["Intel", "AMD"]
    socket: SocketType
    size: FormFactor
    memory_type: MemoryType = Field(description="Generación de RAM soportada")

class GPU(BaseModel):
    name: str
    brand: Literal["NVIDIA", "AMD"]
    vram: int = Field(description="Memoria de video en GB")
    resolution: str
    power: int = Field(description="Consumo en Watts bajo carga")

class Memory(BaseModel):
    name: str
    type: MemoryType
    size: int = Field(description="Capacidad total en GB")

class Storage(BaseModel):
    name: str
    type: StorageType
    space: int = Field(description="Capacidad en GB")

class Cooler(BaseModel):
    name: str
    type: CoolerType

class PSU(BaseModel):
    name: str
    power: int = Field(description="Potencia nominal en Watts")
    size: PSUSize

class Case(BaseModel):
    name: str
    size: FormFactor

class ConfiguracionPC(BaseModel):
    cpu: CPU
    motherboard: Motherboard
    gpu: GPU
    memory: Memory
    storage: Storage
    cooler: Cooler
    psu: PSU
    case: Case
```

### Ejemplo en JSON
```json
{
  "cpu": {
    "name": "AMD Ryzen 5 7600X",
    "brand": "AMD",
    "socket": "AM5",
    "speed": 4.7,
    "core_count": 6,
    "thread_count": 12,
    "power": 105
  },
  "motherboard": {
    "name": "Asus TUF GAMING B650-PLUS WIFI",
    "brand": "AMD",
    "socket": "AM5",
    "size": "ATX",
    "memory_type": "DDR5"
  },
  "gpu": {
    "name": "Asus TUF Gaming GeForce RTX 4070 12GB",
    "brand": "NVIDIA",
    "vram": 12,
    "resolution": "1440p",
    "power": 200
  },
  "memory": {
    "name": "Corsair Vengeance 32 GB (2 x 16 GB) DDR5-6000",
    "type": "DDR5",
    "size": 32
  },
  "storage": {
    "name": "Samsung 980 Pro 1 TB M.2-2280 NVME",
    "type": "NVME",
    "space": 1000
  },
  "cooler": {
    "name": "Cooler Master Hyper 212 Black",
    "type": "air"
  },
  "psu": {
    "name": "Corsair RM750e 750 W 80+ Gold",
    "power": 750,
    "size": "ATX"
  },
  "case": {
    "name": "Corsair 4000D Airflow",
    "size": "ATX"
  }
}
```

---

## 3. Módulo 1 — Validador de Compatibilidad (Persona 1)

**Ubicación:** `src/compatibilidad/validador.py`

### Explicación en lenguaje natural
Este módulo recibe la `ConfiguracionPC` y aplica un conjunto de reglas deterministas (sin IA probabilística) para garantizar que las piezas no fallen ni sufran daños físicos:

1. **Regla de Socket:** `cpu.socket == motherboard.socket`. Si no coinciden, el procesador no encaja físicamente en la placa.
2. **Regla de Memoria RAM:** `memory.type == motherboard.memory_type`. Las muescas de DDR4 y DDR5 son físicamente incompatibles.
3. **Regla de Factor de Forma:** Jerarquía de tamaños:
   $$\text{ITX (1)} \le \text{MicroATX (2)} \le \text{ATX (3)}$$
   El chasis debe ser de tamaño mayor o igual al de la placa madre (`jerarquia[case.size] >= jerarquia[motherboard.size]`).
4. **Regla de Fuente de Poder (Watts):**
   $$\text{Consumo estimado} = \text{CPU.power} + \text{GPU.power} + 75\text{ W (placa, RAM, ventiladores)}$$
   $$\text{Potencia mínima recomendada} = \text{Consumo estimado} + 150\text{ W (margen de picos)}$$
   La fuente debe cumplir: `psu.power >= Potencia mínima recomendada`.

### Firma y tipos en código

```python
class ErrorCompatibilidad(BaseModel):
    regla: Literal["socket", "memoria", "factor_forma", "potencia_psu"]
    mensaje: str
    componentes_afectados: list[str]

class ResultadoCompatibilidad(BaseModel):
    compatible: bool
    consumo_estimado_w: int
    potencia_recomendada_w: int
    errores: list[ErrorCompatibilidad]
    advertencias: list[str]  # Ej: PSU SFX en gabinete ATX (requiere adaptador)

def validar_compatibilidad(config: ConfiguracionPC) -> ResultadoCompatibilidad:
    """Evalúa las 4 reglas deterministas y retorna el diagnóstico completo."""
    ...
```

### Salida JSON (Caso Incompatible)
```json
{
  "compatible": false,
  "consumo_estimado_w": 380,
  "potencia_recomendada_w": 530,
  "errores": [
    {
      "regla": "potencia_psu",
      "mensaje": "La fuente de 450 W es insuficiente. Se recomienda una fuente de al menos 530 W para cubrir picos de consumo.",
      "componentes_afectados": ["Corsair CV450 450 W", "RTX 4070 12GB"]
    }
  ],
  "advertencias": []
}
```

---

## 4. Módulo 2 — Planificador con Grafos (Persona 2)

**Ubicación:** `src/planificador/grafo.py`

### Explicación en lenguaje natural
Armar un computador exige un orden estricto de precedencia física para evitar tener que desarmar piezas ya instaladas.
Este módulo construye un **Grafo Acíclico Dirigido (DAG)** con la librería `networkx`:
* Cada **nodo** representa una tarea de instalación física.
* Cada **arista dirigida ($A \to B$)** indica que la tarea $A$ debe completarse obligatoriamente antes de la tarea $B$.
* Luego, el algoritmo de **Ordenación Topológica (*Topological Sort*)** aplana el grafo en una lista secuencial de pasos `1..N`.

**Comportamiento adaptativo según hardware:**
* Si `storage.type == "NVME"`, se instala en la placa madre **fuera del gabinete** antes del disipador.
* Si `storage.type in ("SATA", "HDD")`, se instala en las bahías del gabinete en la fase de chasis.
* Si `cooler.type == "air"`, se coloca sobre la placa antes de meterla al gabinete. Si es `"liquid"`, primero se fija el radiador al chasis.

### Firma y tipos en código

```python
class PasoEnsamble(BaseModel):
    orden: int
    id_paso: str
    fase: Literal["fuera_gabinete", "preparacion_gabinete", "montaje_chasis", "cableado_y_cierre"]
    titulo: str
    descripcion_base: str
    componentes_involucrados: list[str]
    dependencias_previas: list[str]
    consulta_rag: str  # Query semántica lista para enviar al buscador de ChromaDB

def generar_plan_ensamble(config: ConfiguracionPC) -> list[PasoEnsamble]:
    """Construye el DAG con networkx, aplica topological_sort y retorna los pasos ordenados."""
    ...
```

### Salida JSON de un paso
```json
{
  "orden": 3,
  "id_paso": "instalar_ram",
  "fase": "fuera_gabinete",
  "titulo": "Instalación de memorias RAM",
  "descripcion_base": "Insertar los módulos de memoria RAM en las ranuras correspondientes para activar Dual Channel.",
  "componentes_involucrados": ["Asus TUF GAMING B650-PLUS WIFI", "Corsair Vengeance 32 GB DDR5"],
  "dependencias_previas": ["instalar_cpu"],
  "consulta_rag": "Motherboard Asus TUF GAMING B650 recommended memory slots Dual Channel DIMM configuration"
}
```

---

## 5. Módulo 3 — Pipeline RAG y ChromaDB (Persona 3)

**Ubicación:** `src/rag/buscador.py` y `scripts/ingest_manuals.py`

### Explicación en lenguaje natural
1. **Ingesta (`scripts/ingest_manuals.py`):** Lee los PDFs oficiales en `data/raw/manuals_pdf/`, extrae el texto por página con `pypdf`, corta el texto en fragmentos lógicos (*chunks* de 300-500 palabras) y los guarda en `data/processed/manual_chunks.jsonl`.
2. **Indexación:** Carga los fragmentos en **ChromaDB** en `data/vectorstore/`.
3. **Búsqueda semántica:** Recibe la `consulta_rag` generada por el Módulo 2 y busca los fragmentos más relevantes del manual oficial de la pieza en cuestión.

### Estructura de cada chunk en `data/processed/manual_chunks.jsonl`
```json
{
  "chunk_id": "asus_b650_p18_c01",
  "manual_id": "asus_tuf_gaming_b650_plus_wifi",
  "componente_tipo": "motherboard",
  "pagina": 18,
  "seccion": "1.1.7 System Panel Header",
  "texto": "The 10-1 pin System Panel header connects the front panel switches and LEDs... Pins 3 and 4 connect to the Power Switch button (PWRBTN# and GND). Ensure correct orientation."
}
```

### Firma y tipos en código

```python
class FragmentoManual(BaseModel):
    chunk_id: str
    manual_id: str
    pagina: int
    seccion: str
    texto: str
    distancia: float  # Grado de similitud calculado por ChromaDB (menor = más relevante)

def buscar_contexto_paso(paso: PasoEnsamble, top_k: int = 3) -> list[FragmentoManual]:
    """Consulta ChromaDB usando paso.consulta_rag y retorna los fragmentos más relevantes."""
    ...
```

---

## 6. Módulo 4 — Generador con LLM (Persona 4)

**Ubicación:** `src/llm/generador.py`

### Explicación en lenguaje natural
Este módulo toma:
1. El informe de compatibilidad (Módulo 1).
2. La lista de pasos ordenada por el grafo (Módulo 2).
3. Los fragmentos oficiales recuperados de los manuales (Módulo 3).

Y ensambla un **Prompt Estructurado** para el LLM (Llama 3.3 vía NVIDIA/Groq API), con una directriz estricta:
* El modelo **no puede inventar números de pines ni ranuras**.
* Debe citar la página del manual de donde sacó cada detalle crítico (ej. `[Manual ASUS B650, pág. 18]`).

### Firma y tipos en código

```python
class PasoConContexto(BaseModel):
    paso: PasoEnsamble
    fragmentos_rag: list[FragmentoManual]

class ManualFinal(BaseModel):
    compatible: bool
    resumen_compatibilidad: ResultadoCompatibilidad
    total_pasos: int
    manual_markdown: str  # Texto en Markdown listo para renderizar en Streamlit
    citas_manuales: list[dict]  # Lista de evidencias con manual_id y página

def generar_manual(
    config: ConfiguracionPC,
    compatibilidad: ResultadoCompatibilidad,
    pasos_con_contexto: list[PasoConContexto]
) -> ManualFinal:
    """Envía el contexto estructurado al LLM y retorna la guía personalizada."""
    ...
```

---

## 7. Flujo Integrado en la App (`app/main.py`)

Así se conectan los 4 módulos en el punto de entrada de la aplicación:

```python
# 1. El usuario selecciona componentes en Streamlit
config = obtener_configuracion_ui()

# 2. Persona 1: Valida compatibilidad
validacion = validar_compatibilidad(config)
if not validacion.compatible:
    mostrar_alerta_incompatibilidad(validacion.errores)
else:
    # 3. Persona 2: Genera el orden lógico mediante el DAG
    plan = generar_plan_ensamble(config)
    
    # 4. Persona 3: Enriquece cada paso con contexto de los manuales en ChromaDB
    pasos_con_contexto = [
        PasoConContexto(paso=p, fragmentos_rag=buscar_contexto_paso(p, top_k=2))
        for p in plan
    ]
    
    # 5. Persona 4: El LLM redacta la guía paso a paso con citas exactas
    manual_final = generar_manual(config, validacion, pasos_con_contexto)
    renderizar_manual_interactivo(manual_final)
```
