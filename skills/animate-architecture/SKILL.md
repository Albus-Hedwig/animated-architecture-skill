---
name: animate-architecture
description: Create terminal-style animated architecture diagrams as offline HTML, showing component relationships, directed calls or data flow, and changing execution states. Use for dynamic architecture diagrams, Agent collaboration diagrams, or replayable system walkthroughs; optionally export browser screenshots and GIF previews.
---

# 终端风格动态架构图

把系统的组件结构和一次典型执行过程做成可离线打开、可暂停和拖动时间线的 HTML。默认采用深色终端窗口、等宽字体、柔和的分组颜色、SVG 连线和沿路径移动的光点。图是浏览器实时绘制的；GIF 是可选导出的预览。

## 从用户的系统开始

识别组件、职责、连接方向和需要演示的执行场景。已有材料足够时直接制作；缺少真实架构或关键分支时，仅询问影响正确性的内容。对合理补全的假设作简短说明，模拟的事件和数字标为演示数据。不要把示例中的模型名、规则、阈值或步骤数带到无关系统。

底图表达组件及关系，动画表达一个场景的调用顺序和执行状态。将“任务下发”“结果返回”“异常升级”等不同含义写在连线或事件中。是否需要动画、原生终端输出或视频导出，以用户要求为准；此 skill 的现成模板用于 HTML。

## 制作

读取 [数据格式](references/diagram-format.md)。需要调整风格或复杂连接时再读取 [设计与验证规则](references/design-and-validation.md)。

以 `assets/agent-tree.json` 为当前图的完整案例，或 `assets/order-flow.json` 为另一种拓扑案例。根据目标系统建立 `diagram.json`，不要仅改案例标题。节点、连线与步骤都是数据；通常无需修改渲染器。

先安排节点框，再给连线选择框边上的端口与折点。通道留出标签空间，反馈线绕到外侧，避免线穿过节点。连线使用连续的 SVG 路径；箭头和端口独立，移动光点沿同一路径取位置，不覆盖或替换接点。

运行 skill 目录下的脚本（路径相对于本 skill）：

```bash
python3 scripts/build.py diagram.json --output index.html
```

构建只用 Python 标准库，生成单文件 HTML，数据、CSS 和 JavaScript 全部内嵌。播放无需服务、第三方 CDN 或安装依赖。默认支持播放/暂停、单步、重播、倍速、进度拖动、缩放、适应窗口和全屏；偏好减少动态效果时默认暂停。小窗口保留可读字号并允许横向滚动，也可主动适应窗口。

只在明确需要新视觉行为时修改 `assets/player.template.html`；不要引入图形编辑器、实时模型调用或托管发布来扩大普通制图任务。

## 检查与交付

构建会检查数据引用、时长、数值、边框端点以及路径与节点的关系。对包含反馈、升级或多分支的图，在浏览器检查全流程；不要只看用户圈出的连接或一张静帧。

有 Playwright Chromium 可用时：

```bash
python3 scripts/verify_browser.py index.html --output-dir preview
python3 scripts/verify_browser.py index.html --output-dir preview --gif
```

验证器打开本地 HTML，阻止外部请求，核对所有阶段及播放控制、路径和光点、桌面与小屏布局。第一条输出截图及验证报告；第二条额外输出浏览器截图生成的 GIF，需要 Pillow。若环境限制浏览器，使用可用的浏览器工具验证，明确说明完成范围；不要将构建成功称为视觉验证通过。

查看实际截图，修正溢出、接点、标签遮挡和状态不符。发现布局问题时修数据或模板，重新生成受影响的输出。完成标准是目标图在浏览器正确呈现、需要的交互可用且交付文件已更新；检查通过后停止扩展。

交付可直接打开的 `index.html`、可编辑的 `diagram.json`，以及用户需要的预览。说明哪些事件是模拟，哪些是真实记录。仓库提交、分享、部署或向别人发送文件以当前任务授权为准，普通制图请求不自动授权这些动作。
