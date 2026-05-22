FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

# Clone source from upstream; pin to a specific commit for reproducibility:
#   docker build --build-arg JEANNIE_REF=<commit-sha> .
ARG JEANNIE_REF=main
RUN git clone --depth 1 --branch ${JEANNIE_REF} \
    https://github.com/1ShoukR/jeannie-booking-bot.git /app || \
    git clone --depth 1 https://github.com/1ShoukR/jeannie-booking-bot.git /app

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt supervisor

# Persistent storage dir for soho_tokens.json and last_booking.json
RUN mkdir -p /data

COPY supervisord.conf /etc/supervisor/conf.d/jeannie.conf

EXPOSE 5000

ENV RAILWAY_VOLUME_MOUNT_PATH=/data
ENV PORT=5000

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:${PORT}/ || exit 1

CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/jeannie.conf"]
