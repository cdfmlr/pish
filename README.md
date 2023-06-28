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

### Cgroup

Cgroup（Control Group）是一种用于限制和管理进程组资源的机制，它可以用于限制容器的资源使用。Cgroup通过为进程组提供一个层次结构的组织方式，允许对每个组别的资源进行限制、监控和统计。

#### 原理

此处以 Cgroup V1 为例。

Cgroup 的原理是通过文件系统接口来管理资源限制。在 Linux 系统中，Cgroup 默认以文件系统的形式存在于 `/sys/fs/cgroup` 目录下。通过在该目录下创建相应的控制器组，可以对容器的资源使用进行限制。创建 Cgroup 的目录和文件，以及向 tasks 文件中写入容器的进程ID (PID)，即可实现资源限制。

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

以下是一些常用的Cgroup控制器：

- cpuset：控制进程所能使用的CPU和内存节点。
- cpu：控制进程使用CPU的配额和优先级。
- memory：控制进程使用内存的配额和行为。
- blkio：控制进程对块设备的输入输出访问。
- devices：控制进程访问设备的权限。

#### 实现

此处同样使用 Python 的 subprocess 模块执行命令，通过调用 mkdir 命令创建 Cgroup 目录，通过文件读写设置资源限制，以及向 `tasks` 文件中写入容器进程 ID 来将容器加入 Cgroup 的限制中。

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

上述代码示例中，使用 Python 的 `subprocess` 模块执行命令，通过调用 `mkdir` 命令创建 Cgroup 目录，并通过文件读写来设置资源限制，最后将容器进程ID写入 `tasks` 文件中，将容器加入Cgroup的限制中。

Cgroup类的构造函数接受一个组名（`group_name`）参数，并可选择性地提供基础路径（`base_path`）。构造函数会创建默认的 `cpuset.cpus` 和 `cpuset.mems` 文件，并将其值设置为 `0`。在我们的实践中，一些系统要求这样设置才能让 Cgroup 组中的程序正常工作。

Cgroup类还提供了以下方法：


- `set(key: str, value: str)`：设置指定控制器的参数值。
- `get(key: str) -> str`：获取指定控制器的参数值。
- `apply(pid: int)`：将指定的进程ID加入Cgroup限制。
- `_delete()`：删除Cgroup。

此外，为了方便使用 Cgroup，代码还使用了上下文管理器（`__enter__` 和 `__exit__` 魔术方法）来自动在离开环境后删除 Cgroup。

#### 调用

以下是一个使用上一节实现的 `Cgroup` 进行资源限制的示例：

```py
with Cgroup("pish-test0") as cgroup:
    cgroup.set("cpuset.cpus", "0")
    cgroup.set("cpuset.mems", "0")
    cgroup.apply(pid)
# 退出 context: 自动删除 cgroup
```

### OverlayFS

OverlayFS 是一种文件系统技术，它允许将多个文件系统层叠在一起，形成一个统一的虚拟文件系统。它在容器化技术中被广泛使用，特别是在实现容器镜像功能方面。

容器镜像通常由多个层组成，其中每个层都包含文件和目录的快照。OverlayFS 使用联合挂载（union mount）的方式，将这些层合并到一个单一的文件系统中，使得各层之间的文件和目录能够以透明的方式进行访问和修改。

PISH 使用 OverlayFS 来实现容器的镜像功能。具体来说，OverlayFS 使容器可以使用镜像:

- 镜像层：只读
- 容器层：读写

容器生命结束后，容器层被 pish 自动删除。

#### 原理

> read this: https://wiki.archlinux.org/title/Overlay_filesystem

OverlayFS 的原理非常简单，即使用 mount 挂载 overlay 类型的的文件系统。通过指定三个关键目录参数，即 lowerdir、upperdir 和 workdir，可以创建一个新的合并文件系统。lowerdir 指定只读层，其中包含基本镜像的内容。upperdir 是一个读写层，用于容器的修改。workdir 是 OverlayFS 使用的临时工作目录，用于处理文件系统操作。

```sh
$ sudo mount -t overlay overlay -o lowerdir=/lower,upperdir=/upper,workdir=/work /merged
```

- lowerdir: 只读层
- upperdir: 读写层
- workdir: overlay 是用的临时目录
- merged: 合并后的目录: lowerdir + upperdir, 写入 merged 的数据会写入 upperdir

当在 OverlayFS 中进行文件读取操作时，它会首先在 upperdir 中查找文件，如果找不到，则会回退到 lowerdir 中查找。这样，对于容器来说，它可以读取基本镜像的内容，并在需要时进行修改和扩展。

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

