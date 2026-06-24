"""Test system module — platform detection, filesystem parsing, network stats."""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from webui import config


class TestIsOpenBSD(unittest.TestCase):
    def setUp(self):
        config.setdefault("system", {})["platform"] = "auto"

    def test_config_openbsd(self):
        config["system"]["platform"] = "openbsd"
        from webui.system import _is_openbsd
        self.assertTrue(_is_openbsd())

    def test_config_linux(self):
        config["system"]["platform"] = "linux"
        from webui.system import _is_openbsd
        self.assertFalse(_is_openbsd())

    @mock.patch("os.path.exists", return_value=True)
    def test_bsd_file_detected(self, mock_exists):
        from webui.system import _is_openbsd
        self.assertTrue(_is_openbsd())

    @mock.patch("os.path.exists", return_value=False)
    @mock.patch("subprocess.run")
    def test_uname_detects_openbsd(self, mock_run, mock_exists):
        mock_run.return_value.stdout = "OpenBSD\n"
        from webui.system import _is_openbsd
        self.assertTrue(_is_openbsd())

    @mock.patch("os.path.exists", return_value=False)
    @mock.patch("subprocess.run")
    def test_uname_detects_linux(self, mock_run, mock_exists):
        mock_run.return_value.stdout = "Linux\n"
        from webui.system import _is_openbsd
        self.assertFalse(_is_openbsd())

    @mock.patch("os.path.exists", return_value=False)
    @mock.patch("subprocess.run", side_effect=Exception("no uname"))
    def test_uname_failure_false(self, mock_run, mock_exists):
        from webui.system import _is_openbsd
        self.assertFalse(_is_openbsd())


class TestRun(unittest.TestCase):
    @mock.patch("subprocess.run")
    def test_run_success(self, mock_run):
        mock_run.return_value.stdout = "line1\nline2\n"
        mock_run.return_value.text = True
        from webui.system import _run
        result = _run(["echo", "test"])
        self.assertEqual(result, ["line1", "line2"])

    @mock.patch("subprocess.run", side_effect=Exception("fail"))
    def test_run_failure_returns_empty(self, mock_run):
        from webui.system import _run
        self.assertEqual(_run(["badcmd"]), [])

    @mock.patch("subprocess.run")
    def test_run_truncates_long_output(self, mock_run):
        big = "x" * 2_000_000
        mock_run.return_value.stdout = big
        mock_run.return_value.text = True
        from webui.system import _run
        result = _run(["cat"])
        self.assertLessEqual(len("".join(result)), 1_048_576)


class TestGetFilesystems(unittest.TestCase):
    @mock.patch("webui.system._run")
    def test_linux_df_parsing(self, mock_run):
        config["system"]["platform"] = "linux"
        mock_run.return_value = [
            "Filesystem      Size  Used Avail Use% Mounted on",
            "/dev/sda1        50G   20G   28G  42% /",
            "/dev/sda2       100G   60G   35G  64% /home",
        ]
        from webui.system import get_filesystems
        result = get_filesystems()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["device"], "/dev/sda1")
        self.assertEqual(result[0]["capacity"], 42.0)
        self.assertEqual(result[0]["mount"], "/")
        self.assertEqual(result[1]["device"], "/dev/sda2")
        self.assertEqual(result[1]["capacity"], 64.0)
        self.assertEqual(result[1]["mount"], "/home")

    @mock.patch("webui.system._run")
    def test_openbsd_df_parsing(self, mock_run):
        config["system"]["platform"] = "openbsd"
        mock_run.return_value = [
            "Filesystem      Size  Used Avail Use% Mounted on",
            "/dev/sd0a        50G   20G   28G  42% /",
            "/dev/sd0b       100G   60G   35G  64% /home",
        ]
        from webui.system import get_filesystems
        result = get_filesystems()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["device"], "sd0a")
        self.assertEqual(result[1]["device"], "sd0b")

    @mock.patch("webui.system._run")
    def test_df_skip_header(self, mock_run):
        config["system"]["platform"] = "linux"
        mock_run.return_value = [
            "Filesystem      Size  Used Avail Use% Mounted on",
        ]
        from webui.system import get_filesystems
        self.assertEqual(get_filesystems(), [])

    @mock.patch("webui.system._run", return_value=[])
    def test_df_empty(self, mock_run):
        from webui.system import get_filesystems
        self.assertEqual(get_filesystems(), [])


class TestListDisks(unittest.TestCase):
    @mock.patch("webui.system._run")
    def test_openbsd(self, mock_run):
        config["system"]["platform"] = "openbsd"
        mock_run.return_value = ["sd0,wd0"]
        from webui.system import list_disks
        self.assertEqual(list_disks(), ["sd0", "wd0"])

    @mock.patch("webui.system._run", return_value=[])
    def test_openbsd_empty(self, mock_run):
        config["system"]["platform"] = "openbsd"
        from webui.system import list_disks
        self.assertEqual(list_disks(), [])

    @mock.patch("os.listdir")
    def test_linux(self, mock_listdir):
        config["system"]["platform"] = "linux"
        mock_listdir.return_value = ["sda", "sdb", "loop0", "sr0", "md0"]
        from webui.system import list_disks
        self.assertEqual(list_disks(), ["sda", "sdb"])


