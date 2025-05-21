import threading

from math_verify.parser import parse
from math_verify.grader import verify


def test_parse_multithread():
    expected = parse("1+1", fallback_mode="no_fallback")[0]
    results = []

    def worker():
        results.append(parse("1+1", fallback_mode="no_fallback", parsing_timeout=1)[0])

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 3
    assert all(verify(expected, r, timeout_seconds=1) for r in results)


def test_verify_multithread():
    gold = parse("1+1", fallback_mode="no_fallback")[0]
    results = []

    def worker():
        results.append(verify([gold], [gold], timeout_seconds=1))

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == [True, True, True]
