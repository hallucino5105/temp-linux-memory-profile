#!/usr/bin/env python
# coding: utf-8


import sys
import os
import logging as log
import threading
import multiprocessing as mp
import re
import time
import datetime
import csv
import socket
from collections import deque
from fabric.api import run, local, execute, env
from fabric.contrib import project


class Stack():
    def __init__(self, iterable=[], maxlen=0):
        self.maxlen = maxlen
        self.container = deque(iterable, maxlen=maxlen)
        self.penultimate_storage = None

    def __str__(self):
        ret = "["
        size = self.size()

        for i in xrange(size):
            ret += repr(self.container[i])
            if i != size - 1:
                ret += ","

        ret += "]"

        return ret

    def __repr__(self):
        return self.__str__()

    def push(self, value):
        self.penultimate_storage = self.last()
        self.container.append(value)

    def pop(self):
        try:
            return self.container.pop()
        except IndexError:
            return None

    def clear(self):
        self.container.clear()

    def size(self):
        return len(self.container)

    def get(self, index):
        try:
            return self.container[index]
        except IndexError:
            return None

    def first(self):
        return self.get(0)

    def last(self):
        return self.get(-1)

    def penultimate(self):
        if self.penultimate_storage:
            return self.penultimate_storage
        else:
            return self.get(-2)


# 結果を10件くらい保存しておく
class MemoryProfileDataContainer():
    def __init__(self, data_dir, data_filename="", to_csv=False):
        self.data_dir = data_dir
        self.data_filename = data_filename
        self.to_csv = to_csv

        self.container = Stack(maxlen=10)

        self.setDataPath()

    def __repr__(self):
        if self.container.size() == 0:
            return ""

        def z(a, b):
            if len(a) >= len(b):
                return a
            else:
                return b

        ret = ""
        last_items = self.container.last()
        label_max_size = len(reduce(
            lambda a, b: a if len(a) >= len(b) else b,
            [ item["label"] for item in last_items ]))

        for item in last_items:
            if isinstance(item["value"], int):
                fmt = "%s %-" + str(label_max_size) + "s %d\n"
            else:
                fmt = "%s %-" + str(label_max_size) + "s %s\n"

            ret += fmt % (
                datetime.datetime.fromtimestamp(item["time"]).isoformat(),
                item["label"],
                item["value"])

        return ret

    def __str__(self):
        return self.__repr__()

    def setDataPath(self):
        if not self.data_filename:
            if not self.to_csv:
                ext = "json"
            else:
                ext = "csv"

            self.data_filename = "mprof_%s.%s" % (
                datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
                ext)

        self.data_path = "%s/%s" % (self.data_dir, self.data_filename)

        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def push(self, data):
        self.container.push(data)

    def diff(self, prevdata):
        pass

    def serialize(self):
        pass

    #def outputData(self, fs, writer, data):
    #    with open(self.data_path, "w") as fs:
    #        writer = csv.writer(fs, lineterminator="\n")

    #    for item in data:
    #        with self.lock:
    #            if isinstance(item["value"], int):
    #                fmt = "%d %s %d\n"
    #            else:
    #                fmt = "%d %s %s\n"
    #            sys.stdout.write(fmt % (item["time"], item["label"], item["value"]))

    #        writer.writerow([ item["time"], item["label"], item["value"] ])
    #        fs.flush()


