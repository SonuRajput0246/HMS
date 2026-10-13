from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from src.database.session import db_session
from src.api.models import EnumDefinition, EnumOption


def seed_enums():
    """
    Seed all application enums into enum_definitions and enum_options tables.

    This seeder uses upsert logic - it will create new enums/options
    if they don't exist, or update them if they do.
    All seeded enums are marked as is_system=True.
    """
    try:
        with db_session() as db:
            # Define all enums with their options
            enums_data = {
                "gender": {
                    "label": "Gender",
                    "description": "Gender options",
                    "sort_order": 11,
                    "options": [
                        {"key": "male", "label": "Male", "sort_order": 1},
                        {"key": "female", "label": "Female", "sort_order": 2},
                        {"key": "other", "label": "Other", "sort_order": 3},
                    ],
                },
                "account_deactivated_by": {
                    "label": "Account Deactivated By",
                    "description": "Who deactivated the user",
                    "sort_order": 13,
                    "options": [
                        {"key": "admin", "label": "Admin", "sort_order": 1},
                        {"key": "user", "label": "User", "sort_order": 2},
                        {"key": "system", "label": "System", "sort_order": 3},
                    ],
                },
                "account_deletion_status": {
                    "label": "Account Deletion Status",
                    "description": "Status of account deletion requests",
                    "sort_order": 8,
                    "options": [
                        {"key": "pending", "label": "Pending", "sort_order": 1, "is_default": True},
                        {"key": "approved", "label": "Approved", "sort_order": 2},
                        {"key": "rejected", "label": "Rejected", "sort_order": 3},
                    ],
                },
                "account_deleted_by": {
                    "label": "Account Deleted By",
                    "description": "Who deleted the account",
                    "sort_order": 9,
                    "options": [
                        {"key": "admin", "label": "Admin", "sort_order": 1},
                        {"key": "user", "label": "User", "sort_order": 2},
                        {"key": "system", "label": "System", "sort_order": 3},
                    ],
                },
                # Self-service reason pickers on the deactivate and delete account
                # screens. `option_key` is what the form submits, so the UI compares
                # against 'other' rather than the 'Other' label -- relabelling an
                # option must not change which branch of the form runs.
                "account_deactivation_reason": {
                    "label": "Account Deactivation Reason",
                    "description": "Why a user chose to deactivate their account",
                    "sort_order": 16,
                    "options": [
                        {"key": "privacy_concerns", "label": "Privacy concerns", "sort_order": 1},
                        {"key": "not_useful_anymore", "label": "Not useful anymore", "sort_order": 2},
                        {"key": "switching_service", "label": "Switching to another service", "sort_order": 3},
                        {"key": "too_many_notifications", "label": "Too many notifications", "sort_order": 4},
                        {"key": "found_better_alternative", "label": "Found a better alternative", "sort_order": 5},
                        {"key": "temporary_break", "label": "Temporary break", "sort_order": 6},
                        {"key": "other", "label": "Other", "sort_order": 7},
                    ],
                },
                "account_deletion_reason": {
                    "label": "Account Deletion Reason",
                    "description": "Why a user chose to delete their account",
                    "sort_order": 17,
                    "options": [
                        {"key": "no_longer_needed", "label": "No longer need the account", "sort_order": 1},
                        {"key": "privacy_data_concerns", "label": "Privacy and data concerns", "sort_order": 2},
                        {"key": "switching_service", "label": "Switching to another service", "sort_order": 3},
                        {"key": "too_complicated", "label": "Too complicated to use", "sort_order": 4},
                        {"key": "too_many_emails", "label": "Too many emails or notifications", "sort_order": 5},
                        {"key": "created_by_mistake", "label": "Created account by mistake", "sort_order": 6},
                        {"key": "found_better_alternative", "label": "Found a better alternative", "sort_order": 7},
                        {"key": "too_expensive", "label": "Service is too expensive", "sort_order": 8},
                        {"key": "other", "label": "Other", "sort_order": 9},
                    ],
                },
                "otp_purpose": {
                    "label": "OTP Purpose",
                    "description": "Purpose of OTP generation",
                    "sort_order": 10,
                    "options": [
                        {"key": "email_verification", "label": "Email Verification", "sort_order": 1},
                        {"key": "account_activation", "label": "Account Activation", "sort_order": 2},
                        {"key": "reset_password", "label": "Reset Password", "sort_order": 3},
                    ],
                },
                "guests_id_type": {
                    "label": "Guests ID Type",
                    "description": "Identification document types",
                    "sort_order": 12,
                    "options": [
                        {"key": "passport", "label": "Passport", "sort_order": 1},
                        {"key": "aadhar", "label": "Aadhar", "sort_order": 2},
                        {"key": "driving_license", "label": "Driving License", "sort_order": 3},
                        {"key": "pan_card", "label": "PAN Card", "sort_order": 4},
                    ],
                },
                "room_status": {
                    "label": "Room Status",
                    "description": "Status of hotel rooms",
                    "sort_order": 1,
                    "options": [
                        {"key": "available", "label": "Available", "sort_order": 1, "is_default": True},
                        {"key": "cleaning", "label": "Cleaning", "sort_order": 2},
                        {"key": "maintenance", "label": "Maintenance", "sort_order": 3},
                        {"key": "out_of_service", "label": "Out of Service", "sort_order": 4},
                    ],
                },
                "reservation_status": {
                    "label": "Reservation Status",
                    "description": "Status of room reservations",
                    "sort_order": 2,
                    "options": [
                        {"key": "created", "label": "Created", "sort_order": 1, "is_default": True},
                        {"key": "reserved", "label": "Reserved", "sort_order": 2},
                        {"key": "checked_in", "label": "Checked In", "sort_order": 3},
                        {"key": "checked_out", "label": "Checked Out", "sort_order": 4},
                        {"key": "cancelled", "label": "Cancelled", "sort_order": 5},
                    ],
                },
                "reservation_payment_type": {
                    "label": "Reservation Payment Type",
                    "description": "Payment types for reservations",
                    "sort_order": 3,
                    "options": [
                        {"key": "advance", "label": "Advance", "sort_order": 1},
                        {"key": "additional_advance", "label": "Additional Advance", "sort_order": 2},
                        {"key": "full", "label": "Full", "sort_order": 3},
                    ],
                },
                "payment_type": {
                    "label": "Payment Type",
                    "description": "Types of payments",
                    "sort_order": 4,
                    "options": [
                        {"key": "advance", "label": "Advance", "sort_order": 1},
                        {"key": "additional_advance", "label": "Additional Advance", "sort_order": 2},
                        {"key": "partial", "label": "Partial", "sort_order": 3},
                        {"key": "full", "label": "Full", "sort_order": 4},
                        {"key": "refund", "label": "Refund", "sort_order": 5},
                    ],
                },
                "payment_method": {
                    "label": "Payment Method",
                    "description": "Methods of payment",
                    "sort_order": 5,
                    "options": [
                        {"key": "cash", "label": "Cash", "sort_order": 1, "is_default": True},
                        {"key": "card", "label": "Card", "sort_order": 2},
                        {"key": "upi", "label": "UPI", "sort_order": 3},
                        {"key": "net_banking", "label": "Net Banking", "sort_order": 4},
                        {"key": "online", "label": "Online", "sort_order": 5},
                    ],
                },
                "payment_status": {
                    "label": "Payment Status",
                    "description": "Status of payments",
                    "sort_order": 6,
                    "options": [
                        {"key": "pending", "label": "Pending", "sort_order": 1, "is_default": True},
                        {"key": "success", "label": "Success", "sort_order": 2},
                        {"key": "failed", "label": "Failed", "sort_order": 3},
                    ],
                },
                "template_code": {
                    "label": "Template Code",
                    "description": "System template codes",
                    "sort_order": 14,
                    "options": [
                        {"key": "EMAIL_VERIFICATION_OTP", "label": "Email Verification OTP", "sort_order": 1},
                        {"key": "ACCOUNT_ACTIVATION_OTP", "label": "Account Activation OTP", "sort_order": 2},
                        {"key": "PASSWORD_RESET_OTP", "label": "Password Reset OTP", "sort_order": 3},
                    ],
                },
                "template_channel": {
                    "label": "Template Channel",
                    "description": "Communication channels for templates",
                    "sort_order": 7,
                    "options": [
                        {"key": "in_app", "label": "In App", "icon": "notifications", "sort_order": 1},
                        {"key": "email", "label": "Email", "icon": "mail", "sort_order": 2, "is_default": True},
                    ],
                },
                "template_variable": {
                    "label": "Template Variable",
                    "description": "Available template placeholder variables",
                    "sort_order": 15,
                    "options": [
                        {"key": "user_name", "label": "User Name", "sort_order": 1},
                        {"key": "otp", "label": "OTP", "sort_order": 2},
                        {"key": "expiry_minutes", "label": "Expiry Minutes", "sort_order": 3},
                        {"key": "company_name", "label": "Company Name", "sort_order": 4},
                        {"key": "user_email", "label": "User Email", "sort_order": 5},
                        {"key": "room_number", "label": "Room Number", "sort_order": 6},
                        {"key": "reservation_number", "label": "Reservation Number", "sort_order": 7},
                        {"key": "check_in_date", "label": "Check In Date", "sort_order": 8},
                        {"key": "check_out_date", "label": "Check Out Date", "sort_order": 9},
                        {"key": "amount", "label": "Amount", "sort_order": 10},
                        {"key": "invoice_number", "label": "Invoice Number", "sort_order": 11},
                    ],
                },
            }

            # Seed all enums
            for enum_key, enum_data in enums_data.items():
                # Upsert EnumDefinition
                enum_def = db.query(EnumDefinition).filter_by(
                    enum_key=enum_key
                ).first()

                if enum_def:
                    # Update existing enum definition
                    enum_def.enum_label = enum_data["label"]
                    enum_def.description = enum_data.get("description")
                    enum_def.sort_order = enum_data.get("sort_order", 0)
                    enum_def.is_system = True
                    enum_def.is_deleted = False
                else:
                    # Create new enum definition
                    enum_def = EnumDefinition(
                        enum_key=enum_key,
                        enum_label=enum_data["label"],
                        description=enum_data.get("description"),
                        is_system=True,
                        sort_order=enum_data.get("sort_order", 0),
                        is_deleted=False
                    )
                    db.add(enum_def)
                    db.flush()  # Get the ID

                # Seed enum options
                for opt_data in enum_data["options"]:
                    option = db.query(EnumOption).filter_by(
                        enum_id=enum_def.id,
                        option_key=opt_data["key"],
                    ).first()

                    if option:
                        # Update existing option
                        option.option_label = opt_data["label"]
                        option.icon = opt_data.get("icon")
                        option.sort_order = opt_data.get("sort_order", 0)
                        option.is_default = opt_data.get("is_default", False)
                        option.is_active = True
                        option.is_deleted = False
                    else:
                        # Create new option
                        option = EnumOption(
                            enum_id=enum_def.id,
                            option_key=opt_data["key"],
                            option_label=opt_data["label"],
                            icon=opt_data.get("icon"),
                            is_active=True,
                            is_default=opt_data.get("is_default", False),
                            sort_order=opt_data.get("sort_order", 0),
                            is_deleted=False
                        )
                        db.add(option)

            db.commit()
            print("--- Enums seeded successfully ---")

    except SQLAlchemyError as e:
        print("!!! Error seeding enums:", str(e))
        raise
    except Exception as e:
        print("!!! Error seeding enums:", str(e))
        raise


if __name__ == "__main__":
    seed_enums()