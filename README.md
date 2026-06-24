# mac-proximity-unlock

Mac 近距自动解锁——两台 MacBook/Mac mini 距离感应，本机跟随远程解锁/锁屏。

> 当你走近远程 MacBook 并解锁它，本机自动跟随解锁。离开时远程锁屏，本机也跟随锁定。

## 原理

```
蓝牙 RSSI + Ping 延迟 → DistanceEngine FSM → NEAR/MID/FAR
                                              │
SSH 轮询远程锁屏状态 → locked/unlocked        │
                                              ▼
                                     ProximityExecutor
                                     ├ 远程解锁 + 距离 NEAR → 本机解锁
                                     ├ 远程锁屏 → 本机锁屏（安全优先）
                                     └ 距离变 FAR + 远程锁定 → 本机确认锁屏
```

## 环境要求

- macOS（两台 Mac）
- Python 3.9+
- 两台机器在同一局域网
- SSH Key 免密（`ssh-copy-id` 到远程 MacBook）
- 蓝牙开启（系统服务）

## 快速开始

```bash
git clone git@github.com:your_ssh_useraov/mac-proximity-unlock.git
cd mac-proximity-unlock

# 安装依赖
pip install bleak paramiko python-dotenv

# 配置
cp .env.example .env
# 编辑 .env 填入远程 MacBook 的 IP、SSH 用户、蓝牙 MAC

# 检查环境
python3 main.py --check

# 初始化 Keychain 密码
python3 main.py --init-keychain

# 首次设置：创建 UnlockMac Shortcut（详见下方）
# 启动
python3 main.py
```

## 配置

`.env` 文件：

```
REMOTE_IP=x.x.x.x      # 远程 MacBook IP
REMOTE_USER=your_ssh_user              # 远程 SSH 用户名
REMOTE_BT_MAC=xx:xx:xx:xx:xx:xx  # 远程 MacBook 蓝牙 MAC
```

## Shortcut 设置

首次使用需在 Shortcuts app 创建 "UnlockMac" 快捷指令，AppleScript 内容见 `init_shortcut.sh` 或 `unlock_script.applescript`。

## 项目结构

```
mac-proximity-unlock/
├── main.py                  # 主入口
├── actions/
│   ├── executor.py          # 动作执行器（核心调度）
│   ├── unlocker.py          # 解锁模块（Shortcuts + CGS 双策略）
│   └── locker.py            # 锁屏模块
├── sensors/
│   ├── bluetooth_scanner.py # 蓝牙 RSSI 扫描
│   ├── ping_probe.py        # Ping 延迟探测
│   └── distance_engine.py   # 距离 FSM 状态机
├── remote/
│   ├── ssh_client.py        # SSH 客户端
│   └── state_client.py      # 远程锁屏状态轮询
├── scripts/                 # 安装/诊断脚本
└── docs/                    # 设计文档
```

## 安全

- 登录密码存储在 macOS Keychain，不上盘
- `.env` 已 `.gitignore`，不会进入版本管理
- PID 单例锁，防止多实例竞争泄密
- 解锁前检查锁屏状态，防止密码泄露到前台应用

## 后台运行

```bash
# 方式 1: nohup
nohup python3 ~/my-project/mac-proximity-unlock/main.py > /tmp/mac-proximity-unlock.log 2>&1 &

# 方式 2: launchd
cp scripts/com.mac-proximity-unlock.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mac-proximity-unlock.plist
```

## License

MIT