class MemoryProfileThread(mp.Process):
    MonitorSystemItems = (
        "MemTotal", "MemFree", "MemAvailable", "SwapTotal", "SwapFree",
    )

    MonitorProcItems = (
        "VmPeak", "VmSize", "VmLck", "VmPin", "VmHWM",
        "VmRSS", "VmData", "VmStk", "VmExe", "VmLib",
        "VmPTE", "VmSwap",
    )

    @staticmethod
    def findPid(procname):
        pattern = re.compile(procname)
        target_pids = []
        current_pids = [ pid for pid in os.listdir("/proc") if pid.isdigit() ]

        for pid in current_pids:
            try:
                cmdline_path = os.path.join("/proc", pid, "cmdline")
                cmdline = open(cmdline_path, "rb").read()

                if pattern.search(cmdline):
                    target_pids.append(int(pid))

            except IOError:
                # proc has already terminated
                continue

        # to remove pid myself
        try:
            mypid = os.getpid()
            target_pids.remove(mypid)
        except ValueError:
            pass

        if len(target_pids) == 0:
            raise RuntimeError("Not found target process \"%s\"" % procname)

        elif len(target_pids) >= 2:
            spids = " ".join([ str(t) for t in target_pids ])
            raise RuntimeError("Duplicate process: %s" % spids)

        return int(target_pids[0])

    @staticmethod
    def findProcname(pid):
        with open("/proc/%d/cmdline" % pid) as f:
            procname = f.read().strip().split("\0")[0]
            return procname

    def __init__(self, lock, pid=-1, procname=None, data_dir=None, data_filename=None, to_csv=False, interval=1):
        super(MemoryProfileThread, self).__init__()

        self.daemon = True

        self.lock = lock
        self.interval = interval
        self.data_dir = data_dir
        self.data_filename = data_filename

        self.setPID(pid, procname)
        self.setHostname()

        self.mpdc = MemoryProfileDataContainer(self.data_dir, self.data_filename, to_csv)

    def setPID(self, pid, procname):
        if pid == -1 and procname == None:
            raise RuntimeError("No pid or procname found")

        elif pid == -1 and procname != None:
            self.procname = procname
            self.tpid = MemoryProfileThread.findPid(procname)

        elif pid != -1:
            self.tpid = int(pid)

        if not hasattr(self, "procname") or not self.procname:
            self.procname = MemoryProfileThread.findProcname(self.tpid)

    def setHostname(self):
        self.host = socket.gethostname()

    def formatLine(self, line, unixtime):
        _line = line \
            .strip() \
            .replace("\t", "") \
            .replace(" ", "")

        label, value_temp1 = _line.split(":")
        value_temp2, unit = value_temp1[:-2], value_temp1[-2:]
        value = 0

        if unit == "kB":
            value = int(value_temp2) * 1024
        else:
            value = int(value_temp1)

        return {
            "time": unixtime,
            "label": label,
            "value": value,
        }

    def getMonitorItems(self, unixtime, procfile, monitor_items):
        find_items = []

        with open(procfile, "r") as f:
            lines = f.readlines()
            for line in lines:
                for mi in monitor_items:
                    if line.find(mi) == 0:
                        find_items.append(self.formatLine(line, unixtime))

        return find_items

    def getIdentItems(self, unixtime):
        return [{
                "time": unixtime,
                "label": "PID",
                "value": self.tpid
            }, {
                "time": unixtime,
                "label": "ProcName",
                "value": self.procname,
            }, {
                "time": unixtime,
                "label": "Hostname",
                "value": self.host,
            }]

    def _run(self):
        while True:
            unixtime = int(time.mktime(datetime.datetime.now().timetuple()))

            data_ident = self.getIdentItems(unixtime)

            data_system = self.getMonitorItems(
                unixtime=unixtime,
                procfile="/proc/meminfo",
                monitor_items=MemoryProfileThread.MonitorSystemItems)

            data_proc = self.getMonitorItems(
                unixtime=unixtime,
                procfile="/proc/%d/status" % self.tpid,
                monitor_items=MemoryProfileThread.MonitorProcItems)

            data_all = data_ident + data_system + data_proc

            self.mpdc.push(data_all)
            self.mpdc.serialize()

            with self.lock:
                sys.stdout.write(str(self.mpdc) + "\n")

            time.sleep(self.interval)

    def run(self):
        try:
            self._run()
        except KeyboardInterrupt:
            return


def logging(procname, pid, data_dir, data_filename, to_csv):
    lock = mp.Lock()

    t = MemoryProfileThread(
        lock,
        procname=procname,
        pid=pid,
        data_dir=data_dir,
        data_filename=data_filename,
        to_csv=to_csv)

    t.start()

    while True:
        try:
            t.join(1)
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt")
            t.terminate()
            break


def remoteTask(remote_prof_cmd, remote_close_cmd):
    log.info("remoteTask")

    try:
        run(remote_prof_cmd)
    finally:
        local(remote_close_cmd)


def remote(
        procname,
        pid,
        data_dir,
        data_filename,
        remote_host,
        remote_dir,
        remote_user="",
        remote_password="",
        to_csv=False
):
    env.use_ssh_config = True
    env.hosts = [ remote_host ]
    env.host_string = remote_host
    env.user = remote_user
    env_password = remote_password

    cwd, project_exec = os.path.split(os.path.abspath(sys.argv[0]))

    to_csv_arg = ""
    if to_csv:
        to_csv_arg = "-C"

    remote_prof_cmd = "python %s/%s/%s -c %s -p %d -d %s %s" % (
        remote_dir,
        cwd.split("/")[-1],
        project_exec,
        procname,
        pid,
        data_dir,
        to_csv_arg)

    remote_close_cmd = "mkdir -p %s && rsync -av %s:%s/%s %s" % (
        data_dir,
        remote_host,
        data_dir,
        data_filename,
        data_dir)

    project.rsync_project(
        local_dir=cwd,
        remote_dir=remote_dir,
        exclude=[ "*.pyc", "*~", "*.swp", ".git*" ])

    execute(remoteTask, remote_prof_cmd, remote_close_cmd)

    log.info("done")


def getarg():
    import argparse
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("-c", "--procname", type=str, default=None, help="process name")
    parser.add_argument("-p", "--pid", type=int, default=-1, help="process id")
    parser.add_argument("-d", "--data-dir", type=str, default="mprof_data", help="data dir")
    parser.add_argument("-r", "--enable-remote", action="store_true", help="enable remote")
    parser.add_argument("-h", "--remote-host", type=str, help="remote host")
    parser.add_argument("-t", "--remote-dir", type=str, default="~", help="remote dir")
    parser.add_argument("-U", "--remote-user", type=str, help="remote user")
    parser.add_argument("-P", "--remote-password", type=str, help="remote password")
    parser.add_argument("-C", "--to-csv", action="store_true", help="output csv format")
    parser.add_argument("--help", action="help")

    args = parser.parse_args()
    return args


def main():
    args = getarg()

    log.info("start logging \"%s (%d)\"" % (args.procname, args.pid))

    data_filename = "mprof_%s.csv" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    if not args.enable_remote:
        logging(args.procname, args.pid, args.data_dir, data_filename, args.to_csv)

    else:
        log.info("connecting remote host \"%s\"" % args.remote_host)
        remote(
            args.procname,
            args.pid,
            args.data_dir,
            data_filename,
            args.remote_host,
            args.remote_dir,
            args.remote_user,
            args.remote_password,
            args.to_csv)


if __name__ == "__main__":
    log.basicConfig(
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%Y/%m/%d %H:%M:%S",
        level=log.DEBUG)

    main()


