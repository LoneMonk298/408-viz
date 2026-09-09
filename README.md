# 408-Viz (MVP)

408 考研知识点可视化生成器 MVP —— 输入 IR JSON，输出独立 HTML（可直接 `<VizEmbed>` 嵌入博客）。

## 现状

| 模块 | 状态 |
|---|---|
| IR Schema (tree / fsm) | ✅ `schemas/*.schema.json` |
| 校验器 | ✅ `bin/validate.py`（树/hl 引用、fsm active/trans 引用全检查） |
| 渲染器模板（通用播放器） | ✅ `bin/renderer_template.html`（toolbar/字幕/图例/主题同步/键盘快捷键） |
| 渲染脚本 | ✅ `bin/render.py` |
| tree 渲染器 | ✅ 中序定位、半径/层级自适应、脉冲高亮、6 种语义色 |
| fsm 渲染器 | ✅ 状态圆、有向边+箭头+label、最后转移高亮、start/success/failure 类型色 |
| 示例 | ✅ `examples/bst-insert.json`、`examples/counter-2bit.json` |

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

两种 `struct_type`：

**tree** —— 每步是完整树快照 + 高亮。`children` 位置 0=左子、1=右子，单右子用 `null` 占位
```json
{ "id": "n3", "val": 3, "children": [null, {"id": "n5", "val": 5}] }
```

**fsm** —— 全局状态/转移定义一次，每步标记 active 状态 + 最近转移
```json
{ "states": [...], "transitions": [...], "steps": [{"active": ["S1"], "lastTrans": [{"id": "t01"}]}] }
```

详见 `schemas/README.md`。

## 设计原则（来自 https://github.com/tt-a1i/archify）

- **类型化 JSON IR**：LLM 只写 JSON，绝不写 HTML
- **`additionalProperties: false`**：未知字段直接拒收，避免 LLM 加冗余
- **封闭枚举**：hl.kind / fsm.type 都是固定集合，校验器强制
- **确定性校验**：校验通过才能渲染，校验失败重试 1 次
- **渲染器读 IR 决定画什么**；播放器（toolbar/字幕/主题同步）不读 IR

## 路线图

- v2：加 `array`（排序/查找）、`graph`（路由/最短路）、`timeline`（进程调度甘特）、`grid`（加法器/Cache 映射/子网）
- v3：接 sensenova 的 LLM 解析器（输入题目+答案 → 生成 IR），确定性校验 + 重试
- v4：合并到 vitepress 仓库的 `feature/408-viz` 分支，与 `<VizEmbed>` 打通
