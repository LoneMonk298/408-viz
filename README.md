# 408-Viz (MVP)

408 考研知识点可视化生成器 MVP —— 输入 IR JSON，输出独立 HTML（可直接 `<VizEmbed>` 嵌入博客）。

## 现状

| 模块 | 状态 |
|---|---|
| IR Schema (tree / fsm / array / timeline) | ✅ `schemas/*.schema.json` |
| 校验器 | ✅ `bin/validate.py`（树/hl 引用、fsm active/trans 引用、array 下标范围、timeline bar 重叠全检查） |
| 渲染器模板（通用播放器） | ✅ `bin/renderer_template.html`（toolbar/字幕/图例/主题同步/键盘快捷键） |
| 渲染脚本 | ✅ `bin/render.py` |
| tree 渲染器 | ✅ tidy 布局（叶子槽位+父居中+单子方向偏移）、半径/层级自适应、脉冲高亮 |
| fsm 渲染器 | ✅ 状态圆、有向边+箭头+label、回环/前跳弧线绕行、最后转移高亮 |
| array 渲染器 | ✅ 格子+下标、low/mid/high 指针、swap 双弧交叉飞行动画、8 种语义色 |
| timeline 渲染器 | ✅ 甘特横道、时间游标动画、进程分色、到达标记、active 半透明全长预览 |
| 示例 | ✅ `bst-insert`、`counter-2bit`、`binary-search`、`bubble-sort`、`sjf-scheduling` |

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

四种 `struct_type`：

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

详见 `schemas/README.md`。

## 设计原则（来自 https://github.com/tt-a1i/archify）

- **类型化 JSON IR**：LLM 只写 JSON，绝不写 HTML
- **`additionalProperties: false`**：未知字段直接拒收，避免 LLM 加冗余
- **封闭枚举**：hl.kind / fsm.type 都是固定集合，校验器强制
- **确定性校验**：校验通过才能渲染，校验失败重试 1 次
- **渲染器读 IR 决定画什么**；播放器（toolbar/字幕/主题同步）不读 IR

## 路线图

- v2：加 `graph`（路由/最短路）、`grid`（加法器/Cache 映射/子网）
- v3：接 sensenova 的 LLM 解析器（输入题目+答案 → 生成 IR），确定性校验 + 重试
- v4：合并到 vitepress 仓库的 `feature/408-viz` 分支，与 `<VizEmbed>` 打通
