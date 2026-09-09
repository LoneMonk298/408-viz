# 408-Viz (MVP)

408 考研知识点可视化生成器 MVP —— 输入 IR JSON，输出独立 HTML（可直接 `<VizEmbed>` 嵌入博客）。

## 现状

| 模块 | 状态 |
|---|---|
| IR Schema (tree / fsm / array / timeline / graph / grid / mindmap) | ✅ `schemas/*.schema.json` |
| 校验器 | ✅ `bin/validate.py`（树/hl 引用、fsm active/trans 引用、array 下标范围、timeline bar 重叠、graph 节点/边引用、grid 行列范围、mindmap 节点 id 唯一+深度限制全检查） |
| 渲染器模板（通用播放器） | ✅ `bin/renderer_template.html`（toolbar/字幕/图例/主题同步/键盘快捷键） |
| 渲染脚本 | ✅ `bin/render.py` |
| tree 渲染器 | ✅ tidy 布局（叶子槽位+父居中+单子方向偏移）、半径/层级自适应、脉冲高亮 |
| fsm 渲染器 | ✅ 状态圆、有向边+箭头+label、回环/前跳弧线绕行、最后转移高亮 |
| array 渲染器 | ✅ 格子+下标、low/mid/high 指针、swap 双弧交叉飞行动画、8 种语义色 |
| timeline 渲染器 | ✅ 甘特横道、时间游标动画、进程分色、到达标记、active 半透明全长预览 |
| graph 渲染器 | ✅ 显式/圆形布局、带权边、dist 数值徽章、松弛/树边语义色、可选有向 |
| grid 渲染器 | ✅ 行列网格、行列标题、单元格值快照、hit/miss/compare/write/mask 语义色 |
| mindmap 渲染器 | ✅ 径向布局、可折叠子树（点击节点 +/− 徽章）、碰撞检测防重叠、悬停 desc tooltip |
| LLM 解析器 | ✅ `bin/generate.py` + `prompts/`（提示词资产 + CLI 脚本，待 API key 实跑） |
| 示例 | ✅ `bst-insert`、`counter-2bit`、`binary-search`、`bubble-sort`、`sjf-scheduling`、`dijkstra-prim`、`cache-direct-mapped`、`subnet-division`、`virtual-memory-mindmap`、`tcp-udp-mindmap` |

## 快速开始

```bash
# 校验
python3 bin/validate.py examples/bst-insert.json

# 渲染单个
python3 bin/render.py examples/bst-insert.json /tmp/bst-insert.html

# 渲染全部示例
python3 bin/build_all.py
```

打开 HTML 文件即可（无外部依赖、独立运行）。支持 URL 参数：`preset=0`、`autoplay=1`、`speed=0.5`。

## IR 设计

七种 `struct_type`：

**tree** —— 每步是完整树快照 + 高亮。`children` 位置 0=左子、1=右子，单右子用 `null` 占位
```json
{ "id": "n3", "val": 3, "children": [null, {"id": "n5", "val": 5}] }
```

**fsm** —— 全局状态/转移定义一次，每步标记 active 状态 + 最近转移
```json
{ "states": [...], "transitions": [...], "steps": [{"active": ["S1"], "lastTrans": [{"id": "t01"}]}] }
```

**array** —— 每步是完整数组快照（支持 `null` 空位）+ 按下标高亮 + 命名指针
```json
{ "array": [7, 13, 21, 34], "hl": [{"index": 1, "kind": "compare"}],
  "ptrs": [{"name": "mid", "index": 1}], "title": "...", "desc": "..." }
```
高亮 kind：`insert/visit/compare/swap/pivot/sorted/found/removed`。相邻两步数组恰好两位置互换时自动触发 swap 双弧交叉飞行动画（排序场景）。

**timeline** —— 甘特横道图。rows 全局（1-4 行），bars/markers 为 **preset 级**（对比不同调度算法），每步用 `reveal` 时间游标揭示进度
```json
{ "rows": [{"id": "cpu", "label": "CPU"}],
  "presets": [{
    "bars": [{"id": "b1", "row": "cpu", "label": "P1", "start": 0, "end": 7}],
    "markers": [{"t": 2, "label": "P2 到达"}],
    "steps": [{"reveal": 7, "active": ["b1"], "title": "...", "desc": "..."}]
  }] }
```
bar kind ∈ `run/io/idle`（run 按进程 label 自动分色，跨 preset 一致）；游标动画驱动 bar 生长，active 未完成的 bar 显示半透明全长预览。

