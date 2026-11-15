# Imagen para Hugging Face Spaces (SDK Docker). Expone Streamlit en el puerto 7860.
FROM python:3.12-slim

# Hugging Face ejecuta el contenedor con un usuario no root (uid 1000).
RUN useradd -m -u 1000 user \
    && mkdir -p /home/user/app \
    && chown user:user /home/user/app
ENV HOME=/home/user \
    PATH=/home/user/app/.venv/bin:/home/user/.local/bin:$PATH \
    LIMITAR_GENERACIONES=1 \
    ANONYMIZED_TELEMETRY=False \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user . .
USER user

# Versiones exactas de uv.lock, sin dependencias de desarrollo.
RUN pip install --no-cache-dir --user uv \
    && uv sync --frozen --no-dev

# Descarga el modelo de embeddings (~80 MB) durante la construcción para que
# el primer visitante no espere esa descarga.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['precarga'])"

EXPOSE 7860
CMD ["streamlit", "run", "app/main.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
