import time
import logging
import threading
from pypresence import Presence, DiscordNotFound, PipeClosed

from config import DISCORD_APP_ID, GSI_PORT, UPDATE_INTERVAL
from steam_utils import install_gsi_config, is_deadlock_running
from server import GSIServer
from mapping import lookup_hero, get_game_mode_display

logger = logging.getLogger("deadlock-rpc")


class DeadlockRPC:
    def __init__(self):
        self.rpc: Presence | None = None
        self.gsi: GSIServer | None = None
        self.connected = False
        self.enabled = True
        self.match_start: float | None = None
        self._running = True
        self._status = "Starting..."
        self._lock = threading.Lock()

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @status.setter
    def status(self, val: str):
        with self._lock:
            self._status = val

    def connect_discord(self) -> bool:
        if DISCORD_APP_ID == "YOUR_DISCORD_APP_ID_HERE":
            return False
        try:
            self.rpc = Presence(DISCORD_APP_ID)
            self.rpc.connect()
            self.connected = True
            self.status = "Connected to Discord"
            logger.info("Connected to Discord RPC.")
            return True
        except DiscordNotFound:
            self.status = "Waiting for Discord..."
            return False
        except Exception as e:
            self.status = f"Discord error: {e}"
            return False

    def disconnect_discord(self):
        if self.rpc:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass
        self.rpc = None
        self.connected = False

    def start_gsi(self):
        self.gsi = GSIServer(port=GSI_PORT)
        self.gsi.start()

    def stop_gsi(self):
        if self.gsi:
            self.gsi.shutdown()
            self.gsi = None

    def _resolve_hero(self, gsi):
        """Return (display_name, image_key, tooltip) or Nones."""
        hero_raw = gsi.get_hero_name() if gsi else None
        if not hero_raw:
            return None, None, None
        hero = lookup_hero(hero_raw)
        if hero:
            return hero["name"], hero["image"], hero["name"]
        return hero_raw, None, hero_raw

    def _presence_title_screen(self) -> dict:
        """Deadlock running but no GSI data, player is on the title screen."""
        return {
            "details": "On Title Screen",
            "large_image": "deadlock_logo",
            "large_text": "Deadlock",
        }

    def _presence_hideout(self, gsi) -> dict:
        """Player is in the hideout (not queuing, not in match)."""
        hero_name, hero_img, hero_tooltip = self._resolve_hero(gsi)
        in_party = gsi.is_in_party() if gsi else False

        kwargs: dict = {
            "details": "In Party Hideout" if in_party else "In Hideout",
            "small_image": "deadlock_logo",
            "small_text": "Deadlock",
        }

        if hero_img:
            kwargs["large_image"] = hero_img
            kwargs["large_text"] = hero_tooltip
        else:
            kwargs["large_image"] = "deadlock_logo"
            kwargs["large_text"] = "Deadlock"

        return kwargs

    def _presence_queue(self, gsi) -> dict:
        """Player is searching for a match."""
        hero_name, hero_img, hero_tooltip = self._resolve_hero(gsi)

        kwargs: dict = {
            "details": "Finding Match",
            "small_image": "deadlock_logo",
            "small_text": "Deadlock",
        }

        if hero_img:
            kwargs["large_image"] = hero_img
            kwargs["large_text"] = hero_tooltip
        else:
            kwargs["large_image"] = "deadlock_logo"
            kwargs["large_text"] = "Deadlock"

        return kwargs

    def _presence_in_match(self, gsi) -> dict:
        """Player is actively in a match — full stats display."""
        kwargs: dict = {}
        state_parts: list[str] = []
        details_parts: list[str] = []

        hero_name, hero_img, hero_tooltip = self._resolve_hero(gsi)
        if hero_name:
            details_parts.append(f"Playing {hero_name}")
            if hero_img:
                kwargs["large_image"] = hero_img
                kwargs["large_text"] = hero_tooltip
        if not details_parts:
            details_parts.append("In Match")

        kda = gsi.get_kda() if gsi else None
        if kda:
            state_parts.append(f"{kda[0]}/{kda[1]}/{kda[2]} KDA")

        score = gsi.get_team_score() if gsi else None
        if score:
            state_parts.append(f"Score: {score[0]} - {score[1]}")

        level = gsi.get_player_level() if gsi else None
        if level is not None:
            state_parts.append(f"Lvl {level}")

        souls = gsi.get_souls() if gsi else None
        if souls is not None:
            state_parts.append(f"{souls:,} Souls")

        mode = gsi.get_game_mode() if gsi else None
        if mode:
            kwargs["small_image"] = "deadlock_logo"
            kwargs["small_text"] = get_game_mode_display(mode)

        #if we have a confirmed match start
        if self.match_start:
            kwargs["start"] = int(self.match_start)

        kwargs["details"] = " · ".join(details_parts)
        if state_parts:
            kwargs["state"] = " | ".join(state_parts)

        if "large_image" not in kwargs:
            kwargs["large_image"] = "deadlock_logo"
            kwargs["large_text"] = "Deadlock"

        return kwargs

    def _presence_post_match(self, gsi) -> dict:
        """Match just ended — show final stats without an incrementing timer."""
        kwargs = self._presence_in_match(gsi)
        kwargs.pop("start", None)  #freeze the timer
        kwargs["details"] = kwargs.get("details", "Post Match") + " (ended)"
        return kwargs

    def tick(self):
        if not self.enabled:
            return
        if not self.connected:
            if not self.connect_discord():
                return

        game_running = is_deadlock_running()

        if not game_running:
            if self.match_start is not None:
                self.match_start = None
            try:
                self.rpc.clear()
            except Exception:
                pass
            self.status = "Waiting for Deadlock..."
            return

        gsi = self.gsi.state if self.gsi and not self.gsi.state.is_stale else None

        if gsi is None:
            self.match_start = None
            kwargs = self._presence_title_screen()
            self.status = "In Hideout"

        elif gsi.is_in_queue():
            self.match_start = None
            kwargs = self._presence_queue(gsi)
            self.status = "In Queue"

        elif gsi.is_in_match():
            if self.match_start is None:
                self.match_start = time.time()
            kwargs = self._presence_in_match(gsi)
            hero_part = kwargs.get("details", "")
            kda_part = kwargs.get("state", "")
            self.status = f"{hero_part}" + (f" — {kda_part}" if kda_part else "")

        else:
            self.match_start = None
            kwargs = self._presence_hideout(gsi)
            in_party = gsi.is_in_party()
            self.status = "In Party Hideout" if in_party else "In Hideout"

        #push to discord
        try:
            self.rpc.update(**kwargs)
        except (PipeClosed, BrokenPipeError):
            self.connected = False
            self.status = "reconnecting to discord..."
        except Exception:
            pass

    def run_loop(self):
        install_gsi_config()
        self.start_gsi()
        self.connect_discord()
        self.status = "Waiting for Deadlock..."
        logger.info("Ready — waiting for Deadlock to launch.")

        while self._running:
            try:
                self.tick()
            except Exception as e:
                logger.error("Loop error: %s", e)
            time.sleep(UPDATE_INTERVAL)

        self.disconnect_discord()
        self.stop_gsi()

    def stop(self):
        self._running = False