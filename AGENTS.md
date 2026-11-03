# AGENTS.md — PC-Assembly-RAG

Instrucciones y reglas de ingeniería para los asistentes de IA y desarrolladores que trabajen en este repositorio. Léelo completo antes de proponer cambios o escribir código.

---

## 1. El proyecto en tres líneas

**PC-Assembly-RAG** es un asistente inteligente para el armado de computadores personalizados. Valida la compatibilidad técnica de los componentes (IA clásica / reglas deterministas), calcula el orden óptimo de ensamble físico mediante un **grafo de dependencias**, y genera un manual de instalación paso a paso personalizado utilizando un sistema **RAG** (*Retrieval-Augmented Generation*) sobre los manuales oficiales de cada fabricante indexados en **ChromaDB**. Es el proyecto final de **Inteligencia Artificial (SI3003), EAFIT, 2026-2**.

---

## 2. Reglas de oro (no negociables)

1. **El LLM no calcula compatibilidad ni inventa el orden físico:**
   * La compatibilidad de sockets, potencias (Watts) y dimensiones físicas la resuelve código Python determinista.
   * El orden de las tareas de ensamble se calcula mediante un algoritmo de ordenación topológica (*Topological Sort*) sobre un grafo de restricciones físicas (ejemplo: el procesador y el bracket del disipador se instalan antes de atornillar la placa al chasis).
   * El LLM solo se encarga de tomar ese orden y redactar las instrucciones amigables y detalladas apoyándose en los fragmentos del manual recuperados por el RAG.
2. **Cero secretos en el repositorio:**
   * Las llaves de API (`NVIDIA_API_KEY`, `GROQ_API_KEY`) van exclusivamente en el archivo `.env` (ignorado en `.gitignore`).
   * Cualquier nueva variable debe reflejarse en `.env.example` sin valor.
3. **No versionar binarios pesados:**
   * Los PDFs de manuales (`data/raw/manuals_pdf/*.pdf`) y la carpeta de persistencia de ChromaDB (`data/vectorstore/`) nunca se suben a Git.
4. **Reproducibilidad:**
   * Los entornos y dependencias se gestionan con `uv` (`pyproject.toml` y `uv.lock`). Todo comando de ejecución debe ser reproducible en otra máquina.
5. **Idioma:**
   * Documentación, comentarios, nombres de variables y mensajes de commit en **español**.
   * Términos técnicos sin traducción directa aceptados en inglés (`socket`, `embedding`, `chunk`, `prompt`, `RAG`, `TDP`).
6. **Confirmación antes de ejecutar cambios:**
   * Antes de crear, modificar o borrar archivos significativos, o ejecutar comandos en el sistema, explicar qué se va a hacer y por qué, y esperar confirmación del usuario.

---

## 3. Stack tecnológico

| Capa | Tecnología | Propósito |
|---|---|---|
| **Lenguaje** | Python 3.11 / 3.12 | Lenguaje principal del backend y pipeline. |
| **Gestión de paquetes** | `uv` | Instalación ultrarrápida y bloqueo exacto de versiones (`uv.lock`). |
| **Parte 1 (IA Clásica)** | `networkx` / Algoritmos en Python | Grafo de dependencias y ordenación topológica para la secuencia de montaje; motor de reglas de compatibilidad. |
| **Base de datos vectorial** | `ChromaDB` (modo local persistente) | Indexación y búsqueda semántica de fragmentos de manuales con embeddings integrados (`all-MiniLM-L6-v2`). |
| **Extracción de texto** | `pypdf` | Lectura y parsing de manuales técnicos en PDF. |
| **Generación (LLM)** | API de NVIDIA / Groq (Llama 3.3 70B) | Redacción del manual paso a paso con prompt estructurado. |
| **Interfaz** | `Streamlit` | Interfaz web interactiva para seleccionar componentes y visualizar el manual generado. |
| **Pruebas** | `pytest` | Pruebas unitarias de compatibilidad, grafos de ensamble y búsqueda RAG. |

---

## 4. Estructura modular del proyecto

```
PC-Assembly-RAG/
├── data/
│   ├── raw/                  # Datos crudos (CSVs de Kaggle y PDFs)
│   ├── processed/            # Catálogo limpio y chunks con metadata
│   └── vectorstore/          # Base de datos vectorial persistente (ChromaDB)
├── src/
│   ├── compatibilidad/       # Motor de reglas de sockets, TDP y dimensiones
│   ├── planificador/         # Grafo de dependencias y orden de ensamble
│   ├── rag/                  # Ingesta, chunking y búsqueda en ChromaDB
│   └── llm/                  # Prompts y cliente de generación
├── app/
│   └── main.py               # Interfaz interactiva en Streamlit
├── scripts/
│   ├── build_catalog.py      # Procesa CSVs de Kaggle a catálogo limpio
│   └── ingest_manuals.py     # Extrae texto de PDFs y carga ChromaDB
├── tests/                    # Pruebas automatizadas (pytest)
├── docs/                     # Diagramas y decisiones de diseño
├── .env.example              # Plantilla de variables de entorno
├── .gitignore
├── AGENTS.md                 # Este archivo
├── pyproject.toml            # Especificación de dependencias para uv
└── README.md                 # Especificación académica del proyecto
```
