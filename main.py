import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId

app = FastAPI(title="CTRL-Z API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Schemas ----------
class SizeOption(BaseModel):
    label: str
    available: bool = True

class ProductModel(BaseModel):
    name: str
    description: str
    price: float
    category: str
    subcategory: Optional[str] = None
    sizes: List[str] = Field(default_factory=lambda: ["XS","S","M","L","XL","XXL"]) 
    images: List[str] = Field(default_factory=list)
    stock: int = 0
    tags: List[str] = Field(default_factory=list)

class ProductOut(ProductModel):
    id: str

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: dict

# ---------- Helpers ----------

def serialize_product(doc) -> ProductOut:
    return ProductOut(
        id=str(doc.get("_id")),
        name=doc.get("name"),
        description=doc.get("description"),
        price=doc.get("price"),
        category=doc.get("category"),
        subcategory=doc.get("subcategory"),
        sizes=doc.get("sizes", []),
        images=doc.get("images", []),
        stock=doc.get("stock", 0),
        tags=doc.get("tags", []),
    )


def database_available() -> bool:
    try:
        from database import db
        return db is not None
    except Exception:
        return False


def ensure_seed_data():
    """Seed a few products if collection empty. Safe no-op if db missing."""
    try:
        from database import db
        if db is None:
            return
        if db["product"].count_documents({}) == 0:
            seed = [
                {
                    "name": "CTRL-Z Oversized Tee — Neon Grid",
                    "description": "Heavyweight cotton tee with neon cyan glitch print.",
                    "price": 49.0,
                    "category": "Unisex",
                    "subcategory": "Tees",
                    "sizes": ["XS","S","M","L","XL","XXL"],
                    "images": [
                        "https://images.unsplash.com/photo-1520975661595-6453be3f7070?q=80&w=1200&auto=format&fit=crop",
                        "https://images.unsplash.com/photo-1548883354-94bcfe321cce?q=80&w=1200&auto=format&fit=crop",
                        "https://images.unsplash.com/photo-1520974735194-6c0a6b4a37d1?q=80&w=1200&auto=format&fit=crop"
                    ],
                    "stock": 120,
                    "tags": ["glitch","oversized","core"],
                },
                {
                    "name": "CTRL-Z Tech Cargo — Midnight",
                    "description": "Water-resistant tech cargos with magnetic closures.",
                    "price": 89.0,
                    "category": "Men",
                    "subcategory": "Cargo Pants",
                    "sizes": ["S","M","L","XL"],
                    "images": [
                        "https://images.unsplash.com/photo-1543087903-1ac2ec7aa8c5?q=80&w=1200&auto=format&fit=crop",
                        "https://images.unsplash.com/photo-1544025162-d76694265947?q=80&w=1200&auto=format&fit=crop",
                        "https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1200&auto=format&fit=crop"
                    ],
                    "stock": 60,
                    "tags": ["techwear","cargo"],
                },
                {
                    "name": "CTRL-Z Cropped Hoodie — Crimson Pulse",
                    "description": "Fleece cropped hoodie with crimson pulse embroidery.",
                    "price": 79.0,
                    "category": "Women",
                    "subcategory": "Hoodies",
                    "sizes": ["XS","S","M","L"],
                    "images": [
                        "https://images.unsplash.com/photo-1517649763962-0c623066013b?q=80&w=1200&auto=format&fit=crop",
                        "https://images.unsplash.com/photo-1488188840666-e2308741a62f?q=80&w=1200&auto=format&fit=crop",
                        "https://images.unsplash.com/photo-1520975661595-6453be3f7070?q=80&w=1200&auto=format&fit=crop"
                    ],
                    "stock": 40,
                    "tags": ["cropped","hoodie"],
                },
            ]
            db["product"].insert_many(seed)
    except Exception:
        pass


# ---------- Routes ----------
@app.get("/", tags=["health"])
def read_root():
    return {"message": "CTRL-Z API online"}


@app.get("/test", tags=["health"])
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, "name", None) or "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except ImportError:
        response["database"] = "❌ Database module not found"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.get("/api/products", response_model=List[ProductOut], tags=["products"])
def list_products(
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None)
):
    """List products with optional category or search query"""
    ensure_seed_data()

    # If DB available, query it; else return static fallback
    if database_available():
        from database import db
        filter_obj = {}
        if category:
            filter_obj["category"] = {"$regex": f"^{category}$", "$options": "i"}
        if q:
            filter_obj["$or"] = [
                {"name": {"$regex": q, "$options": "i"}},
                {"description": {"$regex": q, "$options": "i"}},
                {"tags": {"$regex": q, "$options": "i"}},
            ]
        docs = list(db["product"].find(filter_obj).limit(48))
        return [serialize_product(d) for d in docs]
    else:
        fallback = [
            {
                "_id": ObjectId(),
                "name": "CTRL-Z Oversized Tee — Neon Grid",
                "description": "Heavyweight cotton tee with neon cyan glitch print.",
                "price": 49.0,
                "category": "Unisex",
                "subcategory": "Tees",
                "sizes": ["XS","S","M","L","XL","XXL"],
                "images": [
                    "https://images.unsplash.com/photo-1520975661595-6453be3f7070?q=80&w=1200&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1548883354-94bcfe321cce?q=80&w=1200&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1520974735194-6c0a6b4a37d1?q=80&w=1200&auto=format&fit=crop"
                ],
                "stock": 120,
                "tags": ["glitch","oversized","core"],
            }
        ]
        return [serialize_product(d) for d in fallback]


@app.get("/api/products/{product_id}", response_model=ProductOut, tags=["products"])
def get_product(product_id: str):
    if database_available():
        from database import db
        try:
            doc = db["product"].find_one({"_id": ObjectId(product_id)})
            if not doc:
                raise HTTPException(status_code=404, detail="Product not found")
            return serialize_product(doc)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid product id")
    else:
        # Fallback single product
        return ProductOut(
            id=str(ObjectId()),
            name="CTRL-Z Oversized Tee — Neon Grid",
            description="Heavyweight cotton tee with neon cyan glitch print.",
            price=49.0,
            category="Unisex",
            subcategory="Tees",
            sizes=["XS","S","M","L","XL","XXL"],
            images=[
                "https://images.unsplash.com/photo-1520975661595-6453be3f7070?q=80&w=1200&auto=format&fit=crop",
                "https://images.unsplash.com/photo-1548883354-94bcfe321cce?q=80&w=1200&auto=format&fit=crop",
                "https://images.unsplash.com/photo-1520974735194-6c0a6b4a37d1?q=80&w=1200&auto=format&fit=crop"
            ],
            stock=120,
            tags=["glitch","oversized","core"],
        )


@app.post("/api/auth/login", response_model=LoginResponse, tags=["auth"])
def login(payload: LoginRequest):
    # Placeholder auth (demo): validate shape and return a fake token
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="Email and password required")
    return LoginResponse(
        token="demo-token-ctrl-z",
        user={"email": payload.email, "name": "Z-User"}
    )


@app.get("/schema", tags=["schemas"]) 
def get_schemas():
    # Expose schemas.py content for viewer
    try:
        with open("schemas.py", "r") as f:
            return {"schemas": f.read()}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
