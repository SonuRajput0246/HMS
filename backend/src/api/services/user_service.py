from src.api.extensions import bcrypt
from sqlalchemy.orm import joinedload
from sqlalchemy import or_, text
import re

from src.api.models.user_model import User
from src.api.services.enum_service import EnumService

from src.api.utils.responses import service_response


class UserService:
    def __init__(self, db):
        self.db = db
        self.enum_service = EnumService(db)


    def get_users(self, data: dict):
        page_size = data["page_size"]
        page_number = data["page_number"]
        search_value = data.get("search_value")

        query = self.db.query(User).options(joinedload(User.role)).filter(User.is_deleted == False)

        if search_value:
            val = search_value.strip()

            # 1. Prepare FTS query (for names)
            # Only keep tokens >= 3 characters to avoid the min_token_size issue
            clean_val = re.sub(r'[.@_\-]', ' ', val)
            tokens = clean_val.split()
            fts_query = " ".join([f"+{t}*" for t in tokens if len(t) >= 3])

            # 2. Hybrid Filter
            if fts_query:
                # If we have valid FTS tokens, search both
                query = query.filter(
                    or_(
                        text("MATCH(first_name, last_name, email) AGAINST (:search_val IN BOOLEAN MODE)"),
                        User.email.like(f"{val}%")  # Fast B-Tree prefix search
                    )
                ).params(search_val=fts_query)
            else:
                # If search is too short for FTS (e.g. "Ra"), just use LIKE
                query = query.filter(
                    or_(
                        User.first_name.like(f"{val}%"),
                        User.last_name.like(f"{val}%"),
                        User.email.like(f"{val}%")
                    )
                )
        total_records = query.count()
        users = (
            query
            .order_by(User.id.desc())
            .offset((page_number - 1) * page_size)
            .limit(page_size)
            .all()
        )
        user_list = [
            {
                "id": user.id,
                "role_id": user.role_id,
                "role_name": user.role.role_name if user.role else "N/A",
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "is_active": user.is_active
            }
            for user in users
        ]
        last_page = (total_records + page_size - 1) // page_size if total_records > 0 else 1
        return {
            "status": True,
            "data": user_list,
            "meta": {
                "current_page": page_number,
                "last_page": last_page,
                "total_records": total_records,
                "per_page": page_size
            }
        }, 200


    def get_user_by_id(self, user_id):
        user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
        if not user:
            return service_response(False, "User not found", None, 404)
        user_data = {
            "id": user.id,
            "role_id": user.role_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "is_active": user.is_active,
            "is_deleted": user.is_deleted,
            "created_at": user.created_at.isoformat()
        }
        return service_response(True, "User fetched successfully.", user_data, 200)


    def upsert_user(self, data: dict):
        user_id = data["id"]
        user_email = data["email"]
        is_deleted_op = data.get('is_deleted') is True

        if user_email and not is_deleted_op:
            duplicate_check = self.db.query(User).filter(
                User.is_deleted == False,
                User.email == user_email,
                User.id != user_id
            ).first()
            if duplicate_check:
                return service_response(False, "User with this email already exists.", None, 409)

        if user_id == 0:
            REQUIRED_FIELDS = ("first_name", "last_name", "email", "password", "role_id")
            for field in REQUIRED_FIELDS:
                if not data.get(field):
                    return service_response(False, f"Field {field} is required", None, 400)

            hashed_password = bcrypt.generate_password_hash(
                data["password"], 12
            ).decode("utf-8")

            new_user = User(
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                email=data.get("email"),
                password=hashed_password,
                role_id=data.get("role_id"),
                is_email_verified=True,
                is_active=data.get("is_active", True),
                is_deleted=False
            )
            self.db.add(new_user)
            self.db.commit()
            return service_response(True, "User created successfully.", None, 201)
        else:
            user = self.db.query(User).filter_by(is_deleted=False, id=user_id).first()
            if not user:
                return service_response(False, "User not found", None, 404)

            ALLOWED_FIELDS = ("first_name", "last_name", "role_id", "is_active", "is_deleted")
            for field in ALLOWED_FIELDS:
                if field in data:
                    setattr(user, field, data[field])

            if data.get("is_active") is False:
                ## Admin-initiated deactivation. Validated against
                ## enum_options so a new option needs only a seeder change.
                error = self.enum_service.validate(
                    "account_deactivated_by", "admin"
                )
                if error:
                    return service_response(False, error, None, 500)

                user.deactivated_by = "admin"
                user.deactivation_reason = data.get("deactivation_reason", "Deactivated by admin")

            self.db.commit()

            msg = "User deleted successfully." if data.get("is_deleted") is True else "User updated successfully."
            return service_response(True, msg, None, 200)
