from sqlalchemy import select
from src.database.seeders._seeding import resolve_tenant_id, safe_error
from src.database.session import db_session
from src.api.models.login_sliders_model import LoginSliders
from datetime import datetime, timezone

sliders = [
    {
        "title": "Welcome to HMS",
        "image_path": "assets/images/login_slider/slider_img_19.avif",
        "alt_text": "Hotel lobby",
        "display_order": 1
    },
    {
        "title": "Hotel",
        "image_path": "assets/images/login_slider/slider_img_26.webp",
        "alt_text": "Hotel",
        "display_order": 2
    },
    {
        "title": "Reception",
        "image_path": "assets/images/login_slider/slider_img_04.avif",
        "alt_text": "Reception",
        "display_order": 3
    },
    {
        "title": "Luxury Rooms",
        "image_path": "assets/images/login_slider/slider_img_24.avif",
        "alt_text": "Luxury room",
        "display_order": 4
    },
    {
        "title": "Fine Dining",
        "image_path": "assets/images/login_slider/slider_img_23.jpg",
        "alt_text": "Hotel restaurant",
        "display_order": 5
    },
    {
        "title": "Buffet",
        "image_path": "assets/images/login_slider/slider_img_17.webp",
        "alt_text": "Buffet",
        "display_order": 6
    },
    {
        "title": "Room Service",
        "image_path": "assets/images/login_slider/slider_img_03.webp",
        "alt_text": "Room Service",
        "display_order": 7
    },
    {
        "title": "Staff",
        "image_path": "assets/images/login_slider/slider_img_16.jpg",
        "alt_text": "Staff",
        "display_order": 8
    },
    {
        "title": "Services",
        "image_path": "assets/images/login_slider/slider_img_07.jpg",
        "alt_text": "Services",
        "display_order": 9
    }
]

def seed_login_sliders(tenant_id: int | None = None):
    tenant_id = resolve_tenant_id(tenant_id)
    try:
        for slide in sliders:
            ## Scoped to the hotel: two hotels are allowed to have a slide
            ## called "Reception", and without the tenant filter the second one
            ## would be skipped as a duplicate of the first hotel's.
            stmt = select(LoginSliders).filter_by(
                tenant_id=tenant_id,
                title=slide["title"],
                is_deleted=False
            )
            exists = db_session.execute(stmt).scalar_one_or_none()
            if not exists:
                new_item = LoginSliders(
                    tenant_id=tenant_id,
                    title=slide["title"],
                    image_path=slide["image_path"],
                    alt_text=slide["alt_text"],
                    display_order=slide["display_order"],
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db_session.add(new_item)

        db_session.commit()
        print("--- Login sliders created successfully. ---")
    except Exception as e:
        db_session.rollback()
        print("!!! Error seeding login sliders:", safe_error(e))
        raise
    finally:
        db_session.remove()

if __name__ == "__main__":
    seed_login_sliders()