**graph** —— 带权图（Dijkstra/Prim/BFS/DFS）。节点/边全局定义，每步标记节点态、边态和数值徽章
```json
{ "directed": false,
  "nodes": [{"id": "v0", "label": "v0", "x": 10, "y": 50}],
  "edges": [{"id": "e01", "from": "v0", "to": "v1", "weight": 10}],
  "presets": [{
    "steps": [{"hl": [{"node_id": "v0", "kind": "done"}],
               "edge_hl": [{"edge_id": "e01", "kind": "tree"}],
               "vals": [{"node_id": "v1", "val": "10"}],
               "title": "...", "desc": "..."}] }] }
```
节点 kind ∈ `visit/frontier/done/path/found`，边 kind ∈ `relax/tree/path`；`vals` 徽章显示 dist/深度/序号（支持 `∞`）。`x/y` 0-100 归一化坐标可选，缺省圆形自动布局。

**grid** —— 行列网格（Cache/子网/加法器）。每步是完整单元格快照 + 高亮
```json
{ "rows": 4, "cols": 4,
  "row_labels": ["Line 0", "Line 1", ...],
  "col_labels": ["Valid", "Tag", "Set", "Data"],
  "presets": [{
    "steps": [{
      "cells": [{ "r": 0, "c": 0, "val": "1" }, ...],
      "hl":   [{ "r": 0, "c": 0, "kind": "write" }],
      "title": "...", "desc": "..."
    }] }] }
```
高亮 kind：`hit`（命中）/ `miss`（缺失）/ `compare`（比较）/ `write`（写入/装入）/ `found`（查找命中）/ `mask`（掩码位）。

**mindmap** —— 径向思维导图（概念/关系性题目，无步骤，可折叠交互）
```json
{ "presets": [{
    "root": {
      "id": "vm", "label": "虚拟内存", "desc": "扩大地址空间",
      "children": [
        { "id": "pt", "label": "页表", "desc": "虚拟→物理映射",
          "children": [{ "id": "tlb", "label": "TLB", "desc": "加速地址转换" }] }
      ]
    },
    "hl": [{ "node_id": "tlb", "kind": "concept" }]
  }] }
```
高亮 kind：`concept`（概念）/ `contrast`（对比）。点击节点右下角 +/− 徽章折叠/展开子树，悬停显示 desc。

详见 `schemas/README.md`。

## 设计原则（来自 https://github.com/tt-a1i/archify）

- **类型化 JSON IR**：LLM 只写 JSON，绝不写 HTML
- **`additionalProperties: false`**：未知字段直接拒收，避免 LLM 加冗余
- **封闭枚举**：hl.kind / fsm.type 都是固定集合，校验器强制
- **确定性校验**：校验通过才能渲染，校验失败重试 1 次
- **渲染器读 IR 决定画什么**；播放器（toolbar/字幕/主题同步）不读 IR

## LLM 解析器

`bin/generate.py` 接受题目 + 解法，调用 LLM 生成 IR，校验通过后自动渲染：

```bash
export SENSENOVA_API_KEY="your-key"
python bin/generate.py --problem "向空 BST 依次插入 7,3,5,9" \
  --answer "7 为根，3<7 左子，9>7 右子，5 在 3 右子" \
  --out examples/bst-demo
```

提示词资产在 `prompts/`（system.md + few-shot），IR 规范在 `schemas/README.md`（运行时自动注入提示词）。

也可以在 TRAE 对话中直接贴题目，由 AI 读取提示词资产生成 IR——两种方式共用同一套提示词。

## 路线图

- ~~v2：接 sensenova 的 LLM 解析器~~ ✅ 提示词 + CLI 脚本已完成，待 API key 实跑验证
- v3：合并到 vitepress 仓库的 `feature/408-viz` 分支，与 `<VizEmbed>` 打通
