# 1. Base Image
FROM python:3.10-slim

# 2. Optimizaciones y Ruta de Python (Crucial para que encuentre tus módulos)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# 3. Instalación de dependencias
COPY pyproject.toml README.md LICENSE ./
# 3. INSTALACIÓN MANUAL (Para evitar errores de 'hatchling' o README)
RUN pip install --no-cache-dir \
    flask>=3.0.0 \
    flask-cors>=4.0.0 \
    gymnasium>=0.29.0 \
    numpy>=1.26.0 \
    requests>=2.31.0 \
    python-dotenv>=1.0.0 \
    google-genai>=0.3.0

# 4. Copia de código y creación de carpetas
COPY src/ src/
COPY visualizer/ visualizer/
RUN mkdir -p logs replays results match_records

# 5. Puerto estándar de AgentBeats para Green Agent
EXPOSE 5000

# 6. Ejecución dividida (Evita el error de "--host")
# ENTRYPOINT define el comando que NUNCA cambia
ENTRYPOINT ["python", "-m", "src.capsbench.green_agent"]
# CMD define los argumentos que el Leaderboard puede sobrescribir
CMD ["--host", "0.0.0.0", "--port", "5000"]

