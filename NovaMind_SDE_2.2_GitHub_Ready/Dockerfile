FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY data/sample_contacts.csv ./data/sample_contacts.csv
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
RUN useradd --create-home --uid 10001 appuser && mkdir -p /srv/app/data && chown -R appuser:appuser /srv/app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
