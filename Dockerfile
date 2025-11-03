FROM python:3.10-slim

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENV PYTHONUNBUFFERED=TRUE

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:run_health_check"]
