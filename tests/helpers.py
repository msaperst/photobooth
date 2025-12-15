import time
from typing import Callable


def wait_for(
        condition: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.05,
):
    """
    Wait until condition() returns True or timeout is reached.

    Raises AssertionError on timeout.
    """
    deadline = time.time() + timeout

    while time.time() < deadline:
        if condition():
            return
        time.sleep(interval)

    raise AssertionError("Condition not met before timeout")
