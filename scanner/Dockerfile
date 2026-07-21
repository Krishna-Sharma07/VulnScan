FROM ghcr.io/zaproxy/zaproxy:stable

USER root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
USER zap

ENTRYPOINT ["/entrypoint.sh"]
