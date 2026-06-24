"""
SSH 客户端 — 远程执行命令/脚本
连接 x.x.x.x，查询锁屏状态等
需提前配置 SSH Key 免密 (ssh-copy-id)
"""
import asyncio
import logging
from typing import Optional, Tuple

logger = logging.getLogger("ssh_client")

REMOTE_IP = "x.x.x.x"
REMOTE_USER = "your_ssh_user"
SSH_PORT = 22


class SSHClient:
    """基于 paramiko 的 SSH 客户端"""

    def __init__(self, host: str = REMOTE_IP, user: str = REMOTE_USER,
                 port: int = SSH_PORT, key_path: Optional[str] = None):
        self.host = host
        self.user = user
        self.port = port
        self.key_path = key_path
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import paramiko
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            # 优先级: 指定 key → 默认 SSH key → 密码
            if self.key_path:
                pkey = paramiko.RSAKey.from_private_key_file(self.key_path)
                self._client.connect(
                    self.host, port=self.port, username=self.user,
                    pkey=pkey, timeout=10, allow_agent=True, look_for_keys=False,
                )
            else:
                self._client.connect(
                    self.host, port=self.port, username=self.user,
                    timeout=10, allow_agent=True, look_for_keys=True,
                )
        return self._client

    def exec(self, command: str, timeout: int = 15) -> Tuple[int, str, str]:
        """执行远程命令，返回 (exit_code, stdout, stderr)"""
        try:
            _, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return (
                exit_code,
                stdout.read().decode("utf-8", errors="replace"),
                stderr.read().decode("utf-8", errors="replace"),
            )
        except Exception as e:
            logger.error(f"SSH 执行失败 [{self.host}]: {e}")
            return (-1, "", str(e))

    async def exec_async(self, command: str, timeout: int = 15):
        """异步包装 exec"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.exec, command, timeout)

    def close(self):
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ========== 锁屏检测快捷函数 ==========

QUERY_LOCK_SCRIPT = """python3 -c "
# 纯 ctypes + CoreFoundation — 不依赖任何第三方包
import ctypes

# CoreGraphics
cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
cg.CGSessionCopyCurrentDictionary.restype = ctypes.c_void_p

# CoreFoundation
cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
cf.CFDictionaryGetValue.restype = ctypes.c_void_p
cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
cf.CFBooleanGetValue.restype = ctypes.c_bool
cf.CFBooleanGetValue.argtypes = [ctypes.c_void_p]
cf.CFRelease.restype = None
cf.CFRelease.argtypes = [ctypes.c_void_p]
cf.CFStringCreateWithCString.restype = ctypes.c_void_p
cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32]

d = cg.CGSessionCopyCurrentDictionary()
if not d:
    print('unlocked')
else:
    key = cf.CFStringCreateWithCString(None, b'CGSSessionScreenIsLocked', 0x08000100)
    val = cf.CFDictionaryGetValue(d, key)
    locked = cf.CFBooleanGetValue(val) if val else 0
    cf.CFRelease(key)
    cf.CFRelease(d)
    print('locked' if locked else 'unlocked')
" """


def query_lock_state(ssh: SSHClient) -> Optional[bool]:
    """通过 SSH 查询远程锁屏状态

    Returns:
        True = 已锁, False = 未锁, None = 查询失败
    """
    code, out, err = ssh.exec(QUERY_LOCK_SCRIPT)
    if code == 0:
        result = out.strip().lower()
        if result == "locked":
            return True
        elif result == "unlocked":
            return False
    logger.warning(f"锁屏查询失败: code={code} out={out} err={err}")
    return None
