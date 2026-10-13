def service_response(status: bool, message: str, data=None, code=200):
    return {
        "status": status,
        "message": message,
        "data": data
    }, code