import argparse
import logging
import os
import subprocess
import ctypes
import ctypes.util

libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("-c", "--command", required=True)
    parser.add_argument("-v", "--verbose", action="store_true")

    opts = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=logging.DEBUG if opts.verbose else logging.INFO
    )

    run(opts)


def run(opts):
    subprocess.run(["mount", "--make-rprivate", "/"],
                   check=True)  # just in case
    pivot_root(opts.root)

    #subprocess.run(["mount", "-t", "proc", "proc", "/proc"], check=True)
    if libc.mount(ctypes.c_char_p(b"proc"), ctypes.c_char_p(b"/proc"), ctypes.c_char_p(b"proc"), ctypes.c_ulong(0), ctypes.c_char_p(None)) != 0:
        raise OSError(ctypes.get_errno(), "mount /proc failed: " +
                      os.strerror(ctypes.get_errno()))

    cmd = subprocess.Popen(opts.command)

    cmd.wait()


def pivot_root(new_root):
    logging.info("pivot_root to %s" % new_root)

    os.mkdir(new_root + "/old_root")

    subprocess.run(["mount", "--rbind", new_root, new_root], check=True)

    subprocess.run(
        ["pivot_root", new_root, new_root + "/old_root"], check=True)

    # cannot use mount, umount here

    os.chdir("/")
    # subprocess.run(["umount", "old_root"], check=True)
    if libc.umount2(ctypes.c_char_p(b"old_root"), ctypes.c_int(MNT_DETACH)) != 0:
        raise OSError(ctypes.get_errno(),
                      "umount2 /old_root failed: " + os.strerror(ctypes.get_errno()))
    os.rmdir("/old_root")


# after pivot_root, we can't use subprocess.run(["mount", ...])
# there may be no mount binary in the new rootfs.

# https://github.com/torvalds/linux/blob/1ef6663a587ba3e57dc5065a477db1c64481eedd/include/uapi/linux/mount.h#L26 XXX: Last change 5 years ago
MS_REC = 16384
# https://github.com/torvalds/linux/blob/1ef6663a587ba3e57dc5065a477db1c64481eedd/include/uapi/linux/mount.h#L32 XXX: Last change 5 years ago
MS_PRIVATE = (1 << 18)
# https://github.com/torvalds/linux/blob/1ef6663a587ba3e57dc5065a477db1c64481eedd/include/linux/fs.h#L1116 Last change 18 years ago
MNT_DETACH = 0x00000002


if __name__ == '__main__':
    try:
        main()
    finally:
        logging.shutdown()
