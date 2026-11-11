"""Módulo de RAG (Retrieval-Augmented Generation) y base vectorial para PC-Assembly-RAG."""

from src.rag.buscador import MotorVectorial, buscar_contexto_paso, obtener_motor

__all__ = ["MotorVectorial", "buscar_contexto_paso", "obtener_motor"]
