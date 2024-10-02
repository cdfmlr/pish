#!/usr/bin/env python3
import argparse
import logging
import os
import subprocess
import tempfile
from functools import partial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--image", "--root", required=True,
                        help="rootfs directory")
    parser.add_argument("-c", "--command", required=True,
                        help="command to run in container")
    parser.add_argument("-n", "--name", required=False,
                        default=random_name(),
                        help="container id, default is random")
    parser.add_argument("--network", required=False, default="pishbridge",
                        help="a name for the network bridge: Default is `pishbridge`.")
    parser.add_argument("--ip", required=False, default="",
                        help="an ip address for the container: None for no ip. Requires --network.")
    parser.add_argument("--resource", action="append", required=False, default=[],
                        help="resource to limit in `controller.key=value`. This option can be added multiple times.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="verbose mode")

    opts = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.DEBUG if opts.verbose else logging.INFO
    )

    run(opts)


def run(opts):
    with OverlayFS(opts.image) as fs, \
            Cgroup("pish-" + opts.name) as cg, \
            Network(opts.network) as net:
        try:
            root = fs.merged

            ns = net.create_ns(opts.name)
            unshare_net_opt = "--net=/var/run/netns/" + ns

            cmd = subprocess.Popen(["unshare", "-impuf", unshare_net_opt,
                                    "python3", "container.py",
                                    "--root", root, "-c", opts.command])

            logging.info("run: container pid: %d" % cmd.pid)

            for r in opts.resource:
                cg.set(*r.split("="))  # cg.set("memory.limit_in_bytes", "100m")
            cg.apply(cmd.pid)

            net.add_to_network(opts.name, opts.ip)

            cmd.wait()
        except Exception as err:
            logging.error("run: setup and run container error: %s" % err)

        logging.info("run: container exited")


def random_name():
    return "pish" + str(os.getpid()) + str(os.urandom(4).hex())


class OverlayFS:
    def __init__(self, image_path: str):
        self._tmp_dir = tempfile.TemporaryDirectory(None, "pish")
        # base_path is the path to _tmp_dir
        self.base_path = self._tmp_dir.__enter__()
        self.image_path = image_path

        self.lower = None
        self.upper = None
        self.work = None
        self.merged = None

    def __enter__(self):
        base = self.base_path
        image = self.image_path

        lower = os.path.join(base, "lower")
        if os.path.isdir(image):
            logging.info("overlayfs: using directory %s as lower" % image)
            lower = image
        else:
            logging.info("overlayfs: extracting image %s to %s" %
                         (image, lower))
            os.makedirs(lower)
            subprocess.run(["tar", "-xf", image, "-C", lower], check=True)

        upper = os.path.join(base, "upper")
        os.makedirs(upper)

        work = os.path.join(base, "work")
        os.makedirs(work)

        merged = os.path.join(base, "merged")
        os.makedirs(merged)

        # mount -t overlay overlay -o lowerdir=/lower,upperdir=/upper,workdir=/work /merged
        subprocess.run(["mount", "-t", "overlay", "overlay",
                        "-o", "lowerdir=%s,upperdir=%s,workdir=%s" % (
                            lower, upper, work),
                        merged], check=True)

        logging.info("overlayfs: mounted at %s" % merged)

        self.lower = lower
        self.upper = upper
        self.work = work
        self.merged = merged

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logging.info("overlayfs: unmounting %s" % self.merged)
        subprocess.run(["umount", self.merged], check=True)

        logging.info("overlayfs: remove tmp dir %s" % self.base_path)
        self._tmp_dir.__exit__(exc_type, exc_value, traceback)


