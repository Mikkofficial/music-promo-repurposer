FROM docker.n8n.io/n8nio/n8n:latest

USER root

# Install ffmpeg, python3, and curl for yt-dlp
RUN if command -v apk >/dev/null 2>&1; then \
      apk add --no-cache ffmpeg python3 curl ca-certificates; \
    else \
      apt-get update && apt-get install -y --no-install-recommends ffmpeg python3 curl ca-certificates && rm -rf /var/lib/apt/lists/*; \
    fi

# Install latest yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp

# Copy pre-built workflow and create auto-import entrypoint
COPY workflow.json /opt/workflow.json
RUN printf '#!/bin/sh\n\
if [ ! -f /home/node/.n8n/.workflow_imported ]; then\n\
  echo "Importing Music Promo Repurposer workflow..."\n\
  n8n import:workflow --input=/opt/workflow.json && touch /home/node/.n8n/.workflow_imported\n\
fi\n\
exec tini -- /docker-entrypoint.sh\n' > /opt/entrypoint.sh && \
    chmod +x /opt/entrypoint.sh && \
    mkdir -p /home/node/.n8n-files && \
    chown -R node:node /home/node/.n8n-files /opt/workflow.json /opt/entrypoint.sh

USER node

ENTRYPOINT ["/opt/entrypoint.sh"]
