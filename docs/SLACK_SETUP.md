# Slack Bot Setup Guide

This guide will walk you through setting up a Slack bot for the Claude Code Remote Control Bot.

## Prerequisites

- Admin access to a Slack workspace
- Python 3.6 or higher installed
- Claude Code Remote Control Bot cloned and dependencies installed

## Step 1: Create a Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Enter an app name (e.g., "Claude Code Bot")
4. Select your workspace
5. Click **"Create App"**

## Step 2: Configure Bot Token Scopes

1. In your app's settings, navigate to **"OAuth & Permissions"** in the sidebar
2. Scroll down to **"Scopes"** → **"Bot Token Scopes"**
3. Add ALL the following OAuth scopes to avoid permission issues:

### Essential Scopes (Required)
   - `channels:history` - View messages in public channels
   - `channels:read` - View basic information about public channels
   - `chat:write` - Send messages as bot
   - `im:history` - View direct message history
   - `im:read` - View basic information about direct messages
   - `im:write` - Send direct messages
   - `app_mentions:read` - View messages that mention your bot
   - `users:read` - View basic information about users
   - `commands` - Use slash commands (automatically added)

### Private Channel Support
   - `groups:read` - View basic information about private channels
   - `groups:history` - View messages in private channels  
   - `groups:write` - Send messages to private channels

### Multi-Party DM Support  
   - `mpim:read` - View basic information about group DMs
   - `mpim:history` - View messages in group DMs
   - `mpim:write` - Send messages to group DMs

### Enhanced Features
   - `chat:write.public` - Send messages to channels without joining
   - `chat:write.customize` - Send messages with custom username and avatar
   - `files:read` - View files shared in channels (for future file handling)
   - `files:write` - Upload files (for future file upload support)
   - `reactions:read` - View emoji reactions
   - `reactions:write` - Add emoji reactions
   - `users:read.email` - View email addresses (for enhanced user info)
   - `team:read` - View team/workspace information

**Note**: It's better to add all permissions now to avoid reinstalling the app multiple times later. Unused permissions won't affect the bot's performance.

### Quick Permission Checklist
To ensure full functionality, make sure you've added:
- ✅ All Essential Scopes (9 scopes)
- ✅ All Private Channel scopes (3 scopes) 
- ✅ All Multi-Party DM scopes (3 scopes)
- ✅ Any Enhanced Features you want (up to 8 additional scopes)

**Total recommended scopes: ~23 scopes** for full functionality without future permission issues.

## Step 3: Install App to Workspace

1. Still in **"OAuth & Permissions"**, scroll to the top
2. Click **"Install to Workspace"**
3. Review the permissions and click **"Allow"**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
   - Save this as `SLACK_BOT_TOKEN` in your `.env` file

## Step 4: Enable Socket Mode (Recommended)

Socket Mode allows your bot to connect without exposing a public URL.

1. Go to **"Socket Mode"** in the sidebar
2. Toggle **"Enable Socket Mode"** to On
3. You'll be prompted to generate an app-level token:
   - Token Name: "Socket Mode Token"
   - Add scope: `connections:write`
   - Click **"Generate"**
4. Copy the **App-Level Token** (starts with `xapp-`)
   - Save this as `SLACK_APP_TOKEN` in your `.env` file

## Step 5: Configure Event Subscriptions

1. Go to **"Event Subscriptions"** in the sidebar
2. Toggle **"Enable Events"** to On
3. Under **"Subscribe to bot events"**, add ALL these events:

### Message Events
   - `message.channels` - Messages in public channels
   - `message.groups` - Messages in private channels
   - `message.im` - Direct messages
   - `message.mpim` - Messages in group DMs
   - `app_mention` - When someone mentions your bot

### Additional Events (Optional but Recommended)
   - `member_joined_channel` - When bot joins a channel
   - `member_left_channel` - When bot leaves a channel
   - `channel_created` - When a new channel is created
   - `channel_renamed` - When a channel is renamed
   - `team_join` - When a new member joins the workspace

