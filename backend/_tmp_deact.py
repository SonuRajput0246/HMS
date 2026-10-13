# """Reproduce the self-deactivated login flow end to end."""
# from datetime import datetime, timezone
# import json
#
# from app import create_app
# from src.database.session import db_session
# from src.api.models import User
# from src.api.services.auth_service import AuthService
#
# app = create_app()
# EMAIL = 'deact_flow@hmslocal.test'
# PWD = 'Str0ng!Passw0rd'
#
# with app.app_context():
#     from src.api.extensions import bcrypt
#
#     db_session.query(User).filter(User.email == EMAIL).delete(synchronize_session='fetch')
#     db_session.commit()
#
#     role_id = db_session.execute(
#         __import__('sqlalchemy').text('SELECT MIN(id) FROM roles')
#     ).scalar()
#
#     u = User(
#         role_id=role_id,
#         first_name='Deact', last_name='Flow',
#         email=EMAIL,
#         password=bcrypt.generate_password_hash(PWD, 12).decode('utf-8'),
#         is_email_verified=True, is_active=True,
#     )
#     db_session.add(u)
#     db_session.commit()
#     uid = u.id
#
#     ## --- service layer: what does user_login actually return? ---
#     svc = AuthService(db_session)
#
#     print('=' * 72)
#     print('1. deactivated_by comparison (line 230: user.deactivated_by == "user")')
#     print('=' * 72)
#     u.is_active = False
#     u.deactivated_by = DeactivatedByEnum.USER
#     db_session.commit()
#     db_session.refresh(u)
#
#     print('   raw attribute      :', repr(u.deactivated_by))
#     print('   type               :', type(u.deactivated_by).__name__)
#     print('   enum .value        :', repr(u.deactivated_by.value))
#     print('   == "user"          :', u.deactivated_by == 'user')
#     print('   DB literal stored  :', db_session.execute(
#         __import__('sqlalchemy').text(
#             'SELECT deactivated_by FROM users WHERE id=:i'), {'i': uid}).scalar())
#
#     result = svc.user_login({'email': EMAIL, 'password': PWD})
#     print()
#     print('   user_login() returns:', json.dumps(
#         {k: str(v) for k, v in result.items()}))
#
#     ## --- HTTP layer: what does the route actually send? ---
#     print()
#     print('=' * 72)
#     print('2. HTTP POST /api/v1/auth/login  (what the frontend receives)')
#     print('=' * 72)
#     c = app.test_client()
#     r = c.post('/api/v1/auth/login', json={'email': EMAIL, 'password': PWD})
#     body = r.get_json()
#     print('   HTTP status :', r.status_code)
#     print('   body        :', json.dumps(body))
#     print()
#     print('   >> ask_account_activation present in body? ',
#           'ask_account_activation' in (body or {}))
#     print('   >> Angular reads err.error?.ask_account_activation ->',
#           repr((body or {}).get('ask_account_activation')))
#
#     print()
#     print('=' * 72)
#     print('3. Same check for the OTHER 403 branch (start_email_verification)')
#     print('=' * 72)
#     u.is_active = True
#     u.deactivated_by = None
#     u.is_email_verified = False
#     db_session.commit()
#
#     import src.api.services.email_service as es
#     SENT = []
#     es.send_email = lambda to, s, h: (SENT.append(to), True)[1]
#
#     r2 = c.post('/api/v1/auth/login', json={'email': EMAIL, 'password': PWD})
#     b2 = r2.get_json()
#     print('   HTTP status :', r2.status_code)
#     print('   body        :', json.dumps(b2))
#     print('   >> start_email_verification present? ',
#           'start_email_verification' in (b2 or {}))
#
#     db_session.query(User).filter(User.email == EMAIL).delete(synchronize_session='fetch')
#     db_session.commit()
#     print()
#     print('   cleaned up:', db_session.query(User).filter(User.email == EMAIL).count() == 0)
#     db_session.remove()