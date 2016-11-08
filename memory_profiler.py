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
from fabric.api import run, execute, env
from fabric.contrib import project


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

            except IOError: # proc has already terminated
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

    def __init__(self, lock, pid=-1, procname=None, output_path=None, interval=1):
        super(MemoryProfileThread, self).__init__()

        self.daemon = True
        self.lock = lock
        self.interval = interval

        self.setPID(pid, procname)
        self.setOutputPath(output_path)

    def setPID(self, pid, procname):
        if pid == -1 and procname == None:
            raise RuntimeError("No pid or procname found")

        elif pid == -1 and procname != None:
            self.procname = procname
            self.tpid = MemoryProfileThread.findPid(procname)

        elif pid != -1:
            self.tpid = int(pid)

        if not self.procname:
            self.procname = "None"

    def setOutputPath(self, output_path):
        if not output_path:
            self.output_path = "./mprof_data/mprof_%s_%s.csv" % (
                self.procname, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

            self.output_dir = os.path.dirname(self.output_path)
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)

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

    def outputData(self, writer, data):
        for item in data:
            with self.lock:
                if isinstance(item["value"], int):
                    fmt = "%d %s %d"
                else:
                    fmt = "%d %s \"%s\""
                print fmt % (item["time"], item["label"], item["value"])

            writer.writerow([ item["time"], item["label"], item["value"] ])

    def run(self):
        with open(self.output_path, "w") as f:
            writer = csv.writer(f, lineterminator="\n")

            while True:
                unixtime = int(time.mktime(datetime.datetime.now().timetuple()))


                data_ident = [{
                    "time": unixtime,
                    "label": "PID",
                    "value": self.tpid
                }, {
                    "time": unixtime,
                    "label": "ProcName",
                    "value": self.procname,
                }]

                data_system = self.getMonitorItems(
                    unixtime=unixtime,
                    procfile="/proc/meminfo",
                    monitor_items=MemoryProfileThread.MonitorSystemItems)

                data_proc = self.getMonitorItems(
                    unixtime=unixtime,
                    procfile="/proc/%d/status" % self.tpid,
                    monitor_items=MemoryProfileThread.MonitorProcItems)

                self.outputData(writer, data_ident + data_system + data_proc)

                with self.lock:
                    print

                time.sleep(self.interval)


def logging(procname, pid):
    lock = mp.Lock()
    t = MemoryProfileThread(lock, procname=procname, pid=pid)
    t.start()

    while True:
        t.join(1)


def remoteTask():
    log.info("remoteTask")
    #run("python ~/linux-memory-profile/memory_profiler.py mysqld")


def connect(procname, pid, remote_host):
    env.use_ssh_config = True
    env.hosts = [ remote_host ]
    env.host_string = remote_host

    project.rsync_project(remote_dir="~", exclude=["*.pyc", "*~", "*.swp", ".git*"])
    #execute(remoteTask)

    log.info("done")


def getarg():
    import argparse
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("-p", "--procname", type=str, default=None, help="process name")
    parser.add_argument("-P", "--pid", type=int, default=-1, help="process id")
    parser.add_argument("-r", "--enable-remote", action="store_true", help="enable remote")
    parser.add_argument("-h", "--remote-host", type=str, help="remote host")
    parser.add_argument("--help", action="help")

    args = parser.parse_args()
    return args


def main():
    args = getarg()

    log.info("start logging \"%s (%d)\"" % (args.procname, args.pid))

    if not args.enable_remote:
        logging(args.procname, args.pid)

    else:
        log.info("connecting remote host \"%s\"" % args.remote_host)
        connect(args.procname, args.pid, args.remote_host)


if __name__ == "__main__":
    log.basicConfig(
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%Y/%m/%d %H:%M:%S",
        level=log.DEBUG)

    main()


