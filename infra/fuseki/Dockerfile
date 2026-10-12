FROM eclipse-temurin:21-jre-jammy@sha256:8c2dddf1bb2a8455160f4e23080059de5003eddc5cb839130b177c6be0c2cfe0
ARG JENA_VERSION=6.2.0
ARG JENA_SHA512=ba65f5867d2d4741b2ed9e2af5a0d4fbb447909894ab2a0c6bc4dac8997f4fe339c87b13c48d45d054977769f0f8bf763ea346b1f7792d5cdc458041bd43a132
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-${JENA_VERSION}.tar.gz" -o /tmp/fuseki.tar.gz \
    && echo "${JENA_SHA512}  /tmp/fuseki.tar.gz" | sha512sum -c - \
    && mkdir -p /opt/fuseki /data /fuseki-base \
    && tar -xzf /tmp/fuseki.tar.gz --strip-components=1 -C /opt/fuseki \
    && rm /tmp/fuseki.tar.gz && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home fuseki && chown -R fuseki:fuseki /data /fuseki-base
COPY config.ttl /opt/fuseki/config.ttl
ENV FUSEKI_BASE=/fuseki-base
USER fuseki
WORKDIR /opt/fuseki
EXPOSE 3030
ENTRYPOINT ["java", "-Xms128m", "-Xmx768m", "-jar", "/opt/fuseki/fuseki-server.jar", "--config=/opt/fuseki/config.ttl", "--port=3030"]
