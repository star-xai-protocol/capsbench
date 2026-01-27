import argparse
import tomli
import yaml
import sys

def generate_compose(scenario_path):
    with open(scenario_path, "rb") as f:
        scenario = tomli.load(f)

    # Configuración base
    compose = {
        "version": "3.8",
        "services": {},
        "networks": {
            "agent-network": {"driver": "bridge"}
        }
    }

    # 1. Configurar GREEN AGENT (Servidor)
    compose["services"]["green-agent"] = {
        "image": "ghcr.io/star-xai-protocol/capsbench:latest", 
        "ports": ["9009:9009"],
        # TÁCTICA MAESTRA:
        # 1. Usamos entrypoint /bin/sh para tomar el control total.
        # 2. cd /app -> Nos ponemos en la raíz para ver la carpeta 'src'.
        # 3. python -m src.green_agent -> Ejecutamos 'src' como paquete. ¡Esto arregla el import relativo!
        "entrypoint": ["/bin/sh", "-c"],
        "command": ["cd /app && export PYTHONPATH=/app && python -m src.green_agent"],
        "environment": {
            "RECORD_MODE": "true",
            "PYTHONUNBUFFERED": "1"
        },
        "volumes": [
            "./replays:/app/src/replays",
            "./logs:/app/src/logs",
            "./results:/app/src/results"
        ],
        "healthcheck": {
            "test": ["CMD", "curl", "-f", "http://localhost:9009/status"],
            "interval": "5s",
            "timeout": "5s",
            "retries": 20,
            "start_period": "5s"
        },
        "networks": ["agent-network"]
    }

    # 2. Configurar PURPLE AGENT (Tu IA)
    compose["services"]["purple-agent"] = {
        "build": ".", # Construye usando tu Dockerfile y requirements.txt
        "command": ["python", "purple_ai.py"], 
        "environment": {
            "SERVER_URL": "http://green-agent:9009",
            "GOOGLE_API_KEY": "${GOOGLE_API_KEY}"
        },
        "depends_on": {
            "green-agent": {"condition": "service_healthy"}
        },
        "networks": ["agent-network"]
    }

    # 3. Configurar CLIENT (Árbitro)
    compose["services"]["agentbeats-client"] = {
        "image": "ghcr.io/agentbeats/agentbeats-client:v1.0.0",
        "volumes": [
            "./output:/app/output",
        ],
        # Creamos el config al vuelo para evitar errores de lectura
        "entrypoint": ["/bin/sh", "-c"],
        "command": [
            "echo '[green]' > /tmp/config.toml && "
            "echo 'name = \"Green Agent\"' >> /tmp/config.toml && "
            "echo 'endpoint = \"http://green-agent:9009\"' >> /tmp/config.toml && "
            "echo '' >> /tmp/config.toml && "
            "echo '[purple]' >> /tmp/config.toml && "
            "echo 'name = \"Purple Agent\"' >> /tmp/config.toml && "
            "echo 'endpoint = \"http://purple-agent:80\"' >> /tmp/config.toml && "
            "python -m agentbeats.client_cli /tmp/config.toml /app/output/results.json"
        ],
        "depends_on": {
            "green-agent": {"condition": "service_healthy"}
        },
        "networks": ["agent-network"]
    }

    # Guardar el archivo final
    with open("docker-compose.yml", "w") as f:
        yaml.dump(compose, f, sort_keys=False)
    
    print("✅ docker-compose.yml generado correctamente.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, help="Path to scenario.toml")
    args = parser.parse_args()
    generate_compose(args.scenario)
