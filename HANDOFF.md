# 408-Viz 交接文档

**时间**：2026-09-09
**项目位置**：
- 服务器：`hermes@192.168.0.1:~/408-viz/`（git 仓库已 init，remote origin 已配 GitHub token）
- GitHub：`https://github.com/LoneMonk298/408-viz`（public，default_branch=main）
- 分支：`main`（空占位 commit `1ae51c9`）、`feature/mvp`（MVP `4f48c76` + 第一轮视觉修复 `ca42e5d` + 第二轮渲染 bug 修复）

**沙箱位置**：`/opt/data/408-viz/`（沙箱与服务器**不共享**，每次需重新 tar 同步到服务器）

---

## 一、项目目标

408 考研知识点可视化生成器：输入 IR JSON，输出独立 HTML，可嵌入 VitePress 博客。

### 学科覆盖规划

| 学科 | 知识点 | 归一化形态（struct_type） |
|---|---|---|
| 计组 | 加法器/计数器/Cache 映射/子网划分 | grid |
| | 指令周期/中断/流水线 | timeline |
| | 存储层次/虚地址翻译/TLB | grid/树 |
| 操作系统 | 进程调度/磁盘调度 | timeline ★ |
| | 进程状态/银行家/Dijkstra/死锁 | FSM/图 ★ |
| | 页面置换/页表/B+ 树 | array/树 |
| 计算机网络 | TCP 状态机/三次握手/DNS | FSM/sequence ★ |
| | IP 子网/CIDR/路由表 | grid |
| | OSPF/最短路/转发 | 图 |
| | 拥塞控制/滑动窗口 | timeline |

★ = 出题频率最高

### 6 个渲染基元（路线图）

| 基元 | 状态 |
|---|---|
| tree | ✅ MVP 已实现 |
| fsm | ✅ MVP 已实现 |
| array | ✅ 已实现（折半查找/冒泡排序，含 swap 双弧交叉动画） |
| timeline | ✅ 已实现（SJF vs FCFS 进程调度甘特，含游标动画/进程分色） |
| graph | ⏳ 待做（路由/最短路） |
| grid | ⏳ 待做（加法器/Cache/子网） |

---

## 二、架构（参照 archify）

```
输入 IR JSON
  ↓ validate.py（确定性校验，失败重试 1 次）
renderer_template.html（通用播放器 + 按 struct_type 分发到具体渲染器）
  ↓ render.py（注入 IR 到模板的 /*__IR__*/ 占位符）
输出独立 HTML（无外部依赖，可直接 <VizEmbed> 嵌入）
```

### 设计原则（来自 archify）

- 类型化 JSON IR：LLM 只写 JSON，绝不写 HTML
- `additionalProperties: false`：未知字段拒收
- 封闭枚举：hl.kind / fsm.type 都是固定集合
- 确定性校验：校验通过才能渲染
- 渲染器读 IR 决定画什么；播放器不读 IR

### 文件结构

```
408-viz/
├─ README.md
├─ schemas/
│  ├─ tree.schema.json     # tree IR schema（严格）
│  └─ fsm.schema.json      # fsm IR schema（严格）
├─ bin/
│  ├─ validate.py          # 校验器：树/hl 引用、fsm active/trans 引用
│  ├─ render.py            # IR → HTML
│  ├─ build_all.py         # 批量渲染所有示例
│  └─ renderer_template.html  # 通用播放器 + tree/fsm 渲染器
├─ examples/
│  ├─ bst-insert.json      # BST 插入 7→3→5→9（4 步）
│  └─ counter-2bit.json    # 2 位二进制计数器（5 步）
└─ docs/public/visualizers/  # 渲染产物（.gitignore，可重生成）
   ├─ bst-insert.html
   └─ counter-2bit.html
```

---

## 三、IR Schema 速查

### tree

