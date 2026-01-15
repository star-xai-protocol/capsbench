# Dockerfile.green
# -----------------------------------------------------------------------------
# Dockerfile for the Green Agent (CapsBench Server)
# -----------------------------------------------------------------------------

# 1. Use an official Python runtime as a parent image (Lightweight version)
FROM python:3.10-slim

# 2. Set the working directory in the container
WORKDIR /app

# 3. Copy configuration files first (Optimizes Docker layer caching)
COPY pyproject.toml README.md LICENSE ./

# 4. Install dependencies and the 'capsbench' package
# 'pip install .' reads pyproject.toml and installs the package in editable mode.
RUN pip install --no-cache-dir .

# 5. Copy the source code and visualizer
COPY src/ src/
COPY visualizer/ visualizer/

# 6. Create necessary directories for logs and results
# This ensures the server won't crash when trying to write files.
RUN mkdir -p logs replays results match_records

# 7. Expose the Flask port (5000) so other agents can connect
EXPOSE 5000

# 8. Define the command to run the application
# We use the module syntax (-m) to execute the green_agent script inside the package.
ENTRYPOINT ["python3", "-m", "src.capsbench.green_agent"]

