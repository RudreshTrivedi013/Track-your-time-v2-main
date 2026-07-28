FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# ${PORT:-8000}: Railway (and most PaaS) assign the port at runtime via $PORT and
# route to whatever the container binds. Hard-coding 8000 makes the health check
# fail with no useful error. The default keeps `docker compose up` working locally.
#
# Migrations run here, on the web service only — NOT in the worker/beat services,
# which override this command. Running `alembic upgrade head` from three services
# that boot simultaneously races them against the same migration lock.
CMD bash -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
