# -*- coding: utf-8 -*-
"""
把 DWG 另存为 DXF（AutoCAD COM），用于读取图纸里的真实文字。

安全约束：
  - 先把源 DWG 复制到工作目录再打开，原文件只读，绝不改动
  - 绝不调用 acad.Quit()（连接的是用户正在运行的实例）
  - 只关闭自己打开的那一个文档

用法：
    python dwg_to_dxf.py <源.dwg> [输出.dxf]

输出 DXF 默认放在源文件旁，扩展名改为 .dxf（若源在工作目录外，则输出到当前目录下的 <原名>.dxf）
"""
import os
import sys
import shutil
import pythoncom

pythoncom.CoInitialize()

import win32com.client as win32

# 自动探测本机 AutoCAD 版本（不同版本 ProgID 不同，不能写死）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _acad import connect_autocad


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    src = os.path.abspath(sys.argv[1])
    if not os.path.exists(src):
        print("源文件不存在:", src)
        sys.exit(1)

    if len(sys.argv) > 2:
        out = os.path.abspath(sys.argv[2])
    else:
        out = os.path.splitext(src)[0] + ".dxf"

    work = os.path.join(os.getcwd(), "_dwg_work")
    os.makedirs(work, exist_ok=True)
    tmp = os.path.join(work, os.path.basename(src))
    shutil.copy2(src, tmp)
    print("已复制副本:", tmp, "(原文件未改动)")

    acad = connect_autocad()
    before = acad.Documents.Count
    print("打开前文档数:", before)

    doc = acad.Documents.Open(tmp)
    print("已打开:", doc.Name)

    doc.SaveAs(out, 49)          # 49 = ac2010_dxf
    print("已导出 DXF:", out, os.path.getsize(out), "bytes")

    # 只关闭自己打开的那一个文档对象，绝不按名字遍历（可能误关用户的图）
    try:
        doc.Close(False)
        print("已关闭自己打开的文档")
    except Exception as e:
        print("警告: 关闭失败（可能已被手动关闭）:", e)

    after = acad.Documents.Count
    print("操作后文档数:", after, "(操作前:", before, ")")
    if after != before:
        print("!! 警告: 文档数发生变化，请检查你的 AutoCAD 是否有图纸被误关。")
    print("完成。")


if __name__ == "__main__":
    main()
