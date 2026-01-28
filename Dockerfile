FROM python:3.11-slim

# Evita archivos basura de Python y logs en buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ¡CRUCIAL! Añadimos /app/src al PYTHONPATH
# Esto permite que Python encuentre tus módulos dentro de 'src'
# ENV PYTHONPATH="${PYTHONPATH}:/app/src"
ENV PYTHONPATH="/app/src"

WORKDIR /app

# Instalamos dependencias del sistema (curl para healthchecks)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Instalamos las librerías necesarias
RUN pip install --no-cache-dir requests toml flask flask-cors google-genai python-dotenv gymnasium numpy

# Copiamos todo el proyecto al contenedor
COPY . .

# Comando de arranque: Ejecuta el servidor desde la carpeta src
CMD ["python", "src/green_agent.py"]
