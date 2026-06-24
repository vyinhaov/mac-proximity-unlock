# Mac Proximity Unlock

Mac 间蓝牙距离感应自动解锁 / 锁定系统。

当你拿着 MacBook 走近另一台 MacBook 时，本机自动解锁；当你走远或远程 MacBook 锁屏时，本机自动锁屏。

## 原理

```
┌──────────────┐    BT RSSI + Ping     ┌──────────────┐
│  本机 MacBook │ ◄──────────────────► │ 远程 MacBook  │
│              │    SSH 查询锁屏状态    │              │
│  距离引擎 FSM │ ◄──────────────────► │  锁屏 / 解锁  │
│  NEAR→解锁   │                       │              │
│  FAR→锁屏    │                       │              │
└──────────────┘                       └──────────────┘
```

- **距离检测**：蓝牙 RSSI（主）+ ICMP Ping 延迟（辅）→ 有限状态机判断 NEAR / MID / FAR
- **远程状态**：SSH 周期性轮询远程 MacBook 锁屏状态
- **决策引擎**：融合距离 + 远程状态 → 自动锁定 / 解锁

## 环境要求

- 两台 MacBook，同一局域网
- Python 3.9+
- 蓝牙开启
- SSH 免密登录（`ssh-copy-id` 到远程 MacBook）
- 辅助功能权限（系统设置 → 隐私与安全性 → 辅助功能 → 添加 `/usr/bin/python3`）

## 快速开始

```bash
git clone git@github.com:your_ssh_useraov/mac-proximity-unlock.git
cd mac-proximity-unlock

# 安装依赖
pip install bleak paramiko python-dotenv

# 配置
cp .env.example .env
# 编辑 .env，填入远程 MacBook 的蓝牙 MAC、IP、SSH 用户名

# 检查环境
python3 main.py --check

# 初始化 Keychain 密码（仅首次）
python3 main.py --init-keychain

# 创建 UnlockMac 快捷指令（仅首次）
bash init_shortcut.sh

# 运行
python3 main.py
```

## 配置 `.env`

```env
REMOTE_BT_MAC=xx:xx:xx:xx:xx:xx   # 远程 MacBook 蓝牙 MAC
REMOTE_IP=x.x.x.x           # 远程 MacBook IP
REMOTE_USER=your_ssh_user                  # SSH 用户名
```

## 后台运行

```bash
# nohup 方式
nohup python3 ~/my-project/mac-proximity-unlock/main.py > /dev/null 2>&1 &

# launchd 自启动（开机自动运行）
bash scripts/install_launchagent.sh
```

## 安全

- 密码存储在 macOS Keychain，不落盘
- `.env` 已加入 `.gitignore`，不会提交敏感配置
- PID 锁防止多实例并发
- 输入密码前双重确认屏幕已锁定

## 项目结构

```
├── main.py                    # 入口，环境检查，PID 锁
├── actions/
│   ├── executor.py            # 核心决策引擎
│   ├── unlocker.py            # 解锁：Shortcuts + CGS 后备
│   └── locker.py              # 锁屏：6 策略级联
├── sensors/
│   ├── bluetooth_scanner.py   # 蓝牙 RSSI + 卡尔曼滤波
│   ├── ping_probe.py          # ICMP 延迟探测
│   └── distance_engine.py     # 距离 FSM
├── remote/
│   ├── ssh_client.py          # SSH 客户端
│   └── state_client.py        # 远程锁屏状态轮询
└── scripts/
    ├── install_launchagent.sh # 安装 launchd 自启动
    ├── init_keychain.sh       # Keychain 初始化
    └── diag_unlock.py         # 解锁诊断工具
```

## License

MIT
