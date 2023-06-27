# pish: PISH Is Simplified Hind.

```sh
git clone github.com/cdfmlr/pish
cd pish
sudo python3 host.py --root /home/c/docker-export/alpine.tar -c "/bin/sh" -n "test0" --network testpishnet --ip 10.0.4.5/24
```

Output:

```sh
2023-06-27 23:26:18,235 [INFO] overlayfs: extracting image /home/c/docker-export/alpine.tar to /tmp/pish-gwgcz8wy-test0/lower
2023-06-27 23:26:18,265 [INFO] overlayfs: mounted at /tmp/pish-gwgcz8wy-test0/merged
2023-06-27 23:26:18,275 [INFO] container pid: 19221
2023-06-27 23:26:18,276 [INFO] cgroup set: 0 > /sys/fs/cgroup/cpuset/pish-test0/cpuset.cpus
2023-06-27 23:26:18,276 [INFO] cgroup set: 0 > /sys/fs/cgroup/cpuset/pish-test0/cpuset.mems
2023-06-27 23:26:18,276 [INFO] cgroup apply: 19221 > /sys/fs/cgroup/cpuset/pish-test0/tasks
2023-06-27 23:26:18,277 [INFO] network: adding container test0 to network testpishnet (ip 10.0.4.5/24)
2023-06-27 23:26:18,466 [INFO] pivot_root to /tmp/pish-gwgcz8wy-test0/merged
/ # ifconfig
eth0      Link encap:Ethernet  HWaddr 0A:C9:C3:92:BB:2C
          inet addr:10.0.4.5  Bcast:0.0.0.0  Mask:255.255.255.0
          inet6 addr: fe80::8c9:c3ff:fe92:bb2c/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:8 errors:0 dropped:0 overruns:0 frame:0
          TX packets:6 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:696 (696.0 B)  TX bytes:516 (516.0 B)

/ # exit
2023-06-27 23:26:25,009 [INFO] container exited
2023-06-27 23:26:25,092 [INFO] cgroup deleted: pish-test0
```

Cleanup:

```sh
sudo ip link delete pishveth-test00
sudo ip netns delete pishnetns-test0
```
