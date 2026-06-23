# Immutable core image: runtime state lives in mounted volumes.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    dnsutils \
    git \
    iproute2 \
    iputils-ping \
    netcat-openbsd \
    traceroute \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install pip dependencies of bootstrap plugins at build time (code stays in volume at runtime).
RUN mkdir -p /tmp/bootstrap-plugins && \
    git clone --depth 1 https://github.com/Anisan/osysHome-Modules.git /tmp/bootstrap-plugins/Modules && \
    git clone --depth 1 https://github.com/Anisan/osysHome-Objects.git /tmp/bootstrap-plugins/Objects && \
    git clone --depth 1 https://github.com/Anisan/osysHome-Users.git /tmp/bootstrap-plugins/Users && \
    git clone --depth 1 https://github.com/Anisan/osysHome-Scheduler.git /tmp/bootstrap-plugins/Scheduler && \
    git clone --depth 1 https://github.com/Anisan/osysHome-wsServer.git /tmp/bootstrap-plugins/wsServer && \
    git clone --depth 1 https://github.com/Anisan/osysHome-Dashboard.git /tmp/bootstrap-plugins/Dashboard && \
    for req in /tmp/bootstrap-plugins/*/requirements.txt; do \
      if [ -f "$req" ]; then pip install --no-cache-dir -r "$req"; fi; \
    done && \
    rm -rf /tmp/bootstrap-plugins

COPY . /app/

RUN chmod +x /app/docker/*.sh

EXPOSE 5000

VOLUME ["/app/logs", "/app/cache", "/app/files", "/app/plugins"]

# Invoke via sh so the container still starts after in-app ZIP updates strip +x from scripts.
ENTRYPOINT ["sh", "/app/docker/docker-entrypoint.sh"]
CMD ["python", "main.py"]
