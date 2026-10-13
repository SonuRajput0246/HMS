pip install Flask
pip install python-dotenv

### Object Relational Mapper (ORM)
pip install Flask-SQLAlchemy

### For MYSQL Database Connection
pip install mysqlclient

## Initial & setup migration
pip install Flask-Migrate

### For hashing the password
pip install Flask-Bcrypt

pip install PyJWT

pip install flask-cors

pip install marshmallow marshmallow-sqlalchemy


#--------------------------#-----------------------------#

### Commands:
alembic init src/database/migrations
alembic revision --autogenerate -m "[MESSAGE]"
alembic revision --autogenerate -m "initial_migrations"
alembic upgrade head
alembic downgrade -1

python -m src.database.seeders.[SEEDER_FILE_NAME]
python -m src.database.seeders.run_base_seeders

#--------------------------#-----------------------------#

### Cookies variables for production
# COOKIE_SECURE=true
# COOKIE_SAMESITE=None
## response.set_cookie(
##     key="hms_refreshToken",
##     value=refresh_token,
##     httponly=True,
##     secure=False,  ## True in production (HTTPS)
##     samesite="Lax",  ## set "Lax" for localhost and "None" for production
##     max_age=60 * 60 * 24 * current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"],
##     path="/"
## )


#--------------------------#-----------------------------#

### To Do:
## Filter users by roles (if required)
## Cache total guest count in Redis and update on insert/delete.
## Loader in selection formfield



Manage the time of the check-in and check-out every where


check the use of "isDashboard" in the FE

-------------------
Guest History
Guest Stay History
GET /api/guests/{id}/history
Returns: past bookings, rooms stayed, dates, spend (optional, future billing)
-------------------
Admin Apis
Blacklist Guest (then also have to create angule page to list the blacklist guest and also check before creating the booking against this guest)
PATCH /api/guests/{id}/blacklist
Mark VIP (Used for discount, priority booking)
PATCH /api/guests/{id}/vip
-------------------

Reports Page
Route
/reports
Reports
•	Occupancy report
•	Revenue report
•	Daily check-ins
•	Daily check-outs

--------------------------

 During Stay
Guest may use hotel services.
Possible activities:
•	Room service
•	Restaurant
•	Laundry
•	Spa
•	Mini bar
All charges are added to the Guest Folio / Bill.
Example bill table:
Item	Amount
Room Charge	₹3000
Food	₹800
Laundry	₹200
-----------------------------------------
Reception generates final bill.
------------------------------------

Billing / Folio
bill_id
booking_id
item
amount
date
------------------------


***** update reservation




## if you want to insert fake data
pip install faker