4. Click **"Save Changes"**

**Note**: Adding all events now prevents the need to reconfigure later when expanding bot functionality.

## Step 6: Configure Native Slash Commands (Recommended)

Native Slack slash commands provide the best user experience with autocomplete and help text. Here's a detailed step-by-step guide:

### 6.1 Access Slash Commands Configuration

**详细步骤**:
1. **打开浏览器** 并导航到 [https://api.slack.com/apps](https://api.slack.com/apps)
2. **登录你的 Slack 账户** (如果尚未登录)
3. **找到你的 App**: 在 "Your Apps" 列表中找到之前创建的 Claude Code Bot 应用
4. **点击应用名称** 进入应用管理界面
5. **导航到斜杠命令**: 在左侧边栏中，找到 **"Features"** 分组，点击 **"Slash Commands"**
6. **查看当前状态**: 你会看到标题为 "Slash Commands" 的页面，显示任何现有的命令

**页面说明**:
- 如果是新应用，页面会显示 "You haven't created any slash commands yet"
- 右上角有绿色的 **"Create New Command"** 按钮
- 现有命令会以列表形式显示，每个命令都有编辑选项

### 6.2 创建命令的通用流程

**每个命令的创建步骤**:
1. **点击 "Create New Command"** 按钮 (页面右上角的绿色按钮)
2. **填写命令表单** (详见下方每个命令的具体配置)
3. **点击 "Save"** 保存命令
4. **等待确认** - Slack 会显示 "Your slash command was saved!" 的成功消息
5. **返回命令列表** 验证命令已创建

**重要提醒**:
- ⚠️ 每次只能创建一个命令，需要重复8次这个过程
- ⚠️ 命令名称不能重复，不能包含空格
- ⚠️ 所有字段都区分大小写

### 6.3 推荐创建的命令 (逐一配置)

**配置原则**:
- 所有命令的 **Request URL** 都留空 (我们使用 Socket Mode)
- 所有命令都要勾选 **"Escape channels, users, and links"**
- 按照下面的模板逐个创建，可以直接复制粘贴

---

#### 命令 1/8: `/claude-start` 
**📋 复制这些内容到表单**:
```
Command: /claude-start
Request URL: (留空)
Short Description: Show welcome message and help
Usage Hint: Get started with Claude Code bot
```
**操作步骤**:
1. 点击 **"Create New Command"**
2. 在 **"Command"** 字段填入: `/claude-start`
3. **"Request URL"** 保持空白 (不要填任何内容)
4. 在 **"Short Description"** 字段填入: `Show welcome message and help`
5. 在 **"Usage Hint"** 字段填入: `Get started with Claude Code bot`
6. ✅ **勾选** "Escape channels, users, and links" 复选框
7. 点击 **"Save"** 按钮
8. 看到绿色成功消息后点击 **"← Back to Slash Commands"**

#### 命令 2/8: `/claude-status`
**📋 复制这些内容到表单**:
```
Command: /claude-status
Request URL: (留空)
Short Description: Show current queue status
Usage Hint: Check queue and execution status
```
**重复上述步骤，将对应内容填入表单各字段**

---

#### 命令 3/8: `/claude-clear`
**📋 复制这些内容到表单**:
```
Command: /claude-clear
Request URL: (留空)
Short Description: Clear message queue
Usage Hint: Clear all queued messages
```

---

#### 命令 4/8: `/claude-cwd`
**📋 复制这些内容到表单**:
```
Command: /claude-cwd
Request URL: (留空)
Short Description: Show current working directory
Usage Hint: Display current working directory
```

---

#### 命令 5/8: `/claude-set-cwd`
**📋 复制这些内容到表单**:
```
Command: /claude-set-cwd
Request URL: (留空)
Short Description: Set working directory
Usage Hint: Set working directory: /path/to/directory
```

---

#### 命令 6/8: `/claude-queue`
**📋 复制这些内容到表单**:
```
Command: /claude-queue
Request URL: (留空)
Short Description: Show message queue
Usage Hint: View messages in queue
```

---

#### 命令 7/8: `/claude-settings`
**📋 复制这些内容到表单**:
```
Command: /claude-settings
Request URL: (留空)
Short Description: Configure personalization settings
Usage Hint: Open personalization settings menu
```

---

#### 命令 8/8: `/claude-execute`
**📋 复制这些内容到表单**:
```
Command: /claude-execute
Request URL: (留空)
Short Description: Process queue manually
Usage Hint: Manually trigger queue processing
```

**🎉 完成后**: 返回 Slash Commands 主页面，你应该看到所有8个命令都已列出。

### 6.4 Important Configuration Notes

- **Request URL**: Always leave this empty when using Socket Mode (recommended)
- **Socket Mode Required**: These commands only work when Socket Mode is enabled (Step 4)
- **Case Sensitive**: Command names are case-sensitive
- **No Automation**: Currently, Slack doesn't provide an API to create slash commands programmatically - they must be created manually through the web interface
- **3-Second Response**: The bot has 3 seconds to acknowledge slash commands (handled automatically)

### 6.5 Verification

After creating all commands:
1. Go back to the main "Slash Commands" page
2. You should see all 8 commands listed
3. Each command should show "✅ Configured" status

### 6.6 快速设置检查清单

**逐项检查确保设置正确**:
- [ ] 访问了 [https://api.slack.com/apps](https://api.slack.com/apps) 并选择了正确的应用
- [ ] 导航到了 "Features" > "Slash Commands" 页面  
- [ ] 创建了 `/claude-start` 命令
- [ ] 创建了 `/claude-status` 命令
- [ ] 创建了 `/claude-clear` 命令
- [ ] 创建了 `/claude-cwd` 命令
- [ ] 创建了 `/claude-set-cwd` 命令
- [ ] 创建了 `/claude-queue` 命令
- [ ] 创建了 `/claude-settings` 命令
- [ ] 创建了 `/claude-execute` 命令
- [ ] 所有命令的 **Request URL** 都是空白的
- [ ] 所有命令都勾选了 **"Escape channels, users, and links"**
- [ ] 在 Slash Commands 主页面能看到全部8个命令列出

### 6.7 常见问题排查

#### ❌ 问题：命令创建后不显示自动完成
**原因**: 应用可能需要重新安装到工作区
**解决方案**:
1. 前往 "OAuth & Permissions" 页面
2. 点击 "Reinstall to Workspace"
3. 重新授权应用

#### ❌ 问题：输入 `/claude-` 没有命令提示
**可能原因**:
- 命令名称拼写错误 (检查是否有多余空格或字符)
- 应用未正确安装到当前工作区
- Socket Mode 未启用

**解决步骤**:
1. 检查命令列表，确认命令名称完全正确
2. 确认 Socket Mode 已启用 (Step 4)
3. 确认 bot 已添加到当前频道: `/invite @YourBotName`

#### ❌ 问题："This command doesn't exist" 错误
**原因**: 命令配置有误或未保存成功
**解决方案**:
1. 回到 Slash Commands 页面验证命令确实存在  
2. 检查命令名称是否与输入完全匹配
3. 尝试删除并重新创建该命令

#### ❌ 问题：命令执行后无响应
**原因**: Bot 应用可能未运行或连接有问题
**解决方案**:
1. 检查 bot 进程是否在运行
2. 查看 bot 日志是否有错误信息
3. 确认 `SLACK_APP_TOKEN` 和 `SLACK_BOT_TOKEN` 配置正确

### 6.8 设置完成验证

**测试步骤**:
1. 在任意频道或 DM 中输入 `/claude-` 
2. 应该看到所有8个命令的自动完成列表
3. 选择 `/claude-start` 并发送
4. Bot 应该响应欢迎消息

**预期结果**: 
- ✅ 命令自动完成正常工作
- ✅ 命令执行后 bot 能正确响应
- ✅ 在频道中使用命令会创建线程回复

### 6.7 Automation Possibilities (Currently Limited)

**Can Slash Commands Be Created Automatically?**

Unfortunately, as of 2025, Slack does not provide an API to programmatically create slash commands. They must be created manually through the Slack App Management interface at [api.slack.com/apps](https://api.slack.com/apps).

**Why No Automation?**
- Slack considers slash commands part of the app's core configuration
- Each command requires careful consideration of permissions and scope  
- Manual creation ensures proper security review
- Prevents automated spam of command namespaces

**Alternative Approaches:**
- Use the existing `/claude-*` command pattern for consistency
- Focus on @ mention + command syntax for dynamic commands
- Consider using Slack's Block Kit for interactive menus instead of many commands

**Future Possibilities:**
- Slack may introduce API endpoints for slash command management
- Consider using Slack's Workflow Builder for some automation needs
- Monitor Slack's developer blog for new automation features

## Step 7: Configure Your Environment

Update your `.env` file with the following:

```env
# Set platform to slack
IM_PLATFORM=slack

# Slack configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# Optional: Whitelist of allowed channel IDs (empty = DM only, null = all channels)
SLACK_TARGET_CHANNEL=[C1234567890,C0987654321]
```

### Finding Channel IDs

To find a channel ID:
1. Right-click on the channel name in Slack
2. Select **"View channel details"**
3. Scroll to the bottom
4. The Channel ID starts with `C` for public channels

## Step 8: Invite Bot to Channels

Before the bot can interact with a channel, you need to invite it:

1. In Slack, go to the channel
2. Type `/invite @YourBotName`
3. Press Enter

## Step 9: Start the Bot

```bash
python main.py
```

## Usage

### Command Methods

The bot supports multiple ways to use commands:

#### 1. Native Slash Commands (Recommended)
If you configured slash commands in Step 6:
```
/claude-start
/claude-status
/claude-cwd
```
- Provides autocomplete and help text
- Works in any channel where the bot is invited
- Most user-friendly experience

#### 2. @ Mention + Command
Mention the bot followed by a command:
```
@YourBotName /start
@YourBotName /status
@YourBotName /cwd
```

#### 3. Direct Message Commands
In DMs with the bot, use commands directly:
```
/start
/status
/cwd
```

### In Channels
- Mention the bot: `@YourBotName your message here`
- The bot will create a thread for the conversation

### In Direct Messages
- Send any message directly to the bot
- No mention needed in DMs

### Commands
All commands work the same as in Telegram:
- `/start` - Show welcome message
- `/execute` - Manually process queue
- `/clear` - Clear message queue
- `/status` - Show current status
- `/queue` - Show messages in queue
- `/cwd` - Show working directory
- `/set_cwd <path>` - Set working directory
- `/settings` - Configure message visibility

## Thread Support

The Slack bot automatically uses threads to organize conversations:
- Each user's messages are grouped in a thread
- Responses from Claude Code appear in the same thread
- This keeps channel history clean and organized

## Troubleshooting

### Bot not responding
1. Check that the bot is online (green dot in Slack)
2. Verify the bot was invited to the channel
3. Check logs for any error messages

### Permission errors
1. Ensure all required scopes are added (including `groups:read` for private channels)
2. **Important**: After adding new scopes, you MUST reinstall the app to workspace:
   - Go to **"OAuth & Permissions"** page
   - Click **"Reinstall to Workspace"** button at the top
   - Review and approve the new permissions
3. Verify tokens are correctly set in `.env`

### Private Channel Access Issues
If you see `missing_scope` errors with `groups:read`:
1. Add ALL private channel scopes: `groups:read`, `groups:history`, `groups:write`
2. Click **"Reinstall to Workspace"** (this is mandatory!)
3. Copy the new Bot Token and update your `.env` file
4. Restart the bot
5. Ensure bot is invited to the private channel: `/invite @YourBotName`

### Thread Reply Issues
If you see `cannot_reply_to_message` error:
1. This usually means the bot is trying to reply to a message that doesn't exist or in wrong context
2. Ensure the bot has `channels:history` or `groups:history` permission for the channel type
3. Check that the message timestamp (thread_ts) is valid
4. Verify the bot is a member of the channel where it's trying to reply

### Socket Mode issues
1. Ensure `SLACK_APP_TOKEN` is set correctly
2. Check that the app-level token has `connections:write` scope
3. Verify Socket Mode is enabled in app settings

### Slash Command Issues

#### Slash commands not appearing in autocomplete
**Symptoms:** When typing `/claude-`, no autocomplete suggestions appear
**Solutions:**
1. Verify slash commands were created successfully in app settings
2. Check that the bot is installed in the workspace
3. Try reinstalling the app to workspace
4. Ensure you're in a channel where the bot is invited

#### "Command not found" error
**Symptoms:** Slack shows "Sorry, `/claude-start` didn't work. You might be looking for something else?"
**Solutions:**
1. Double-check command spelling in Slack App settings
2. Ensure Socket Mode is enabled and connected
3. Verify `SLACK_APP_TOKEN` is set correctly
4. Check bot logs for connection errors
5. Try restarting the bot application

#### Slash commands timeout
**Symptoms:** Slack shows "Timeout: Command failed to respond"  
**Solutions:**
1. Check bot application is running and connected
2. Verify Socket Mode connection is stable
3. Look for errors in bot logs during command execution
4. Ensure the bot responds within 3 seconds (handled automatically by our code)

#### Commands work in DMs but not in channels
**Symptoms:** Slash commands work in direct messages but fail in channels
**Solutions:**
1. Ensure bot is invited to the channel: `/invite @YourBotName`
2. Check bot has necessary channel permissions
3. Verify `channels:history` and `channels:read` scopes are added

#### "This app doesn't have permission to respond" error
**Symptoms:** Bot receives command but can't respond
**Solutions:**
1. Add missing OAuth scopes: `chat:write`, `im:write`
2. Reinstall app to workspace after adding scopes
3. Check `SLACK_BOT_TOKEN` is correctly set

#### Slash commands show but execute as text
**Symptoms:** Commands appear as regular messages instead of executing
**Solutions:**
1. Verify Socket Mode is enabled (not webhook mode)
2. Check `_handle_slash_command` method is being called in logs
3. Ensure command mapping in `slack_bot.py` is correct
4. Restart the bot application

### Debug Commands

Use these methods to test if slash commands are working:

#### Test in Direct Message
1. Send a DM to the bot
2. Try `/claude-start` 
3. Should work without @ mention

#### Test in Channel with @ Mention
1. In a channel where bot is invited
2. Try `@YourBotName /start`
3. Should create a thread with response

#### Check Bot Status
1. Look for "🟢 Online" indicator next to bot name
2. If offline, check connection and tokens
3. Restart bot if needed

#### Verify Command Registration
Check the bot logs for these messages on startup:
```
INFO - Starting Slack bot in Socket Mode...
INFO - A new session has been established
```

## Alternative: Webhook Mode

If you prefer to use webhooks instead of Socket Mode:

1. Set up a public HTTPS endpoint
2. Configure the Request URL in Event Subscriptions
3. Add `SLACK_SIGNING_SECRET` to your `.env`
4. Remove or leave empty `SLACK_APP_TOKEN`

Note: Webhook mode requires a publicly accessible HTTPS endpoint, which is more complex to set up.

## Security Considerations

- Never commit tokens to version control
- Use environment variables for all sensitive data
- Regularly rotate your tokens
- Only grant necessary permissions to the bot

## Additional Resources

- [Slack API Documentation](https://api.slack.com/)
- [Python Slack SDK](https://slack.dev/python-slack-sdk/)
- [Socket Mode Guide](https://api.slack.com/apis/connections/socket)