class TixError(Exception):
    """Base for all tix application errors."""


class ZendeskAPIError(TixError):
    """Zendesk API returned an error or was unreachable."""


class GitOperationError(TixError):
    """A git subprocess failed."""


class ExternalToolError(TixError):
    """gh CLI or terminal launch failure."""
