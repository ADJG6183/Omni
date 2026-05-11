from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: bool = True
    code: str
    message: str
    retryable: bool = False
