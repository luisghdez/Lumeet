"""Shared cancellation primitives for background generation workers."""


class PipelineCancelled(RuntimeError):
    """Raised when a user cancellation should stop an in-flight pipeline."""

