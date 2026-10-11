# -*- coding: utf-8 -*-
"""
用 AutoCAD 自身把 DXF 打印成 PDF。

这是机械图纸预览的唯一正确做法 —— 绝不要用 matplotlib 渲染 DXF 生成预览 PDF，
matplotlib 不认识 SHX 字体，会把每个汉字画成空心方框（tofu）。

用法：
    python plot_pdf.py <图纸.dxf> [输出.pdf] [选项]

选项：
    --paper NAME     纸张规范名，默认 ISO_full_bleed_A4_(210.00_x_297.00_MM)
    --window x0,y0,x1,y1    打印窗口（图纸单位 mm），默认 0,0,210,297
    --keep           打印完不关闭文档（默认关闭）

关键坑（已固化在代码里）：
  1. 纸张必须用 full_bleed 无边距规格，否则 1:1 对不齐
  2. SetWindowToPlot() 必须先于 PlotType=4，顺序反了报"输入无效"
  3. PlotStyleSheet 属性在 2018 上不可写，忽略即可
"""
import os
import sys
import time
import pythoncom

pythoncom.CoInitialize()

import win32com.client as win32
from win32com.client import VARIANT

# 自动探测本机 AutoCAD 版本（不同版本 ProgID 不同，不能写死）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _acad import connect_autocad


def parse_args(argv):
    src = None
    out = None
    paper = "ISO_full_bleed_A4_(210.00_x_297.00_MM)"
    window = (0.0, 0.0, 210.0, 297.0)
    keep = False

    positional = []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--paper":
            paper = argv[i + 1]; i += 2
        elif a == "--window":
            window = tuple(float(v) for v in argv[i + 1].split(",")); i += 2
        elif a == "--keep":
            keep = True; i += 1
        else:
            positional.append(a); i += 1

    if not positional:
        print(__doc__); sys.exit(1)
    src = os.path.abspath(positional[0])
    out = os.path.abspath(positional[1]) if len(positional) > 1 \
        else os.path.splitext(src)[0] + ".pdf"
    return src, out, paper, window, keep


def main():
    src, out, paper, window, keep = parse_args(sys.argv)

    if not os.path.exists(src):
        print("DXF 不存在:", src); sys.exit(1)
    if os.path.exists(out):
        os.remove(out)

    acad = connect_autocad()
    before = acad.Documents.Count

    acad.Documents.Open(src)
    time.sleep(1.5)
    doc = acad.ActiveDocument
    print("已打开:", doc.Name)

    doc.SetVariable("BACKGROUNDPLOT", 0)     # 同步返回

    lay = doc.ActiveLayout
    # 打印设备名在不同版本/语言下可能不同，优先标准名，找不到就挑带 PDF 的
    want = "DWG To PDF.pc3"
    devices = list(lay.GetPlotDeviceNames())
    if want not in devices:
        cands = [d for d in devices if "pdf" in d.lower()]
        if not cands:
            print("错误: 未找到任何 PDF 打印设备。可用设备:", devices)
            sys.exit(1)
        want = cands[0]
        print("注意: 标准设备不可用，改用:", want)
    lay.ConfigName = want
    lay.RefreshPlotDeviceInfo()
    print("打印设备:", want)

    names = list(lay.GetCanonicalMediaNames())
    if paper not in names:
        print("警告: 纸张 %r 不在可用列表中，回退到 full_bleed A4" % paper)
        cands = [m for m in names if "full_bleed" in m.lower() and "A4" in m]
        if not cands:
            cands = [m for m in names if "A4" in m]
        paper = cands[0]
    lay.CanonicalMediaName = paper
    print("纸张:", paper)

    lay.PaperUnits = 1                        # acMillimeters
    lay.PlotRotation = 0
    lay.RefreshPlotDeviceInfo()

    # 顺序关键：先设窗口，再设 PlotType
    x0, y0, x1, y1 = window
    lo = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x0, y0])
    hi = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x1, y1])
    lay.SetWindowToPlot(lo, hi)
    lay.PlotType = 4                          # acWindow
    print("打印窗口: (%.1f,%.1f)-(%.1f,%.1f)  PlotType=%d" % (x0, y0, x1, y1, lay.PlotType))

    lay.CenterPlot = True
    lay.PlotWithLineweights = True
    lay.PlotHidden = False
    lay.ScaleLineweights = False
    lay.UseStandardScale = False
    lay.SetCustomScale(1.0, 1.0)              # 1 图纸单位 = 1 mm

    doc.Regen(1)
    plot = doc.Plot
    plot.QuietErrorMode = True
    plot.NumberOfCopies = 1

    print("开始打印 ->", out)
    ok = plot.PlotToFile(out)
    print("PlotToFile 返回:", ok)

    time.sleep(1.0)
    if os.path.exists(out):
        print("成功! 大小:", os.path.getsize(out), "bytes")
    else:
        print("失败: PDF 未生成")

    if not keep:
        # 只关闭自己打开的那一个文档对象，绝不按名字遍历（可能误关用户的图）
        try:
            doc.Close(False)
            print("已关闭:", src)
        except Exception as e:
            print("警告: 关闭自己打开的文档失败（可能已被手动关闭）:", e)

    after = acad.Documents.Count
    print("操作后文档数:", after, "(操作前:", before, ")")
    if after != before:
        print("!! 警告: 文档数发生变化，请立即检查你的 AutoCAD 是否有图纸被误关。")
        print("!! 本脚本只会关闭自己打开的那一个文档，其余变化通常来自手动操作。")


if __name__ == "__main__":
    main()
