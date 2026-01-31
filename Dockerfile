FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src"

WORKDIR /app

# Instalamos curl para el healthcheck (como en el ejemplo que pasaste)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests toml flask flask-cors google-genai python-dotenv gymnasium numpy

# Copy pyproject.toml and source code
COPY pyproject.toml /app/
COPY src /app/src

EXPOSE 9009

# HEALTHCHECK (Opcional pero recomendado, copiado del ejemplo que funciona)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9009/.well-known/agent-card.json || exit 1

# EL SECRETO:
# ENTRYPOINT ejecuta python
ENTRYPOINT ["python", "-m", "src.green_agent.py"]

# CMD provee los argumentos por defecto.
# Si el Leaderboard envía los suyos, estos se borran y se usan los del Leaderboard.
# Como tu script YA tiene argparse (Paso 1), funcionará perfecto en ambos casos.
CMD ["--host", "0.0.0.0", "--port", "9009"]
