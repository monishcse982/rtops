from fastapi import FastAPI
from starlette.requests import Request

from app.config import logger
from app.request_context import generate_request_id, reset_request_id, set_request_id
from app.routers import orders, products

app = FastAPI()

app.include_router(orders.router, prefix="/api", tags=["Orders"])
app.include_router(products.router, prefix="/api", tags=["Products"])


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
    finally:
        reset_request_id(token)

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def health():
    logger.info("Health check requested")
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
