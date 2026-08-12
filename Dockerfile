FROM python:3.12-slim

WORKDIR /opt/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src/ src/

WORKDIR /opt/app/src

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
