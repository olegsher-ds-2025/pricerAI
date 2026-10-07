FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/run.sh /usr/local/bin/pricerai-run
ENTRYPOINT ["pricerai-run"]
