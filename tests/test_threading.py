import sys
import threading
import time


# see https://nitratine.net/blog/post/python-threading-basics/
class Updater(threading.Thread):
    def __init__(self, period: float):
        super(Updater, self).__init__()
        self._period = period
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def task(self):
        with self._lock:
            print("hello")

    def stop(self):
        self._stop_event.set()
        self.join()

    def run(self):
        self._stop_event.clear()
        next_deadline = time.time() + self._period
        while not self._stop_event.is_set():
            self.task()
            now = time.time()

            # make sure we are on the grid, even when the task took too long
            while next_deadline <= now:
                next_deadline += self._period

            time.sleep(next_deadline - time.time())
            next_deadline += self._period


def test_threading():
    u: Updater = Updater(0.2)

    u.start()
    time.sleep(0.5)
    u.task()
    u.task()
    u.stop()
    print("bang!")
