# data/ — Gestión y Almacenamiento de Datos

Estructura para el almacenamiento y versionado de los datos del proyecto **PC-Assembly-RAG**:

## Estructura

```
data/
├── raw/                      # Datos crudos tal como se obtienen (inmutables)
│   ├── specs/                # CSVs de especificaciones descargados de Kaggle (PCPartPicker)
│   │   ├── CPU.csv
│   │   ├── Motherboard.csv
│   │   ├── GPU.csv
│   │   ├── Memory.csv
│   │   ├── Storage.csv
│   │   ├── Cooler.csv
│   │   ├── PSU.csv
│   │   ├── Case.csv
│   │   └── correcciones_ram_lga1700.csv   # Tipo de RAM de las placas LGA 1700 (hecho por el equipo)
│   └── manuals_pdf/          # Manuales oficiales de fabricantes en formato PDF
│                             # NOTA: En escalabilidad con miles de manuales se ignoran en Git por tamaño.
│                             # Para el MVP se incluye el manual de referencia oficial de ASUS (3.2 MB).
├── processed/                # Datos limpios y procesados
│   ├── hardware_catalog.json # Catálogo normalizado (lo genera scripts/build_catalog.py)
│   └── manual_chunks.jsonl   # Fragmentos de texto extraídos listos para indexación (pendiente)
└── vectorstore/              # Base de datos vectorial persistente de ChromaDB (ignorado en Git)
```

## Origen de los datos

1. **Especificaciones de componentes (CSVs):**
   * Fuente: Kaggle (Dataset de *PCPartPicker* / *PC Parts by Type*).
   * Los nombres de archivo llevan mayúscula inicial (`CPU.csv`, `PSU.csv`...). Respetarlos: en Linux y macOS los nombres distinguen mayúsculas.
   * Columnas por archivo (las que lee `scripts/build_catalog.py`):

     | Archivo | Columnas |
     |---|---|
     | `CPU.csv` | `name`, `brand`, `socket`, `speed`, `coreCount`, `threadCount`, `power` |
     | `Motherboard.csv` | `name`, `brand`, `socket`, `size` (poco confiable, ver abajo) |
     | `GPU.csv` | `name`, `brand`, `VRAM`, `resolution`, `power` |
     | `Memory.csv` | `name`, `type`, `size` |
     | `Storage.csv` | `name`, `type`, `space` |
     | `Cooler.csv` | `name`, `type` |
     | `PSU.csv` | `name`, `power`, `size` |
     | `Case.csv` | `name`, `size` |

   * **Lo que los CSV no traen** (por eso el MVP no lo valida): largo de la GPU, espacio libre del gabinete, compatibilidad socket-disipador y el tipo de RAM de las placas.

2. **Manuales técnicos (PDFs):**
   * Descargados de los sitios oficiales de soporte de fabricantes (ASUS, MSI, Gigabyte, Corsair, NZXT).
   * Documentados en detalle en la bitácora de datos del proyecto.

## Correcciones que aplica `scripts/build_catalog.py`

| Problema en el dato crudo | Corrección |
|---|---|
| `Motherboard.size` marca como `ATX` la mayoría de placas Micro ATX | Se deduce del nombre (`Micro ATX`, `ITX`) |
| `Motherboard` no trae tipo de RAM | Se deduce del nombre (`DDR3/4/5`, sufijos `D3/D4/D5`), luego de `correcciones_ram_lga1700.csv`, luego del socket |
| El sufijo `D3` en Gigabyte no es DDR3 (es una gama de producto) | Se ignora solo para Gigabyte |
| Registros con errores conocidos (ej. Biostar A620MT con socket equivocado) | Se excluyen |

Cada placa del catálogo trae `memory_type_confianza`: `"alta"` si el tipo de RAM sale del nombre o de un socket de una sola generación, y `"media"` si sale de una corrección de confianza media o del socket LGA 1151 (que tiene placas DDR3 sin marca en el nombre).

Para regenerar el catálogo: `python scripts/build_catalog.py`.
