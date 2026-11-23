class ServiceError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class NotFoundError(ServiceError):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            "not_found",
            f"{resource} '{identifier}' was not found.",
        )


class ConfigurationUnavailable(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__("configuration_unavailable", message)
