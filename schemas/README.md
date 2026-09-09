# 408-Viz IR 规范

所有可视化共享的外层结构：

```json
{
  "schema_version": 1,
  "struct_type": "tree | fsm | array | timeline",
  "meta": { "title": "...", "caption": "..." },
  "presets": [{ "name": "...", "steps": [...] }]
}
```

- `meta.title` 必填（≤80 字符）；`meta.caption` 可选副标题
- `presets`：同一数据的不同演示剧本（如"查找 21" / "查找 100"），1-12 个
- 每个 step：`title`（≤60）+ `desc`（≤400，支持 `` `code` `` 行内代码）必填

## tree

每步是**完整树快照**。节点：`{ "id": "n7", "val": 7, "children": [...] }`

- `children` 位置 0=左子、1=右子，最多 2 个；**单右子用 `null` 占位**：`[null, {"id":"n5","val":5}]`
- `id` 全树唯一（`^[A-Za-z0-9_-]{1,24}$`），`val` 为整数或字符串
- 高亮 `hl: [{"node_id": "n5", "kind": "..."}]`，kind ∈ `insert / visit / compare / unbalanced / rotated / removed`

## fsm

状态/转移全局定义一次，每步只标记 active 状态和最近转移。

```json
{
  "states":    [{ "id": "S0", "label": "00", "type": "start", "col": 0 }],
  "transitions": [{ "id": "t01", "from": "S0", "to": "S1", "label": "clk↑" }],
  "steps": [{ "active": ["S0"], "lastTrans": ["t01"], "title": "...", "desc": "..." }]
}
```

- `states[].type` ∈ `start / active / success / failure / terminal`（封闭枚举）
- `col`：列号（0 起），同列多状态垂直分布；转移边为直线，与其他节点距离过近时自动改弧线绕行（回环走下方、前跳走上方）
- `lastTrans`：本步刚经过的转移（id 列表），高亮显示

## array

每步是**完整数组快照**（1-20 个元素，`int | string | null`，`null` 为空位）。

```json
{
  "array": [7, 13, 21, 34],
  "hl":   [{ "index": 1, "kind": "compare" }],
  "ptrs": [{ "name": "mid", "index": 1 }],
  "title": "...", "desc": "..."
}
```

- 高亮 `hl`：按数组下标，kind ∈ `insert / visit / compare / swap / pivot / sorted / found / removed`
  - `visit`：当前查找/操作区间
  - `compare`：正在比较的元素
  - `swap`：正在交换的两个位置
  - `sorted`：已最终就位（排序）
  - `found`：查找命中
- 指针 `ptrs`：命名指针（`low` / `mid` / `high` / `i` / `j` ...），同一格多个指针自动横向错开
- **swap 飞行动画**：相邻两步数组长度相同且恰好两个位置的值互换时，渲染器自动检测并播放双弧交叉飞行动画（元素携带旧值飞到对面，无需额外标记）

## timeline

甘特横道图（进程调度/磁盘调度/流水线）。**rows 全局**，**bars/markers 为 preset 级**（同一题的不同调度算法各成一个 preset，如 SJF vs FCFS）。

```json
{
  "rows": [{ "id": "cpu", "label": "CPU" }],
  "presets": [{
    "name": "SJF 短作业优先",
    "bars": [
      { "id": "b1", "row": "cpu", "label": "P1", "start": 0, "end": 7 },
      { "id": "b2", "row": "cpu", "label": "P3", "start": 7, "end": 8, "kind": "run" }
    ],
    "markers": [{ "t": 2, "label": "P2 到达" }],
    "steps": [{
      "reveal": 7, "active": ["b2"],
      "title": "t=7 调度 P3", "desc": "..."
    }]
  }]
}
```

- `rows`：1-4 行横道（如 `cpu`、`io`，或流水线的 IF/ID/EX/MEM/WB 各一行）
- `bars`：每根横道的占用段，`start < end`（0-1000，可为小数）；**同一行内不允许重叠**（校验器强制，LLM 生成调度序列最易犯的错）
  - `kind` ∈ `run`（执行/占用，按 `label` 自动分色且**跨 preset 一致**）/ `io`（I/O 琥珀色）/ `idle`（空闲灰）
  - `label`：如 `P1`，显示在色块内；idle 可不填
- `markers`：时刻事件（如进程到达），轴上方倒三角 + 标签，`reveal` ≥ `t` 时显示
- `steps[].reveal`：时间游标位置（必填，0..该 preset 最大 end）——游标动画驱动 bar 从左向右生长
- `steps[].active`：当前步骤高亮的 bar id 列表（绿色脉冲）；active 且未完成的 bar 额外显示半透明全长预览（调度已决定的区间）
- 时间轴刻度自动生成，LLM 无需指定

## 校验规则（validate.py）

- 未知字段拒收（schema 层 `additionalProperties: false`，校验器同步检查）
- 引用完整性：tree 的 `hl.node_id` 必须在树中；fsm 的 `from/to` 必须在 states 中、`lastTrans` 必须在 transitions 中；array 的 `hl.index` / `ptrs.index` 必须在数组下标范围内；timeline 的 `bar.row` 必须在 rows 中、`active` 必须在 bars 中
- 时序合法性（timeline）：同一行内 bars 不得重叠；`reveal` / `markers.t` 必须在 0..该 preset 最大 end 范围内
- 数量限制：array 元素 1-20，timeline bars 1-30 / rows 1-4，presets 1-12，steps ≤ 80
