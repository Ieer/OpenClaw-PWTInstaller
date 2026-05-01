#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 RPA 业务组织图
"""

from graphviz import Digraph
import json

# 读取通讯录数据
with open('/home/node/.openclaw/workspace/artifacts/rpa-contact-2026-03-13/artifact.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 创建有向图
dot = Digraph(comment='RPA业务组织图', format='png')
dot.attr(rankdir='TB', splines='ortho')
dot.attr('node', shape='box', style='rounded,filled', fontname='Arial')
dot.attr('edge', fontsize='10')

# 按大类分类
categories = {
    '工程類': {'color': '#4CAF50', 'label': '工程类'},
    '品質類': {'color': '#2196F3', 'label': '品质类'},
    '資材類': {'color': '#FF9800', 'label': '资材类'},
    '生產類': {'color': '#F44336', 'label': '生产类'},
    '周边类': {'color': '#9C27B0', 'label': '周边类'}
}

# 添加分类节点
for cat_key, cat_info in categories.items():
    dot.node(f'cat_{cat_key}', cat_info['label'], fillcolor=cat_info['color'], fontsize='14', fontweight='bold')

# 添加部门节点
for dept in data['departments']:
    func = dept['function']
    code = dept['code']
    name = dept['name_long']
    manager = dept['manager']
    officer = dept['officer']
    seed_count = dept['seed_count']

    # 部门节点
    dept_label = f"{dept['name_short']}\n{name}\n主管: {manager}\n干事: {officer}\n种子: {seed_count}人"
    dot.node(code, dept_label, fillcolor='#E3F2FD', fontsize='10')

    # 连接分类
    dot.edge(f'cat_{func}', code)

# 添加图例
with dot.subgraph(name='cluster_legend') as legend:
    legend.attr(label='图例', style='dashed')
    legend.node('legend_eng', '工程类', fillcolor='#4CAF50')
    legend.node('legend_qual', '品质类', fillcolor='#2196F3')
    legend.node('legend_mat', '资材类', fillcolor='#FF9800')
    legend.node('legend_prod', '生产类', fillcolor='#F44336')
    legend.node('legend_sur', '周边类', fillcolor='#9C27B0')

# 保存
output_path = '/home/node/.openclaw/workspace/RPA组织图'
dot.render(output_path, cleanup=True, format='png')

print(f"组织图已生成: {output_path}.png")
