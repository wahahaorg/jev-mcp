# Jev MCP

[English README](README.md)

`jev-mcp` 将 [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) 封装成一个本地、带会话管理的 MCP Server，用于快速的**只读商品浏览与采集**。Jev 根据 DOM 快照选择动作和已观察到的目标元素；本项目提供适合 MCP Host 调用的工具、会话生命周期与安全护栏。

## 它是什么，不是什么

这是**一个本地 stdio MCP Server**，不是浏览器扩展，也不是四个独立 MCP。它管理由 Jev 创建的 Chrome 页面，并暴露五个供模型调用的工具：

| 工具 | 适用场景 | 不会执行 |
| --- | --- | --- |
| `jev_browse` | 在公开站点搜索、筛选、打开商品详情 | 登录、下单、付款、上传或提交订单 |
| `jev_status` | 查看会话 URL、可见文本、可操作控件和最近动作 | 额外点击、输入或滚动 |
| `jev_extract_products` | 提取当前可见商品卡片的名称、价格、评分、详情和链接 | 滚动、点击或保证所有站点都能准确解析 |
| `jev_stop` | 关闭 Jev 自己创建的 Chrome 页面 | 影响用户正在使用的普通 Chrome 标签页 |
| `jev_decide` | 中继模式：判断外部传入的页面状态并返回下一步动作 + 目标元素，不碰浏览器 | 打开浏览器、会话或标签页；执行任何页面动作 |

**中继模式**：如果只想把 Jev 当作中间判断的中继——由你自己的浏览器工具（如 opencli、computer-use）驱动页面，把观察到的元素传进来——只使用 `jev_decide`。它不会打开浏览器、会话或标签页，因此不会产生任何新页面。

上游 Jev 仍以独立 Git 依赖的方式使用，并固定在提交 `1231850a0bf1a0c0341fe408ef1668dbbfdfac46`。本仓库只负责 MCP 会话层、结果压缩、商品提取和安全限制；这样既不侵入上游，也便于之后审查升级。

## 前置条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- 可被 `browser-harness` 使用的 Chrome/Chromium
- 用于 Jev 决策的 `OPENROUTER_API_KEY`（推荐），或直连 TypeSafe 的 `TYPESAFE_API_KEY`
- 用于填写搜索词或筛选条件的 `TEXT_MODEL_API_KEY`；示例默认使用 OpenRouter

## 安装

```bash
git clone https://github.com/wahahaorg/jev-mcp.git
cd jev-mcp
cp .env.example .env
# 在 .env 写入真实密钥；不要提交此文件。默认走 OpenRouter Decisions。
uv sync
uv run browser-harness --doctor
```

`browser-harness` 第一次运行时可能请求 Chrome 的远程调试权限。Jev 会创建自己的后台页面，不会抢占你当前可见的标签页。

本地启动：

```bash
uv run --env-file .env jev-mcp
```

服务使用 stdio；标准输出专用于 MCP JSON-RPC，因此启动后会等待 MCP Host 连接，不会自行打开网页。

## 配置到 MCP Host

将 [`.mcp.json`](.mcp.json) 中 `mcpServers.jev-browser` 的对象复制到 MCP Host 配置。若 Host 不在仓库目录启动命令，请将目录替换为本仓库的绝对路径。

示例：

```json
{
  "mcpServers": {
    "jev-browser": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/jev-mcp", "--env-file", ".env", "jev-mcp"]
    }
  }
}
```

密钥请放到 Host 环境变量或 `.env`，绝不应写入并提交到仓库配置。仓库内的示例配置假定 Host 从本仓库目录启动；其他场景请使用上面的绝对路径版本。

## 常用调用流程

1. 使用 `jev_browse`，提供公开 URL 和明确目标。例如：“搜索无线降噪耳机，设置价格低于 100 美元，结果列表可见时停止。”
2. 保存返回的 `session_id`。
3. 需要判断页面状态或受阻原因时，调用 `jev_status`。
4. 结果列表或详情页可见后，调用 `jev_extract_products`。
5. 完成后调用 `jev_stop`。

存在 `OPENROUTER_API_KEY` 时，服务会通过 OpenRouter 的 alpha Decisions endpoint 调用 `~typesafe/jev-latest`；否则保留上游直连 TypeSafe 的兼容路径。单次 `jev_browse` 最多执行 30 个浏览器动作；上游 Jev 整次运行最多 60 步。输出是页面观察结果，不代表库存、可售状态或结算价格已被确认。

## 安全模型

服务会在打开浏览器前拒绝交易型目标；在动作执行前拦截加入购物车、购买、结算、付款、上传、密码、银行卡和验证码控件。上游的 DOM 快照本身也会排除密码和文件控件。因此这是浏览/采集工具，而不是代购或下单机器人。

网页内容一律视为不可信数据。商品提取只处理当前可见卡片，属于尽力而为的解析；重要价格、规格、运费和库存都应回到原页面核验。

## 开发与验证

```bash
uv run ruff check .
uv run pytest
npx @modelcontextprotocol/inspector uv run --env-file .env jev-mcp
```

测试使用假的浏览器和 Agent，不会消耗 API 额度或要求 Chrome。`evals.xml` 含有十个多工具场景，覆盖正常路径、错误恢复与安全边界。请在配置真实密钥后，通过 Inspector 再完成一次公开网站的 MCP 联调。

## 许可证

MIT。上游 Jev 也是 MIT 许可证，具体条款和声明请查看其仓库。
