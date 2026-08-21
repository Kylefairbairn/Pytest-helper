class CaptureError(RuntimeError):
    """Base error for capture failures."""


class CaptureAlreadyRunning(CaptureError):
    pass


class CaptureNotRunning(CaptureError):
    pass

