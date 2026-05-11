from fastapi import Request
from fastapi.responses import JSONResponse


class OmniError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, retryable: bool = False):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)


async def omni_error_handler(request: Request, exc: OmniError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
        },
    )
