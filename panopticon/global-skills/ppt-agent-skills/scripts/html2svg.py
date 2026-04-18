#!/usr/bin/env python3
"""HTML -> 真矢量 SVG 转换（文字保留为可编辑 <text> 元素）

核心方案：Puppeteer + dom-to-svg
- Puppeteer 在 headless 浏览器中打开 HTML
- dom-to-svg 直接将 DOM 树转为 SVG，保留 <text> 元素
- 不经过 PDF 中转，文字不会变成 path

降级方案：
- 优先使用 PNG 包裹 SVG（保住产物链，文字不可编辑）
- 最后尝试 Puppeteer PDF + pdf2svg（文字变 path，不可编辑）

首次运行自动安装依赖（dom-to-svg, puppeteer, esbuild）。

用法：
    python3 scripts/html2svg.py <html_dir_or_file> [-o output_dir]
"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Puppeteer + dom-to-svg bundle 注入脚本
CONVERT_SCRIPT = r"""
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

(async () => {
    const config = JSON.parse(process.argv[2]);
    const launchOptions = {
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
               
               '--font-render-hinting=none']
    };
    if (config.browserPath) {
        launchOptions.executablePath = config.browserPath;
    }
    const browser = await puppeteer.launch(launchOptions);

    for (const item of config.files) {
        const page = await browser.newPage();
        await page.setViewport({ width: 1280, height: 720 });

        await page.goto('file://' + item.html, {
            waitUntil: 'domcontentloaded',
            timeout: 60000
        });
        // 等待本地资源渲染（字体/图片 fallback 已足够）
        await new Promise(r => setTimeout(r, 1000));
        await new Promise(r => setTimeout(r, 1000));

        // 注入预打包的 dom-to-svg bundle
        await page.addScriptTag({ path: config.bundlePath });

        // 预处理：在 Node.js 端读取图片文件转 base64，传给浏览器替换 src
        // (浏览器端 canvas.toDataURL 会因 file:// CORS 被阻止)
        const imgSrcs = await page.evaluate(() => {
            const imgs = document.querySelectorAll('img');
            return Array.from(imgs).map(img => img.getAttribute('src') || '');
        });

        const imgDataMap = {};
        const htmlDir = path.dirname(item.html);  // HTML文件所在目录
        for (const src of imgSrcs) {
            if (!src) continue;
            if (src.startsWith('data:')) continue;  // 跳过已内联的
            // 处理 file:// 和绝对/相对路径
            let filePath = src;
            if (filePath.startsWith('file://')) filePath = filePath.slice(7);
            // 相对路径以HTML文件所在目录为基准resolve
            if (!path.isAbsolute(filePath)) {
                filePath = path.resolve(htmlDir, filePath);
            }
            if (fs.existsSync(filePath)) {
                const data = fs.readFileSync(filePath);
                const ext = path.extname(filePath).slice(1) || 'png';
                const mime = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;
                imgDataMap[src] = `data:${mime};base64,${data.toString('base64')}`;
            } else {
                console.warn('Image not found:', filePath, '(src:', src, ')');
            }
        }

        if (Object.keys(imgDataMap).length > 0) {
            await page.evaluate((dataMap) => {
                const imgs = document.querySelectorAll('img');
                for (const img of imgs) {
                    const origSrc = img.getAttribute('src');
                    if (origSrc && dataMap[origSrc]) {
                        img.src = dataMap[origSrc];
                    }
                }
            }, imgDataMap);
            // 等待图片重新渲染
            await new Promise(r => setTimeout(r, 300));
        }

        // === 预处理：将 dom-to-svg 不支持的 CSS 特性转为真实 DOM ===
        await page.evaluate(() => {
            // 1. 物化伪元素 ::before / ::after -> 真实 span
            // dom-to-svg 无法读取 CSS 伪元素，导致箭头/装饰丢失
            const all = document.querySelectorAll('*');
            for (const el of all) {
                for (const pseudo of ['::before', '::after']) {
                    const style = getComputedStyle(el, pseudo);
                    const content = style.content;
                    if (!content || content === 'none' || content === '""' || content === "''") continue;

                    const w = parseFloat(style.width) || 0;
                    const h = parseFloat(style.height) || 0;
                    const bg = style.backgroundColor;
                    const border = style.borderTopWidth;
                    const borderColor = style.borderTopColor;

                    // 只处理有尺寸或有边框的伪元素（箭头/装饰块）
                    if ((w > 0 || h > 0 || parseFloat(border) > 0) && content !== 'normal') {
                        const span = document.createElement('span');
                        span.style.display = style.display === 'none' ? 'none' : 'inline-block';
                        span.style.position = style.position;
                        span.style.width = style.width;
                        span.style.height = style.height;
                        span.style.backgroundColor = bg;
                        span.style.borderTop = style.borderTop;
                        span.style.borderRight = style.borderRight;
                        span.style.borderBottom = style.borderBottom;
                        span.style.borderLeft = style.borderLeft;
                        span.style.transform = style.transform;
                        span.style.top = style.top;
                        span.style.left = style.left;
                        span.style.right = style.right;
                        span.style.bottom = style.bottom;
                        span.style.borderRadius = style.borderRadius;
                        span.setAttribute('data-pseudo', pseudo);

                        // 文本内容（去掉引号）
                        const textContent = content.replace(/^["']|["']$/g, '');
                        if (textContent && textContent !== 'normal' && textContent !== 'none') {
                            span.textContent = textContent;
                            span.style.color = style.color;
                            span.style.fontSize = style.fontSize;
                            span.style.fontWeight = style.fontWeight;
                        }

                        if (pseudo === '::before') {
                            el.insertBefore(span, el.firstChild);
                        } else {
                            el.appendChild(span);
                        }
                    }
                }
            }

            // 2. 将 conic-gradient 环形图转为 SVG
            // 查找带有 conic-gradient 背景的元素
            for (const el of document.querySelectorAll('*')) {
                const bg = el.style.background || el.style.backgroundImage || '';
                const computed = getComputedStyle(el);
                const bgImage = computed.backgroundImage || '';

                if (!bgImage.includes('conic-gradient')) continue;

                const rect = el.getBoundingClientRect();
                const size = Math.min(rect.width, rect.height);
                if (size <= 0) continue;

                // 解析 conic-gradient 的百分比和颜色
                const match = bgImage.match(/conic-gradient\(([^)]+)\)/);
                if (!match) continue;

                const gradStr = match[1];
                // 提取百分比（典型格式: #color 0% 75%, #color2 75% 100%）
                const percMatch = gradStr.match(/([\d.]+)%/g);
                let percentage = 75; // 默认
                if (percMatch && percMatch.length >= 2) {
                    percentage = parseFloat(percMatch[1]);
                }

                // 提取颜色
                const colorMatch = gradStr.match(/(#[0-9a-fA-F]{3,8}|rgb[a]?\([^)]+\))/g);
                const mainColor = colorMatch ? colorMatch[0] : '#4CAF50';
                const bgColor = colorMatch && colorMatch.length > 1 ? colorMatch[1] : '#e0e0e0';

                // 创建 SVG 替换
                const svgNS = 'http://www.w3.org/2000/svg';
                const svg = document.createElementNS(svgNS, 'svg');
                svg.setAttribute('width', String(size));
                svg.setAttribute('height', String(size));
                svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
                svg.style.display = el.style.display || 'block';
                svg.style.position = computed.position;
                svg.style.top = computed.top;
                svg.style.left = computed.left;

                const cx = size / 2, cy = size / 2;
                const r = size * 0.4;
                const circumference = 2 * Math.PI * r;
                const strokeWidth = size * 0.15;

                // 背景圆环
                const bgCircle = document.createElementNS(svgNS, 'circle');
                bgCircle.setAttribute('cx', String(cx));
                bgCircle.setAttribute('cy', String(cy));
                bgCircle.setAttribute('r', String(r));
                bgCircle.setAttribute('fill', 'none');
                bgCircle.setAttribute('stroke', bgColor);
                bgCircle.setAttribute('stroke-width', String(strokeWidth));

                // 进度圆环
                const fgCircle = document.createElementNS(svgNS, 'circle');
                fgCircle.setAttribute('cx', String(cx));
                fgCircle.setAttribute('cy', String(cy));
                fgCircle.setAttribute('r', String(r));
                fgCircle.setAttribute('fill', 'none');
                fgCircle.setAttribute('stroke', mainColor);
                fgCircle.setAttribute('stroke-width', String(strokeWidth));
                fgCircle.setAttribute('stroke-dasharray', `${circumference * percentage / 100} ${circumference}`);
                fgCircle.setAttribute('stroke-linecap', 'round');
                fgCircle.setAttribute('transform', `rotate(-90 ${cx} ${cy})`);

                svg.appendChild(bgCircle);
                svg.appendChild(fgCircle);

                // 保留子元素（如百分比文字），放到 foreignObject 不行
                // 直接添加 SVG text
                const textEl = el.querySelector('*');
                if (el.textContent && el.textContent.trim()) {
                    const svgText = document.createElementNS(svgNS, 'text');
                    svgText.setAttribute('x', String(cx));
                    svgText.setAttribute('y', String(cy));
                    svgText.setAttribute('text-anchor', 'middle');
                    svgText.setAttribute('dominant-baseline', 'central');
                    svgText.setAttribute('fill', computed.color);
                    svgText.setAttribute('font-size', computed.fontSize);
                    svgText.setAttribute('font-weight', computed.fontWeight);
                    svgText.textContent = el.textContent.trim();
                    svg.appendChild(svgText);
                }

                el.style.background = 'none';
                el.style.backgroundImage = 'none';
                el.insertBefore(svg, el.firstChild);
            }

            // 3. 将 CSS border 三角形箭头修复
            // 查找宽高为 0 但有 border 的元素（CSS 三角形技巧）
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                const w = parseFloat(cs.width);
                const h = parseFloat(cs.height);
                if (w !== 0 || h !== 0) continue;

                const bt = parseFloat(cs.borderTopWidth) || 0;
                const br = parseFloat(cs.borderRightWidth) || 0;
                const bb = parseFloat(cs.borderBottomWidth) || 0;
                const bl = parseFloat(cs.borderLeftWidth) || 0;

                // 至少两个边框有宽度才是三角形
                const borders = [bt, br, bb, bl].filter(v => v > 0);
                if (borders.length < 2) continue;

                const btc = cs.borderTopColor;
                const brc = cs.borderRightColor;
                const bbc = cs.borderBottomColor;
                const blc = cs.borderLeftColor;

                // 找有色边框（非 transparent）
                const nonTransparent = [];
                if (bt > 0 && !btc.includes('0)') && btc !== 'transparent') nonTransparent.push({dir: 'top', size: bt, color: btc});
                if (br > 0 && !brc.includes('0)') && brc !== 'transparent') nonTransparent.push({dir: 'right', size: br, color: brc});
                if (bb > 0 && !bbc.includes('0)') && bbc !== 'transparent') nonTransparent.push({dir: 'bottom', size: bb, color: bbc});
                if (bl > 0 && !blc.includes('0)') && blc !== 'transparent') nonTransparent.push({dir: 'left', size: bl, color: blc});

                if (nonTransparent.length !== 1) continue;

                // 用实际尺寸的 div 替换
                const arrow = nonTransparent[0];
                const totalW = bl + br;
                const totalH = bt + bb;
                el.style.width = totalW + 'px';
                el.style.height = totalH + 'px';
                el.style.border = 'none';

                // 用 SVG 绘制三角形
                const svgNS = 'http://www.w3.org/2000/svg';
                const svg = document.createElementNS(svgNS, 'svg');
                svg.setAttribute('width', String(totalW));
                svg.setAttribute('height', String(totalH));
                svg.style.display = 'block';
                svg.style.overflow = 'visible';

                const polygon = document.createElementNS(svgNS, 'polygon');
                let points = '';
                if (arrow.dir === 'bottom') points = `0,0 ${totalW},0 ${totalW/2},${totalH}`;
                else if (arrow.dir === 'top') points = `${totalW/2},0 0,${totalH} ${totalW},${totalH}`;
                else if (arrow.dir === 'right') points = `0,0 ${totalW},${totalH/2} 0,${totalH}`;
                else if (arrow.dir === 'left') points = `${totalW},0 0,${totalH/2} ${totalW},${totalH}`;
                polygon.setAttribute('points', points);
                polygon.setAttribute('fill', arrow.color);
                svg.appendChild(polygon);
                el.appendChild(svg);
            }

            // 4. 修复 background-clip: text 渐变文字
            // dom-to-svg 不支持此特性，导致渐变背景变成色块、文字变白
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                const bgClip = cs.webkitBackgroundClip || cs.backgroundClip || '';
                if (bgClip !== 'text') continue;

                // 提取渐变/背景中的主色作为文字颜色
                const bgImage = cs.backgroundImage || '';
                let mainColor = '#FF6900'; // fallback
                const colorMatch = bgImage.match(/(#[0-9a-fA-F]{3,8}|rgb[a]?\([^)]+\))/);
                if (colorMatch) mainColor = colorMatch[1];

                // 清除渐变背景效果，改用直接 color
                el.style.backgroundImage = 'none';
                el.style.background = 'none';
                el.style.webkitBackgroundClip = 'border-box';
                el.style.backgroundClip = 'border-box';
                el.style.webkitTextFillColor = 'unset';
                el.style.color = mainColor;
                console.warn('html2svg fallback: background-clip:text -> color:' + mainColor, el.tagName);
            }

            // 5. 修复 -webkit-text-fill-color（非 background-clip:text 的独立使用）
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                const fillColor = cs.webkitTextFillColor;
                if (!fillColor || fillColor === cs.color) continue;
                // 如果 text-fill-color 与 color 不同，SVG 中会丢失
                // 将 text-fill-color 值应用到 color
                if (fillColor !== 'rgba(0, 0, 0, 0)' && fillColor !== 'transparent') {
                    el.style.color = fillColor;
                    el.style.webkitTextFillColor = 'unset';
                }
            }

            // 6. 修复 mask-image / -webkit-mask-image（SVG 不支持）
            // 根据元素层级智能降级：底层图片降透明度，前景元素直接移除蒙版
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                const maskImg = cs.maskImage || cs.webkitMaskImage || '';
                if (!maskImg || maskImg === 'none') continue;

                // 清除 mask
                el.style.maskImage = 'none';
                el.style.webkitMaskImage = 'none';

                // 判断是否为底层装饰图片（通过 z-index、pointer-events、opacity 推断）
                const zIndex = parseInt(cs.zIndex) || 0;
                const pointerEvents = cs.pointerEvents;
                const isImg = el.tagName === 'IMG';
                const currentOpacity = parseFloat(cs.opacity) || 1;

                if (isImg || pointerEvents === 'none' || zIndex <= 0) {
                    // 底层氛围图：降低透明度 + 限制尺寸，不要遮挡内容
                    const newOpacity = Math.min(currentOpacity, 0.15);
                    el.style.opacity = String(newOpacity);
                    // 如果图片过大，限制为容器的合理比例
                    if (isImg) {
                        const parent = el.parentElement;
                        if (parent) {
                            const parentRect = parent.getBoundingClientRect();
                            const elRect = el.getBoundingClientRect();
                            if (elRect.width > parentRect.width * 0.8) {
                                el.style.maxWidth = '60%';
                                el.style.maxHeight = '60%';
                            }
                        }
                    }
                    console.warn('html2svg fallback: mask-image -> opacity:' + newOpacity + ' (background layer)', el.tagName);
                } else {
                    // 前景元素：只移除蒙版，保持原样
                    console.warn('html2svg fallback: mask-image removed (foreground)', el.tagName);
                }
            }

            // 7. 修复 background-image: url() -> 转为 <img> 标签
            // dom-to-svg 忽略 CSS background-image，导致背景图完全消失
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                const bgImg = cs.backgroundImage || '';
                if (!bgImg || bgImg === 'none') continue;
                // 跳过渐变（渐变是安全的）
                if (bgImg.startsWith('linear-gradient') || bgImg.startsWith('radial-gradient')
                    || bgImg.startsWith('repeating-')) continue;
                const urlMatch = bgImg.match(/url\(["']?([^"')]+)["']?\)/);
                if (!urlMatch) continue;
                const url = urlMatch[1];
                if (url.startsWith('data:')) continue; // data URI 背景保留

                const img = document.createElement('img');
                img.src = url;
                img.style.position = 'absolute';
                img.style.top = '0'; img.style.left = '0';
                img.style.width = '100%'; img.style.height = '100%';
                img.style.objectFit = 'cover';
                img.style.pointerEvents = 'none';
                if (cs.position === 'static') el.style.position = 'relative';
                el.style.backgroundImage = 'none';
                el.insertBefore(img, el.firstChild);
                console.warn('html2svg fix: background-image:url() -> <img>', el.tagName);
            }

            // 8. 移除 clip-path（svg2pptx 不支持 clipPath）
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                if (cs.clipPath && cs.clipPath !== 'none') {
                    el.style.clipPath = 'none';
                    el.style.webkitClipPath = 'none';
                    if (!el.style.overflow) el.style.overflow = 'hidden';
                    console.warn('html2svg fix: clip-path -> overflow:hidden', el.tagName);
                }
            }

            // 9. 移除 backdrop-filter（dom-to-svg 不支持）
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                const bf = cs.backdropFilter || cs.webkitBackdropFilter || '';
                if (bf && bf !== 'none') {
                    el.style.backdropFilter = 'none';
                    el.style.webkitBackdropFilter = 'none';
                    console.warn('html2svg fix: backdrop-filter removed', el.tagName);
                }
            }

            // 10. 修复 CSS filter（blur/drop-shadow -> 移除以防光栅化）
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                const filter = cs.filter || '';
                if (!filter || filter === 'none') continue;
                if (filter.includes('blur(')) {
                    el.style.filter = 'none';
                    el.style.opacity = String(Math.min(parseFloat(cs.opacity) || 1, 0.7));
                    console.warn('html2svg fix: filter:blur() -> opacity', el.tagName);
                } else if (filter.includes('drop-shadow(')) {
                    const m = filter.match(/drop-shadow\(([^)]+)\)/);
                    el.style.filter = 'none';
                    if (m) el.style.boxShadow = m[1];
                    console.warn('html2svg fix: drop-shadow -> box-shadow', el.tagName);
                }
            }

            // 11. 移除 mix-blend-mode（svg2pptx 不支持）
            for (const el of document.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                if (cs.mixBlendMode && cs.mixBlendMode !== 'normal') {
                    el.style.mixBlendMode = 'normal';
                    console.warn('html2svg fix: mix-blend-mode removed', el.tagName);
                }
            }

            // 12. 将内联 SVG 中的 <text> 元素提取为 HTML 叠加层
            // svg2pptx 处理 SVG text 有 baseline 偏移问题，HTML 定位更精确
            for (const svg of document.querySelectorAll('svg')) {
                // 跳过页面级 SVG（非用户内联的）
                if (!svg.parentElement || svg.parentElement === document.body) continue;
                const texts = Array.from(svg.querySelectorAll('text'));
                if (texts.length === 0) continue;

                const parent = svg.parentElement;
                const pcs = getComputedStyle(parent);
                if (pcs.position === 'static') parent.style.position = 'relative';
                const parentRect = parent.getBoundingClientRect();

                for (const text of texts) {
                    try {
                        // 跳过带旋转的文字（HTML 难以精确复制）
                        const tf = text.getAttribute('transform') || '';
                        if (tf.includes('rotate') || tf.includes('skew')) continue;

                        const tspans = text.querySelectorAll('tspan');
                        const items = tspans.length > 0 ? Array.from(tspans) : [text];

                        for (const item of items) {
                            const content = item.textContent;
                            if (!content || !content.trim()) continue;
                            const itemRect = item.getBoundingClientRect();
                            if (itemRect.width === 0 && itemRect.height === 0) continue;

                            const fill = item.getAttribute('fill') || text.getAttribute('fill')
                                || text.getAttribute('color') || '#000';
                            const fs = (item.getAttribute('font-size') || text.getAttribute('font-size') || '14')
                                .replace('px', '');
                            const fw = item.getAttribute('font-weight') || text.getAttribute('font-weight') || '400';
                            const ff = item.getAttribute('font-family') || text.getAttribute('font-family') || '';
                            const op = item.getAttribute('opacity') || text.getAttribute('opacity') || '';

                            const span = document.createElement('span');
                            span.textContent = content.trim();
                            span.style.position = 'absolute';
                            span.style.left = (itemRect.left - parentRect.left) + 'px';
                            span.style.top = (itemRect.top - parentRect.top) + 'px';
                            span.style.fontSize = fs + 'px';
                            span.style.fontWeight = fw;
                            span.style.color = fill;
                            if (ff) span.style.fontFamily = ff;
                            if (op) span.style.opacity = op;
                            span.style.lineHeight = '1.2';
                            span.style.whiteSpace = 'nowrap';
                            span.style.pointerEvents = 'none';

                            parent.appendChild(span);
                        }
                        text.remove();
                        console.warn('html2svg fix: SVG <text> -> HTML overlay');
                    } catch (e) {
                        // 失败时保留原始 SVG text
                    }
                }
            }

            // 13. 展开 <use> 引用为实际元素（svg2pptx 不递归展开 <use>）
            for (const svg of document.querySelectorAll('svg')) {
                const uses = Array.from(svg.querySelectorAll('use'));
                for (const use of uses) {
                    const href = use.getAttribute('href')
                        || use.getAttributeNS('http://www.w3.org/1999/xlink', 'href');
                    if (!href || !href.startsWith('#')) continue;
                    try {
                        const ref = svg.querySelector(href);
                        if (!ref) continue;
                        const clone = ref.cloneNode(true);
                        clone.removeAttribute('id');
                        const ux = use.getAttribute('x') || '0';
                        const uy = use.getAttribute('y') || '0';
                        if (ux !== '0' || uy !== '0') {
                            const et = clone.getAttribute('transform') || '';
                            clone.setAttribute('transform', ('translate(' + ux + ',' + uy + ') ' + et).trim());
                        }
                        for (const attr of ['fill', 'stroke', 'opacity', 'stroke-width']) {
                            if (use.hasAttribute(attr)) clone.setAttribute(attr, use.getAttribute(attr));
                        }
                        use.parentNode.replaceChild(clone, use);
                        console.warn('html2svg fix: <use> expanded inline');
                    } catch (e) {}
                }
            }
        });
        await new Promise(r => setTimeout(r, 300));

        // === 执行 DOM -> SVG 转换 ===
        let svgString = await page.evaluate(async () => {
            const { documentToSVG, inlineResources } = window.__domToSvg;
            const svgDoc = documentToSVG(document);
            await inlineResources(svgDoc.documentElement);

            // 后处理：将 <text> 的 color 属性转为 fill（SVG 标准）
            const texts = svgDoc.querySelectorAll('text');
            for (const t of texts) {
                const c = t.getAttribute('color');
                if (c && !t.getAttribute('fill')) {
                    t.setAttribute('fill', c);
                    t.removeAttribute('color');
                }
            }

            return new XMLSerializer().serializeToString(svgDoc);
        });

        const semanticData = await page.evaluate(() => {
            const normalizeText = (value) => String(value || '')
                .replace(/\u00a0/g, ' ')
                .replace(/\s+/g, ' ')
                .trim();
            const rectToObject = (rect) => ({
                x: Number(rect.left.toFixed(2)),
                y: Number(rect.top.toFixed(2)),
                width: Number(rect.width.toFixed(2)),
                height: Number(rect.height.toFixed(2)),
            });
            const isVisible = (el) => {
                if (!el) return false;
                const style = getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none'
                    && style.visibility !== 'hidden'
                    && Number(style.opacity || '1') > 0
                    && rect.width > 0
                    && rect.height > 0;
            };
            const cardRole = (cardId, node) => {
                const explicitRole = node.getAttribute('data-role');
                if (explicitRole) return explicitRole;
                if (!cardId) return null;
                const parts = cardId.split('-');
                return parts.length >= 2 ? parts[1] : null;
            };
            const hasNestedCard = (node, root) => {
                const closest = node.closest('[data-card-id]');
                return Boolean(closest && closest !== root);
            };
            const areaOf = (bbox) => Number((bbox.width * bbox.height).toFixed(2));
            const blockForNode = (node, blockRoots) => {
                for (const blockNode of blockRoots) {
                    if (blockNode.contains(node)) {
                        return blockNode;
                    }
                }
                return null;
            };
            const chartTypeHint = (node) => {
                const dataType = node.getAttribute('data-chart-type')
                    || node.getAttribute('data-chart-kind')
                    || node.getAttribute('data-chart-id');
                if (dataType) return dataType;
                const classText = String(node.className || '').toLowerCase();
                const tag = node.tagName.toLowerCase();
                const checks = [
                    ['progress_bar', ['progress', 'meter']],
                    ['comparison_bar', ['comparison-bar', 'bar-chart', 'bars']],
                    ['stacked_bar', ['stacked-bar', 'stacked_bar', 'stack']],
                    ['ring', ['ring', 'donut']],
                    ['metric_row', ['metric-row', 'metric_row', 'metrics-row']],
                    ['kpi', ['kpi', 'metric']],
                    ['sparkline', ['sparkline', 'trend']],
                    ['rating', ['rating', 'score', 'star-rating']],
                    ['radar', ['radar']],
                    ['funnel', ['funnel']],
                    ['timeline', ['timeline']],
                    ['waffle', ['waffle']],
                    ['treemap', ['treemap']],
                ];
                for (const [typeName, tokens] of checks) {
                    if (tokens.some((token) => classText.includes(token))) {
                        return typeName;
                    }
                }
                if (tag === 'svg') {
                    const circles = node.querySelectorAll('circle').length;
                    const rects = node.querySelectorAll('rect').length;
                    if (circles >= 2) return 'ring';
                    if (rects >= 2) return 'comparison_bar';
                }
                return 'chart_like';
            };
            const semanticTextSelector = 'h1,h2,h3,h4,h5,h6,p,li,caption,figcaption,th,td';
            const chartSelector = 'svg,canvas,[data-chart-id],[data-chart-type],[data-chart-kind],.chart,.chart-card,[class*="chart"],[class*="kpi"],[class*="metric"],[class*="progress"],[class*="ring"],[class*="stack"],[class*="sparkline"],[class*="rating"],[class*="score"],[class*="radar"],[class*="funnel"],[class*="timeline"],[class*="waffle"],[class*="treemap"],[role="img"]';
            const cardRoots = Array.from(document.querySelectorAll('[data-card-id]')).filter(isVisible);
            const blockRoots = cardRoots.length ? cardRoots : [document.body];
            const blockIndexByNode = new Map();
            const blocks = blockRoots.map((node, index) => {
                blockIndexByNode.set(node, index);
                const blockId = node.getAttribute('data-card-id') || `page-root-${index + 1}`;
                const semanticTextCount = Array.from(node.querySelectorAll(semanticTextSelector))
                    .filter((entry) => isVisible(entry) && !hasNestedCard(entry, node))
                    .filter((entry) => normalizeText(entry.textContent).length > 0)
                    .length;
                return {
                    block_id: blockId,
                    card_id: node.getAttribute('data-card-id') || null,
                    role_hint: cardRole(node.getAttribute('data-card-id'), node),
                    tag: node.tagName.toLowerCase(),
                    class_name: node.className || '',
                    bbox: rectToObject(node.getBoundingClientRect()),
                    contains_table: Boolean(node.querySelector('table')),
                    contains_chart_like: Boolean(node.querySelector(chartSelector)),
                    semantic_text_count: semanticTextCount,
                };
            });

            const chartCandidates = Array.from(document.querySelectorAll(chartSelector))
                .filter(isVisible)
                .filter((node) => !node.closest('table'))
                .filter((node) => {
                    const rect = node.getBoundingClientRect();
                    return rect.width >= 36 && rect.height >= 8 && (rect.width * rect.height) >= 800;
                })
                .filter((node) => {
                    const parentCandidate = node.parentElement && node.parentElement.closest(chartSelector);
                    return !parentCandidate || parentCandidate === node.closest(chartSelector);
                });

            const charts = chartCandidates.map((node, index) => {
                const owningBlock = blockForNode(node, blockRoots);
                const blockId = owningBlock
                    ? blocks[blockIndexByNode.get(owningBlock)].block_id
                    : null;
                const textSamples = Array.from(node.querySelectorAll(semanticTextSelector))
                    .filter(isVisible)
                    .map((entry) => normalizeText(entry.textContent))
                    .filter(Boolean)
                    .slice(0, 6);
                const bbox = rectToObject(node.getBoundingClientRect());
                return {
                    chart_id: `chart-${index + 1}`,
                    block_id: blockId,
                    tag: node.tagName.toLowerCase(),
                    class_name: String(node.className || ''),
                    chart_type_hint: chartTypeHint(node),
                    bbox,
                    area: areaOf(bbox),
                    text_samples: textSamples,
                };
            });

            const tables = Array.from(document.querySelectorAll('table'))
                .filter(isVisible)
                .map((table, tableIndex) => {
                    const owningBlock = blockForNode(table, blockRoots);
                    const rows = Array.from(table.rows).map((row, rowIndex) => (
                        Array.from(row.cells).map((cell, cellIndex) => {
                            const style = getComputedStyle(cell);
                            return {
                                row_index: rowIndex,
                                cell_index: cellIndex,
                                tag: cell.tagName.toLowerCase(),
                                text: normalizeText(cell.innerText || cell.textContent),
                                colspan: Number(cell.colSpan || 1),
                                rowspan: Number(cell.rowSpan || 1),
                                bbox: rectToObject(cell.getBoundingClientRect()),
                                styles: {
                                    background_color: style.backgroundColor,
                                    color: style.color,
                                    font_size: style.fontSize,
                                    font_weight: style.fontWeight,
                                    text_align: style.textAlign,
                                    vertical_align: style.verticalAlign,
                                    border_top_color: style.borderTopColor,
                                    border_right_color: style.borderRightColor,
                                    border_bottom_color: style.borderBottomColor,
                                    border_left_color: style.borderLeftColor,
                                },
                            };
                        })
                    ));
                    const blockId = owningBlock
                        ? blocks[blockIndexByNode.get(owningBlock)].block_id
                        : null;
                    return {
                        table_id: `table-${tableIndex + 1}`,
                        block_id: blockId,
                        bbox: rectToObject(table.getBoundingClientRect()),
                        row_count: rows.length,
                        cell_count: rows.reduce((count, row) => count + row.length, 0),
                        rows,
                    };
                });

            return {
                generated_at: new Date().toISOString(),
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight,
                },
                summary: {
                    blocks: blocks.length,
                    tables: tables.length,
                    charts: charts.length,
                    chart_like_blocks: blocks.filter((block) => block.contains_chart_like).length,
                },
                blocks,
                charts,
                tables,
            };
        });

        fs.writeFileSync(item.svg, svgString, 'utf-8');
        if (item.semantic) {
            fs.writeFileSync(item.semantic, JSON.stringify(semanticData, null, 2), 'utf-8');
        }
        console.log('SVG: ' + path.basename(item.html));
        await page.close();
    }

    await browser.close();
    console.log('Done: ' + config.files.length + ' SVGs');
})();
"""

# 降级 PDF 方案脚本
FALLBACK_SCRIPT = r"""
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