`OverlayFS` 类封装了 OverlayFS 的使用过程。它在创建实例时指定了镜像路径，并在 `__enter__` 方法中执行了 OverlayFS 的挂载操作。它通过创建临时目录和解压镜像文件来准备 `lowerdir`，然后创建 `upperdir`、`workdir` 和 `merged` 目录。最后，使用 `subprocess.run` 命令执行挂载操作，将 OverlayFS 应用到指定的目录上。

当容器生命周期结束时，`OverlayFS` 将容器层的修改丢弃，而保留基本镜像的只读部分。这样可以实现容器的快速重置和清理，同时节省存储空间。

#### 调用

通过使用上一节实现的 `OverlayFS`，pish 实现了容器的镜像功能，使得容器可以方便地使用基本镜像，并在容器层进行修改，同时实现了容器的快速清理和重置。

```py
with OverlayFS("/home/c/docker-export/alpine.tar") as overlay:
    # overlay.merged is the merged dir
# 退出 context: 自动删除 overlay
```

在上面的调用示例中，使用 `with` 语句创建了 OverlayFS 实例，并指定了容器镜像的路径。在 `with` 代码块中，可以访问 `overlay.merged` 目录，该目录即为合并后的文件系统。当退出 `with` 代码块时，`__exit__` 方法会自动执行，卸载 OverlayFS 并清理临时目录。

### Network

用 Network Namespace 使容器有独立的网络栈。

通过 veth 虚拟网卡和 bridge 网桥，使容器可以连通。

#### 原理

**Network Namespace** 是 Linux 内核提供的一种机制，用于隔离不同进程的网络栈和网络资源。每个 Network Namespace 都有自己的网络接口、路由表和 IP 地址空间，使得不同的进程或容器可以具有独立的网络环境。通过使用 Network Namespace，可以在同一主机上创建多个隔离的网络环境，每个环境都拥有自己的 IP 地址、网络接口和路由规则。

**veth（Virtual Ethernet）**是一种虚拟网卡设备对，由一对成对的虚拟网络设备组成，可以通过一个端口与网络命名空间中的进程或容器相连，通过另一个端口与宿主机的网络栈相连。veth 对通常被用于将容器连接到宿主机的网络，使得容器可以与宿主机和其他容器进行通信。

在容器网络中，通过创建一对 veth 设备，其中一个端口连接到容器的网络命名空间，另一个端口连接到宿主机的网络命名空间或网络设备上，实现容器与宿主机之间以及容器之间的网络连通性。

**Bridge 网桥**是一个网络设备，用于将多个网络接口连接在一起，形成一个逻辑上的广播域。它工作在 OSI 模型的第二层（数据链路层），通过学习网络设备的 MAC 地址，将数据包从一个接口转发到另一个接口，实现网络设备之间的通信。


通过使用 Network Namespace、veth 虚拟网卡和 bridge 网桥，就实现了容器的独立网络栈，并提供了容器之间的连通性。这样，每个容器都可以拥有自己的网络环境，彼此之间的网络通信可以相互隔离：

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

上述代码片段展示了一个简单的容器网络实现示例。该示例使用 Network 类封装了创建网络、创建网络命名空间、添加容器到网络等操作。具体步骤包括：

1. 创建一个 Bridge 网桥，用于连接容器和宿主机网络。
2. 创建一对 veth 设备，其中一个端口连接到容器的网络命名空间，另一个端口连接到 Bridge 网桥上。
3. 在容器的网络命名空间中配置网络设备，包括设置 IP 地址和启用网络接口。
4. 将容器所在的网络命名空间添加到网络对象的管理列表中。
5. 在退出网络对象的上下文环境时，自动删除网络命名空间和 veth 设备。

注意，一切皆文件，网络设备、命名空间也是文件：

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

上述代码中的 Network 类封装了创建和管理网络的操作。它通过创建一个 bridge（网桥）来实现容器之间的网络连通。具体来说，它使用了以下几个关键步骤：

- `__init__(self, name: str)`：在初始化时，指定了一个 bridge 名称，并检查该 bridge 是否已存在。如果不存在，则创建一个新的 bridge。
- `_create(self)`：创建一个 bridge，通过运行 ip link add 和 ip link set 命令来创建和启用该 bridge。
- `delete(self)`：删除网络配置。它会关闭并删除每个网络命名空间中的 eth0 接口，并删除网络命名空间。然后，删除与每个容器相关联的 veth 虚拟网卡。
- `create_ns(self, containerID: str) -> str`：创建一个网络命名空间，并将其添加到网络中。它会运行 ip netns add 命令创建网络命名空间，并将其添加到 self.netns 集合中。
- `add_to_network(self, containerID: str, ip: str)`：将容器添加到网络中。它会为容器创建一对 veth 虚拟网卡，一个连接到容器的网络命名空间中，另一个连接到主机的 bridge 上。然后，配置容器内的 veth 接口，包括重命名为 eth0，并设置 IP 地址。

