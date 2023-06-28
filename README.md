# pish: PISH Is a Simplified Hind

Pish is yet another container runtime implementation..

Pish is a rewrite of [cdfmlr/hind](https://github.com/cdfmlr/hind), focusing on simplicity and readability.

```sh
git clone github.com/cdfmlr/pish
cd pish
sudo python3 host.py --root /home/c/docker-export/alpine.tar -c "/bin/sh" -n "test1" --network testpishnet --ip 10.0.4.6/24
```

Output:

```sh
2023-06-28 14:28:39,048 [INFO] overlayfs: extracting image /home/c/docker-export/alpine.tar to /tmp/pish8s521m6y/lower
2023-06-28 14:28:39,078 [INFO] overlayfs: mounted at /tmp/pish8s521m6y/merged
2023-06-28 14:28:39,079 [INFO] cgroup: set 0 > /sys/fs/cgroup/cpuset/pish-test1/cpuset.cpus
2023-06-28 14:28:39,079 [INFO] cgroup: set 0 > /sys/fs/cgroup/cpuset/pish-test1/cpuset.mems
2023-06-28 14:28:39,079 [INFO] network: creating bridge testpishnet
2023-06-28 14:28:39,091 [INFO] network: creating netns pishnetns-test1
2023-06-28 14:28:39,109 [INFO] run: container pid: 9015
2023-06-28 14:28:39,111 [INFO] cgroup: apply 9015 > /sys/fs/cgroup/cpuset/pish-test1/tasks
2023-06-28 14:28:39,111 [INFO] network: adding container test1 to network testpishnet (ip 10.0.4.6/24)
2023-06-28 14:28:39,122 [INFO] network: created veth pair pishveth-test10 <=> pishveth-test11
2023-06-28 14:28:39,311 [INFO] container: pivot_root to /tmp/pish8s521m6y/merged
/ # ls
bin    etc    lib    mnt    proc   run    srv    tmp    var
dev    home   media  opt    root   sbin   sys    usr
/ # cat /etc/os-release
NAME="Alpine Linux"
ID=alpine
VERSION_ID=3.18.2
PRETTY_NAME="Alpine Linux v3.18"
HOME_URL="https://alpinelinux.org/"
BUG_REPORT_URL="https://gitlab.alpinelinux.org/alpine/aports/-/issues"
/ # ifconfig
eth0      Link encap:Ethernet  HWaddr 52:6E:EC:AB:17:9F
          inet addr:10.0.4.6  Bcast:0.0.0.0  Mask:255.255.255.0
          inet6 addr: fe80::506e:ecff:feab:179f/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:15 errors:0 dropped:0 overruns:0 frame:0
          TX packets:8 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:1262 (1.2 KiB)  TX bytes:656 (656.0 B)

/ # exit
2023-06-28 14:28:54,562 [INFO] run: container exited
2023-06-28 14:28:54,562 [INFO] network: deleting netns pishnetns-test1
Cannot remove namespace file "/var/run/netns/pishnetns-test1": Device or resource busy
2023-06-28 14:28:54,589 [INFO] network: deleting vnet pishveth-test11
Cannot find device "pishveth-test11"
2023-06-28 14:28:54,595 [INFO] network: deleting netns pishnetns-test1
2023-06-28 14:28:54,601 [INFO] network: deleting bridge testpishnet
2023-06-28 14:28:54,622 [INFO] overlayfs: unmounting /tmp/pish8s521m6y/merged
2023-06-28 14:28:54,666 [INFO] overlayfs: remove tmp dir /tmp/pish8s521m6y
2023-06-28 14:28:54,675 [INFO] cgroup: deleting pish-test1
```

## 实现

- 完全用 Python 标准库和系统自带的命令实现（由于一点不可抗因素还调了 C 库）
- 尽量保证代码可读性、易用性。

- cloc:

```
---------------------------------------------------------------
File                 blank        comment           code
---------------------------------------------------------------
./host.py               72             11            199
./container.py          23              8             46
---------------------------------------------------------------
SUM:                    95             19            245
---------------------------------------------------------------
```

- 环境：

```
Linux 4.19.0-15-amd64 #1 SMP Debian 4.19.177-1 (2021-03-03) x86_64 GNU/Linux
```

- 依赖:

```
python(1) 3.7, unshare(1), cgroup(8) v1, mount(8), umount(8), pivot_root(8), ip(8), LIBC(7)
```

### Namespace

Namespace 使容器与宿主机隔离。

#### 原理

> UNSHARE(1) - run program with some namespaces unshared from parent

```sh
$ unshare [options] [<program> [<argument>...]]

Options:
 -m, --mount[=<file>]      unshare mounts namespace
 -u, --uts[=<file>]        unshare UTS namespace (hostname etc)
 -i, --ipc[=<file>]        unshare System V IPC namespace
 -n, --net[=<file>]        unshare network namespace
 -p, --pid[=<file>]        unshare pid namespace
 -f, --fork                fork before launching <program>

 -h, --help                display this help
```

- see `man unshare`

#### 实现

```py
unshare_net_opt = "--net=/var/run/netns/" + net.create_ns(opts.name)
cmd = subprocess.Popen(["unshare", "-impuf", unshare_net_opt,
                        "python3", "container.py", ...])
```

网络由 ip netns 提前创建并管理，所以需要在 unshare 时指定 `--net=/var/run/netns/<netns-name>`。

cmd 启动了容器的 pid 1 进程。

### Cgroup

Cgroup 限制容器的资源使用。

#### 原理

```sh
# 创建 cgroup
$ mkdir /sys/fs/cgroup/cpuset/pish-test0
# 配置资源限制
$ echo 0 > /sys/fs/cgroup/cpuset/pish-test0/cpuset.cpus
# 将容器进程加入 cgroup
$ echo 19221 > /sys/fs/cgroup/cpuset/pish-test0/tasks
# 删除 cgroup
$ cgdelete cpuset:pish-test0
```

#### 实现

```py
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
        with open(f, "w") as f:
            f.write(str(value))

    def get(self, key: str) -> str:
        controller, key = key.split(".")

        f = os.path.join(self.base, controller, self.group, controller + "." + key)
        with open(f, "r") as f:
            return f.read()

    def apply(self, pid: int):
        for controller in self.controllers:
            f = os.path.join(self.base, controller, self.group, "tasks")
            with open(f, "a") as f:
                f.write(str(pid))

    def _delete(self):
        subprocess.run(["cgdelete", ",".join(self.controllers) + ":" + self.group])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._delete()
```

#### 调用

```py
with Cgroup("pish-test0") as cgroup:
    cgroup.set("cpuset.cpus", "0")
    cgroup.set("cpuset.mems", "0")
    cgroup.apply(pid)
# 退出 context: 自动删除 cgroup
```

### OverlayFS

OverlayFS 使容器可以使用镜像:

- 镜像层：只读
- 容器层：读写

容器生命结束后，容器层被删除。

#### 原理

> read this: https://wiki.archlinux.org/title/Overlay_filesystem

```sh
$ sudo mount -t overlay overlay -o lowerdir=/lower,upperdir=/upper,workdir=/work /merged
```

- lowerdir: 只读层
- upperdir: 读写层
- workdir: overlay 是用的临时目录
- merged: 合并后的目录: lowerdir + upperdir, 写入 merged 的数据会写入 upperdir

#### 实现

```py
class OverlayFS:
    def __init__(self, image_path: str):
        self._tmp_dir = tempfile.TemporaryDirectory(None, "pish")
        self.base_path = self._tmp_dir.__enter__() # base_path is the path to _tmp_dir

        self.image_path = image_path

    def __enter__(self):
        base, image = self.base_path, self.image_path

        lower = os.path.join(base, "lower")
        if os.path.isdir(image):
            lower = image
        else:
            os.makedirs(lower)
            subprocess.run(["tar", "-xf", image, "-C", lower])

        upper = os.path.join(base, "upper")
        os.makedirs(upper)
        ... # 类似，创建 work 和 merged 目录

        subprocess.run(["mount", "-t", "overlay", "overlay", "-o", "lowerdir=%s,upperdir=%s,workdir=%s" % (lower, upper, work), merged])

        self.lower, self.upper, self.work, self.merged = lower, upper, work, merged
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        subprocess.run(["umount", self.merged])
        self._tmp_dir.__exit__(exc_type, exc_value, traceback)
```

#### 调用

```py
with OverlayFS("/home/c/docker-export/alpine.tar") as overlay:
    # overlay.merged is the merged dir
    # overlay.lower is the lower dir
    # overlay.upper is the upper dir
    # overlay.work is the work dir
# 退出 context: 自动删除 overlay
```

### Network

用 Network Namespace 使容器有独立的网络栈。

通过 veth 虚拟网卡和 bridge 网桥，使容器可以连通。

#### 原理

```sh
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

# 5. repeat: another container

sudo ip netns add netns71

sudo ip link set veth710 netns netns71
sudo ip netns exec netns71 ip link set dev veth710 name eth0
sudo ip netns exec netns71 ip addr add 10.0.0.3/24 dev eth0
sudo ip netns exec netns71 ip link set eth0 up

sudo ip netns exec netns71 ifconfig

sudo ip link set veth711 master br700
sudo ip link set veth711 up

# 6. 两个容器互相连通了：

sudo ip netns exec netns71 ping 10.0.0.2
sudo ip netns exec netns70 ping 10.0.0.3
```

- ip link add 的网络设备在 `/sys/class/net/` (可以用 `ip link list` 查看)
- ip netns add 的命名空间在 `/var/run/netns/` (可以用 `ip netns list` 查看)

#### 实现

```py

class Network:
    def __init__(self, name: str) -> None:
        self.bridge = name

        self.netns = set()
        self.vnets = set()

        if not self._exists():
            self._create()

    def _exists(self) -> bool:
        return os.path.exists("/sys/class/net/" + self.bridge)

    def _create(self):
        subprocess.run(["ip", "link", "add", self.bridge, "type", "bridge"])
        subprocess.run(["ip", "link", "set", self.bridge, "up"])

    def delete(self):
        for ns in self.netns:
            ... # 关闭 ns 中的 eth0, 在 ns 中删除之，再删除 ns
        for vnet in self.vnets:
            subprocess.run(["ip", "link", "delete", vnet])

        subprocess.run(["ip", "link", "delete", self.bridge, "type", "bridge"])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.delete()

    def create_ns(self, containerID: str) -> str:
        ns = "pishnetns-" + containerID
        subprocess.run(["ip", "netns", "add", ns])

        self.netns.add(ns)
        return ns

    def add_to_network(self, containerID: str, ip: str):
        ns = "pishnetns-" + containerID
        veth_container = "pishveth-" + containerID + "0"
        veth_host = "pishveth-" + containerID + "1"

        subprocess.run(["ip", "link", "add", veth_container, "type", "veth", "peer", "name", veth_host])
        self.vnets.add(veth_host)

        # host side: veth_host 连接到 bridge，并 up
        ...
        # container side: veth_container 插进 ns 里，重命名为 eth0，设置 IP，up
        ...
```

#### 调用

```py
with Network("testpishnet") as network:
    ns = network.create_ns("ns0")
    network.add_to_network("ns0", "10.0.4.3/24")
# 退出环境: 自动删除 ns 和 veth pair
```

### 组装

#### 宿主机创建容器环境

```py
def run(opts):
    with OverlayFS(opts.image) as fs, \
            Cgroup("pish-" + opts.name) as cg, \
            Network(opts.network) as net:
        # namespace
        cmd = subprocess.Popen(["unshare", "-impuf", 
                                "--net=/var/run/netns/" + net.create_ns(opts.name),
                                "python3", "container.py",
                                "--root", fs.merged, "-c", opts.command])
        # cgroup
        for r in opts.resource:
            cg.set(*r.split("="))
        cg.apply(cmd.pid)

        # network
        net.add_to_network(opts.name, opts.ip)

        # 容器开始运行
        cmd.wait()

        # 容器退出后: 自动清理 network, cgroup 和临时文件系统
```

#### 容器初始化

在容器内部，PID 1 还需要做一些初始化工作，才能交给用户进程。

#### pivot_root

把容器的根目录换到创建好的 overlayfs 上:

> pivot_root - change the root filesystem

```sh
mkdir new_root/put_old
pivot_root new_root put_old
cd /
umount /put_old
rm -r /put_old
```

- see `man pivot_root`

#### mount proc

然后挂载 proc 文件系统:

```sh
mount -t proc proc /proc
```

#### exec

最后执行用户指定的命令:

```py
subprocess.Popen(opts.command)
```

## 实验

### 容器网络连通

容器 1:

```sh
$ sudo python3 host.py --root /home/c/docker-export/alpine.tar -c "/bin/sh" -n "test0" --network testpishnet --ip 10.0.4.5/24
2023-06-28 13:32:11,366 [INFO] network: creating bridge testpishnet
2023-06-28 13:32:11,439 [INFO] network: creating netns pishnetns-test0
2023-06-28 13:32:11,450 [INFO] run: container pid: 7648
2023-06-28 13:32:11,450 [INFO] network: adding container test0 to network testpishnet (ip 10.0.4.5/24)
2023-06-28 13:32:11,460 [INFO] network: created veth pair pishveth-test00 <=> pishveth-test01
/ # ifconfig
eth0      Link encap:Ethernet  HWaddr EE:79:39:87:1D:6C
          inet addr:10.0.4.5  Bcast:0.0.0.0  Mask:255.255.255.0
          inet6 addr: fe80::ec79:39ff:fe87:1d6c/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:19 errors:0 dropped:0 overruns:0 frame:0
          TX packets:9 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:1542 (1.5 KiB)  TX bytes:726 (726.0 B)

/ # ping 10.0.4.6
PING 10.0.4.6 (10.0.4.6): 56 data bytes
64 bytes from 10.0.4.6: seq=0 ttl=64 time=0.091 ms
64 bytes from 10.0.4.6: seq=1 ttl=64 time=0.113 ms
64 bytes from 10.0.4.6: seq=2 ttl=64 time=0.107 ms
64 bytes from 10.0.4.6: seq=3 ttl=64 time=0.105 ms
^C
--- 10.0.4.6 ping statistics ---
4 packets transmitted, 4 packets received, 0% packet loss
round-trip min/avg/max = 0.091/0.104/0.113 ms
/ #
2023-06-28 13:33:32,328 [INFO] run: container exited
2023-06-28 13:33:32,357 [INFO] network: deleting vnet pishveth-test01
2023-06-28 13:33:32,365 [INFO] network: deleting netns pishnetns-test0
```

容器 2:

```sh
$ sudo python3 host.py --root /home/c/docker-export/alpine.tar -c "/bin/sh" -n "test1" --network testpishnet --ip 10.0.4.6/24
2023-06-28 13:32:36,344 [INFO] run: container pid: 7689
2023-06-28 13:32:36,345 [INFO] network: adding container test1 to network testpishnet (ip 10.0.4.6/24)
2023-06-28 13:32:36,356 [INFO] network: created veth pair pishveth-test10 <=> pishveth-test11
/ # ifconfig
eth0      Link encap:Ethernet  HWaddr CA:2C:07:A4:F8:2E
          inet addr:10.0.4.6  Bcast:0.0.0.0  Mask:255.255.255.0
          inet6 addr: fe80::c82c:7ff:fea4:f82e/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:10 errors:0 dropped:0 overruns:0 frame:0
          TX packets:9 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:796 (796.0 B)  TX bytes:726 (726.0 B)

/ # ping 10.0.4.5
PING 10.0.4.5 (10.0.4.5): 56 data bytes
64 bytes from 10.0.4.5: seq=0 ttl=64 time=0.123 ms
64 bytes from 10.0.4.5: seq=1 ttl=64 time=0.106 ms
64 bytes from 10.0.4.5: seq=2 ttl=64 time=0.098 ms
^C
--- 10.0.4.5 ping statistics ---
3 packets transmitted, 3 packets received, 0% packet loss
round-trip min/avg/max = 0.098/0.109/0.123 ms
/ #
2023-06-28 13:33:34,547 [INFO] run: container exited
2023-06-28 13:33:34,579 [INFO] network: deleting netns pishnetns-test1
2023-06-28 13:33:34,586 [INFO] network: deleting bridge testpishnet
```
