#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_typora_1.14.9.py
======================
Typora 1.14.9 (build 7785) macOS 教学激活绕过补丁（信息安全实验课作业用途）

⚠️ 版本适配说明
----------------
老师指引中的偏移仅适用于 1.10.8 (build 7385)。
本机安装的实验对象是 1.14.9 (build 7785)，
符号 vmaddr 已通过 nm/符号侦察重新定位，文件偏移已按各 slice 在 fat 中的
起始位置重新换算（x86_64 slice 起始 0x4000，arm64 slice 起始 0x194000）。

补丁策略不变（与指引 §4 相同）：
  [1] -[LicenseManager hasLicense]   -> 恒返回 YES   （mov w0,#1 / mov eax,1; ret）
      —— 切断所有本地判定收敛点（试用闸门、激活面板、给 JS 层的查询）
  [2] -[LicenseManager unfillLicense]-> 直接 ret
      —— 使服务器 12h 心跳复核无法“远程撤销”本地激活状态（防反噬）

本脚本仅校验并写入二进制字节；建议先备份，再用 codesign 重签名。
"""

import sys

# ---------- 可配置项 ----------
# 实验对象绝对路径
path = "/Applications/Typora.app/Contents/MacOS/Typora"
# 备份路径
backup = "/tmp/Typora.bak"

# ---------- 目标函数定位（本机 1.14.9 build 7785 实测） ----------
# nm 符号 vmaddr：
#   arm64  hasLicense   = 0x1000708cc | unfillLicense = 0x1000722f0
#   x86_64 hasLicense   = 0x100086d7d | unfillLicense = 0x100088ce4
# fat slice 起点：
#   x86_64 slice @ 0x4000 ; arm64 slice @ 0x194000 （本版与指引的 fat 布局不同！）
arm_slice = 0x194000
x86_slice = 0x4000

def fat_offset(slice_start, vmaddr):
    """slice 内 __TEXT vmaddr 基准 = 0x100000000，且 __TEXT seg 位于 slice 起点(fileoff 0)，
    故 fat 全文件偏移 = slice_start + (vmaddr - 0x100000000)"""
    return slice_start + (vmaddr - 0x100000000)

# (名称, 全文件偏移, 期望原字节, 补丁字节)
# arm64: mov w0, #1; ret  = 20 00 80 52 / c0 03 5f d6 ; ret = c0 03 5f d6
# x86_64: mov eax,1; ret  = b8 01 00 00 00 / c3        ; ret = c3
patches = [
    ("arm64  hasLicense",    fat_offset(arm_slice, 0x1000708cc),
     bytes.fromhex("000c40f9400000b4"),
     bytes.fromhex("20008052c0035fd6")),   # hasLicense 前8字节 -> mov w0,#1;ret
    ("arm64  unfillLicense", fat_offset(arm_slice, 0x1000722f0),
     bytes.fromhex("f44fbea9"),
     bytes.fromhex("c0035fd6")),           # 前4字节 -> ret
    ("x86_64 hasLicense",    fat_offset(x86_slice, 0x100086d7d),
     bytes.fromhex("488b7f1848 85".replace(" ","")),
     bytes.fromhex("b801000000c3")),       # 本机版开头无 push rbp，直接 mov 读 ivar；前6字节 -> mov eax,1;ret
    ("x86_64 unfillLicense", fat_offset(x86_slice, 0x100088ce4),
     bytes.fromhex("55"),
     bytes.fromhex("c3")),                 # 第1字节 push rbp -> ret
]

def main():
    # 备份
    import shutil
    shutil.copyfile(path, backup)
    print(f"[*] 已备份原二进制到 {backup}")

    data = bytearray(open(path, "rb").read())
    for name, off, orig, patch in patches:
        cur = bytes(data[off:off + len(orig)])
        if cur != orig:
            print(f"[FAIL] {name}: 原字节不匹配 @0x{off:x}，"
                  f"期望 {orig.hex()}，实际 {cur.hex()}")
            print("       -> 版本/符号定位可能不一致，已中止，未做任何写入。")
            sys.exit(1)
        data[off:off + len(patch)] = patch
        print(f"[OK ] {name} @0x{off:x}: {orig.hex()} -> {patch.hex()}")

    with open(path, "wb") as f:
        f.write(data)
    print("[*] 补丁写入完成。")
    print("\n下一步（需手动/确认执行）：")
    print("    codesign --force --sign - --timestamp=none /Applications/Typora.app")
    print("    codesign --verify --verbose=2 /Applications/Typora.app")

if __name__ == "__main__":
    main()
