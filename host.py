#!/usr/bin/env python3
import argparse
import logging
import os
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--image", "--root", required=True,
                        help="rootfs directory")
    parser.add_argument("-c", "--command", required=True,
                        help="command to run in container")
    parser.add_argument("-n", "--name", required=False,
                        default=random_name(),
                        help="container id, default is random")
    parser.add_argument("--network", required=False, default="None", help="a name for the network bridge: None for no network. Requires --ip.")
    parser.add_argument("--ip", required=False, default="", help="an ip address for the container: None for no ip. Requires --network.")
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
    net = None
    if opts.network and opts.network != "None" and opts.ip:
        net = Network(opts.network)

    with tempfile.TemporaryDirectory("-" + opts.name, "pish-") as tmp_dir:
        root = overlayfs(tmp_dir, opts.image)
        
        unshare_net_opt = "--net"
        if net:
            ns = net.create_ns(opts.name)
            unshare_net_opt += "=/var/run/netns/" + ns
        
        cmd = subprocess.Popen(["unshare", "-impuf", unshare_net_opt, 
                                "python3", "container.py",
                                "--root", root, "-c", opts.command])

        logging.info("container pid: %d" % cmd.pid)

        with Cgroup("pish-" + opts.name) as cg:
            for r in opts.resource:
                cg.set(*r.split("=")) # cg.set("memory.limit_in_bytes", "100m")
            cg.apply(cmd.pid)

            if net:
                net.add_to_network(opts.name, opts.ip)

            cmd.wait()

        logging.info("container exited")

        # unmount overlayfs before tmp_dir is removed
        subprocess.run(["umount", root], check=True)


def random_name():
    return "pish" + str(os.getpid()) + str(os.urandom(4).hex())


def overlayfs(base: str, image: str) -> str:
    lower = os.path.join(base, "lower")
    if os.path.isdir(image):
        logging.info("overlayfs: using directory %s as lower" % image)
        lower = image
    else:
        logging.info("overlayfs: extracting image %s to %s" % (image, lower))
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

    return merged

# Network is a bridge
# TODO: cleanup
class Network:
    def __init__(self, name: str) -> None:
        self.name = name

        if not self._exists():
            self._create()

    def _exists(self) -> bool:
        return os.path.exists("/sys/class/net/" + self.name)
    
    def _create(self):
        subprocess.run(["ip", "link", "add", self.name, "type", "bridge"], check=True)
        subprocess.run(["ip", "link", "set", self.name, "up"], check=True)

    def delete(self):
        subprocess.run(["ip", "link", "delete", self.name, "type", "bridge"], check=True)

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.delete()

    def create_ns(self, containerID: str) -> str:
        ns = "pishnetns-" + containerID
        subprocess.run(["ip", "netns", "add", ns], check=True)
        return ns

    def add_to_network(self, containerID: str, ip: str):
        br = self.name

        veth_container = "pishveth-" + containerID + "0"
        veth_host = "pishveth-" + containerID + "1"

        ns = "pishnetns-" + containerID

        logging.info("network: adding container %s to network %s (ip %s)" % (containerID, br, ip))

        subprocess.run(["ip", "link", "add", veth_container, "type", "veth", "peer", "name", veth_host], check=True)
        
        # host side
        subprocess.run(["ip", "link", "set", veth_host, "master", br], check=True)
        subprocess.run(["ip", "link", "set", veth_host, "up"], check=True)
        
        # container side
        # subprocess.run(["ip", "netns", "add", ns], check=True)

        subprocess.run(["ip", "link", "set", veth_container, "netns", ns], check=True)
        subprocess.run(["ip", "netns", "exec", ns, "ip", "link", "set", veth_container, "name", "eth0"], check=True)
        subprocess.run(["ip", "netns", "exec", ns, "ip", "addr", "add", ip, "dev", "eth0"], check=True)
        subprocess.run(["ip", "netns", "exec", ns, "ip", "link", "set", "eth0", "up"], check=True)

        # TODO: set the route
        

def __netns_memo(netns_name: str, ip: str):
    """
    # 1. 创建一个网桥

    sudo ip link add br700 type bridge
    sudo ip link set br700 up

    # 2. 创建一个 veth pair: 连接 ns 和 host 的虚拟网线

    # 700 给 ns 用，701 给 host 用
    sudo ip link add veth700 type veth peer name veth701

    # 3. 设置 ns 中的网络设备，分配 IP
    
    sudo ip netns add netns70

    sudo ip link set veth700 netns netns70
    sudo ip netns exec netns70 ip link set dev veth700 name eth0
    sudo ip netns exec netns70 ip addr add 10.0.0.2/24 dev eth0
    sudo ip netns exec netns70 ip link set eth0 up

    sudo ip netns exec netns70 ifconfig # 已经分配到网卡和 IP 了

    # 4. host 作为网桥的一端，连接到 veth701

    sudo ip link set veth701 master br700
    sudo ip link set veth701 up

    # 5. another container

    sudo ip netns add netns71

    sudo ip link set veth710 netns netns71
    sudo ip netns exec netns71 ip link set dev veth710 name eth0
    sudo ip netns exec netns71 ip addr add 10.0.0.3/24 dev eth0
    sudo ip netns exec netns71 ip link set eth0 up

    sudo ip netns exec netns71 ifconfig

    sudo ip link set veth711 master br700
    sudo ip link set veth711 up

    # 两个容器互相连通了：

    sudo ip netns exec netns71 ping 10.0.0.2
    sudo ip netns exec netns70 ping 10.0.0.3
    """
    pass

class Cgroup:
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
        logging.info("cgroup set: %s > %s" % (value, f))
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
            logging.info("cgroup apply: %s > %s" % (pid, f))
            with open(f, "a") as f:
                f.write(str(pid))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # self.__del__()
        pass

    def __del__(self):
        subprocess.run(["cgdelete", ",".join(
            self.controllers) + ":" + self.group])
        logging.info("cgroup deleted: %s" % self.group)


if __name__ == "__main__":
    try:
        main()
    finally:
        logging.shutdown()
