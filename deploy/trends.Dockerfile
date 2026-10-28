FROM python:3.13-slim
WORKDIR /app
COPY server/intelligence.py server/public_trends.py server/trend_contract.py server/trend_service.py ./server/
RUN useradd --uid 10001 --create-home goodform && mkdir /data && chown goodform /data
USER goodform
ENV GOODFORM_PUBLIC_BIND=0.0.0.0 GOODFORM_PUBLIC_PORT=4320 GOODFORM_PUBLIC_TREND_STORE=/data/briefing.json
EXPOSE 4320
VOLUME ["/data"]
CMD ["python", "server/trend_service.py"]
