#!/usr/bin/env python
# coding: utf-8


import sys
import os
import logging as log
import threading
import re
import time
import datetime
import pandas as pd
import numpy as np
import csv


class MemoryProfileThread(threading.Thread):
    MonitorItems = [
        "VmPeak", "VmSize", "VmLck", "VmPin", "VmHWM", "VmRSS",
        "VmData", "VmStk", "VmExe", "VmLib", "VmPTE", "VmSwap",
    ]

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
        target_pids.remove(os.getpid())

        if len(target_pids) == 0:
            raise RuntimeError("Not found target process")

        elif len(target_pids) >= 2:
            spids = " ".join([ str(t) for t in target_pids ])
            raise RuntimeError("Duplicate process: %s" % spids)

        return int(target_pids[0])

    def __init__(self, pid=-1, procname=None, output_path=None, interval=1):
        super(MemoryProfileThread, self).__init__()

        self.daemon = True
        self.interval = interval

        if pid == -1 and procname == None:
            raise RuntimeError("Illegal pid or procname")

        elif pid == -1 and procname != None:
            self.pid = MemoryProfileThread.findPid(procname)

        elif pid != -1:
            self.pid = int(pid)

        if not output_path:
            self.output_path = "./mprof_%s_%s.csv" % (
                procname, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

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

        print "%d %6s %d" % (unixtime, label, value)

        return {
            "time": unixtime,
            "label": label,
            "value": value,
        }

    def getMonitorItems(self):
        find_items = []
        unixtime = int(time.mktime(datetime.datetime.now().timetuple()))

        with open("/proc/%d/status" % self.pid, "r") as f:
            lines = f.readlines()
            for line in lines:
                for mi in MemoryProfileThread.MonitorItems:
                    if line.find(mi) == 0:
                        find_items.append(self.formatLine(line, unixtime))

        return find_items

    def outputData(self, writer, data):
        for item in data:
            writer.writerow([ item["time"], item["label"], item["value"] ])

    def run(self):
        with open(self.output_path, "w") as f:
            writer = csv.writer(f, lineterminator="\n")

            while True:
                data = self.getMonitorItems()
                self.outputData(writer, data)

                time.sleep(self.interval)


def main():
    procname = sys.argv[1]

    t = MemoryProfileThread(procname=procname)
    t.start()

    while True:
        t.join(1)


if __name__ == "__main__":
    log.basicConfig(
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%Y/%m/%d %H:%M:%S",
        level=log.DEBUG)

    main()


