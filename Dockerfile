FROM python:3.11-slim

# Evita archivos basura
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src"

WORKDIR /app

# Instalamos curl y dependencias
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Instalamos librerías python
RUN pip install --no-cache-dir requests toml flask flask-cors google-genai python-dotenv gymnasium numpy

# Copiamos código
COPY . .

# EXPOSE (Informativo)
EXPOSE 9009

# 🛑 CAMBIO VITAL: Usamos ENTRYPOINT, no CMD.
# Esto asegura que "python src/green_agent.py" SIEMPRE se ejecute,
# y los argumentos (--host ...) se peguen detrás.
ENTRYPOINT ["python", "src/green_agent.py"]