```json
{
  "schema_version": 1,
  "struct_type": "tree",
  "meta": { "title": "...", "caption": "..." },
  "presets": [{
    "name": "...",
    "steps": [{
      "tree": { "id": "n1", "val": 7, "children": [{"id": "n3", "val": 3}] },
      "hl": [{"node_id": "n1", "kind": "insert"}],
      "title": "步骤标题",
      "desc": "步骤描述，`code` 高亮"
    }]
  }]
}
```

- `hl.kind` 枚举：`insert` `visit` `compare` `unbalanced` `rotated` `removed`
- 校验：每步 hl.node_id 必须在该步的树中存在

### fsm

```json
{
  "schema_version": 1,
  "struct_type": "fsm",
  "meta": { "title": "...", "caption": "..." },
  "states": [{ "id": "S0", "type": "start|active|success|failure|terminal",
               "label": "00", "sublabel": "S0", "col": 0 }],
  "transitions": [{ "id": "t01", "from": "S0", "to": "S1", "label": "clk↑" }],
  "presets": [{
    "name": "...",
    "steps": [{
      "active": ["S0"],
      "lastTrans": [{"id": "t01"}],
      "title": "...", "desc": "..."
    }]
  }]
}
```

- `state.col` 0..5 决定横向列
- 校验：transitions.from/to 必须在 states 中；active 必须在 states 中；lastTrans.id 必须在 transitions 中

### array（2026-09-09 新增）

```json
{
  "schema_version": 1,
  "struct_type": "array",
  "meta": { "title": "...", "caption": "..." },
  "presets": [{
    "name": "...",
    "steps": [{
      "array": [7, 13, 21, 34],
      "hl": [{"index": 1, "kind": "compare"}],
      "ptrs": [{"name": "mid", "index": 1}],
      "title": "...", "desc": "..."
    }]
  }]
}
```

- `array`：每步完整快照，1-20 元素，`int | string | null`（null=空位，如顺序表删除）
- `hl`：按下标高亮，kind 枚举 `insert visit compare swap pivot sorted found removed`（compare=比较中，visit=操作区间，sorted=已就位，found=查找命中）
- `ptrs`：命名指针（low/mid/high/i/j...），同一格多个指针自动横向错开
- **swap 自动检测**：相邻两步长度相同且恰好两位置值互换 → 自动播放双弧交叉飞行动画（600ms，元素携带旧值飞行，结束后归位换值），排序场景无需额外标记
- 校验：hl.index / ptrs.index 必须在数组下标范围内；schema 见 `schemas/array.schema.json`

### timeline（2026-09-09 新增）

甘特横道图（进程调度/磁盘调度/流水线）。**rows 全局、bars/markers 为 preset 级**（SJF vs FCFS 对比 preset 各持不同调度序列）：

```json
{
  "schema_version": 1,
  "struct_type": "timeline",
  "meta": { "title": "...", "caption": "..." },
  "rows": [{ "id": "cpu", "label": "CPU" }],
  "presets": [{
    "name": "SJF 短作业优先",
    "bars": [{ "id": "b1", "row": "cpu", "label": "P1", "start": 0, "end": 7 }],
    "markers": [{ "t": 2, "label": "P2 到达" }],
    "steps": [{ "reveal": 7, "active": ["b1"], "title": "...", "desc": "..." }]
  }]
}
```

- `rows` 1-4 行（CPU/IO 单行，或流水线 IF/ID/EX/MEM/WB 五行）
- `bars`：`kind` ∈ `run/io/idle`；run 按 label 自动分色（8 色轮，**跨 preset 一致**——色表按全部 preset 首次出现顺序计算）；同 row 不允许重叠（校验器强制）
- `steps[].reveal`：时间游标（必填，0..preset 最大 end）——游标动画驱动 bar 生长；`active` 绿色脉冲，active 且未完成的 bar 画半透明全长预览（调度已决定的区间，不剧透未调度的 bar）
- 时间轴刻度自动生成（maxT≤20 → 步长 1，≤40 → 2，≤100 → 5 …）
- 校验：row 引用、active 引用、bar 重叠、reveal/markers 范围；schema 见 `schemas/timeline.schema.json`
- 实现要点：`S.nowT = {t, tt}` 插值（draw 主循环里 `+= (tt-t)*0.15`）；loadPreset 重置 `S.nowT=null` 并同步 `presetSelect.value`（URL `preset=N` 参数此前不同步下拉框，已修）

