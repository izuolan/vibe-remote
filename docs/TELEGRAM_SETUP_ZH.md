# Telegram 机器人设置指南

本指南将指导你为 Vibe Remote 设置 Telegram 机器人。

## 前置条件

- Telegram 账户
- 已安装 Python 3.6 或更高版本
- 已克隆 Vibe Remote 并安装依赖

## 步骤 1：创建 Telegram 机器人

1. 打开 Telegram 并搜索 **@BotFather**
2. 与 BotFather 开始对话
3. 发送命令 `/newbot`
4. 按照提示操作：
   - 为你的机器人选择一个名称（例如 "Vibe Remote"）
   - 为你的机器人选择用户名（必须以 `bot` 结尾，例如 `claude_code_bot`）
5. BotFather 会提供一个**机器人令牌**，格式如下：
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890
   ```
6. **保存此令牌** - 配置时需要使用

## 步骤 2：配置机器人设置（可选）

继续与 BotFather 对话，你可以配置其他设置：

### 设置机器人描述

```
/setdescription
```

然后选择你的机器人并提供描述，例如：
"Vibe Remote - 远程编码助手"

### 设置关于文本

```
/setabouttext
```

选择你的机器人并添加：
"Vibe Remote - AI 驱动的远程编码助手"

### 设置机器人命令

```
/setcommands
```

选择你的机器人并粘贴这些命令：

```
start - 显示欢迎消息和可用命令
clear - 重置对话并重新开始
cwd - 显示当前工作目录
set_cwd - 更改工作目录
settings - 打开个性化设置
```

### 启用内联模式（可选）

```
/setinline
```

这允许机器人在其他聊天中以内联方式使用。

## 步骤 3：配置你的环境

使用以下内容更新你的 `.env` 文件：

```env
# 设置平台为 telegram
IM_PLATFORM=telegram

# Telegram 配置
TELEGRAM_BOT_TOKEN=your-bot-token-here

# 可选：白名单特定聊天 ID（null = 允许所有聊天）
TELEGRAM_CHAT_ID=[-1001234567890,987654321]

# Claude Code 的工作目录
CLAUDE_CWD=/path/to/your/project
```

### 查找聊天 ID

查找聊天 ID 的方法：

#### 个人聊天

1. 向你的机器人发送任何消息
2. 检查机器人日志 - 将显示聊天 ID
3. 个人聊天 ID 是正数

#### 群组

1. 将机器人添加到群组
2. 在群组中发送消息
3. 检查机器人日志中的聊天 ID
4. 群组聊天 ID 是以 `-100` 开头的负数

#### 使用 IDBot（替代方法）

1. 将 **@username_to_id_bot** 添加到你的群组
2. 它会自动显示聊天 ID
3. 获取 ID 后移除该机器人

## 步骤 4：群组的机器人权限

如果你想在群组中使用机器人：

1. 与 **@BotFather** 对话
2. 发送 `/mybots`
3. 选择你的机器人
4. 点击 **Bot Settings**
5. 点击 **Group Privacy**
6. **禁用**隐私模式

这允许机器人查看群组中的所有消息，而不仅仅是命令。

## 步骤 5：启动机器人

```bash
python main.py
```

机器人现在应该正在运行并准备接受命令。

## 使用方法

### 命令

- `/start` - 显示欢迎消息和可用命令
- `/clear` - 重置对话上下文
- `/cwd` - 显示当前工作目录
- `/set_cwd <路径>` - 更改工作目录
- `/settings` - 配置消息可见性和偏好设置

### 向 Claude 发送消息

启动机器人后，只需发送任何消息，它就会被转发到 Claude Code。机器人将：

1. 将你的消息发送到 Claude Code
2. 实时流式传输响应
3. 为后续消息维护对话上下文

### 在群组中使用

在群组中使用机器人时：

- 消息必须以 `/` 开头才能作为命令处理
- 常规消息作为 Claude 查询处理
- 机器人为每个聊天维护独立的会话

## 功能特性

### 消息格式化

机器人支持 Telegram 的 MarkdownV2 格式：

- **粗体文本** 使用 `**文本**`
- _斜体文本_ 使用 `*文本*`
- `代码` 使用反引号
- `代码块` 使用三个反引号

### 内联键盘

设置命令提供内联键盘按钮：

- 显示/隐藏原始 Claude 输出
- 显示/隐藏思考过程
- 重置会话
- 返回主菜单

### 实时流式传输

来自 Claude 的消息实时流式传输：

- 长消息自动分割
- 代码块正确格式化
- 处理期间显示进度

## 故障排除

### 机器人无响应

1. 检查 `.env` 中的机器人令牌是否正确
2. 确保机器人正在运行（检查日志）
3. 验证你的聊天 ID 是否在白名单中（如果使用白名单）

### "未授权"错误

1. 仔细检查机器人令牌
2. 确保你使用的是来自 BotFather 的令牌
3. 如有必要，重新生成令牌：
   - 与 @BotFather 对话
   - 发送 `/revoke`
   - 选择你的机器人
   - 获取新令牌

### 机器人在群组中看不到消息

1. 确保隐私模式已禁用（步骤 4）
2. 检查机器人是否是群组管理员（可选但推荐）
3. 如果使用 `TELEGRAM_CHAT_ID`，验证群组聊天 ID 是否在白名单中

### 消息格式问题

1. 机器人使用 MarkdownV2，需要转义特殊字符
2. 如果消息显示异常，检查日志中的解析错误
3. 特殊字符如 `_`、`*`、`[`、`]`、`(`、`)`、`~`、`` ` ``、`>`、`#`、`+`、`-`、`=`、`|`、`{`、`}`、`.`、`!` 需要转义

