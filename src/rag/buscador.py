"""
Motor vectorial y recuperación semántica sobre manuales técnicos de hardware.

Módulo 3 de PC-Assembly-RAG (Persona 3):
- Indexa fragmentos de manuales (manual_chunks.jsonl) en ChromaDB con persistencia local en data/vectorstore/.
- Implementa la búsqueda semántica de fragmentos de manuales requerida por el planificador (PasoEnsamble).
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.api.models.Collection import Collection

# ---------------------------------------------------------------------------
# Configuración del entorno y rutas del proyecto
# ---------------------------------------------------------------------------
# Asegura que la raíz del repositorio esté en sys.path para permitir importaciones
# absolutas tanto si el módulo se ejecuta como script o como paquete.
RAIZ = Path(__file__).resolve().parent.parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.esquemas import FragmentoManual, PasoEnsamble

logger = logging.getLogger("rag.buscador")

# Rutas estándar del proyecto (relativas a la raíz según AGENTS.md)
RUTA_VECTORSTORE = RAIZ / "data" / "vectorstore"
RUTA_CHUNKS_JSONL = RAIZ / "data" / "processed" / "manual_chunks.jsonl"
NOMBRE_COLECCION_DEFECTO = "manuales_hardware"


class MotorVectorial:
    """Administra la base de datos vectorial ChromaDB para PC-Assembly-RAG."""

    def __init__(
        self,
        ruta_db: Path = RUTA_VECTORSTORE,
        nombre_coleccion: str = NOMBRE_COLECCION_DEFECTO,
    ) -> None:
        """
        Inicializa la conexión persistente a ChromaDB y la colección de manuales.
        """
        self.ruta_db = Path(ruta_db)
        self.nombre_coleccion = nombre_coleccion

        # 1. Crear el directorio de almacenamiento en disco si no existe
        self.ruta_db.mkdir(parents=True, exist_ok=True)

        # 2. Inicializar el cliente persistente de ChromaDB en modo local
        # Los datos y vectores se guardan en archivos en data/vectorstore/
        self.cliente = chromadb.PersistentClient(path=str(self.ruta_db))

        # 3. Obtener o crear la colección vectorial:
        # - Usa por defecto DefaultEmbeddingFunction (modelo local all-MiniLM-L6-v2)
        # - Configura hnsw:space en 'cosine' para comparar distancias angulares normalizadas
        self.coleccion: Collection = self.cliente.get_or_create_collection(
            name=self.nombre_coleccion,
            metadata={"hnsw:space": "cosine"},
        )

    def cargar_chunks_jsonl(
        self,
        ruta_archivo: Path = RUTA_CHUNKS_JSONL,
        forzar_recarga: bool = False,
        lote_tamano: int = 100,
    ) -> int:
        """
        Carga e indexa los fragmentos desde manual_chunks.jsonl en ChromaDB.

        Es idempotente: si la colección ya cuenta con documentos y forzar_recarga=False,
        no duplica registros.
        """
        # 1. Validar que el archivo fuente de chunks exista en disco
        ruta_archivo = Path(ruta_archivo)
        if not ruta_archivo.exists():
            raise FileNotFoundError(f"No se encontró el archivo de chunks: {ruta_archivo}")

        total_existente = self.coleccion.count()

        # 2. Control de idempotencia: si ya hay datos indexados, evitar reindexación costosa
        if total_existente > 0 and not forzar_recarga:
            logger.info(
                "Colección '%s' ya cargada con %d fragmentos. Omitiendo recarga.",
                self.nombre_coleccion,
                total_existente,
            )
            return total_existente

        # 3. Si se solicita forzar la recarga, eliminar la colección previa y crear una vacía
        if forzar_recarga and total_existente > 0:
            logger.info("Forzando recarga: eliminando colección '%s' previa...", self.nombre_coleccion)
            self.cliente.delete_collection(self.nombre_coleccion)
            self.coleccion = self.cliente.get_or_create_collection(
                name=self.nombre_coleccion,
                metadata={"hnsw:space": "cosine"},
            )

        # 4. Leer y transformar los fragmentos del archivo JSONL
        # ChromaDB requiere listas separadas para IDs, textos y metadatos
        ids: list[str] = []
        documentos: list[str] = []
        metadatos: list[dict[str, Any]] = []

        with open(ruta_archivo, "r", encoding="utf-8") as f:
            for linea in f:
                linea_limpia = linea.strip()
                if not linea_limpia:
                    continue
                chunk = json.loads(linea_limpia)
                ids.append(chunk["chunk_id"])
                documentos.append(chunk["texto"])
                metadatos.append({
                    "manual_id": str(chunk.get("manual_id", "")),
                    "componente_tipo": str(chunk.get("componente_tipo", "general")),
                    "pagina": int(chunk.get("pagina", 0)),
                    "pagina_etiqueta": str(chunk.get("pagina_etiqueta", "")),
                    "seccion": str(chunk.get("seccion", "")),
                })

        # 5. Indexar en lotes (batching) usando upsert para evitar sobrecargar memoria
        total = len(ids)
        for i in range(0, total, lote_tamano):
            fin = min(i + lote_tamano, total)
            self.coleccion.upsert(
                ids=ids[i:fin],
                documents=documentos[i:fin],
                metadatas=metadatos[i:fin],
            )

        logger.info(
            "Indexación completada: %d fragmentos cargados en la colección '%s'.",
            total,
            self.nombre_coleccion,
        )
        return total

    def buscar(
        self,
        query: str,
        top_k: int = 3,
        manual_id: Optional[str] = None,
        componente_tipo: Optional[str] = None,
    ) -> list[FragmentoManual]:
        """
        Ejecuta la búsqueda semántica en ChromaDB y convierte el resultado
        al contrato tipado FragmentoManual.
        """
        # 1. Comprobar que la colección tenga datos; si está vacía, retornar lista vacía
        total_elementos = self.coleccion.count()
        if total_elementos == 0:
            logger.warning("La colección '%s' está vacía.", self.nombre_coleccion)
            return []

        # 2. Ajustar top_k para no solicitar más elementos de los existentes en la base
        k = max(1, min(top_k, total_elementos))

        # 3. Construir filtros de metadatos opcionales (ej. filtrar por manual o componente)
        filtros: dict[str, Any] = {}
        if manual_id:
            filtros["manual_id"] = manual_id
        if componente_tipo:
            filtros["componente_tipo"] = componente_tipo

        where_clause: Optional[dict[str, Any]] = None
        if len(filtros) == 1:
            where_clause = filtros
        elif len(filtros) > 1:
            # Si hay más de un filtro, ChromaDB requiere el operador $and
            where_clause = {"$and": [{k_f: v_f} for k_f, v_f in filtros.items()]}

        # 4. Ejecutar la búsqueda vectorial por similitud semántica
        # ChromaDB calcula el embedding de la query y retorna los k vectores más cercanos
        resultados = self.coleccion.query(
            query_texts=[query],
            n_results=k,
            where=where_clause,
        )

        # 5. Validar que se hayan obtenido respuestas válidas
        fragmentos: list[FragmentoManual] = []
        if not resultados or not resultados.get("ids") or not resultados["ids"][0]:
            return fragmentos

        # 6. Desempaquetar las listas paralelas devueltas por ChromaDB
        ids = resultados["ids"][0]
        documentos = resultados["documents"][0] if resultados.get("documents") else [""] * len(ids)
        metas = resultados["metadatas"][0] if resultados.get("metadatas") else [{}] * len(ids)
        distancias = resultados["distances"][0] if resultados.get("distances") else [0.0] * len(ids)

        # 7. Convertir cada coincidencia en una instancia del modelo Pydantic FragmentoManual
        for cid, doc, meta, dist in zip(ids, documentos, metas, distancias):
            fragmentos.append(
                FragmentoManual(
                    chunk_id=str(cid),
                    manual_id=str(meta.get("manual_id", "")),
                    pagina=int(meta.get("pagina", 0)),
                    pagina_etiqueta=str(meta.get("pagina_etiqueta", "")),
                    seccion=str(meta.get("seccion", "")),
                    texto=str(doc),
                    distancia=round(float(dist), 4),
                )
            )

        return fragmentos


# ---------------------------------------------------------------------------
# Singleton e interfaz funcional según contratos.md
# ---------------------------------------------------------------------------
_motor_global: Optional[MotorVectorial] = None


def obtener_motor(
    ruta_db: Path = RUTA_VECTORSTORE,
    nombre_coleccion: str = NOMBRE_COLECCION_DEFECTO,
) -> MotorVectorial:
    """
    Devuelve la instancia global del motor vectorial.
    Si no ha sido instanciado, lo crea e indexa automáticamente los chunks
    si la colección en disco se encuentra vacía.
    """
    global _motor_global
    if _motor_global is None:
        # 1. Crear la instancia única del motor vectorial
        _motor_global = MotorVectorial(ruta_db=ruta_db, nombre_coleccion=nombre_coleccion)

        # 2. Carga perezosa inicial: si la base está vacía y existe el JSONL, indexar los datos
        if _motor_global.coleccion.count() == 0 and RUTA_CHUNKS_JSONL.exists():
            _motor_global.cargar_chunks_jsonl(RUTA_CHUNKS_JSONL)

    return _motor_global


def buscar_contexto_paso(
    paso: PasoEnsamble, top_k: int = 3, manual_id: Optional[str] = None
) -> list[FragmentoManual]:
    """
    Consulta ChromaDB usando paso.consulta_rag y retorna los fragmentos más relevantes.
    Firma oficial del contrato docs/contratos.md (Sección 5).

    Si se pasa manual_id, solo busca en ese manual. Devuelve [] si no hay manual
    indexado para la pieza (nunca texto de otro manual).
    """
    # 1. Obtener la instancia compartida de ChromaDB
    motor = obtener_motor()

    # 2. Delegar la búsqueda usando la consulta semántica del paso de ensamble
    return motor.buscar(query=paso.consulta_rag, top_k=top_k, manual_id=manual_id)