---

## 四、通用播放器 UI 规范（与 viz-animation skill 对齐）

- toolbar：标题 + 预设下拉 + [重置][上一步][播放][下一步] + 速度滑块
- 速度默认 0.5x，范围 0.5-2.5
- 步骤字幕：画布底部内嵌，步骤编号（绿药丸）+ 标题 + 描述
- 图例浮动：画布右上角
- 主题同步：消息类型 `'viz-theme'`，`isDark()` 只检查 `.dark` 类
- 键盘：←→ 上/下一步，空格 播放/暂停，R 重置
- URL 参数：`preset=0` `autoplay=1` `speed=0.5` `hidelegend=1`
- 色彩语义：insert 绿、visit 蓝、compare 黄、unbalanced 黄、rotated 紫、removed 红

---

## 五、已完成的视觉修复

### 第一轮（2026-09-09，commit ca42e5d）

### 问题

服务器截图 + canvas 像素 bbox 分析（沙箱 Playwright headless）发现：

**修复前**：
- tree step0（单节点）：bbox `[87,48,132,91]`，挤在左上角
- fsm：bbox y `[124..210]`，4 状态挤在中间一条线，上下大片空白

### 修复内容（renderer_template.html）

**tree `computeTreeLayout`**：
1. 引入 `insetL=60 insetR=60 topPad=70 bottomPad=100` 可用区域
2. **单节点特殊处理**：`n===1` 时 x 居中（之前 `gapX=availW` 导致偏左）
3. `gapX = availW / (n-1)`，首节点在 `insetL`，末节点在 `insetL+availW`
4. 半径 `gapX*0.28`，范围 14-22

**fsm `computeFSMLayout`**：
1. 同样引入可用区域
2. 垂直方向按 r 收缩：`effTop = topPad + r + 12`（给 sublabel 留位）
3. 单节点垂直居中
4. 列内多节点均匀分布

### 修复后

| 步骤 | 修复前 bbox | 修复后 bbox |
|---|---|---|
| tree step0（单节点） | `[87,48,132,91]`（左上角） | `[434,54,465,85]`（**水平居中**）|
| tree step3（4节点） | `[37,54,854,470]` | `[36,54,861,470]` |
| fsm 全步骤 | `[44,222,854,308]`（高 86） | `[44,222,854,308]`（同，但更接近中心）|

### 第二轮修复（2026-09-09，本地评估发现 3 个 bug，全部修复）

评估方法：本地渲染 → Playwright(Edge headless) 截图 + bbox 分析 + `S.display` 程序化检查 + 截图视觉复核。

1. **P0 暗色画布仍是白色**：`html.dark` 没覆盖 `--bg`（`:root` 里是 `transparent`，独立打开时透出浏览器白底，节点又是深色系，黑字白底）。修复：`html.dark { --bg: #141518 }`。
2. **P0 FSM 回环边视觉丢失 + label 错位**：长转移（S3→S0）画直线横穿画布，被中间节点遮挡成碎线；其 label 中点恰好与相邻边 label 像素级重叠（"clk↑ 溢出"盖住了 t12 的 "clk↑"）。修复：直线距任一其他节点 < r+10 时自动改为弧线绕行（贝塞尔，回退边从下方绕、前跳长边从上方绕，同向多条依次错开 28px），label 放贝塞尔中点；顺带支持自环（`from==to`，画节点上方小弧，TCP 状态机需要）。
3. **P2 树连线脱节 + 节点半径不更新**：连线端点用布局最终坐标而非动画坐标（节点平移时线圆脱节）；且 `S.display` 的 `r` 不随步骤更新——节点增多导致 gapX 变化时，早出现的节点永远保持旧半径（BST 根节点从 step0 的 14px 一直不涨）。修复：端点改用 `S.display` 坐标；`r` 增加 `tr` 目标值并纳入插值动画。

