# 408-Viz 交接文档

**时间**：2026-09-09
**项目位置**：
- 服务器：`hermes@192.168.0.1:~/408-viz/`（git 仓库已 init，remote origin 已配 GitHub token）
- GitHub：`https://github.com/LoneMonk298/408-viz`（public，default_branch=main）
- 分支：`main`（空占位 commit `1ae51c9`）、`feature/mvp`（MVP 全部代码 commit `4f48c76`）
- ⚠️ 视觉修复**尚未 commit**，服务器上是旧版渲染器

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
| array | ⏳ 待做（排序/折半查找） |
| timeline | ⏳ 待做（进程调度甘特） |
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

## 五、已完成的视觉修复（⚠️ 未 commit）

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

### ⚠️ 未解决/需评估

fsm 的 4 个状态在 `col:0,1,2,3` 横向排开，本来就该是横线。但视觉上"挤中间"——canvas 高 510 浪费了大量垂直空间。**如果视觉上还是不满意，可以考虑**：
- 让 FSM 节点垂直分布（不再一行）
- 或者按 col 数动态调整 canvas 高度
- 或者增加 sublabel 的视觉重量，让单行 FSM 更"满"

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

1. **评估修复后的视觉效果**（你本地打开 HTML 看）
2. **commit + push 视觉修复到 feature/mvp**
3. **视觉迭代**（如果 FSM 还是太扁）：让 FSM 节点垂直分布 / 按 col 数动态调整 canvas 高度
4. **加 array 渲染器**（排序/折半查找，最简单，约 150 行）
5. **加 timeline 渲染器**（进程调度甘特，408 大题常客，约 200 行）
6. **加 graph 渲染器**（路由/最短路，约 200 行）
7. **加 grid 渲染器**（加法器/Cache/子网，约 250 行）
8. **接 sensenova LLM 解析器**（输入题目+答案 → 生成 IR，确定性校验 + 重试 1 次）
9. **集成到 VitePress 博客**（合并 feature/mvp 到 main，VizEmbed 支持新 struct_type）

---

## 九、参考资源

- archify 源码：`https://github.com/tt-a1i/archify`（IR schema 设计参考）
- 沙箱已下载参考文件：`/workspace/archify-ref/*.schema.json`（lifecycle/workflow/architecture schema）
- archify 核心模式：`schemas/*.schema.json` + `renderers/shared/validator.mjs` + `bin/archify.mjs validate`
- viz-animation skill：`/opt/data/skills/software-development/viz-animation/SKILL.md`（博客可视化 UI 规范）
- 用户博客仓库：`https://github.com/LoneMonk298/vitepress-`（最终集成目标）
