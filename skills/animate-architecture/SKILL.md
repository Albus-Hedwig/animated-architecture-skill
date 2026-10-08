---
name: animate-architecture
license: MIT
description: Create terminal-style animated architecture diagrams as offline HTML, showing component relationships, directed calls or data flow, and changing execution states. Use for dynamic architecture diagrams, Agent collaboration diagrams, or replayable system walkthroughs; optionally export browser screenshots and GIF previews.
---

# 终端风格动态架构图

把真实组件关系和一次典型执行过程做成单文件 HTML：深色终端窗口、SVG 连线、路径光点，可离线播放、暂停和拖动。GIF 仅在用户需要时导出。

## 确定内容

先确认组件职责、连接方向和演示场景。沿用现行事实源；已有资料足够时直接制作，不为制图重新全面梳理项目。缺少会改变架构正确性的信息才提问。模拟事件、数字和播放时长必须标明演示，不宣称真实运行记录。

底图表达组件关系，动画表达调用顺序。请求、结果、异常用各自明确的方向和文字；不把所有可能分支塞进一单演示，也不沿用示例的模型、阈值或业务规则。

## 按需读取与制作

1. 读取 [数据格式](references/diagram-format.md)，再选一个最接近的布局样例：
   - 横向流水线与回执：`assets/order-flow.json`。
   - 中心协调、左右服务和往返通道：`assets/hub-feedback.json`。
   - 分层协作与异常复核：`assets/agent-tree.json`。
2. 根据用户系统填写 `diagram.json`，复用合适的几何结构，不只替换示例标题。涉及复杂反馈或风格调整时，才读 [设计与验证](references/design-and-validation.md)。
3. 通常直接运行脚本；只有修改或排查失败时才读取脚本或播放器完整实现。不要为每张图重新编写验证脚本。

先安排节点和走线通道再填文字。端点落在框边非角点，路径不穿节点、不无意义交叉或重叠；反馈占独立通道。节点、箭头、端口保持固定，只有活动路径和光点运动。双向交互用分开的请求、回报路线。

在 skill 目录下运行，路径按实际文件位置调整：

```bash
python3 scripts/build.py diagram.json --output index.html --verify
```

这一次调用构建 HTML、选择已安装的验证环境、检查完整流程，并生成 `preview/preview.png`、`mobile.png`、`verification.json`。构建只依赖 Python 标准库；播放不依赖本地资源路径、服务或 CDN。

## 验证与交付

验证默认复用现有 `agent-browser`；不可用时选已安装的 Playwright。不会自动安装依赖。后端选定后，权限失败、启动失败或验收失败应明确报出，不能换后端掩盖问题；权限限制按当前执行环境处理。

独立验证、环境查看和可选输出：

```bash
python3 scripts/verify_browser.py index.html --output-dir preview
python3 scripts/verify_browser.py --doctor
python3 scripts/verify_browser.py index.html --engine playwright --browser-path /path/to/chrome
python3 scripts/verify_browser.py index.html --all-steps
python3 scripts/verify_browser.py index.html --gif
```

默认检查每个阶段，但只保存代表图和小屏截图；`--all-steps` 才保存逐阶段 PNG。GIF 保留 Playwright 路径，需要 Pillow，不作为常规检查的一部分。需要安装时按 [可选浏览器环境](references/browser-setup.md) 使用独立虚拟环境。选择 `agent-browser` 时，先按该 CLI 的 core 指南确认工作方式；无需加载整套 `--full` 手册。

验证覆盖状态、文字边界、端点/箭头/光点、暂停/单步/拖动/倍速/循环、缩放/全屏、桌面/小屏及减少动态效果。查看实际截图，修正溢出或接点问题；报告通过不等于视觉审阅通过。若浏览器受限，说明尚未完成的检查，不把构建成功当作视觉验收。

同一轮小改动只补查受影响的状态、文字和路径；播放器或控制逻辑改变时重新跑完整检查。只在确需新视觉行为时修改 `assets/player.template.html`，不引入图形编辑器、实时模型或托管发布。

交付 `index.html`、`diagram.json` 和所需预览。说明模拟范围；Git 提交、分享、部署或发送给别人仍以用户当前授权为准。

## 许可与来源

本 skill 使用 [MIT 许可证](LICENSE)。保留模板及生成 HTML 注释中的完整版权和许可声明，单独分发 skill 时附带 LICENSE。MIT 覆盖本项目的渲染器、文档和原创示例；用户自行输入的业务内容和第三方素材遵循各自的权利及许可，不因使用本工具自动改为 MIT。
