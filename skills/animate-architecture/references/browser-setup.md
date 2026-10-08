# 可选浏览器验证环境

生成和播放 HTML 只需 Python 标准库与浏览器。已安装 `agent-browser` 时，HTML／PNG 验证不需要安装 Python 浏览器依赖。只有需要 Playwright 验证或 GIF 时才安装以下环境；不会修改系统 Python。

在仓库根目录执行，使用已安装的 uv：

```bash
uv venv --python python3 "$HOME/.local/share/animate-architecture/venv"
uv pip install --python "$HOME/.local/share/animate-architecture/venv/bin/python" -r skills/animate-architecture/requirements-browser.txt
"$HOME/.local/share/animate-architecture/venv/bin/python" skills/animate-architecture/scripts/verify_browser.py --doctor
```

没有 uv 时可用标准库：`python3 -m venv "$HOME/.local/share/animate-architecture/venv"`，再用该环境的 `bin/python -m pip install -r skills/animate-architecture/requirements-browser.txt`。若系统没有 venv 支持，先按系统的安装流程补齐，不向系统 Python 安装这些包。

从已安装的 skill 执行时，把 `skills/animate-architecture/` 换成实际 skill 目录。可通过 `--browser-path` 明确指定本地 Chrome；默认识别 PATH 中的 Chromium 浏览器，以及 macOS `/Applications` 或 `~/Applications` 下的 Chrome、Chromium、Edge。

```bash
"$HOME/.local/share/animate-architecture/venv/bin/python" skills/animate-architecture/scripts/build.py skills/animate-architecture/assets/hub-feedback.json --output dist/hub-feedback.html
"$HOME/.local/share/animate-architecture/venv/bin/python" skills/animate-architecture/scripts/verify_browser.py dist/hub-feedback.html --output-dir dist/hub-feedback-preview --engine playwright --gif
```

输出包含真实浏览器截图、`verification.json` 和 `demo.gif`。若未检测到浏览器且没有 Playwright 缓存，明确选择下载 Chromium 后，使用该环境的 `bin/python -m playwright install chromium`；验证器不自动下载。

HTML／PNG 默认 `--engine auto`，优先现有 `agent-browser`；GIF 自动选择 Playwright。选定后不会因权限、启动或验收失败改用另一个后端。`--doctor` 只报告当前 Python 解释器内的依赖：系统 `python3` 与虚拟环境可能给出不同结果。

## 本次实测

2026-10-08 在 Linux、Python 3.12.3、Chrome 155 上验证 Playwright 1.63.0 与 Pillow 12.3.0；GIF 使用现有 Chrome，未下载 Chromium。macOS 浏览器路径识别有单元测试，但尚未在 Mac 上执行安装和完整浏览器验收。
