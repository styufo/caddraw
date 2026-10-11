# -*- coding: utf-8 -*-
"""
检查并安装 cad-drawing skill 所需的 Python 依赖。

用法：
    python install_deps.py            # 检查，缺什么装什么
    python install_deps.py --check    # 只检查不安装
    python install_deps.py --full     # 连三维建模依赖（cadquery）一起装，较慢

说明：
    - 用当前解释器（sys.executable）装，不污染系统 Python，也不需要管理员权限
    - cadquery 必须配 cadquery-ocp==8.0.1.1.0，版本不匹配会报
      "cannot import name 'TColgp_HArray1OfPnt' from 'OCP.TColgp'"
    - 装完跑 python _acad.py 自检 CAD 连接
"""
import subprocess
import sys

# (import 名, pip 包名, 是否必需)
BASE = [
    ("ezdxf",   "ezdxf",      True),
    ("fitz",    "pymupdf",    True),
    ("win32com","pywin32",    True),
    ("numpy",   "numpy",      True),
    ("PIL",     "pillow",     True),
    ("matplotlib", "matplotlib", True),
]
FULL = [
    ("cadquery", "cadquery==2.8.0",            False),
    ("OCP",      "cadquery-ocp==8.0.1.1.0",    False),
]


def have(mod):
    import importlib.util
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


def pip_install(pkg):
    cmd = [sys.executable, "-m", "pip", "install", "-U", pkg]
    print("   $", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        return True
    print(r.stdout[-1500:])
    print(r.stderr[-1500:])
    return False


def main():
    args = sys.argv[1:]
    check_only = "--check" in args
    full = "--full" in args

    pkgs = list(BASE) + (FULL if full else [])
    print("Python:", sys.executable)
    print("模式:", "仅检查" if check_only else "检查并安装",
          "| 含三维建模依赖" if full else "| 仅二维出图依赖")
    print()

    missing = []
    for mod, pkg, required in pkgs:
        ok = have(mod)
        mark = "OK  " if ok else "缺失"
        print("  [%s] %-14s (pip: %s)" % (mark, mod, pkg))
        if not ok:
            missing.append((mod, pkg, required))

    print()
    if not missing:
        print("全部依赖已就绪。")
        return 0

    if check_only:
        print("缺失 %d 项，运行 `python install_deps.py` 安装。" % len(missing))
        return 1

    failed = []
    for mod, pkg, required in missing:
        print("安装 %s ..." % pkg)
        if not pip_install(pkg):
            failed.append((mod, pkg, required))
            print("  失败: %s" % pkg)
        else:
            print("  完成: %s" % pkg)

    print()
    if failed:
        print("以下依赖安装失败：")
        for mod, pkg, req in failed:
            print("  - %s (%s)%s" % (mod, pkg, " [必需]" if req else " [可选]"))
        print("\n若失败与网络有关，可换国内源重试：")
        print("  pip install -i https://pypi.tuna.tsinghua.edu.cn/simple " + pkg)
        return 2

    print("依赖安装完成。下一步：python _acad.py  （自检 AutoCAD / SolidWorks 连接）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
