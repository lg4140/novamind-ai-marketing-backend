"""ASGI entrypoint: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager
import logging
import time
from uuid import uuid4
from fastapi import Request
from fastapi import FastAPI
from app.api.routes import router
from app.db.session import init_database

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    yield

app = FastAPI(title='NovaMind Marketing Automation API', version='2.2.0',
              description='Safe-by-default SDE reference implementation.', lifespan=lifespan)
app.include_router(router)
logger = logging.getLogger('novamind.api')

@app.middleware('http')
async def request_logging(request: Request, call_next):
    request_id = request.headers.get('X-Request-ID') or str(uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    # Never log Authorization tokens, body content, or contact emails.
    logger.info('request_id=%s method=%s route=%s status=%s duration_ms=%.1f',
                request_id, request.method, request.url.path, response.status_code,
                (time.perf_counter() - start) * 1000)
    return response


@app.get('/health/live', tags=['health'])
def live():
    return {'status':'ok'}
