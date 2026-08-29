import os
from decimal import Decimal
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="Demo Order Service",
    description="A deterministic order API bundled as the platform's real test target.",
    version="1.0.0",
)

_TOKEN = "demo-access-token"
_lock = Lock()
_products = {
    1: {"id": 1, "name": "机械键盘", "price": Decimal("99.90"), "stock": 20},
    2: {"id": 2, "name": "无线鼠标", "price": Decimal("59.00"), "stock": 30},
}
_orders: dict[str, dict] = {}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class OrderRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=10)


def _ok(data: dict) -> dict:
    return {"code": 0, "message": "ok", "data": data}


def _require_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if authorization != f"Bearer {_TOKEN}":
        raise HTTPException(status_code=401, detail="invalid token")
    return _TOKEN


def reset_state() -> None:
    with _lock:
        _orders.clear()
        _products[1]["stock"] = 20
        _products[2]["stock"] = 30


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "demo-order"}


@app.post("/api/login", tags=["auth"])
def login(payload: LoginRequest) -> dict:
    if payload.username != "demo" or payload.password != "demo123":
        raise HTTPException(status_code=401, detail="invalid credentials")
    return _ok({"access_token": _TOKEN, "token_type": "bearer"})


@app.get("/api/products/{product_id}", tags=["product"])
def get_product(product_id: int, _: str = Depends(_require_token)) -> dict:
    product = _products.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return _ok({**product, "price": float(product["price"])})


@app.post("/api/orders", status_code=201, tags=["order"])
def create_order(payload: OrderRequest, _: str = Depends(_require_token)) -> dict:
    with _lock:
        product = _products.get(payload.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="product not found")
        if product["stock"] < payload.quantity:
            raise HTTPException(status_code=409, detail="insufficient stock")
        product["stock"] -= payload.quantity
        order_id = f"ord-{len(_orders) + 1}"
        total = product["price"] * payload.quantity
        if os.getenv("DEMO_BUG_MODE", "").lower() == "wrong_total":
            total += Decimal("1.00")
        order = {
            "id": order_id,
            "product_id": payload.product_id,
            "quantity": payload.quantity,
            "total": float(total),
            "status": "created",
        }
        _orders[order_id] = order
    return _ok(dict(order))


@app.post("/api/orders/{order_id}/pay", tags=["order"])
def pay_order(order_id: str, _: str = Depends(_require_token)) -> dict:
    with _lock:
        order = _orders.get(order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        if order["status"] != "created":
            raise HTTPException(status_code=409, detail="order already paid")
        order["status"] = "paid"
        return _ok(dict(order))


@app.get("/api/orders/{order_id}", tags=["order"])
def get_order(order_id: str, _: str = Depends(_require_token)) -> dict:
    order = _orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return _ok(dict(order))
