import os
import subprocess
import sys

from cli.server_runtime import IdleWatchdog, remove_pidfile, stop_previous_instance, write_pidfile


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_watchdog_idle_after_timeout():
    clock = _Clock()
    wd = IdleWatchdog(60, on_idle=lambda: None, clock=clock)
    clock.now = 59
    assert not wd.is_idle()
    clock.now = 60
    assert wd.is_idle()


def test_watchdog_request_resets_timer():
    clock = _Clock()
    wd = IdleWatchdog(60, on_idle=lambda: None, clock=clock)
    clock.now = 50
    wd.request_started()
    wd.request_finished()
    clock.now = 100
    assert not wd.is_idle()
    clock.now = 110
    assert wd.is_idle()


def test_watchdog_not_idle_while_request_in_flight():
    clock = _Clock()
    wd = IdleWatchdog(60, on_idle=lambda: None, clock=clock)
    wd.request_started()  # e.g. waiting on a browser login
    clock.now = 10_000
    assert not wd.is_idle()
    wd.request_finished()
    clock.now = 10_060
    assert wd.is_idle()


def test_watchdog_fires_on_idle():
    import threading

    fired = threading.Event()
    wd = IdleWatchdog(0, on_idle=fired.set, check_every=0.01)
    wd.start()
    assert fired.wait(2)


def test_stop_previous_instance_no_file(tmp_path):
    assert stop_previous_instance(tmp_path / "server.pid") is None


def test_stop_previous_instance_garbage_file(tmp_path):
    pidfile = tmp_path / "server.pid"
    pidfile.write_text("not a pid")
    assert stop_previous_instance(pidfile) is None


def test_stop_previous_instance_dead_pid_cleans_file(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    pidfile = tmp_path / "server.pid"
    pidfile.write_text(str(proc.pid))
    assert stop_previous_instance(pidfile) is None
    assert not pidfile.exists()


def test_stop_previous_instance_ignores_unrelated_process(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        pidfile = tmp_path / "server.pid"
        pidfile.write_text(str(proc.pid))
        assert stop_previous_instance(pidfile) is None
        assert proc.poll() is None  # never signal a process that isn't `adalove serve`
    finally:
        proc.kill()
        proc.wait()


def test_stop_previous_instance_stops_adalove_server(tmp_path):
    # argv contains "adalove" and "serve", like the real server's command line
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "adalove", "serve"])
    try:
        pidfile = tmp_path / "server.pid"
        pidfile.write_text(str(proc.pid))
        assert stop_previous_instance(pidfile) == proc.pid
        assert proc.wait(5) is not None
        assert not pidfile.exists()
    finally:
        if proc.poll() is None:
            proc.kill()


def test_remove_pidfile_only_if_ours(tmp_path):
    pidfile = tmp_path / "server.pid"
    write_pidfile(pidfile)
    assert pidfile.read_text() == str(os.getpid())
    remove_pidfile(pidfile)
    assert not pidfile.exists()

    pidfile.write_text("999999")  # a newer server took over
    remove_pidfile(pidfile)
    assert pidfile.exists()
