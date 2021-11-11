import socket
import time
import unittest

from pylorax.monitor import LogMonitor

class LogMonitorTest(unittest.TestCase):
    def test_monitor(self):
        monitor = LogMonitor(timeout=1)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((monitor.host, monitor.port))
                s.sendall("Just a test string\nwith two and a half\nlines in it".encode("utf8"))
                time.sleep(1)
                self.assertFalse(monitor.server.log_check())
                s.sendall("\nAnother line\nTraceback (Not a real traceback)\n".encode("utf8"))
                time.sleep(1)
                self.assertTrue(monitor.server.log_check())
                self.assertEqual(monitor.server.error_line, "Traceback (Not a real traceback)")
        finally:
            monitor.shutdown()

    def test_monitor_IGNORED(self):
        monitor = LogMonitor(timeout=1)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((monitor.host, monitor.port))
                s.sendall("Just a test string\nwith two and a half\nlines in it".encode("utf8"))
                time.sleep(1)
                self.assertFalse(monitor.server.log_check())
                s.sendall("\nAnother line\nIGNORED: Traceback (Not a real traceback)\n".encode("utf8"))
                time.sleep(1)
                self.assertFalse(monitor.server.log_check())
                self.assertEqual(monitor.server.error_line, "")
        finally:
            monitor.shutdown()

    def test_monitor_timeout(self):
        # Timeout is in minutes so to shorten the test we pass 0.1
        monitor = LogMonitor(timeout=0.1)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((monitor.host, monitor.port))
                s.sendall("Just a test string\nwith two and a half\nlines in it".encode("utf8"))
                time.sleep(1)
                self.assertFalse(monitor.server.log_check())
                time.sleep(7)
                self.assertTrue(monitor.server.log_check())
                self.assertEqual(monitor.server.error_line, "")
        finally:
            monitor.shutdown()


    def test_monitor_utf8(self):
        ## If a utf8 character spans the end of the 4096 byte buffer it will fail to
        ## decode. Test to make sure it is reassembled correctly.
        monitor = LogMonitor(timeout=1)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((monitor.host, monitor.port))

                # Simulate a UTF8 character that gets broken into parts by buffering, etc.
                data = "Just a test string\nTraceback (Not a real traceback)\nWith A"
                s.sendall(data.encode("utf8") + b"\xc3")
                time.sleep(1)
                self.assertTrue(monitor.server.log_check())
                self.assertEqual(monitor.server.error_line, "Traceback (Not a real traceback)")
        finally:
            monitor.shutdown()