验证数据：FSM bbox y 从 308 → 346（回环弧线占用了垂直空间）；BST 四节点半径全部收敛到 22。

### 第三轮修复（2026-09-09，用户反馈"布局太奇怪"）

用户宽窗口截图反馈：树被横向拉伸散开——根节点不在中心、父子间全是超长对角线、节点 5 被甩到远处。

根因：布局用的是**中序均匀槽位**——n 个节点从画布最左到最右等距铺开（gapX = availW/(n-1)）。窗口越宽拉伸越夸张，且根节点落在 62% 宽度处而非中心。900px 测试视口下不明显，宽窗口暴露。

修复：改为 **tidy 布局**（computeTreeLayout 重写）：
- 叶子从左到右占单位槽位；内部节点 = 首末子节点槽位中点（单子链垂直下垂，同 VisuAlgo）
- 槽位间距撑满可用宽度但**上限 150px**（小树不拉伸），整体水平居中
- 层间距撑满可用高度，上限 120px、下限 2r+12（防深树垂直重叠），浅树垂直居中
- 半径 r = min(clamp(sx*0.3, 14, 22), (sx-10)/2)：间距不足时自动缩小防重叠

验证：4 节点树宽从 825px → 196px，根在画布正中，900/1600 两种视口均紧凑居中。

已知取舍（第四轮已解决）：~~单子链渲染为垂直线~~ → 见下方第四轮修复。

### FSM 垂直空间（第一轮遗留评估项）

回环弧线已部分缓解（内容高度 86 → 124px）。单行 FSM 本来就该是横线，如仍不满意再考虑：节点垂直分布 / 动态 canvas 高度。

### 第四轮修复（2026-09-09，用户反馈"看不出左右孩子"）

问题：单子链渲染为垂直线，无法区分左子/右子（第三轮 tidy 布局的已知取舍）。

根因：IR 的 `children` 是普通数组，单孩子就是单元素数组，**没有左右语义**——渲染器无从得知方向。

修复（schema 语义约定 + 布局方向偏移）：
- **IR 约定**：`children` 位置 0=左子、1=右子，最多 2 个；单右子用 `null` 占位（`[null, {n5}]`），单左子 `[n3]` 或 `[n3, null]` 均可。validate.py 现在校验 children ≤2 且允许 null；README 已更新。
- **布局**：单子时父节点从子节点槽位偏移 ∓0.6（左子 → 父在子右上方，右子 → 父在子左上方），形成阶梯形（同 VisuAlgo）。spanX 改用全部节点槽位的 min/max（偏移会产生负槽位/越界槽位）。
- **防重叠保护**：同层最小水平间距 < 2r+8 时整体缩小半径（下限 8）——偏移累积在密集树中可能产生 0.4 槽位的同层间距。
- 示例 bst-insert.json：n3 的 children 改为 `[null, n5]`（5 是右子）。

验证：step2 的 7→3→5 链呈阶梯形（3 在 7 左下 90px，5 在 3 右下 90px）；step3 完整树 3 左下、9 右下、5 在 3 右下，方向一眼可辨。

### 调试环境注意（本地 Windows）

- 本地已装 playwright（pip），用系统 Edge：`p.chromium.launch(channel='msedge', headless=True)`
- `renderer_template.html` 行尾已统一为 LF（git 索引本来就是 LF，autocrlf=true）
- Edit 工具对该文件中以注释行开头的 old_string 匹配有问题，遇到时改用 Python 锚点替换

---

## 六、调试工具链（沙箱已装好）

