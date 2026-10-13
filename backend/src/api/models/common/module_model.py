from sqlalchemy import String, Boolean, JSON
from src.database.base_model import BaseModel
from sqlalchemy.orm import Mapped, mapped_column


class Module(BaseModel):
    __tablename__ = 'modules'

    id: Mapped[int] = mapped_column(primary_key=True)
    module_name: Mapped[str] = mapped_column(String(50), nullable=False)
    module_display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    menu_parent_code: Mapped[int] = mapped_column(nullable=False)
    has_child_menu: Mapped[bool] = mapped_column(Boolean, default=False)
    route_path: Mapped[str] = mapped_column(String(50), nullable=False)
    display_order_no: Mapped[int] = mapped_column(nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False)
    access_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


    def __repr__(self):
        return f"Module(id={self.id}, module_name={self.module_name})"
