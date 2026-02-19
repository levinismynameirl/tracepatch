"""Web framework integrations for tracepatch.

Each sub-module provides middleware or helpers for a specific framework.
Frameworks are imported lazily — if the framework is not installed,
importing the integration raises ``ImportError`` with a helpful message.

Available integrations:

* ``tracepatch.integrations.fastapi`` — FastAPI / Starlette ASGI
* ``tracepatch.integrations.flask`` — Flask
* ``tracepatch.integrations.django`` — Django
* ``tracepatch.integrations.wsgi`` — Any WSGI application
"""
