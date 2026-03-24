"""
Vercel serverless entry point.

Vercel looks for an ASGI/WSGI app in api/index.py.
We re-export the FastAPI app from backend.main.
"""

from backend.main import app
