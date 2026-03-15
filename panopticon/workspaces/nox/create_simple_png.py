#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建简单的组织图PNG
使用Python内置模块 + 原始像素操作
"""

import struct
import json

def create_png_from_text(text_lines, width=1200, height=1800, filename='RPA组织图.png'):
    """
    从文本创建简单的PNG图像
    """
    # PNG文件头
    png_signature = b'\x89PNG\r\n\x1a\n'

    def chunk(chunk_type, data):
        """创建PNG数据块"""
        chunk_data = chunk_type + data
        crc = 0xFFFFFFFF
        for byte in chunk_data:
            crc = crc ^ byte
            crc = crc & 0xFFFFFFFF
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc = crc >> 1
        crc = crc ^ 0xFFFFFFFF
        length = struct.pack('>I', len(data))
        return length + chunk_data + struct.pack('>I', crc)

    # IHDR块
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)  # RGBA
    ihdr = chunk(b'IHDR', ihdr_data)

    # 创建图像数据
    pixels = []
    for y in range(height):
        row = [0]  # 滤波器类型
        for x in range(width):
            line_index = y // 50
            if line_index < len(text_lines):
                line = text_lines[line_index]
                char_index = (x - 50) // 8
                if 0 <= char_index < len(line) and y % 50 < 40 and x >= 50 and x < width - 50:
                    if line[char_index] not in ' \t\n':
                        # 文字颜色（黑色）
                        row.extend([0, 0, 0, 255])
                    else:
                        # 背景颜色（白色）
                        row.extend([255, 255, 255, 255])
                else:
                    row.extend([255, 255, 255, 255])
            else:
                row.extend([255, 255, 255, 255])
        pixels.extend(row)

    # 压缩数据（简单的zlib压缩）
    import zlib
    raw_data = bytes(pixels)
    compressed_data = zlib.compress(raw_data)

    # IDAT块
    idat = chunk(b'IDAT', compressed_data)

    # IEND块
    iend = chunk(b'IEND', b'')

    # 写入PNG文件
    with open(filename, 'wb') as f:
        f.write(png_signature)
        f.write(ihdr)
        f.write(idat)
        f.write(iend)

    print(f"PNG文件已创建: {filename}")

# 读取通讯录数据
with open('/home/node/.openclaw/workspace/artifacts/rpa-contact-2026-03-13/artifact.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 生成文本行
text_lines = []
text_lines.append("RPA 业务组织图")
text_lines.append("=" * 60)
text_lines.append("")

# 按大类分类
categories = {
    '工程類': '工程类',
    '品質類': '品质类',
    '資材類': '资材类',
    '生產類': '生产类',
    '周边类': '周边类'
}

for func, label in categories.items():
    text_lines.append(f"【{label}】")
    for dept in data['departments']:
        if dept['function'] == func:
            text_lines.append(f"  {dept['name_short']} - {dept['name_long']} ({dept['code']})")
            text_lines.append(f"    主管: {dept['manager']} | 干事: {dept['officer']} | 种子: {dept['seed_count']}人")
    text_lines.append("")

# 添加统计信息
text_lines.append("=" * 60)
text_lines.append(f"总部门数: {data['summary']['total_departments']} 个")
for cat, count in data['summary']['categories'].items():
    text_lines.append(f"  {cat}: {count} 个")

# 创建PNG
create_png_from_text(text_lines, width=1400, height=1600, filename='/home/node/.openclaw/workspace/RPA组织图.png')
