FROM python:3.12-slim

WORKDIR /code

# Install dependencies first so Docker can cache this layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Production start-up. For local development, docker-compose.yml overrides this
# with a command that adds auto-reload.
CMD ["sh", "start.sh"]