(async () => {
    const config = JSON.parse(process.argv[2]);
    const launchOptions = {
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
               
               '--font-render-hinting=none']
    };
    if (config.browserPath) {
        launchOptions.executablePath = config.browserPath;
    }
    const browser = await puppeteer.launch(launchOptions);

    for (const item of config.files) {
        const page = await browser.newPage();
        await page.setViewport({ width: 1280, height: 720 });
        await page.goto('file://' + item.html, {
            waitUntil: 'domcontentloaded',
            timeout: 60000
        });
        await new Promise(r => setTimeout(r, 1000));
        await page.pdf({
            path: item.pdf,
            width: '1280px',
            height: '720px',
            printBackground: true,
            preferCSSPageSize: true
        });
        console.log('PDF: ' + path.basename(item.html));
        await page.close();
    }
    await browser.close();
    console.log('Done: ' + config.files.length + ' PDFs');
})();
"""

# esbuild 打包入口
BUNDLE_ENTRY = """\
import { documentToSVG, elementToSVG, inlineResources } from 'dom-to-svg';
window.__domToSvg = { documentToSVG, elementToSVG, inlineResources };
"""

# bundle.js 固定放在 skill 根目录（scripts/ 的父目录），所有 run 共享，一次打包永久复用
_SKILL_DIR = Path(__file__).resolve().parent.parent
_CANONICAL_BUNDLE_PATH = _SKILL_DIR / "dom-to-svg.bundle.js"
NODE_DEPS_DIR = Path(
    os.environ.get("PPT_AGENT_NODE_DEPS_DIR")
    or (Path.home() / ".cache" / "ppt-agent-skills-node")
).resolve()
REPORT_FILE_NAME = "svg-export-report.json"
SEMANTIC_SUFFIX = ".semantic.json"
PUPPETEER_BROWSER_ENV_VARS = (
    "PUPPETEER_EXECUTABLE_PATH",
    "CHROME_BIN",
    "CHROMIUM_PATH",
)
COMMON_BROWSER_PATHS = (
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/snap/bin/chromium",
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path, base_dir: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(base_dir.resolve()))
    except ValueError:
        return str(resolved)


def _report_path_for(work_dir: Path, report_path: str | None = None) -> Path:
    if report_path:
        return Path(report_path).resolve()
    return (work_dir / REPORT_FILE_NAME).resolve()


def _semantic_path_for(output_dir: Path, html_file: Path) -> Path:
    return (output_dir / f"{html_file.stem}{SEMANTIC_SUFFIX}").resolve()


def _inspect_semantic_payload(semantic_path: Path | None) -> dict[str, int]:
    if semantic_path is None or not semantic_path.exists():
        return {
            "block_count": 0,
            "table_count": 0,
            "chart_count": 0,
            "chart_like_block_count": 0,
        }
    try:
        payload = json.loads(semantic_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "block_count": 0,
            "table_count": 0,
            "chart_count": 0,
            "chart_like_block_count": 0,
        }
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if isinstance(summary, dict):
        return {
            "block_count": int(summary.get("blocks") or 0),
            "table_count": int(summary.get("tables") or 0),
            "chart_count": int(summary.get("charts") or 0),
            "chart_like_block_count": int(summary.get("chart_like_blocks") or 0),
        }
    return {
        "block_count": 0,
        "table_count": 0,
        "chart_count": 0,
        "chart_like_block_count": 0,
    }


def resolve_browser_executable() -> str | None:
    for env_name in PUPPETEER_BROWSER_ENV_VARS:
        raw = os.environ.get(env_name)
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if candidate.exists():
            return str(candidate.resolve())
    for binary_name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        resolved = shutil.which(binary_name)
        if resolved:
            return str(Path(resolved).resolve())
    for raw in COMMON_BROWSER_PATHS:
        candidate = Path(raw)
        if candidate.exists():
            return str(candidate.resolve())
    return None


def _subprocess_env(*, browser_path: str | None = None, skip_browser_download: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    node_path_parts = [str((NODE_DEPS_DIR / "node_modules").resolve())]
    existing_node_path = env.get("NODE_PATH")
    if existing_node_path:
        node_path_parts.append(existing_node_path)
    env["NODE_PATH"] = os.pathsep.join(node_path_parts)
    if browser_path:
        env.setdefault("PUPPETEER_EXECUTABLE_PATH", browser_path)
        env.setdefault("CHROME_BIN", browser_path)
    if skip_browser_download:
        env["PUPPETEER_SKIP_DOWNLOAD"] = "1"
        env["PUPPETEER_SKIP_CHROMIUM_DOWNLOAD"] = "1"
    return env


def _inspect_svg(svg_path: Path) -> dict[str, int]:
    try:
        content = svg_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {
            "text_count": 0,
            "image_count": 0,
            "path_count": 0,
        }
    return {
        "text_count": content.count("<text "),
        "image_count": content.count("<image "),
        "path_count": content.count("<path "),
    }


def _make_page_result(
    *,
    page_number: int,
    html_file: Path,
    svg_path: Path,
    work_dir: Path,
    method: str,
    editable: bool,
    success: bool,
    warning: str | None = None,
    semantic_path: Path | None = None,
) -> dict[str, object]:
    metrics = _inspect_svg(svg_path) if svg_path.exists() else {
        "text_count": 0,
        "image_count": 0,
        "path_count": 0,
    }
    semantic_metrics = _inspect_semantic_payload(semantic_path)
    page_warning = warning
    if success and method == "dom_to_svg_editable" and metrics["text_count"] == 0 and page_warning is None:
        page_warning = "no_text_nodes_detected"
    if success and method == "dom_to_svg_editable" and semantic_path is not None and not semantic_path.exists() and page_warning is None:
        page_warning = "semantic_sidecar_missing"
    return {
        "page_number": page_number,
        "page_name": html_file.stem,
        "source_html": _display_path(html_file, work_dir),
        "source_svg": _display_path(svg_path, work_dir),
        "semantic_path": _display_path(semantic_path, work_dir) if semantic_path and semantic_path.exists() else None,
        "method": method,
        "editable": editable,
        "success": success,
        "text_count": metrics["text_count"],
        "image_count": metrics["image_count"],
        "path_count": metrics["path_count"],
        "block_count": semantic_metrics["block_count"],
        "table_count": semantic_metrics["table_count"],
        "chart_count": semantic_metrics["chart_count"],
        "chart_like_block_count": semantic_metrics["chart_like_block_count"],
        "warning": page_warning,
    }


def _build_failed_page_results(html_files: list[Path], output_dir: Path, work_dir: Path, warning: str) -> list[dict[str, object]]:
    return [
        _make_page_result(
            page_number=index,
            html_file=html_file,
            svg_path=output_dir / f"{html_file.stem}.svg",
            work_dir=work_dir,
            method="failed",
            editable=False,
            success=False,
            warning=warning,
        )
        for index, html_file in enumerate(html_files, start=1)
    ]


def _build_export_report(
    *,
    html_input: Path,
    output_dir: Path,
    work_dir: Path,
    page_results: list[dict[str, object]],
) -> dict[str, object]:
    editable_pages = sum(1 for page in page_results if bool(page.get("editable")))
    raster_fallback_pages = sum(1 for page in page_results if page.get("method") == "png_wrapper_raster")
    pathified_pages = sum(1 for page in page_results if page.get("method") == "pdf2svg_pathified")
    failed_pages = sum(1 for page in page_results if not bool(page.get("success")))
    warning_pages = sum(1 for page in page_results if page.get("warning"))
    semantic_pages = sum(1 for page in page_results if page.get("semantic_path"))
    block_count = sum(int(page.get("block_count") or 0) for page in page_results)
    table_count = sum(int(page.get("table_count") or 0) for page in page_results)
    chart_count = sum(int(page.get("chart_count") or 0) for page in page_results)
    chart_like_blocks = sum(int(page.get("chart_like_block_count") or 0) for page in page_results)
    return {
        "generated_at": _iso_now(),
        "html_input": _display_path(html_input, work_dir),
        "svg_output_dir": _display_path(output_dir, work_dir),
        "summary": {
            "total_pages": len(page_results),
            "editable_pages": editable_pages,
            "raster_fallback_pages": raster_fallback_pages,
            "pathified_pages": pathified_pages,
            "failed_pages": failed_pages,
            "warning_pages": warning_pages,
            "semantic_pages": semantic_pages,
            "block_count": block_count,
            "table_count": table_count,
            "chart_count": chart_count,
            "chart_like_blocks": chart_like_blocks,
        },
        "pages": page_results,
    }


def _write_report(report_path: Path, payload: dict[str, object]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_raster_warning(reason: str, fix_hint: str = "") -> None:
    """降级为光栅 PNG wrapper 时打印醒目警告，确保用户知情。"""
    border = "=" * 70
    print(border, file=sys.stderr)
    print("  WARNING: SVG 将以光栅 PNG 包裹输出，文字【不可编辑】", file=sys.stderr)
    print(f"  原因: {reason}", file=sys.stderr)
    if fix_hint:
        print(f"  修复: {fix_hint}", file=sys.stderr)
    print("  要获得可编辑文字的真矢量 SVG，请解决上述依赖问题后重新运行。", file=sys.stderr)
    print(border, file=sys.stderr)


def ensure_deps(work_dir: Path) -> tuple:
    """安装依赖，返回 (方案名, bundle路径)

    bundle.js 固定生成在 SKILL_DIR（scripts/ 的父目录），所有 run 共享。
    优先级：
    1. _CANONICAL_BUNDLE_PATH 已存在 → 直接复用（最快路径，所有 run 共享）
    2. require('dom-to-svg') 可用 → esbuild 打包到 _CANONICAL_BUNDLE_PATH
    3. npm install dom-to-svg → 再次尝试打包
    4. 全部失败 → 降级 png-wrapper（打印 WARNING，文字不可编辑）
    """
    browser_path = resolve_browser_executable()
    if browser_path:
        print(f"Using browser: {browser_path}")

    deps_dir = NODE_DEPS_DIR
    deps_dir.mkdir(parents=True, exist_ok=True)
    selected_bundle = None

    # ── 第一优先级：bundle.js 已存在，直接复用（无需安装任何依赖）────────────
    # 先查 work_dir（当前 run 目录，向后兼容已生成的 bundle）
    run_bundle = work_dir / "dom-to-svg.bundle.js"
    for candidate in (run_bundle, _CANONICAL_BUNDLE_PATH):
        if candidate.exists():
            selected_bundle = candidate
            break


    # ── puppeteer ─────────────────────────────────────────────────────────────
    try:
        r = subprocess.run(
            ["node", "-e", "require('puppeteer')"],
            capture_output=True, text=True, timeout=10, cwd=str(deps_dir),
            env=_subprocess_env(browser_path=browser_path)
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        r = None
    if r is None or r.returncode != 0:
        print("Installing puppeteer...")
        try:
            subprocess.run(["npm", "install", "puppeteer"],
                           capture_output=True, text=True, timeout=180, cwd=str(deps_dir),
                           env=_subprocess_env(browser_path=browser_path, skip_browser_download=bool(browser_path)))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("Puppeteer install unavailable, will rely on existing local deps or fallback.", file=sys.stderr)

    if selected_bundle is not None:
        print(f"Reusing existing dom-to-svg bundle: {selected_bundle}")
        return ("dom-to-svg", str(selected_bundle), browser_path)

    # ── dom-to-svg（node_modules 源码包，用于 esbuild 打包）──────────────────
    def _dom_to_svg_available() -> bool:
        try:
            res = subprocess.run(
                ["node", "-e", "require('dom-to-svg')"],
                capture_output=True, text=True, timeout=10, cwd=str(deps_dir),
                env=_subprocess_env(browser_path=browser_path)
            )
            return res.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    if not _dom_to_svg_available():
        print("Installing dom-to-svg...")
        try:
            subprocess.run(["npm", "install", "dom-to-svg"],
                           capture_output=True, text=True, timeout=60, cwd=str(deps_dir),
                           env=_subprocess_env(browser_path=browser_path, skip_browser_download=bool(browser_path)))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    if not _dom_to_svg_available():
        _print_raster_warning("dom-to-svg 安装失败，无法生成可编辑 SVG",
                              "Run: npm install dom-to-svg (inside the skill directory)")
        return ("png-wrapper", None)

    # ── esbuild 打包为浏览器 bundle（输出到 SKILL_DIR，所有 run 共享）──────────
    print("Building dom-to-svg browser bundle...")
    entry_path = deps_dir / ".bundle_entry.js"
    entry_path.write_text(BUNDLE_ENTRY)
    try:
        r = subprocess.run(
            ["npx", "-y", "esbuild", str(entry_path),
             "--bundle", "--format=iife",
             f"--outfile={_CANONICAL_BUNDLE_PATH}", "--platform=browser"],
            capture_output=True, text=True, timeout=60, cwd=str(deps_dir),
            env=_subprocess_env(browser_path=browser_path)
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        r = None
    if entry_path.exists():
        entry_path.unlink()

    if r is None or r.returncode != 0:
        stderr = r.stderr if r is not None else "esbuild unavailable"
        print(f"esbuild failed: {stderr}", file=sys.stderr)
        _print_raster_warning("esbuild 打包失败，无法生成可编辑 SVG",
                              "Run: npm install esbuild (or: npx esbuild --version)")
        return ("png-wrapper", None, browser_path)

    return ("dom-to-svg", str(_CANONICAL_BUNDLE_PATH), browser_path)


def convert_dom_to_svg(html_files, output_dir, work_dir, bundle_path, browser_path):
    """用 dom-to-svg 方案转换"""
    config = {
        "browserPath": browser_path,
        "bundlePath": bundle_path,
        "files": [
            {
                "html": str(f),
                "svg": str(output_dir / (f.stem + ".svg")),
                "semantic": str(_semantic_path_for(output_dir, f)),
            }
            for f in html_files
        ]
    }

    script_path = work_dir / ".dom2svg_tmp.js"
    script_path.write_text(CONVERT_SCRIPT)

    try:
        print(f"Converting {len(html_files)} HTML files (dom-to-svg, text editable)...")
        r = subprocess.run(
            ["node", str(script_path), json.dumps(config)],
            cwd=str(work_dir), timeout=300,
            env=_subprocess_env(browser_path=browser_path)
        )
        if r.returncode != 0:
            return None

        page_results: list[dict[str, object]] = []
        total_text_count = 0
        for index, html_file in enumerate(html_files, start=1):
            svg_path = output_dir / f"{html_file.stem}.svg"
            if not svg_path.exists():
                print(f"Missing SVG after dom-to-svg: {svg_path}", file=sys.stderr)
                return None
            page_result = _make_page_result(
                page_number=index,
                html_file=html_file,
                svg_path=svg_path,
                work_dir=work_dir,
                method="dom_to_svg_editable",
                editable=True,
                success=True,
                semantic_path=_semantic_path_for(output_dir, html_file),
            )
            total_text_count += int(page_result["text_count"])
            page_results.append(page_result)

        print(f"Text elements: {total_text_count} (editable in PPT)")
        return page_results
    finally:
        if script_path.exists():
            script_path.unlink()


def convert_pdf2svg(html_files, output_dir, work_dir, browser_path):
    """降级方案：Puppeteer PDF + pdf2svg"""
    if not shutil.which("pdf2svg"):
        print("pdf2svg not found. Install: sudo apt install pdf2svg", file=sys.stderr)
        return None

    pdf_tmp = work_dir / ".pdf_tmp"
    pdf_tmp.mkdir(exist_ok=True)

    config = {
        "browserPath": browser_path,
        "files": [
            {"html": str(f), "pdf": str(pdf_tmp / (f.stem + ".pdf"))}
            for f in html_files
        ]
    }

    script_path = work_dir / ".fallback_tmp.js"
    script_path.write_text(FALLBACK_SCRIPT)

    try:
        print(f"Step 1/2: HTML -> PDF ({len(html_files)} files)...")
        r = subprocess.run(
            ["node", str(script_path), json.dumps(config)],
            cwd=str(work_dir), timeout=300,
            env=_subprocess_env(browser_path=browser_path)
        )
        if r.returncode != 0:
            return None

        print("Step 2/2: PDF -> SVG (WARNING: text becomes paths, NOT editable)...")
        success = 0
        page_results: list[dict[str, object]] = []
        for item in config["files"]:
            svg_name = Path(item["pdf"]).stem + ".svg"
            svg_path = output_dir / svg_name
            r = subprocess.run(
                ["pdf2svg", item["pdf"], str(svg_path)],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                print(f"  OK {svg_name}")
                success += 1
        if success != len(html_files):
            return None

        for index, html_file in enumerate(html_files, start=1):
            svg_path = output_dir / f"{html_file.stem}.svg"
            page_results.append(
                _make_page_result(
                    page_number=index,
                    html_file=html_file,
                    svg_path=svg_path,
                    work_dir=work_dir,
                    method="pdf2svg_pathified",
                    editable=False,
                    success=True,
                    warning="text_became_paths",
                )
            )
        return page_results
    finally:
        if script_path.exists():
            script_path.unlink()
        if pdf_tmp.exists():
            shutil.rmtree(pdf_tmp)


def convert_png_wrapper(html_input: Path, html_files, output_dir: Path, work_dir: Path):
    """兜底方案：复用 html2png.py 产出 PNG，再包装成 SVG <image>。"""
    png_tmp = work_dir / ".svg_fallback_png"
    existing_png_dir = work_dir / "png"
    if existing_png_dir.is_dir():
        png_tmp = existing_png_dir
    else:
        png_tmp.mkdir(exist_ok=True)

    html2png_script = Path(__file__).resolve().parent / "html2png.py"
    try:
        png_ready = all((png_tmp / f"{html_file.stem}.png").exists() for html_file in html_files)
        if not png_ready:
            print(
                "Fallback 1/1: HTML -> PNG -> SVG wrapper "
                "(WARNING: text becomes raster, but downstream SVG/PPTX flow stays intact)..."
            )
            r = None
            for attempt in range(1, 3):
                r = subprocess.run(
                    [
                        sys.executable,
                        str(html2png_script),
                        str(html_input),
                        "-o",
                        str(png_tmp),
                        "--scale",
                        "2",
                    ],
                    cwd=str(work_dir),
                    timeout=300,
                )
                png_ready = all((png_tmp / f"{html_file.stem}.png").exists() for html_file in html_files)
                if r.returncode == 0 or png_ready:
                    break
                print(f"Retrying PNG wrapper fallback ({attempt}/2 failed)...", file=sys.stderr)

            if (r is None or r.returncode != 0) and not png_ready:
                return None
        else:
            print("Fallback 1/1: Reusing existing PNG renders to build SVG wrappers...")

        page_results: list[dict[str, object]] = []
        for html_file in html_files:
            png_path = png_tmp / f"{html_file.stem}.png"
            if not png_path.exists():
                print(f"Missing fallback PNG: {png_path}", file=sys.stderr)
                return None

            data = base64.b64encode(png_path.read_bytes()).decode("ascii")
            svg_path = output_dir / f"{html_file.stem}.svg"
            svg_path.write_text(
                (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
                    'viewBox="0 0 1280 720">'
                    f'<image href="data:image/png;base64,{data}" x="0" y="0" '
                    'width="1280" height="720" preserveAspectRatio="none" />'
                    '</svg>'
                ),
                encoding="utf-8",
            )
            print(f"SVG(wrapper): {html_file.name} -> {svg_path.name}")
            page_results.append(
                _make_page_result(
                    page_number=len(page_results) + 1,
                    html_file=html_file,
                    svg_path=svg_path,
                    work_dir=work_dir,
                    method="png_wrapper_raster",
                    editable=False,
                    success=True,
                    warning="text_rasterized_into_png_wrapper",
                )
            )
        return page_results
    except subprocess.TimeoutExpired:
        print("Timeout: PNG fallback took too long", file=sys.stderr)
        return None
    finally:
        if png_tmp != existing_png_dir and png_tmp.exists():
            shutil.rmtree(png_tmp)


def convert(html_dir: Path, output_dir: Path, report_path: str | None = None) -> bool:
    """主转换入口"""
    if html_dir.is_file():
        html_files = [html_dir]
        work_dir = html_dir.parent.parent
    else:
        html_files = sorted(html_dir.glob("*.html"), key=lambda p: [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', p.stem)])
        work_dir = html_dir.parent

    if not html_files:
        print(f"No HTML files in {html_dir}", file=sys.stderr)
        return False

    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = _report_path_for(work_dir, report_path)

    method, bundle_path, browser_path = ensure_deps(work_dir)

    if method == "dom-to-svg" and bundle_path:
        page_results = convert_dom_to_svg(html_files, output_dir, work_dir, bundle_path, browser_path)
        if page_results is not None:
            _write_report(
                report_file,
                _build_export_report(
                    html_input=html_dir,
                    output_dir=output_dir,
                    work_dir=work_dir,
                    page_results=page_results,
                ),
            )
            print(f"\nDone! {len(html_files)} SVGs -> {output_dir}")
            print(f"Report: {report_file}")
            return True
        print("dom-to-svg failed, falling back to rasterized SVG wrappers...")

    page_results = convert_png_wrapper(html_dir, html_files, output_dir, work_dir)
    if page_results is not None:
        _write_report(
            report_file,
            _build_export_report(
                html_input=html_dir,
                output_dir=output_dir,
                work_dir=work_dir,
                page_results=page_results,
            ),
        )
        print(f"\nDone! {len(html_files)} SVG wrappers -> {output_dir}")
        print(f"Report: {report_file}")
        return True

    print("PNG wrapper fallback failed, trying pdf2svg...", file=sys.stderr)
    page_results = convert_pdf2svg(html_files, output_dir, work_dir, browser_path)
    if page_results is not None:
        _write_report(
            report_file,
            _build_export_report(
                html_input=html_dir,
                output_dir=output_dir,
                work_dir=work_dir,
                page_results=page_results,
            ),
        )
        print(f"Report: {report_file}")
        return True

    _write_report(
        report_file,
        _build_export_report(
            html_input=html_dir,
            output_dir=output_dir,
            work_dir=work_dir,
            page_results=_build_failed_page_results(html_files, output_dir, work_dir, "all_conversion_methods_failed"),
        ),
    )
    print(f"Report: {report_file}", file=sys.stderr)
    return False


def main():
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("Usage: python3 scripts/html2svg.py <html_dir_or_file> [-o output_dir] [--report-path report.json]")
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    html_path = Path(sys.argv[1]).resolve()
    if "-o" in sys.argv:
        idx = sys.argv.index("-o")
        output_dir = Path(sys.argv[idx + 1]).resolve()
    else:
        output_dir = (html_path.parent if html_path.is_file() else html_path.parent) / "svg"

    report_path = None
    if "--report-path" in sys.argv:
        idx = sys.argv.index("--report-path")
        report_path = sys.argv[idx + 1]

    success = convert(html_path, output_dir, report_path=report_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
