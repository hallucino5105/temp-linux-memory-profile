#!/usr/bin/env python
# coding: utf-8


import sys
import os
import logging as log
import threading
import re
import time


class MemoryProfileThread(threading.Thread):
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

    def __init__(self, pid=-1, procname=None, interval=1):
        super(MemoryProfileThread, self).__init__()

        self.daemon = True
        self.interval = interval

        if pid == -1 and procname == None:
            raise RuntimeError("Illegal pid or procname")

        elif pid == -1 and procname != None:
            self.pid = MemoryProfileThread.findPid(procname)

        elif pid != -1:
            self.pid = int(pid)

    def run(self):
        while True:
            with open("/proc/%/stats", "r") as f:
                print f.readlines()

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


