# PC-Assembly-RAG

Asistente inteligente de ensamble de computadores con validación determinista, planificación por grafos y RAG sobre manuales técnicos de fabricantes. Proyecto final de **Inteligencia Artificial (SI3003), EAFIT, 2026-2**.

> **Estado:** en definición y arquitectura inicial.

---

## 1. El problema

Al armar un computador de escritorio (*PC Custom*), el usuario tiene una colección de cajas independientes (procesador, placa madre, tarjeta gráfica, memoria RAM, fuente de poder, gabinete, almacenamiento y refrigeración). 

Sin embargo:
1. **No existe un manual unificado:** Cada componente trae un folleto aislado que no sabe qué otros componentes tienes.
2. **El orden físico de montaje es crítico:** Si instalas la placa madre en el gabinete antes de colocar el procesador o el soporte (*bracket*) trasero del disipador, o si colocas una tarjeta gráfica gigante antes de conectar los cables de la fuente, el usuario se ve obligado a desarmar todo.
3. **Detalles técnicos diminutos causan frustración:** El usuario no sabe en qué ranuras colocar la RAM para aprovechar el *Dual Channel* (doble canal) ni en qué orden conectar los pines diminutos del panel frontal (`POWER SW`, `RESET SW`, `HDD LED`) de su placa madre específica.

---

## 2. La solución

Una aplicación interactiva donde el usuario ingresa o selecciona la lista de componentes que compró y el sistema:

1. **Valida la compatibilidad técnica:** Confirma que el procesador coincide con el zócalo (*socket*) de la placa, que la RAM es del tipo correcto (DDR4 o DDR5), que la fuente de poder entrega suficientes Watts y que la tarjeta gráfica cabe físicamente en el gabinete.
2. **Genera el orden óptimo de montaje:** Resuelve un **grafo de restricciones físicas** mediante ordenación topológica (*Topological Sort*) para indicar exactamente qué paso va antes de cuál.
3. **Recupera las especificaciones exactas mediante RAG:** Busca en la base de datos vectorial (**ChromaDB**) los fragmentos exactos de los manuales oficiales de cada una de sus piezas (diagramas de pines, ranuras recomendadas, cables necesarios).
4. **Redacta una guía paso a paso personalizada:** Un modelo de lenguaje (**LLM**) sintetiza el orden físico con los fragmentos de los manuales recuperados, generando una guía clara, detallada y a prueba de errores.

---

## 3. Arquitectura del sistema

```
┌────────────────────────────────────────────────────────┐
│             Entrada del usuario                        │
│   (CPU, Motherboard, GPU, RAM, PSU, Case, Cooler)      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Componente 1: Validador de Compatibilidad              │ (IA Clásica - Reglas)
│ - Sockets, TDP / Watts, dimensiones y DDR              │
└──────────────────────────┬─────────────────────────────┘
                           │ Componentes válidos
                           ▼
┌────────────────────────────────────────────────────────┐
│ Componente 2: Planificador de Ensamble                 │ (IA Clásica - Grafos)
│ - Grafo acíclico dirigido (DAG) de dependencias        │
│ - Ordenación topológica de montaje                     │
└──────────────────────────┬─────────────────────────────┘
                           │ Secuencia ordenada de pasos
                           ▼
┌────────────────────────────────────────────────────────┐
│ Componente 3: Motor RAG con ChromaDB                   │ (IA Moderna - Embeddings)
│ - Búsqueda semántica sobre manuales oficiales en PDF   │
│ - Recuperación de diagramas, pines y precauciones      │
└──────────────────────────┬─────────────────────────────┘
                           │ Fragmentos de contexto recuperados
                           ▼
┌────────────────────────────────────────────────────────┐
│ Componente 4: Generador del Manual (LLM)               │ (Llama 3.3 / NVIDIA / Groq)
│ - Redacción de la guía personalizada paso a paso       │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│           Interfaz Interactiva (Streamlit)             │
│ - Resumen de compatibilidad + Manual interactivo       │
└────────────────────────────────────────────────────────┘
```

---

## 4. Datos

El sistema trabaja con dos conjuntos de datos complementarios:

### A. Catálogo de hardware estructurado (CSVs de Kaggle)
* **Fuente:** Datasets públicos de especificaciones de hardware derivados de *PCPartPicker* (Kaggle).
* **Entidades:** Procesadores (`cpu.csv`), Placas madre (`motherboard.csv`), Tarjetas gráficas (`video-card.csv`), Memorias (`memory.csv`), Fuentes de poder (`power-supply.csv`), Gabinetes (`case.csv`) y Disipadores (`cpu-cooler.csv`).
* **Propósito:** Validar compatibilidad de hardware con reglas deterministas antes de proceder al ensamble.

