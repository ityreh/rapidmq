FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY requirements.txt /app/requirements.txt

RUN uv pip install --system --no-cache-dir -r /app/requirements.txt

COPY main.py /app/main.py

EXPOSE 8082

CMD ["python", "/app/main.py"]
