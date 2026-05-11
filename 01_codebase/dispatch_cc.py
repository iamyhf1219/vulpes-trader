"""Claude Code 任务下发工具

用法:
  python dispatch_cc.py <任务文件.txt>
  
任务文件中写入要给 Claude Code 执行的具体代码任务。
"""
import subprocess
import sys
import os

CC_FLAGS = ["-p", "--allow-dangerously-skip-permissions", "--allowedTools", "Write Edit Bash Read"]

def dispatch(prompt_file: str, workdir: str = None):
    """将任务文件下发给 Claude Code 执行"""
    if not os.path.exists(prompt_file):
        print(f"[ERROR] 任务文件不存在: {prompt_file}")
        return False

    if workdir is None:
        workdir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(workdir)

    env = os.environ.copy()
    env["CLAUDE_CODE_ALLOW_DANGEROUS"] = "1"

    print(f"[CC] 下发任务: {prompt_file}")
    print(f"[CC] 工作目录: {workdir}")
    print()

    with open(prompt_file, "r", encoding="utf-8") as f:
        result = subprocess.run(
            ["claude"] + CC_FLAGS,
            stdin=f,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )

    if result.stdout:
        print(result.stdout[:3000])

    if result.stderr:
        err = result.stderr[:500]
        if err.strip():
            print("[CC STDERR]", err)

    if result.returncode == 0:
        print(f"\n[CC] 完成 (exit=0)")
        return True
    else:
        print(f"\n[CC] 异常退出 (exit={result.returncode})")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python dispatch_cc.py <任务文件.txt>")
        sys.exit(1)
    success = dispatch(sys.argv[1])
    sys.exit(0 if success else 1)
