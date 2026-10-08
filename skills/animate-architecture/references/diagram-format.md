# diagram.json 格式（version 1）

构建器验证引用、数值和连线路径。所有文字作为文本渲染，不支持在字段中注入 HTML。输入编码为 UTF-8，坐标和尺寸用画布 CSS px。

## 顶层

| 字段 | 内容 |
| --- | --- |
| `version` | 必填，`1` |
| `title` | 必填，主标题 |
| `subtitle` / `windowTitle` | 可选，副标题与窗口栏文字 |
| `simulated` | 默认为模拟；仅当来源为真实执行记录时设置 `false` |
| `canvas` | 必填，`{"width":1200,"height":842}`；不是固定尺寸 |
| `legend` | 可选，`[{"label":"worker","color":"blue"}]` |
| `nodes` | 必填，非空节点数组 |
| `routes` | 必填，连接数组，可以为空 |
| `steps` | 必填，非空时间线步骤数组 |

可用颜色：`cyan`、`blue`、`green`、`purple`、`pink`、`red`。id 使用字母开头的小写字母、数字、连字符或下划线，最多 64 字符，在同类元素中唯一。

画布顶部约 110px 用于标题和图例。不要将普通节点放到这里。小图可以调整模板，不要依靠遮挡标题来节省空间。

## 节点

```json
{
  "id": "router",
  "title": "ROUTER · decision layer",
  "kind": "decision",
  "color": "green",
  "bounds": [240, 300, 420, 210],
  "subtitle": "route selected by policy",
  "lines": ["first condition", "second condition"],
  "rows": [{"label":"mode","value":"demo"}],
  "meters": [{"id":"confidence","label":"confidence","value":0.88,"warningBelow":0.7}],
  "state": "IDLE",
  "operation": "waiting for request",
  "footer": "simulated decisions"
}
```

必填：id、title、bounds。kind 默认为 main，可选 info、main、decision、reviewer、worker，仅影响布局样式。color 默认为 cyan。其余字段按需使用；不要把所有字段都塞进小框。bounds 是 `[x,y,width,height]`。meter value 为 0 到 1；warningBelow 是本系统显式设定的视觉警戒线，不是通用路由阈值。长标题、复杂正文或大量行应增大节点。

## 连接

```json
{
  "id": "request",
  "source": "client",
  "target": "router",
  "color": "cyan",
  "points": [[450,250],[450,300]],
  "label": "request",
  "labelAt": [465,269]
}
```

source/target 引用节点 id。points 必填，至少两点，每段水平或垂直；合并连续同方向段，不能折返。首尾落在 source/target 对应边框的非角落位置。没有自动布局或自动绕线；修改拓扑时明确规划端口和折点。默认颜色取 source 节点的 color。

label 可省略；提供 label 时必须给 labelAt，避免推测标签位置导致遮挡。没有连接含义的交叉和重叠会构建失败；共享节点端口可接多条路径，但节点外共同的线段需要改用明确的 junction 节点。

## 时间线

```json
{
  "id": "evaluate",
  "label": "EVALUATE THE REQUEST",
  "shortLabel": "评估请求",
  "description": "路由层评估候选方案，更新置信度。",
  "duration": 2.8,
  "activeNodes": ["router"],
  "activeRoutes": ["request"],
  "nodeStates": {
    "router": {
      "state": "EVALUATING",
      "operation": "select an action",
      "selectedMeter": "confidence",
      "meterValues": {"confidence":0.88},
      "footer": "decision in progress",
      "tone": "green"
    }
  },
  "routeLabels": {"request":"decision input"}
}
```

必填 id、label、duration；duration 为正数秒，所有步骤的 duration 相加就是播放总时长。activeNodes/activeRoutes 控制高亮与光点，nodeStates 更新任意多个节点；未覆盖字段回到节点基础值，不继承上一步，所以拖动可以直接重建任意阶段。tone 可使用颜色名控制状态文字，selectedMeter 为对应 meter id 或 null。routeLabels 可在某一步更改已有连接标签。

## 参考样例

`assets/agent-tree.json` 保留原图的 Agent 分层、异常复核和决策条；`assets/order-flow.json` 是不同数量节点、画布和流程的订单处理案例。先阅读与目标最接近的案例，再改为自己的真实组件与动作。
