# 1. Base Image
FROM python:3.10-slim

# 2. Optimizaciones y Ruta de Python (Crucial para que encuentre tus módulos)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# 3. Instalación de dependencias
COPY pyproject.toml README.md LICENSE ./
RUN pip install --no-cache-dir .

# 4. Copia de código y creación de carpetas
COPY src/ src/
COPY visualizer/ visualizer/
RUN mkdir -p logs replays results match_records

# 5. Puerto estándar de AgentBeats para Green Agent
EXPOSE 5000

# 6. Ejecución dividida (Evita el error de "--host")
# ENTRYPOINT define el comando que NUNCA cambia
ENTRYPOINT ["python3", "-m", "src.capsbench.green_agent"]
# CMD define los argumentos que el Leaderboard puede sobrescribir
CMD ["--host", "0.0.0.0", "--port", "5000"]

