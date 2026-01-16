# ToHatch Bot 🥚

Telegram bot for sending and hatching eggs via inline mode with statistics tracking.

## Features

- ✅ Inline mode - send eggs in any chat via `@tohatchbot egg`
- ✅ Only recipients can hatch eggs (sender cannot hatch their own)
- ✅ Statistics tracking - how many eggs you hatched and how many of yours were hatched
- ✅ API server for mini app integration
- ✅ Beautiful mini app integration

## Quick Start

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set bot token in `bot.py` or use environment variable:
```bash
export BOT_TOKEN=your_token_here
```

3. Run bot:
```bash
python bot.py
```

The bot will start and API server will be available on `http://localhost:8080/api/stats`

## Deployment

### Railway (Recommended)

1. Go to https://railway.app
2. New Project → Deploy from GitHub repo
3. Select this repository: `ViberKoder/bot`
4. Add environment variable:
   - `BOT_TOKEN=8439367607:AAGcK4tBrXKkqm5DDG7Sp3YSKEQTX09XqXE`
5. Railway will automatically detect Python and run the bot

After deployment, you'll get a public URL like: `https://your-app.railway.app`

### Render

1. Go to https://render.com
2. New → Web Service
3. Connect GitHub repo
4. Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
5. Add `BOT_TOKEN` environment variable

## API Endpoint

The bot runs an API server on port 8080 (or PORT from environment):

```
GET /api/stats?user_id={user_id}
```

Response:
```json
{
  "hatched_by_me": 10,
  "my_eggs_hatched": 5
}
```

## Usage

1. Find bot in Telegram: @tohatchbot
2. In any chat, type `@tohatchbot egg`
3. Select "🥚 Send Egg" from results
4. Recipient clicks "Hatch" to hatch the egg
5. After hatching, "📊 Hatch App" button appears to view stats

## Mini App

The bot integrates with a mini app for viewing statistics:
- Mini app repo: https://github.com/ViberKoder/hatch
- Deployed on Vercel: https://hatch-ruddy.vercel.app

Update `API_URL` in mini app to point to your bot's API endpoint.

## Environment Variables

- `BOT_TOKEN` - Telegram bot token (required)
- `PORT` - Port for API server (default: 8080)

## Tech Stack

- Python 3.11+
- python-telegram-bot 20.0+
- aiohttp 3.8.0+

## License

MIT
