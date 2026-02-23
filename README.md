# DeadlockRPC

Discord Rich Presence for [Deadlock](https://store.steampowered.com/app/1422450/Deadlock/) by Valve.

Shows your current in-game status on your Discord profile — hero, game mode, party size, match timer, and more.

## Features

- **Automatic game launch** — starts Deadlock with `-condebug` via Steam so console logging is always enabled
- **Hero detection** — displays your selected hero's portrait as the large image (supports all released and renamed heroes)
- **Game mode display** — Standard, Ranked, Hero Labs, Street Brawl, Private Lobby, Bot Match, Sandbox, and more
- **Party support** — shows party size and hero name for party members
- **Match timer** — live elapsed time during matches
- **Phase tracking** — Main Menu, Hideout, In Queue, Match Intro, In Match, Post-Match, Spectating
- **System tray** — runs quietly in the background with a tray icon (falls back to console mode if unavailable)
- **Cross-platform** — Windows and Linux

## Requirements

- Python 3.10+
- Discord (desktop app, running)
- Steam + Deadlock installed

## Setup

1. **Clone the repo**

   ```
   git clone https://github.com/your-username/DeadlockRPC.git
   cd DeadlockRPC
   ```

2. **Install dependencies**

   ```
   pip install -r requirements.txt
   ```

3. **Configure** (optional)

   Edit `src/config.json` if needed:
   - `deadlock_install_path` — set this if Deadlock isn't in a standard Steam library location
   - `update_interval_seconds` — how often Discord presence refreshes (default: 15s)

4. **Run**

   ```
   python src/main.py
   ```

   This will launch Deadlock with `-condebug` automatically and connect to Discord.

## How It Works

DeadlockRPC monitors Deadlock's `console.log` file (written when the game runs with `-condebug`). It parses log events using regex patterns to detect game state changes — hero selection, map loads, matchmaking signals, party info — and pushes updates to Discord via the Rich Presence API.

The game's runtime and memory are never touched. Everything is read passively from the log file.

## Project Structure

```
DeadlockRPC/
  src/
    main.py             # Entry point — launches Deadlock and starts RPC
    game_state.py       # State machine, hero/mode definitions
    console_log.py      # Log file watcher and parser
    presence.py         # Discord Rich Presence builder
    ensure_condebug.py  # Deadlock launcher (steam:// protocol)
    systray.py          # System tray icon
    config.json         # Configuration
    parser.py           # Debug tool for replaying console logs
  assets/
    deadlock_logo.png
  requirements.txt
  LICENSE
```

## License

MIT

---

## TO-DO

- [ ] Party queue detection — "Looking for Match..." currently only shows for the party leader/solo players. Party members don't emit `k_EMsgClientToGCStartMatchmaking` (9010). Need to find the correct GC message or alternative signal.
- [ ] Auto-reconnect to Discord if it restarts mid-session
- [ ] Configurable launch behavior — option to skip auto-launching Deadlock (for users who launch the game separately)
- [ ] Packaged release — PyInstaller or similar so users don't need Python installed
- [ ] Keep hero asset names in sync as Valve continues renaming internal codenames
- [ ] Spectator mode details — show map/mode being spectated if detectable
