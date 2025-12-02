FROM python:3.14-slim

RUN pip install pipenv
# Preserve env across multi-stage build.
ENV PIPENV_VENV_IN_PROJECT=1

WORKDIR /app

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies
RUN pipenv sync

COPY serve.py .
COPY serve_waitress.py .

CMD ["pipenv", "run", "python", "serve_waitress.py"]