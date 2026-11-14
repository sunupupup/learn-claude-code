# 保存虚拟机快照

Firecracker 用命令行启动进程，再用 curl 调用管理 API，完成暂停、保存和恢复。
Linux Bash 示例，假设已有一台运行中的 VM，管理入口是 /tmp/vm1.socket。这些命令都在宿主机执行。

整个步骤：暂停 → 保存快照 → 退出旧进程 → 启动新进程 → 加载并继续运行

## 1. 暂停这台VM

先停住客户机的执行。

```bash
curl --unix-socket /tmp/vm1.socket \
  -X PATCH http://localhost/vm \
  -H 'Content-Type: application/json' \
  -d '{"state":"Paused"}'
```


## 2. 保存完整快照

```bash
curl --unix-socket /tmp/vm1.socket \
  -X PUT http://localhost/snapshot/create \
  -H 'Content-Type: application/json' \
  -d '{
    "snapshot_type": "Full",
    "snapshot_path": "/tmp/vm.state",
    "mem_file_path": "/tmp/vm.memory"
  }'
```

生成两个宿主机文件
- /tmp/vm.state   → 虚拟 CPU、设备等状态
- /tmp/vm.memory  → 客户机内存内容


磁盘镜像要另外保留对应版本。 例如原磁盘是 /data/rootfs.ext4，可以在 VM 保持暂停时备份：
```bash
cp /data/rootfs.ext4 /data/rootfs.snapshot.ext4
```


## 3. 退出原Firecracker，再启动一个新的进程

可以在原 Firecracker 所在终端按 Ctrl+C 退出。然后启动：

```bash
firecracker --api-sock /tmp/vm2.socket
```

此时只是启动新的 Firecracker 进程，还没有让客户机重新开机。

## 4. 加载快照，并继续执行

确保对应磁盘仍在原配置路径，且内容与快照一致，再在另一个终端执行：

```bash
curl --unix-socket /tmp/vm2.socket \
  -X PUT http://localhost/snapshot/load \
  -H 'Content-Type: application/json' \
  -d '{
    "snapshot_path": "/tmp/vm.state",
    "mem_backend": {
      "backend_type": "File",
      "backend_path": "/tmp/vm.memory"
    },
    "resume_vm": true
  }'
```

"resume_vm": true 就表示：加载成功后，直接从保存的位置继续运行。