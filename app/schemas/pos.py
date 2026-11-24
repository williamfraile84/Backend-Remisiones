from typing import List, Optional, Any, Union
from pydantic import BaseModel, Field


class ProductLookupResponse(BaseModel):
    found: bool
    item_id: Optional[str] = None
    barcode: str
    modal_barcode: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    cost_price: Optional[float] = 0.0
    sale_price: Optional[float] = 0.0
    stock: Optional[str] = "0"
    unit_code: Optional[str] = "UN"
    match_type: Optional[str] = "csopos"


class ProductItem(BaseModel):
    item_id: str
    barcode: str
    name: str
    category: str = ""
    cost_price: float = 0.0
    unit_price: float = 0.0
    formatted_sale_price: str = "$0"
    stock: str = "0"
    unit_code: str = "UN"


class ProductSearchResponse(BaseModel):
    query: str
    total: int
    items: List[ProductItem]


class SinglePriceUpdateRequest(BaseModel):
    barcode: str = Field(..., description="Código de barras o UPC")
    modal_barcode: Optional[str] = Field(None, description="Código secundario si aplica")
    new_price: float = Field(..., gt=0, description="Nuevo precio de venta unitario")
    item_id: Optional[str] = Field(None, description="ID del artículo en el sistema POS")
    item_name: Optional[str] = Field(None, description="Nombre del producto")


class BulkPriceUpdateRequest(BaseModel):
    item_ids: List[str] = Field(..., min_length=1, description="Lista de IDs de artículos a modificar")
    new_price: float = Field(..., gt=0, description="Nuevo precio de venta para todos")
    details: Optional[str] = Field(None, description="Detalles")


class PriceUpdateResponse(BaseModel):
    success: bool
    message: str
    updated_count: int = 1
    new_price: float
    formatted_new_price: str


class PosStatusResponse(BaseModel):
    is_ready: bool
    is_logged_in: bool
    base_url: str
    active_domain: str = "csopos.co"
    active_page: str
    last_error: Optional[str] = None
    last_sync: Optional[str] = None
    total_cached_items: int = 0


class PosItemDetailResponse(BaseModel):
    item_id: str
    name: str
    item_number: Optional[str] = None
    category: str = "General"
    category_code: Optional[Union[str, int]] = None
    department_code: Optional[Union[str, int]] = None
    cost_price: float = 0.0
    unit_price: float = 0.0
    formatted_sale_price: str = "$0"
    unit_code: str = "UN"
    stock_quantity: float = 0.0
    description: Optional[str] = None
    profit_percentage: float = 30.0
    additional_numbers: List[str] = []


class PosConciliarItem(BaseModel):
    producto_id: Optional[int] = None
    pos_item_id: Optional[str] = None
    barcode: Optional[str] = None
    nombre: str
    nuevo_precio_venta: float
    nuevo_costo: Optional[float] = None


class PosConciliarRequest(BaseModel):
    items: List[PosConciliarItem]
    actualizar_catalogo_local: bool = True
