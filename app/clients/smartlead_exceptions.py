class SmartleadApiError(Exception):
    """Base exception for all Smartlead API errors."""
    def __init__(self, message: str, status_code: int = 0, response_text: str = ""):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_text = response_text


class SmartleadAuthError(SmartleadApiError):
    """Raised when authentication fails (HTTP 401 or 403)."""
    pass


class SmartleadNotFoundError(SmartleadApiError):
    """Raised when requested resource is not found (HTTP 404)."""
    pass


class SmartleadRateLimitError(SmartleadApiError):
    """Raised when rate limit is exceeded (HTTP 429)."""
    def __init__(self, message: str, retry_after: float = 2.0, response_text: str = ""):
        super().__init__(message, status_code=429, response_text=response_text)
        self.retry_after = retry_after


class SmartleadServerError(SmartleadApiError):
    """Raised when Smartlead returns a 5xx server error."""
    pass


class SmartleadNetworkError(SmartleadApiError):
    """Raised when network, connection, or timeout errors occur."""
    pass