### B. Corpus de manuales técnicos oficiales (PDFs)
* **Fuente:** Manuales de usuario oficiales descargados de sitios de soporte de fabricantes (ASUS, MSI, Gigabyte, Corsair, NZXT, Cooler Master).
* **Procesamiento:**
  * Extracción de texto mediante `pypdf`.
  * *Chunking* (segmentación) en fragmentos semánticos (300-600 palabras) etiquetados con metadatos (`componente`, `tipo`, `seccion`).
  * Indexación vectorial persistente en **ChromaDB** con embeddings locales.

---

## 5. Metas y evaluación del proyecto

Para garantizar rigor académico y demostrar el valor de ambas partes del curso:

| Módulo | Técnica | Métrica de evaluación | Meta del proyecto |
|---|---|---|---|
| **1. Compatibilidad** | Reglas deterministas | Exactitud en 20 configuraciones de prueba (10 compatibles y 10 incompatibles) | **100 % de detección correcta** |
| **2. Planificador** | Grafo de dependencias + Topological Sort | Verificación de orden físico válido (sin pasos contradictorios) | **100 % de grafos acíclicos válidos** |
| **3. RAG** | ChromaDB + Embeddings | Recuperación de contexto relevante (ej. pines del panel frontal y ranuras de RAM) | **≥ 90 % de recuperación precisa** |
| **4. Generador** | LLM con contexto inyectado | Rúbrica de manual (completitud, precisión técnica y ausencia de alucinaciones) | **0 alucinaciones en advertencias de cables y pines** |

---

## 6. Estructura del repositorio

```
PC-Assembly-RAG/
├── data/
│   ├── raw/                  # Datos crudos (CSVs y manuales en PDF)
│   ├── processed/            # Catálogo limpio y chunks procesados
│   └── vectorstore/          # Base vectorial de ChromaDB (local)
├── src/
│   ├── compatibilidad/       # Motor de reglas de compatibilidad
│   ├── planificador/         # Grafo de dependencias y orden de ensamble
│   ├── rag/                  # Ingesta, chunking y búsqueda vectorial
│   └── llm/                  # Cliente LLM y plantillas de prompts
├── app/
│   └── main.py               # Interfaz interactiva de usuario en Streamlit
├── scripts/
│   ├── build_catalog.py      # Limpieza y preparación de datos tabulares
│   └── ingest_manuals.py     # Ingesta de manuales en ChromaDB
├── tests/                    # Pruebas unitarias de compatibilidad y ordenación
├── AGENTS.md                 # Reglas de desarrollo para el equipo y agentes
├── pyproject.toml            # Dependencias del proyecto con uv
└── README.md                 # Este documento
```

---

## 7. Plan de desarrollo por fases

1. **Fase 1: Datos y compatibilidad**
   * Descarga y curaduría del catálogo de hardware desde Kaggle.
   * Implementación del módulo de reglas de compatibilidad con pruebas unitarias (`pytest`).
2. **Fase 2: Planificador de montaje (Grafo de dependencias)**
   * Modelado del grafo de restricciones de ensamble físico.
   * Generación de la secuencia de pasos con ordenación topológica.
3. **Fase 3: Pipeline RAG con ChromaDB**
   * Descarga de manuales oficiales de muestra.
   * Extracción de texto, segmentación en chunks con metadatos e indexación en ChromaDB.
   * Evaluación de recuperación semántica.
4. **Fase 4: Generador de manuales (LLM) e interfaz interactiva**
   * Integración del contexto recuperado en el prompt del LLM (NVIDIA/Groq).
   * Interfaz en Streamlit para seleccionar componentes y generar el manual en tiempo real.
5. **Fase 5: Evaluación y documentación final**
   * Pruebas de extremo a extremo, medición de métricas y preparación de la sustentación.

---

## 8. Cómo empezar

### Requisitos previos
* Python 3.11 o superior.
* Gestor de paquetes `uv` instalado.

### Instalación
```bash
# Clonar el repositorio
git clone git@github.com:juanjosediazrodriguez/PC-Assembly-RAG.git
cd PC-Assembly-RAG

# Crear el entorno virtual e instalar dependencias con uv
uv venv
uv pip install -e .

# Configurar variables de entorno
cp .env.example .env
# Luego editar .env con tu API key de NVIDIA o Groq
```
