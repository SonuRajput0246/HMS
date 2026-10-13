from sqlalchemy import String, Boolean
from src.database.base_model import BaseModel
from sqlalchemy.orm import Mapped, mapped_column


class LoginSliders(BaseModel):
    __tablename__ = 'login_sliders'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    alt_text: Mapped[str] = mapped_column(String(50), nullable=False)
    display_order: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


    def __repr__(self):
        return f"LoginSliders(id={self.id})"