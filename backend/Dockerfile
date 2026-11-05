FROM python:3.11-slim
WORKDIR /app
COPY app.py .
RUN mkdir -p /var/lib/backend_data && chown 10001:10001 /var/lib/backend_data
USER 10001:10001
EXPOSE 5000
CMD ["python", "app.py"]
