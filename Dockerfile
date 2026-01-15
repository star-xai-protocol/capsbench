# 1. Imagen Base
FROM python:3.10-slim

# 2. Entorno (Para que Python encuentre src/capsbench)
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 3. INSTALACIÓN MANUAL DE DEPENDENCIAS 
# (Más seguro que 'pip install .' porque evitamos errores de build/readme)
RUN pip install --no-cache-dir \
    flask>=3.0.0 \
    flask-cors>=4.0.0 \
    gymnasium>=0.29.0 \
    numpy>=1.26.0 \
    requests>=2.31.0 \
    python-dotenv>=1.0.0 \
    google-genai>=0.3.0

# 4. COPIAR TODO EL CONTENIDO DEL PROYECTO
# Esto incluye src/, visualizer/, README.md, pyproject.toml, etc.
# Es la forma más segura de garantizar que no falta nada.
COPY . .

# 5. CREAR CARPETAS DE LOGS
RUN mkdir -p logs replays results match_records

# 6. PUERTO
EXPOSE 5000

# 7. EJECUCIÓN
# Gracias a COPY . ., la ruta src/capsbench/green_agent.py existirá dentro de /app
ENTRYPOINT ["python", "-m", "src.capsbench.green_agent"]
CMD ["--host", "0.0.0.0", "--port", "5000"]
