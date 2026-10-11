# -*- coding: utf-8 -*-
"""
校验打印出来的 PDF 是否合格：页面尺寸、内容边界、着墨率。

用法：
    python verify_plot.py <图纸.pdf> [--page 210x297] [--bbox x0,y0,x1,y1] [--ref 参考.pdf]

  --page   期望页面尺寸 mm，默认 210x297
  --bbox   期望内容边界 mm（图纸坐标，y 向上），默认 5,5,205,297
  --ref    对照参考 PDF（通常是用户的模板图纸），输出逐段着墨率差异

判定标准：
  - 页面尺寸误差 < 1mm
  - 内容边界误差 < 1mm（允许线宽带来的零点几毫米）
  - 整页着墨率不应远低于参考图（低于 60% 说明有内容没打出来）
"""
import os
import sys

import pymupdf
import numpy as np

S = 25.4 / 72.0


def load_ink(path, dpi=250):
    d = pymupdf.open(path)
    pg = d[0]
    pix = pg.get_pixmap(dpi=dpi)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    a = a[:, :, :3].mean(axis=2)
    return (a < 200), pg.rect.width / 72 * 25.4, pg.rect.height / 72 * 25.4


def content_bbox(ink, w_mm, h_mm):
    h, w = ink.shape
    cols = ink.sum(axis=0)
    rows = ink.sum(axis=1)
    xs = [i for i, v in enumerate(cols > 0) if v]
    ys = [i for i, v in enumerate(rows > 0) if v]
    if not xs or not ys:
        return None
    return (xs[0] * w_mm / w, h_mm - ys[-1] * h_mm / h,
            xs[-1] * w_mm / w, h_mm - ys[0] * h_mm / h)


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__); sys.exit(1)

    target = argv[0]
    page = (210.0, 297.0)
    bbox = (5.0, 5.0, 205.0, 297.0)
    ref = None

    i = 1
    while i < len(argv):
        if argv[i] == "--page":
            page = tuple(float(v) for v in argv[i + 1].lower().split("x")); i += 2
        elif argv[i] == "--bbox":
            bbox = tuple(float(v) for v in argv[i + 1].split(",")); i += 2
        elif argv[i] == "--ref":
            ref = argv[i + 1]; i += 2
        else:
            i += 1

    ink, pw, ph = load_ink(target)
    print("目标:", os.path.basename(target))
    print("  页面尺寸: %.1f x %.1f mm  (期望 %.1f x %.1f)" % (pw, ph, page[0], page[1]))
    ok_page = abs(pw - page[0]) < 1 and abs(ph - page[1]) < 1
    print("  ->", "OK" if ok_page else "!! 页面尺寸不符")

    bb = content_bbox(ink, pw, ph)
    print("  内容边界: x %.1f~%.1f  y %.1f~%.1f" % (bb[0], bb[2], bb[1], bb[3]))
    print("  期望边界: x %.1f~%.1f  y %.1f~%.1f" % (bbox[0], bbox[2], bbox[1], bbox[3]))
    ok_bb = all(abs(a - b) < 1.0 for a, b in zip(bb, bbox))
    print("  ->", "OK" if ok_bb else "!! 内容偏移/被裁剪（检查是否用了 full_bleed 纸张）")

    ink_rate = ink.mean() * 100
    print("  整页着墨率: %.3f%%" % ink_rate)

    if ref and os.path.exists(ref):
        rink, _, _ = load_ink(ref)
        r_rate = rink.mean() * 100
        print("\n参考图:", os.path.basename(ref))
        print("  整页着墨率: %.3f%%" % r_rate)
        ratio = ink_rate / r_rate if r_rate else 0
        print("  比值: %.2f" % ratio)
        if ratio < 0.6:
            print("  !! 着墨率偏低，可能有内容未打印（检查图层/打印样式/打印范围）")
        else:
            print("  -> OK")

        print("\n  逐段对比 (y 从下往上, 20mm 一段):")
        h = ink.shape[0]
        rh = rink.shape[0]
        for y0 in range(0, int(page[1]), 20):
            y1 = min(y0 + 20, page[1])
            i1 = int(h * (1 - y0 / page[1])); i0 = int(h * (1 - y1 / page[1]))
            j1 = int(rh * (1 - y0 / page[1])); j0 = int(rh * (1 - y1 / page[1]))
            a = ink[i0:i1, :].mean() * 100
            b = rink[j0:j1, :].mean() * 100
            flag = "  <-- 空白!" if a < 0.01 and b > 0.5 else ""
            print("    %3d-%3d mm   新 %6.3f%%   参考 %6.3f%%%s" % (y0, y1, a, b, flag))

    print("\n建议：裁局部放大图用 Read 工具肉眼核对标题栏文字与关键剖面。")


if __name__ == "__main__":
    main()
