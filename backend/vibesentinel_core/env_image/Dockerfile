# The project "environment" image: a minimal Linux box the user drives through
# two browser terminals. Kept small — real language runtimes get layered on by
# the user inside their own project, this just needs to boot a shell, run
# python, and make outbound HTTP for the demo server.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        ca-certificates \
        curl \
        bash \
        procps \
        net-tools \
        nano \
        less \
    && rm -rf /var/lib/apt/lists/*

COPY ptybroker.py /opt/ptybroker.py
COPY demo_server.py /opt/demo_server.py
COPY traffic.py /opt/traffic.py

WORKDIR /root
# Kept alive by the backend; terminals attach via `docker exec`.
CMD ["sleep", "infinity"]