class TestNetworkInterfaces(unittest.TestCase):
    @mock.patch("webui.system._run")
    def test_openbsd(self, mock_run):
        config["system"]["platform"] = "openbsd"
        mock_run.return_value = [
            "em0: flags=8843<UP,BROADCAST,RUNNING>",
            "lo0: flags=8049<UP,LOOPBACK>",
            "enc0: flags=...",
        ]
        from webui.system import _list_interfaces
        self.assertEqual(_list_interfaces(), ["em0"])

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data=
        "Inter-|   Receive\n"
        "  eth0: bytes  packets\n"
        "    lo: bytes  packets\n")
    def test_linux(self, mock_open):
        config["system"]["platform"] = "linux"
        from webui.system import _list_interfaces
        self.assertEqual(_list_interfaces(), ["eth0"])


class TestNetworkStats(unittest.TestCase):
    def _make_netstat_output(self):
        return [
            "Name   Mtu   Network       Address              Ipkts Ierrs Ibytes    Opkts Oerrs Obytes",
            "em0   1500  <Link>        xx:xx:xx:xx:xx:xx    1000   0     1000000   2000  0     2000000",
            "lo0   16384 <Link>        yy:yy:yy:yy:yy:yy    10     0     500       20    0     1000",
        ]

    @mock.patch("webui.system._run")
    def test_openbsd_all_interfaces(self, mock_run):
        config["system"]["platform"] = "openbsd"
        mock_run.return_value = self._make_netstat_output()
        from webui.system import _get_network_stats
        result = _get_network_stats()
        self.assertEqual(result["rx_bytes"], 1000000)
        self.assertEqual(result["tx_bytes"], 2000000)

    @mock.patch("webui.system._run")
    def test_openbsd_with_filter(self, mock_run):
        config["system"]["platform"] = "openbsd"
        mock_run.return_value = self._make_netstat_output()
        from webui.system import _get_network_stats
        result = _get_network_stats("em0")
        self.assertEqual(result["rx_bytes"], 1000000)
        self.assertEqual(result["tx_bytes"], 2000000)

    @mock.patch("webui.system._run")
    def test_openbsd_filter_no_match(self, mock_run):
        config["system"]["platform"] = "openbsd"
        mock_run.return_value = self._make_netstat_output()
        from webui.system import _get_network_stats
        result = _get_network_stats("nonexistent")
        self.assertEqual(result["rx_bytes"], 0)
        self.assertEqual(result["tx_bytes"], 0)

    @mock.patch("webui.system._run")
    def test_openbsd_ibytes_obytes_columns(self, mock_run):
        config["system"]["platform"] = "openbsd"
        mock_run.return_value = [
            "Name   Mtu   Network       Address              Ipkts Ierrs Ibytes    Opkts Oerrs Obytes",
            "em0   1500  <Link>        xx:xx:xx:xx:xx:xx    1000   0     1000000   2000  0     2000000",
        ]
        from webui.system import _get_network_stats
        result = _get_network_stats()
        self.assertEqual(result["rx_bytes"], 1000000)
        self.assertEqual(result["tx_bytes"], 2000000)

    @mock.patch("webui.system._run", return_value=[])
    def test_openbsd_empty_output(self, mock_run):
        config["system"]["platform"] = "openbsd"
        from webui.system import _get_network_stats
        result = _get_network_stats()
        self.assertEqual(result["rx_bytes"], 0)
        self.assertEqual(result["tx_bytes"], 0)

    def _linux_netdev_content(self):
        return (
            "Inter-|   Receive\n"
            " eth0: 1000000 2000 0 0 0 0 0 0 2000000 1000 0\n"
            "   lo: 500 10 0 0 0 0 0 0 100 5 0\n"
        )

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    def test_linux(self, mock_open):
        config["system"]["platform"] = "linux"
        mock_open.return_value.read.return_value = self._linux_netdev_content()
        from webui.system import _get_network_stats
        result = _get_network_stats()
        self.assertEqual(result["rx_bytes"], 1000000)
        self.assertEqual(result["tx_bytes"], 2000000)

    def _linux_netdev_content_two(self):
        return (
            "Inter-|   Receive\n"
            " eth0: 1000000 2000 0 0 0 0 0 0 2000000 1000 0\n"
            " eth1: 500 10 0 0 0 0 0 0 100 5 0\n"
        )

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    def test_linux_with_filter(self, mock_open):
        config["system"]["platform"] = "linux"
        mock_open.return_value.read.return_value = self._linux_netdev_content_two()
        from webui.system import _get_network_stats
        result = _get_network_stats("eth1")
        self.assertEqual(result["rx_bytes"], 500)
        self.assertEqual(result["tx_bytes"], 100)

    @mock.patch("builtins.open", side_effect=OSError)
    def test_linux_no_proc_net(self, mock_open):
        config["system"]["platform"] = "linux"
        from webui.system import _get_network_stats
        result = _get_network_stats()
        self.assertEqual(result["rx_bytes"], 0)
        self.assertEqual(result["tx_bytes"], 0)


class TestGetSystemInfo(unittest.TestCase):
    @mock.patch("webui.system._run")
    def test_openbsd(self, mock_run):
        config["system"]["platform"] = "openbsd"
        mock_run.return_value = ["myhost"]
        from webui.system import get_system_info
        info = get_system_info()
        self.assertIn("hostname", info)
        self.assertIn("ostype", info)

    @mock.patch("webui.system._run")
    def test_linux(self, mock_run):
        config["system"]["platform"] = "linux"
        mock_run.return_value = ["myhost"]
        from webui.system import get_system_info
        info = get_system_info()
        self.assertIn("hostname", info)


if __name__ == "__main__":
    unittest.main()