这样，通过使用 Network 类，可以方便地创建和管理容器的网络环境。每个容器都可以拥有独立的网络栈和网络资源，通过 veth 设备和 Bridge 网桥连接在一起，实现容器之间和容器与宿主机之间的网络通信。

#### 调用

```py
with Network("testpishnet") as network:
    ns = network.create_ns("ns0")
    network.add_to_network("ns0", "10.0.4.3/24")
# 退出环境: 自动删除 ns 和 veth pair
```

上述示例中的 `with Network("testpishnet") as network`，创建了一个名为 `testpishnet` 的 `Network` 实例，并进入了一个上下文管理器。在该上下文中，可以使用 `Network` 实例进行网络操作。在示例中，首先创建了一个名为 `ns0` 的网络命名空间，并将其添加到网络中。然后，将 `ns0` 添加到网络中，并分配 IP 地址为 `10.0.4.3/24`。当退出上下文管理器时，网络配置将被自动删除。

### Namespace

Namespace 使容器与宿主机隔离。通过创建具有不同隔离属性的 Namespace，容器可以在独立的环境中运行，实现资源隔离和安全性。

#### 原理

Namespace 是一种用于实现容器与宿主机之间隔离的技术。通过使用 Namespace，容器可以在自己的独立环境中运行，与宿主机和其他容器相互隔离。

我们使用 Linux 内核提供的 unshare 命令创建具有不同隔离属性的新进程。unshare 命令可以创建多种类型的 Namespace，包括挂载（mount）、UTS（主机名等）、IPC（进程间通信）、网络（network）和 PID（进程标识符）等。

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

通过在 unshare 命令后指定相应的选项，可以创建具有特定隔离属性的 Namespace。

- -m 或 --mount：创建挂载 Namespace。
- -u 或 --uts：创建 UTS Namespace，用于隔离主机名等。
- -i 或 --ipc：创建 IPC Namespace，用于隔离进程间通信。
- -n 或 --net：创建网络 Namespace，用于隔离网络栈。
- -p 或 --pid：创建 PID Namespace，用于隔离进程标识符。

- see `man unshare`

#### 实现

在 Python 代码中，我们使用 subprocess.Popen 函数来调用 unshare 命令并创建 Namespace：

```py
cmd = subprocess.Popen(["unshare", "-impuf",
                        "--net=/var/run/netns/" + net.create_ns(opts.name)
                        "python3", "container.py", ...])
```
我们通过调用 subprocess.Popen 创建了一个新的进程，在其中通过 unshare 设置命名空间，并在其中执行容器的 PID 1 程序，即初始化脚本 `container.py`（详见后文）。

通过这种方式，容器的第一个进程（PID 1）将在创建的 Namespace 中运行，与宿主机和其他容器隔离开来，拥有独立的网络环境和其他隔离属性。

需要注意的是，网络 Namespace 是提前通过上文的 `Network` 环境创建和管理的，因此在使用 unshare 命令时需要指定正确的网络 Namespace 路径 `--net=/var/run/netns/<netns-name>`。

### 组装

将上述各个组件组合在一起，就可以形成完整的容器环境。下面对组装过程中的几个关键步骤进行详细介绍。

#### 宿主机创建容器环境

在完成命令行参数解析，获取容器配置后，宿主机会创建容器的根文件系统、网络环境和 Cgroup 等资源，并将其组装成容器环境：

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

在容器内部，PID 1 进程还需要进行一些初始化工作，然后才能交给用户进程。这些初始化工作通常包括设置容器的根文件系统和挂载必要的文件系统。

#### pivot_root

在容器初始化的过程中，一个重要的步骤是将容器的根文件系统更改为创建好的 OverlayFS。这个操作使用 `pivot_root` 系统调用来完成，它能够改变根文件系统的挂载点。

> pivot_root - change the root filesystem

以下是 `pivot_root` 命令的示例用法：

```sh
mkdir new_root/put_old
pivot_root new_root put_old
cd /
umount /put_old
rm -r /put_old
```

这段操作的作用是将新的根文件系统 `new_root` 切换为容器的根文件系统，并将旧的根文件系统移动到 `new_root/put_old` 目录下，然后移除 `new_root/put_old` 目录。这样，容器的根文件系统就被更改为 `new_root` 了。并且无法访问到宿主机的根文件系统，实现了隔离。

- see `man pivot_root`

#### mount proc

接下来，在容器内部，还需要挂载 /proc 文件系统，以提供进程和系统信息。这可以通过执行以下命令来完成：

```sh
mount -t proc proc /proc
```

通过这个操作，容器内的进程可以访问 /proc 目录下的信息，包括当前运行的进程列表、内存使用情况等。

#### exec

最后，至此容器的初始化过程完成，容器环境准备就绪，可以交给用户进程运行。这可以通过使用 subprocess.Popen 函数来启动用户指定的命令进程：

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
