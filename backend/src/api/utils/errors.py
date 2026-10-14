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

class BadRequestError(APIError):
    def __init__(self, message="Bad request", payload=None):
        super().__init__(message, status_code=400, payload=payload)

class ResourceNotFoundError(APIError):
    def __init__(self, message="Resource not found", payload=None):
        super().__init__(message, status_code=404, payload=payload)

class ForbiddenError(APIError):
    """403.

    Lives here rather than beside its first caller so that every 403 in the
    codebase -- authorization's module refusal and tenant suspension alike -- is
    the same class, and a client cannot tell them apart by their type.
    """
    def __init__(self, message="You do not have access to this resource", payload=None):
        super().__init__(message, status_code=403, payload=payload)