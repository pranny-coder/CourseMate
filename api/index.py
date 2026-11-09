import os
import sys

# Add parent directory to sys.path so app modules can be resolved
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app as _app


class VercelPathNormalizer:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            for prefix in ("/api/index.py", "/api/index", "/api"):
                if path == prefix or path == prefix + "/":
                    scope["path"] = "/"
                    break
                elif path.startswith(prefix + "/"):
                    scope["path"] = path[len(prefix):]
                    break
        await self.app(scope, receive, send)


app = VercelPathNormalizer(_app)
