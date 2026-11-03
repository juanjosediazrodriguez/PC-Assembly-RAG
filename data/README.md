# data/ — Gestión y Almacenamiento de Datos

Estructura para el almacenamiento y versionado de los datos del proyecto **PC-Assembly-RAG**:

## Estructura

```
data/
├── raw/                      # Datos crudos tal como se obtienen (inmutables)
│   ├── specs/                # CSVs de especificaciones descargados de Kaggle (PCPartPicker)
│   │   ├── cpu.csv
│   │   ├── motherboard.csv
│   │   ├── video-card.csv
│   │   ├── case.csv
│   │   ├── power-supply.csv
│   │   └── memory.csv
│   └── manuals_pdf/          # Manuales oficiales de fabricantes en formato PDF
│                             # NOTA: En escalabilidad con miles de manuales se ignoran en Git por tamaño.
│                             # Para el MVP se incluye el manual de referencia oficial de ASUS (3.2 MB).
├── processed/                # Datos limpios y procesados
│   ├── hardware_catalog.json # Catálogo normalizado para validación de compatibilidad
│   └── manual_chunks.jsonl   # Fragmentos de texto extraídos listos para indexación
└── vectorstore/              # Base de datos vectorial persistente de ChromaDB (ignorado en Git)
```

## Origen de los datos

1. **Especificaciones de componentes (CSVs):**
   * Fuente: Kaggle (Dataset de *PCPartPicker* / *PC Parts by Type*).
   * Columnas clave: `name`, `socket`, `form_factor`, `tdp`, `memory_type`, `length`, `wattage`.

2. **Manuales técnicos (PDFs):**
   * Descargados de los sitios oficiales de soporte de fabricantes (ASUS, MSI, Gigabyte, Corsair, NZXT).
   * Documentados en detalle en la bitácora de datos del proyecto.
