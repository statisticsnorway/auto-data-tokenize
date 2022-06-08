FROM azul/zulu-openjdk-alpine:17
RUN apk --no-cache add curl
COPY build/libs/dapla-dlp.zip dapla-dlp.zip