```bash
# 沙箱已装：playwright + headless chromium + 依赖
pip install playwright && playwright install chromium && playwright install-deps chromium

# 渲染截图（自动等 2.5s 让动画收敛）
python3 << 'EOF'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={'width': 900, 'height': 600})
    page.goto('file:///tmp/bst-insert.html?autoplay=0')
    page.wait_for_timeout(800)
    # 跳到最后一步
    page.evaluate(f'applyStep({page.evaluate("S.steps.length-1")})')
    page.wait_for_timeout(1500)
    page.screenshot(path='/tmp/shot.png')
    # 分析 canvas bbox
    stats = page.evaluate("""() => {
        const c = document.getElementById('canvas');
        const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
        let minX=c.width,minY=c.height,maxX=0,maxY=0,n=0;
        for(let y=0;y<c.height;y++) for(let x=0;x<c.width;x++)
          if(d[(y*c.width+x)*4+3]>0){n++;if(x<minX)minX=x;if(x>maxX)maxX=x;if(y<minY)minY=y;if(y>maxY)maxY=y;}
        return {bbox:[minX,minY,maxX,maxY], n};
    }""")
    print(stats)
    b.close()
EOF
```

### 注意：vision_analyze 不可用

`vision_analyze` 返回 401 unauthorized（Hermes 配置的 vision provider 认证失效）。
**无法用视觉模型看图**，只能用 Playwright 像素 bbox 分析。如果需要在本地电脑继续视觉调试，**用 Claude Code/Cursor 直接打开 HTML** 看效果最快。

---

## 七、服务器 git 操作规范

```bash
# 同步代码到服务器
tar -czf - -C /opt/data 408-viz | ssh hermes@192.168.0.1 'rm -rf ~/408-viz && tar -xzf - -C ~'

# 提交并 push
ssh hermes@192.168.0.1 'cd ~/408-viz && git add -A && git commit -m "..." && git push origin feature/mvp'

# 验证远程 commit（不能仅凭本地 push success）
ssh hermes@192.168.0.1 'cd ~/408-viz && git log origin/feature/mvp --oneline && git ls-tree -r --name-only origin/feature/mvp'

# 用 GitHub API 最终确认
ssh hermes@192.168.0.1 'source /opt/ai-agent/workspace/.env && curl -sS https://api.github.com/repos/LoneMonk298/408-viz/commits/feature/mvp -H "Authorization: token ${GITHUB_TOKEN:-$GH_TOKEN}" | jq .sha'
```

---

## 八、待办（按优先级）

1. ✅ 评估修复后的视觉效果（2026-09-09 完成：本地截图评估，发现并修复 3 个 bug，见第五节）
2. ✅ commit + push 视觉修复到 feature/mvp（第一轮 ca42e5d、第三轮 740c4fd、第四轮 3da5f55 均已推送）
3. ✅ FSM 视觉迭代（回环弧线部分缓解垂直空间问题，暂不再处理）
4. ✅ 加 array 渲染器（2026-09-09 完成：折半查找 + 冒泡排序示例，含 swap 双弧交叉动画，见第三节 array 规范）
5. ✅ 加 timeline 渲染器（2026-09-09 完成：SJF vs FCFS 进程调度甘特，含游标动画/进程分色/到达标记，见第三节 timeline 规范）
6. **加 graph 渲染器**（路由/最短路，约 200 行）
7. **加 grid 渲染器**（加法器/Cache/子网，约 250 行）
8. **接 sensenova LLM 解析器**（输入题目+答案 → 生成 IR，确定性校验 + 重试 1 次；IR 规范文档 `schemas/README.md` 已备好可直接入提示词）
9. **集成到 VitePress 博客**（合并 feature/mvp 到 main，VizEmbed 支持新 struct_type）

---

## 九、参考资源

- archify 源码：`https://github.com/tt-a1i/archify`（IR schema 设计参考）
- 沙箱已下载参考文件：`/workspace/archify-ref/*.schema.json`（lifecycle/workflow/architecture schema）
- archify 核心模式：`schemas/*.schema.json` + `renderers/shared/validator.mjs` + `bin/archify.mjs validate`
- viz-animation skill：`/opt/data/skills/software-development/viz-animation/SKILL.md`（博客可视化 UI 规范）
- 用户博客仓库：`https://github.com/LoneMonk298/vitepress-`（最终集成目标）
