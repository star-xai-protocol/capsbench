FROM python:3.11-slim

# 1. Configuración de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src"

WORKDIR /app

# 2. Instalamos lo básico
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 3. Instalamos librerías
RUN pip install --no-cache-dir requests toml flask flask-cors google-genai python-dotenv gymnasium numpy

# 4. Copiamos el código
COPY . .

# 5. Puerto
EXPOSE 9009

# 🏆 LA ESTRUCTURA GANADORA (Igual que el ejemplo que pasaste)
# El ENTRYPOINT es el comando fijo (el "Jefe")
ENTRYPOINT ["python", "src/green_agent.py"]

# El CMD son los argumentos por defecto (los "Recados")
# Si AgentBeats envía otros argumentos, estos se sustituyen, pero el ENTRYPOINT se mantiene.
CMD ["--host", "0.0.0.0"]