class Network:
    """Network is a bridge"""

    def __init__(self, name: str) -> None:
        self.bridge = name

        self.netns = set()
        self.vnets = set()

        if not self._exists():
            self._create()

    def _exists(self) -> bool:
        return os.path.exists("/sys/class/net/" + self.bridge)

    def _create(self):
        logging.info("network: creating bridge %s" % self.bridge)

        subprocess.run(["ip", "link", "add", self.bridge,
                       "type", "bridge"], check=True)
        subprocess.run(["ip", "link", "set", self.bridge, "up"], check=True)

    def delete(self):
        # just let it fail, i don't care
        try_run = partial(subprocess.run, check=False)
        for ns in self.netns:
            logging.info("network: deleting netns %s" % ns)
            try_run(["ip", "netns", "exec", ns, "ip",
                    "link", "set", "dev", "eth0", "down"])
            try_run(["ip", "netns", "exec", ns, "ip", "link", "delete", "eth0"])
            try_run(["ip", "netns", "delete", ns])
            # first: Device or resource busy
        logging.info("don't worrying about the \"Device or resource busy\" error above. This is expected.")
        for vnet in self.vnets:
            logging.info("network: deleting vnet %s" % vnet)
            try_run(["ip", "link", "delete", vnet])
        logging.info("don't worrying about the \"Cannot find device\" error above. This is expected.")
        for ns in self.netns:
            logging.info("network: deleting netns %s" % ns)
            try_run(["ip", "netns", "delete", ns])
            # second: success delete, reason unknown

        logging.info("network: deleting bridge %s" % self.bridge)
        res = try_run(["ip", "link", "delete", self.bridge, "type", "bridge"])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.delete()

    def create_ns(self, containerID: str) -> str:
        ns = "pishnetns-" + containerID

        logging.info("network: creating netns %s" % ns)
        subprocess.run(["ip", "netns", "add", ns], check=True)

        self.netns.add(ns)
        return ns

    def add_to_network(self, containerID: str, ip: str):
        br = self.bridge

        veth_container = "pishveth-" + containerID + "0"
        veth_host = "pishveth-" + containerID + "1"

        ns = "pishnetns-" + containerID

        logging.info("network: adding container %s to network %s (ip %s)" % (
            containerID, br, ip))

        subprocess.run(["ip", "link", "add", veth_container,
                       "type", "veth", "peer", "name", veth_host], check=True)
        logging.info("network: created veth pair %s <=> %s" %
                     (veth_container, veth_host))

        # self.vnets.add(veth_container) # peer: one is enough
        self.vnets.add(veth_host)

        # host side
        subprocess.run(["ip", "link", "set", veth_host,
                       "master", br], check=True)
        subprocess.run(["ip", "link", "set", veth_host, "up"], check=True)

        # container side

        subprocess.run(
            ["ip", "link", "set", veth_container, "netns", ns], check=True)
        subprocess.run(["ip", "netns", "exec", ns, "ip", "link",
                       "set", veth_container, "name", "eth0"], check=True)
        subprocess.run(["ip", "netns", "exec", ns, "ip", "addr",
                       "add", ip, "dev", "eth0"], check=True)
        subprocess.run(["ip", "netns", "exec", ns, "ip",
                       "link", "set", "eth0", "up"], check=True)

        # TODO: set the route


class CgroupV1:
    def __init__(self, group_name: str, base_path="/sys/fs/cgroup") -> None:
        self.group = group_name
        self.base = base_path

        self.controllers = set()

        self.set("cpuset.cpus", "0")
        self.set("cpuset.mems", "0")

    def set(self, key: str, value: str):
        controller, key = key.split(".")
        self.controllers.add(controller)

        d = os.path.join(self.base, controller, self.group)
        if not os.path.exists(d):
            os.makedirs(d)

        f = os.path.join(d, controller + "." + key)
        logging.info("cgroup: set %s > %s" % (value, f))
        with open(f, "w") as f:
            f.write(str(value))

    def get(self, key: str) -> str:
        controller, key = key.split(".")

        f = os.path.join(self.base, controller, self.group,
                         controller + "." + key)
        with open(f, "r") as f:
            return f.read()

    def apply(self, pid: int):
        for controller in self.controllers:

            d = os.path.join(self.base, controller, self.group)
            if not os.path.exists(d):  # never happens
                os.makedirs(d)

            f = os.path.join(d, "tasks")
            logging.info("cgroup: apply %s > %s" % (pid, f))
            with open(f, "a") as f:
                f.write(str(pid))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # self.__del__()
        pass

    def __del__(self):
        logging.info("cgroup: deleting %s" % self.group)
        subprocess.run(["cgdelete", ",".join(
            self.controllers) + ":" + self.group])


class CgroupV2:
    def __init__(self, group_name: str, base_path="/sys/fs/cgroup") -> None:
        self.group = group_name
        self.base = base_path

        self.set("cgroup.subtree_control", "+cpu +memory")

        self.set("cpuset.cpus", "0")
        self.set("cpuset.mems", "0")

        # https://unix.stackexchange.com/a/713343
        self.base = os.path.join(self.base, self.group)

    def set(self, key: str, value: str):
        d = os.path.join(self.base, self.group)
        if not os.path.exists(d):
            os.makedirs(d)

        f = os.path.join(d, key)
        logging.info("cgroup: set %s > %s" % (value, f))
        with open(f, "w") as f:
            f.write(str(value))

    def get(self, key: str) -> str:
        f = os.path.join(self.base, self.group, key)
        with open(f, "r") as f:
            return f.read()

    def apply(self, pid: int):
        d = os.path.join(self.base, self.group)
        if not os.path.exists(d):  # never happens
            os.makedirs(d)

        f = os.path.join(d, "cgroup.procs")
        logging.info("cgroup: apply %s > %s" % (pid, f))
        with open(f, "a") as f:
            f.write(str(pid))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # self.__del__()
        pass

    def __del__(self):
        logging.info("cgroup: deleting %s" % self.group)
        subprocess.run(["rmdir", os.path.join(self.base, self.group)])
        subprocess.run(["rmdir", self.base])


Cgroup = CgroupV2


if __name__ == "__main__":
    try:
        main()
    finally:
        logging.shutdown()
