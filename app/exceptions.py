class EventProcessingError(Exception):
    """Base class for event processing errors"""

    def __init__(self, message, *, retryable=False):
        self.retryable = retryable
        super().__init__(message)


class EventPublishingError(EventProcessingError):
    """Exception raised when an event fails to be published"""

    def __init__(self, event_type, error, *, phase="publish", retryable=True):
        super().__init__(
            f"Error during {phase} for event '{event_type}': {error}",
            retryable=retryable,
        )


class EventConsumptionError(EventProcessingError):
    """Exception raised when an error occurs during event consumption"""

    def __init__(self, message, *, event_data=None, error=None, retryable=True):
        details = message
        if event_data is not None:
            details = f"{details}. event={event_data}"
        if error is not None:
            details = f"{details}. error={error}"
        super().__init__(details, retryable=retryable)


class UnknownEventError(EventConsumptionError):
    def __init__(self, event_data):
        super().__init__(
            "No handler registered for event",
            event_data=event_data,
            retryable=False,
        )


class MalformedEventError(EventConsumptionError):
    def __init__(self, event_data=None, error=None):
        super().__init__(
            "Malformed event payload",
            event_data=event_data,
            error=error,
            retryable=False,
        )


class PricingError(Exception):
    """Base class for pricing errors"""


class InvalidPricingConfigurationError(PricingError):
    """Raised when a pricing strategy is configured with invalid values"""


class IncompleteOrderPricingError(PricingError):
    """Raised when order data is insufficient to compute pricing"""
