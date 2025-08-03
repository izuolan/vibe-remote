import time
import anyio
from claude_code_sdk import (
    query,
    ClaudeCodeOptions,
    AssistantMessage,
    TextBlock,
    UserMessage,
)


async def main():
    options = ClaudeCodeOptions(
        permission_mode="bypassPermissions", cwd="./_tmp", continue_conversation=True
    )

    async for message in query(
        prompt="写一个 Hello World 的 python3 程序并运行它", options=options
    ):
        print(message)
        print()


if __name__ == "__main__":
    anyio.run(main)
