"""
Hero data is loaded dynamically from assets.deadlock-api.com via HeroDataStore.
See hero_data.py for caching and fallback logic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hero_data import HeroDataStore

# Module-level store reference; injected by main.py after initialization.
_hero_store: "HeroDataStore | None" = None


def set_hero_store(store: "HeroDataStore") -> None:
    """Inject the shared HeroDataStore instance."""
    global _hero_store
    _hero_store = store


class GamePhase(Enum):
    NOT_RUNNING = auto()
    MAIN_MENU = auto()
    HIDEOUT = auto()
    PARTY_HIDEOUT = auto()
    IN_QUEUE = auto()
    MATCH_INTRO = auto()
    IN_MATCH = auto()
    POST_MATCH = auto()
    SPECTATING = auto()


class MatchMode(Enum):
    """
    Steam_Citadel_RP_MM_Unranked      "Deadlock:"
    Steam_Citadel_RP_MM_Ranked        "Ranked:"
    Steam_Citadel_RP_MM_HeroLabs      "Hero Labs:"
    Steam_Citadel_RP_MM_PrivateLobby  "Lobby:"
    Steam_Citadel_RP_MM_CoopBot       "Bots:"
    Steam_Citadel_RP_MM_Tutorial      "Tutorial:"
    Steam_Citadel_RP_MM_Sandbox       "Sandbox:"
    Steam_Citadel_RP_MM_Calibration   "Placement Match:"
    Steam_Citadel_RP_StreetBrawl      "Street Brawl:"
    """
    UNKNOWN = auto()
    UNRANKED = auto()
    RANKED = auto()
    HERO_LABS = auto()
    PRIVATE_LOBBY = auto()
    BOT_MATCH = auto()
    TUTORIAL = auto()
    SANDBOX = auto()
    CALIBRATION = auto()
    STREET_BRAWL = auto()


MODE_DISPLAY: dict[MatchMode, str] = {
    MatchMode.UNKNOWN: "Playing a Match",
    MatchMode.UNRANKED: "Playing Standard (6v6)",
    MatchMode.RANKED: "Playing Ranked (6v6)",
    MatchMode.HERO_LABS: "Playing Hero Labs",
    MatchMode.PRIVATE_LOBBY: "Playing Private Lobby",
    MatchMode.BOT_MATCH: "Playing in a Bot Match",
    MatchMode.TUTORIAL: "Tutorial",
    MatchMode.SANDBOX: "Training in Sandbox Mode",
    MatchMode.CALIBRATION: "Placement Match",
    MatchMode.STREET_BRAWL: "Playing Street Brawl (4v4)",
}

# Hero names and asset keys are now loaded dynamically from the API.
# See hero_data.py — HeroDataStore provides display_name(), asset_key(), hideout_text().


@dataclass
class GameState:
    phase: GamePhase = GamePhase.NOT_RUNNING
    match_mode: MatchMode = MatchMode.UNKNOWN
    hero_key: str | None = None  # internal codename
    is_transformed: bool = False
    party_size: int = 1  # 1 = solo
    server_address: str | None = None  # ip:port from console
    map_name: str | None = None
    is_loopback: bool = False  # hideout
    match_start_time: float | None = None  # epoch when match began
    queue_start_time: float | None = None  # epoch when queue began
    session_start_time: float | None = None  # epoch when game was detected
    last_update: float = field(default_factory=time.time)
    game_state_id: int | None = None  # from ChangeGameState
    player_count: int = 0
    bot_count: int = 0
    bot_difficulty: str | None = None

    @property
    def hero_display_name(self) -> str | None:
        if self.hero_key is None:
            return None
        if _hero_store:
            return _hero_store.display_name(self.hero_key)
        # Fallback: title-case the raw key
        return self.hero_key.replace("_", " ").title()

    @property
    def hero_asset_name(self) -> str | None:
        """Discord asset key for the current hero."""
        if self.hero_key is None:
            return None

        key = self.hero_key.lower()

        # Silver (werewolf) transform swap
        if key in ("werewolf", "silver") and self.is_transformed:
            return "hero_werewolf_wolf"

        if _hero_store:
            return _hero_store.asset_key(key)
        return f"hero_{key}"

    @property
    def hero_hideout_text(self) -> str:
        """Hero-specific hideout presence text from the API, e.g. 'Mixing Drinks in the Hideout'."""
        if self.hero_key and _hero_store:
            return _hero_store.hideout_text(self.hero_key)
        return "In the Hideout"

    @property
    def in_party(self) -> bool:
        return self.party_size > 1

    @property
    def is_in_match(self) -> bool:
        return self.phase in (GamePhase.IN_MATCH, GamePhase.MATCH_INTRO)

    def mode_display(self) -> str:
        return MODE_DISPLAY.get(self.match_mode, "Match")

    def enter_main_menu(self) -> None:
        self.phase = GamePhase.MAIN_MENU
        self._clear_match()

    def enter_hideout(self) -> None:
        self.phase = GamePhase.PARTY_HIDEOUT if self.in_party else GamePhase.HIDEOUT
        self._clear_match()
        self.is_loopback = True

    def enter_queue(self) -> None:
        self.phase = GamePhase.IN_QUEUE
        self.queue_start_time = time.time()

    def leave_queue(self) -> None:
        self.queue_start_time = None
        self.enter_hideout()

    def enter_spectating(self) -> None:
        self.phase = GamePhase.SPECTATING
        self.hero_key = None
        self.is_transformed = False
        self.match_start_time = None
        self.queue_start_time = None

    def enter_match_intro(self) -> None:
        self.phase = GamePhase.MATCH_INTRO
        self.game_state_id = 4

    def start_match(self, mode: MatchMode = MatchMode.UNKNOWN) -> None:
        self.phase = GamePhase.IN_MATCH
        if mode != MatchMode.UNKNOWN:
            self.match_mode = mode
        if self.match_start_time is None:
            self.match_start_time = time.time()
        self.queue_start_time = None
        self.game_state_id = 5

    def end_match(self) -> None:
        self.phase = GamePhase.POST_MATCH
        self.match_start_time = None
        self.game_state_id = 6

    def set_hero(self, hero_key: str) -> None:
        normalized = hero_key.lower().replace("hero_", "")

        # Strip skin/variant suffixes from VMDL folder names
        # e.g. "mirage_v2" -> "mirage", "gigawatt_prisoner" -> "gigawatt"
        # Try the store first, then brute-force strip suffixes.
        if _hero_store and not _hero_store.get(normalized):
            parts = normalized.split("_")
            for i in range(len(parts) - 1, 0, -1):
                candidate = "_".join(parts[:i])
                if _hero_store.get(candidate):
                    normalized = candidate
                    break
        elif not _hero_store:
            # No store — just strip known numeric/variant suffixes blindly
            parts = normalized.split("_")
            for i in range(len(parts) - 1, 0, -1):
                normalized = "_".join(parts[:i])
                break

        if normalized != self.hero_key:
            self.hero_key = normalized
            self.is_transformed = False  # reset form on hero change

    def set_party_size(self, size: int) -> None:
        self.party_size = max(1, size)
        if self.phase in (GamePhase.HIDEOUT, GamePhase.PARTY_HIDEOUT):
            self.phase = GamePhase.PARTY_HIDEOUT if self.in_party else GamePhase.HIDEOUT

    def connect_to_server(self, address: str) -> None:
        self.server_address = address
        self.is_loopback = "loopback" in address.lower()

    def _clear_match(self) -> None:
        self.match_mode = MatchMode.UNKNOWN
        self.match_start_time = None
        self.server_address = None
        self.map_name = None
        self.game_state_id = None
        self.is_transformed = False
        self.bot_count = 0
        self.bot_difficulty = None

    def reset(self) -> None:
        """Full reset when the game closes."""
        self._clear_match()
        self.phase = GamePhase.NOT_RUNNING
        self.hero_key = None
        self.party_size = 1
        self.queue_start_time = None
        self.session_start_time = None
        self.is_loopback = False
        self.player_count = 0