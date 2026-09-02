import fcntl
from contextlib import contextmanager
from pathlib import Path


class RunnerAlreadyActiveError(RuntimeError):
    pass


@contextmanager
def single_runner_lock(path=".trading_bot_runner.lock"):
    """Prevent two local runner processes from submitting the same signal."""
    lock_path = Path(path)
    with lock_path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RunnerAlreadyActiveError(
                "Another trading bot runner is already active"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
