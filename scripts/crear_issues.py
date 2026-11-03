import subprocess
import sys

issues = [
    {
        "title": "data: implementar limpieza y procesamiento del catalogo en build_catalog.py",
        "body": """### Descripcion
Crear `scripts/build_catalog.py` que lea los 8 CSVs de `data/raw/specs/` y genere `data/processed/hardware_catalog.json` estructurado y sin nulos.

### Criterios de aceptacion
- [ ] Leer CSVs de CPU, Motherboard, GPU, RAM, Case, PSU, Storage y Cooler
- [ ] Inferir `memory_type` (DDR3, DDR4, DDR5) en placas madre segun socket y modelo
- [ ] Limpiar nulos en campos criticos (potencia, sockets, dimensiones)
- [ ] Exportar catalogo normalizado a `data/processed/hardware_catalog.json`"""
    },
    {
        "title": "feat(compatibilidad): implementar motor de reglas deterministas en validador.py",
        "body": """### Descripcion
Implementar en `src/compatibilidad/validador.py` la funcion `validar_compatibilidad(config: ConfiguracionPC) -> ResultadoCompatibilidad`.

### Criterios de aceptacion
- [ ] Regla de Socket: CPU vs Placa Madre
- [ ] Regla de RAM: Tipo de memoria vs soporte de la placa
- [ ] Regla de Gabinete: Jerarquia de tamano (ITX <= MicroATX <= ATX)
- [ ] Regla de Potencia: PSU >= CPU + GPU + 150W de margen
- [ ] Retornar diagnostico con booleanos, consumos y errores detallados"""
    },
    {
        "title": "test(compatibilidad): suite de pruebas automatizadas con 20 escenarios",
        "body": """### Descripcion
Crear suite de pruebas unitarias en `tests/test_compatibilidad.py` con pytest.

### Criterios de aceptacion
- [ ] 10 escenarios de configuraciones compatibles reales
- [ ] 10 escenarios con incompatibilidades inducidas (socket, fuente, memoria, tamano)
- [ ] 100% de deteccion correcta sin falsos positivos"""
    },
    {
        "title": "feat(planificador): modelar DAG de restricciones de ensamble con networkx",
        "body": """### Descripcion
Modelar la red de dependencias fisicas de armado como un Grafo Aciclico Dirigido (DAG) en `src/planificador/grafo.py`.

### Criterios de aceptacion
- [ ] Definir nodos para cada tarea fisica de instalacion
- [ ] Definir aristas dirigidas de precedencia obligatoria
- [ ] Verificar matematicamente que el grafo base no contenga ciclos (`nx.is_directed_acyclic_graph`)"""
    },
    {
        "title": "feat(planificador): ordenacion topologica adaptativa segun hardware",
        "body": """### Descripcion
Implementar `generar_plan_ensamble(config: ConfiguracionPC) -> list[PasoEnsamble]` en `src/planificador/grafo.py`.

### Criterios de aceptacion
- [ ] Adaptar nodos segun tipo de almacenamiento (NVMe en placa vs SATA en bahia)
- [ ] Adaptar nodos segun tipo de disipador (aire en placa vs liquido en chasis)
- [ ] Aplicar ordenacion topologica (`nx.topological_sort`)
- [ ] Generar lista secuencial de pasos con su `consulta_rag` correspondiente"""
    },
    {
        "title": "test(planificador): pruebas de precedencia fisica y aciclicidad",
        "body": """### Descripcion
Crear pruebas unitarias en `tests/test_planificador.py` con pytest.

### Criterios de aceptacion
- [ ] Verificar que la GPU siempre quede despues de montar placa y cables de poder
- [ ] Verificar que el CPU siempre preceda la pasta termica y disipador
- [ ] Comprobar orden correcto para configuraciones aire vs liquida"""
    },
    {
        "title": "feat(rag): procesador de PDFs y chunking semantico de manuales",
        "body": """### Descripcion
Crear `scripts/ingest_manuals.py` para procesar manuales en PDF usando `pypdf`.

### Criterios de aceptacion
- [ ] Extraer texto por pagina respetando la numeracion oficial del manual
- [ ] Segmentar en fragmentos semanticos (~400 palabras)
- [ ] Asociar metadatos obligatorios (manual_id, pagina, seccion)
- [ ] Exportar `data/processed/manual_chunks.jsonl`"""
    },
    {
        "title": "feat(rag): indexacion y buscador vectorial en ChromaDB",
        "body": """### Descripcion
Implementar el motor vectorial en `src/rag/buscador.py` con almacenamiento local en `data/vectorstore/`.

### Criterios de aceptacion
- [ ] Cargar chunks en coleccion ChromaDB con embeddings locales por defecto
- [ ] Implementar `buscar_contexto_paso(paso, top_k=3) -> list[FragmentoManual]`"""
    },
    {
        "title": "test(rag): evaluacion de precision de recuperacion (Recall@k)",
        "body": """### Descripcion
Crear banco de evaluacion en `tests/test_rag.py` con consultas tecnicas clave.

### Criterios de aceptacion
- [ ] 10 preguntas tecnicas (pines de encendido, ranuras de RAM para dual channel, etc.)
- [ ] Validar que la pagina real del manual este dentro del top 3 de resultados
- [ ] Meta de precision: >= 90%"""
    },
    {
        "title": "feat(llm): generador del manual con prompt estructurado y citas",
        "body": """### Descripcion
Implementar `src/llm/generador.py` con cliente de generacion (API de NVIDIA o Groq / Llama 3.3).

### Criterios de aceptacion
- [ ] Construir System Prompt que inyecte el plan del grafo y los fragmentos del RAG
- [ ] Regla estricta: cero alucinacion de pines y obligatoriedad de citar pagina del manual
- [ ] Retornar manual estructurado en Markdown"""
    },
    {
        "title": "feat(ui): interfaz interactiva de ensamble en Streamlit",
        "body": """### Descripcion
Construir la app web en `app/main.py` con Streamlit.

### Criterios de aceptacion
- [ ] Selectores desplegables para los 8 componentes a partir del catalogo JSON
- [ ] Panel de compatibilidad en vivo (consumo estimado, potencia requerida, advertencias)
- [ ] Visor interactivo del manual paso a paso con citas y recomendaciones"""
    },
    {
        "title": "test(e2e): prueba de integracion de extremo a extremo",
        "body": """### Descripcion
Crear prueba integral en `tests/test_integracion.py`.

### Criterios de aceptacion
- [ ] Ejecutar el pipeline completo sin interfaz: Catalogo -> Validacion -> Grafo -> RAG -> LLM
- [ ] Validar comunicacion fluida entre los 4 modulos respetando contratos"""
    }
]

repo = "juanjosediazrodriguez/PC-Assembly-RAG"

for i, issue in enumerate(issues, start=1):
    print(f"[{i}/{len(issues)}] Creando: {issue['title']}...")
    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", issue["title"],
        "--body", issue["body"]
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"  -> Creada: {res.stdout.strip()}")
    else:
        print(f"  -> Error: {res.stderr.strip()}")