### 速率限制

Telegram 有速率限制：

- 每秒向不同用户发送 30 条消息
- 每分钟向同一群组发送 20 条消息
- 每秒向同一用户发送 1 条消息

如果达到速率限制，机器人将自动延迟重试。

## 安全注意事项

### 令牌安全

- 永远不要将机器人令牌提交到版本控制
- 保持令牌私密 - 任何拥有它的人都可以控制你的机器人
- 如果令牌曾经暴露，请重新生成

### 聊天白名单

- 使用 `TELEGRAM_CHAT_ID` 限制机器人访问特定聊天
- 这可以防止未授权用户使用你的机器人
- 仅在开发/测试时将其设置为 `null`

### 群组安全

- 考虑将机器人设为具有受限权限的管理员
- 监控群组中的机器人使用情况
- 在生产部署中使用聊天白名单

## 高级配置

### Webhook 模式（可选）

对于生产部署，你可以使用 webhook 而不是轮询模式。Webhook 模式具有更好的实时性和资源效率。

#### 配置 Webhook

在你的 `.env` 文件中添加以下配置：

```env
# Webhook 配置
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram-webhook
TELEGRAM_WEBHOOK_PORT=8443
TELEGRAM_WEBHOOK_LISTEN=0.0.0.0
TELEGRAM_WEBHOOK_SECRET_TOKEN=your-secret-token-here

# SSL 证书配置（可选，用于自签名证书）
TELEGRAM_WEBHOOK_CERT_PATH=/path/to/your/cert.pem
TELEGRAM_WEBHOOK_KEY_PATH=/path/to/your/private.key
```

#### Webhook 配置参数说明

| 参数 | 说明 | 必需 | 默认值 |
|------|------|------|--------|
| `TELEGRAM_WEBHOOK_URL` | 公开可访问的 HTTPS URL | 是 | 无 |
| `TELEGRAM_WEBHOOK_PORT` | Webhook 服务器监听端口 | 否 | 8443 |
| `TELEGRAM_WEBHOOK_LISTEN` | 监听地址 | 否 | 0.0.0.0 |
| `TELEGRAM_WEBHOOK_SECRET_TOKEN` | 安全令牌，用于验证请求来源 | 推荐 | 无 |
| `TELEGRAM_WEBHOOK_CERT_PATH` | SSL 证书文件路径 | 否 | 无 |
| `TELEGRAM_WEBHOOK_KEY_PATH` | SSL 私钥文件路径 | 否 | 无 |

### 自定义键盘

你可以为常用命令实现自定义键盘布局：

- 用于快速命令访问的回复键盘
- 用于交互式菜单的内联键盘
- 不需要时移除键盘

### 持久化设置

用户设置存储在 `user_settings.json` 中：

- 每用户偏好设置
- 会话管理
- 消息可见性选项

## 其他资源

- [Telegram Bot API 文档](https://core.telegram.org/bots/api)
- [Python Telegram Bot 库](https://python-telegram-bot.org/)
- [BotFather 命令](https://core.telegram.org/bots#botfather)
- [Telegram Bot 最佳实践](https://core.telegram.org/bots/faq)

## 提示

1. **测试**：先创建一个测试机器人来试验设置
2. **日志**：启用调试日志以排除问题
3. **更新**：保持 python-telegram-bot 库更新
4. **监控**：使用机器人分析跟踪使用情况
5. **备份**：定期备份你的 `user_settings.json` 文件
