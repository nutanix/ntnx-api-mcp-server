FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARTIFACTS_DIR=/tmp/nutanix-mcp-artifacts \
    LOG_DIR=/tmp/nutanix-mcp-logs

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN pip install --no-cache-dir -e . \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p /tmp/nutanix-mcp-artifacts /tmp/nutanix-mcp-logs \
    && useradd --system --no-create-home --shell /usr/sbin/nologin nutanix-mcp \
    && chown -R nutanix-mcp:nutanix-mcp /app /tmp/nutanix-mcp-artifacts /tmp/nutanix-mcp-logs

USER nutanix-mcp

EXPOSE 8080

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["serve-http"]
