class APIError(Exception):
    """Base class for all custom API errors."""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

class ResourceConflictError(APIError):
    def __init__(self, message="Resource already exists"):
        super().__init__(message, status_code=409)

class UnauthorizedError(APIError):
    def __init__(self, message="Unauthorized access", payload=None):
        super().__init__(message, status_code=401, payload=payload)