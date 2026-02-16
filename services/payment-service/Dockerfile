FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    opentelemetry-bootstrap -a install

COPY main.py .

EXPOSE 8083

CMD ["opentelemetry-instrument", \
     "--service_name", "payment-service", \
     "--exporter_otlp_protocol", "grpc", \
     "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8083"]
