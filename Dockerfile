FROM python:3.11-slim

# Configuración básica para evitar problemas de logs y caché
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src"

WORKDIR /app

# Instalamos curl para que el Leaderboard pueda comprobar si estamos vivos
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Tus librerías
RUN pip install --no-cache-dir requests toml flask flask-cors google-genai python-dotenv gymnasium numpy

COPY . .

EXPOSE 9009

# 1. ENTRYPOINT: Define QUÉ ejecutamos (siempre python)
ENTRYPOINT ["python", "src/green_agent.py"]

# 2. CMD: Define los ARGUMENTOS por defecto.
# El Leaderboard sustituirá esto con los suyos, pero como tu script ya tiene argparse, funcionará.
CMD ["--host", "0.0.0.0", "--port", "9009"]
