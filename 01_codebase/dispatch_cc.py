"""Claude Code 任务下发工具

用法:
  python dispatch_cc.py <任务文件.txt>
  
任务文件中写入要给 Claude Code 执行的具体代码任务。
"""
import subprocess
import sys
import os

CC_FLAGS = ["--allow-dangerously-skip-permissions", "--allowedTools", "Write Edit Bash Read"]

def dispatch(prompt_file: str):
    """将任务文件下发给 Claude Code 执行"""
    if not os.path.exists(prompt_file):
        print(f"[ERROR] 任务文件不存在: {prompt_file}")
        return False

    # 切到 01_codebase 目录
    codebase = os.path.join(os.path.dirname(__file__), "01_codebase")
    os.chdir(codebase)

    cmd = ["claude", "-p"] + CC_FLAGS

    print(f"[CC] 下发任务: {prompt_file}")
    print(f"[CC] 工作目录: {codebase}")
    print(f"[CC] 开始执行...")

    with open(prompt_file, "r", encoding="utf-8") as f:
        result = subprocess.run(
            cmd,
            stdin=f,
            capture_output=True,
            text=True,
            timeout=300,
        )

    if result.stdout:
        print("[CC 输出]")
        print(result.stdout[:3000])

    if result.stderr:
        print("[CC 错误]", result.stderr[:500])

    if result.returncode == 0:
        print(f"[CC] 任务完成 (exit=0)")
        return True
    else:
        print(f"[CC] 任务异常退出 (exit={result.returncode})")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python dispatch_cc.py <任务文件.txt>")
        sys.exit(1)
    success = dispatch(sys.argv[1])
    sys.exit(0 if success else 1)
