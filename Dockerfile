FROM python:3.14-slim

RUN pip install pipenv
# Preserve env across multi-stage build.
ENV PIPENV_VENV_IN_PROJECT=1

WORKDIR /app

# Copy Pipfile and Pipfile.lock
COPY serve-bucket/Pipfile serve-bucket/Pipfile.lock ./

# Install dependencies
RUN pipenv sync

COPY serve-bucket/serve.py .
COPY serve-bucket/serve_waitress.py .
COPY serve-bucket/edit_simple.html serve-bucket/sidebar.html .
COPY palimpsest ./palimpsest

CMD ["pipenv", "run", "python", "serve_waitress.py"]