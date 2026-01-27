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

    # 1. Configurar GREEN AGENT (Servidor Oficial)
    compose["services"]["green-agent"] = {
        # Usamos la imagen oficial (EL PAQUETE SÍ EXISTE EN LA NUBE)
        "image": "ghcr.io/star-xai-protocol/capsbench:latest", 
        "ports": ["9009:9009"],
        
        # --- LIMPIEZA TOTAL ---
        # NO ponemos 'command' ni 'entrypoint'.
        # Dejamos que la imagen use su configuración de fábrica (CMD por defecto).
        
        "environment": {
            "RECORD_MODE": "true",
            "PYTHONUNBUFFERED": "1"
            # Quitamos PYTHONPATH, dejamos que la imagen use el suyo.
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
        "build": ".", 
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
    
    print("✅ docker-compose.yml generado (Modo Clon Local).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, help="Path to scenario.toml")
    args = parser.parse_args()
    generate_compose(args.scenario)
