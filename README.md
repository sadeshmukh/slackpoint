# Slackpoint

A Slack bot to generate checkpoints from thread replies to jump within the thread quickly.

## Development Setup
Scopes required for message shortcut capability: channels:history, channels:join, chat:write, chat:write.public, commands, groups:history, groups:read, im:read, mpim:read, channels:read

To install and run with `uv`, 
```bash
uv sync && uv run main.py
```

Include your Slack bot and app token in `.env`:
```SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

## Contributing
Contributions are welcome! Please open issues or pull requests for any features, bugs, or improvements.