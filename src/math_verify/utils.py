# MIT License

# Copyright (c) 2024 The HuggingFace Team

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
import os
import threading

from math_verify.errors import TimeoutException

TIMEOUT_WARNING_SHOWN = False
logger = logging.getLogger(__name__)


def timeout(timeout_seconds: int | None = 10):  # noqa: C901
    """A decorator that applies a timeout to the decorated function.

    Args:
        timeout_seconds (int): Number of seconds before timing out the decorated function.
            Defaults to 10 seconds.

    Notes:
        On Unix systems, the main thread uses a signal-based alarm approach which is more efficient as
        it doesn't require spawning a new process. In non-main threads or on Windows, a
        multiprocessing-based approach is used since ``signal.alarm`` is either unavailable or
        unsupported. This will incur a performance penalty but allows using the decorator in a
        multi-threaded environment.
    """
    if timeout_seconds is None or timeout_seconds <= 0:

        def no_timeout_decorator(func):
            return func

        return no_timeout_decorator

    from multiprocessing import Process, Queue

    if os.name == "posix":
        # Unix-like approach: signal.alarm when running in main thread,
        # otherwise fall back to multiprocessing.
        import signal

        def decorator(func):
            def handler(signum, frame):
                raise TimeoutException("Operation timed out!")

            def run_with_signal(*args, **kwargs):
                old_handler = signal.getsignal(signal.SIGALRM)
                signal.signal(signal.SIGALRM, handler)
                signal.alarm(timeout_seconds)
                try:
                    return func(*args, **kwargs)
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

            def run_with_process(*args, **kwargs):
                q = Queue()

                def run_func(q, args, kwargs):
                    try:
                        result = func(*args, **kwargs)
                        q.put((True, result))
                    except Exception as e:
                        q.put((False, e))

                p = Process(target=run_func, args=(q, args, kwargs))
                p.start()
                p.join(timeout_seconds)

                if p.is_alive():
                    p.terminate()
                    p.join()
                    raise TimeoutException("Operation timed out!")

                success, value = q.get()
                if success:
                    return value
                else:
                    raise value

            def wrapper(*args, **kwargs):
                if threading.current_thread() is threading.main_thread():
                    return run_with_signal(*args, **kwargs)
                else:
                    return run_with_process(*args, **kwargs)

            return wrapper

        return decorator

    else:
        # Windows approach (or other OS without signal.alarm): multiprocessing

        def decorator(func):
            def wrapper(*args, **kwargs):
                q = Queue()

                def run_func(q, args, kwargs):
                    try:
                        result = func(*args, **kwargs)
                        q.put((True, result))
                    except Exception as e:
                        q.put((False, e))

                p = Process(target=run_func, args=(q, args, kwargs))
                p.start()
                p.join(timeout_seconds)

                if p.is_alive():
                    p.terminate()
                    p.join()
                    raise TimeoutException("Operation timed out!")

                success, value = q.get()
                if success:
                    return value
                else:
                    raise value

            return wrapper

        return decorator
