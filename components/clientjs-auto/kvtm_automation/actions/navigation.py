from __future__ import annotations

import time

from ..context import AutomationContext
from ..errors import NavigationError, ScreenTimeout
from ..runtime.vision import VisionEngine
from ..runtime.wait import Waiter
from .popup import PopupActions


class NavigationActions:
    """Reusable farm/friend navigation reconstructed from GoFiendHome."""

    FRIEND_BUTTON_ZONE = (0, 935, 78, 65)
    FRIEND_LIST_ZONE = (81, 690, 708, 65)
    ADD_FRIEND_ZONE = (488, 936, 143, 58)
    VISITING_HOME_ZONE = (920, 925, 78, 71)
    OWN_SHOP_ZONE = (913, 931, 83, 66)

    # Exact seven visible friend card coordinates recovered from GoFiendHome.
    FRIEND_CARD_CENTERS = (
        (272, 818),
        (398, 821),
        (513, 815),
        (651, 823),
        (766, 828),
        (893, 818),
        (994, 817),
    )

    def __init__(
        self,
        context: AutomationContext,
        vision: VisionEngine,
        waiter: Waiter,
        popup: PopupActions,
    ) -> None:
        self.context = context
        self.vision = vision
        self.waiter = waiter
        self.popup = popup

    def is_visiting_friend(self) -> bool:
        return self.vision.find(
            "icon_home",
            threshold=0.82,
            zone=self.VISITING_HOME_ZONE,
        ) is not None

    def is_own_home(self) -> bool:
        # At own home AUTO PRO sees cua_hang in the same lower-right area while
        # the return-home icon is absent.
        shop = self.vision.find(
            "cua_hang",
            threshold=0.78,
            zone=self.OWN_SHOP_ZONE,
        )
        home = self.vision.find(
            "icon_home",
            threshold=0.82,
            zone=self.VISITING_HOME_ZONE,
        )
        return shop is not None and home is None

    def _open_friend_panel(self) -> None:
        for attempt in range(10):
            self.context.ensure_running()
            if self.vision.find(
                "add_friend",
                threshold=0.76,
                zone=self.ADD_FRIEND_ZONE,
            ) is not None:
                return
            if self.vision.find(
                "list_friend",
                threshold=0.86,
                zone=self.FRIEND_LIST_ZONE,
                click=True,
            ) is not None:
                self.waiter.sleep(0.65)
                continue
            if self.vision.find(
                "friend",
                threshold=0.76,
                zone=self.FRIEND_BUTTON_ZONE,
                click=True,
            ) is None:
                # Exact AUTO PRO fallback for the friend button.
                self.vision.driver.click(36, 963)
            self.context.log(
                f"Mở danh sách bạn bè • lần {attempt + 1}/10"
            )
            self.waiter.sleep(0.75)
        raise NavigationError("Không mở được danh sách bạn bè")

    def go_to_friend(self, friend_ordinal: int, timeout: float = 60.0) -> None:
        position = int(friend_ordinal)
        if not 1 <= position <= len(self.FRIEND_CARD_CENTERS):
            # Recovered GoFiendHome clamps specific_friend_pos to the seven
            # visible cards. Refuse to guess a page/swipe and risk a wrong home.
            raise NavigationError(
                "Bản clean hiện chỉ xác nhận an toàn bạn bè số 1..7; "
                f"đã nhận {position}"
            )
        self.popup.ensure_main_screen(timeout=30.0)
        self._open_friend_panel()
        self.context.stage(f"friend-select-{position}")
        self.vision.driver.click(*self.FRIEND_CARD_CENTERS[position - 1])
        self.waiter.sleep(0.8)

        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self.context.ensure_running()
            if self.is_visiting_friend():
                self.context.log(f"Đã sang đúng nhà bạn số {position}")
                return
            self.popup.dismiss_one()
            self.waiter.sleep(0.5)
        raise ScreenTimeout(
            f"Không xác nhận được nhà bạn số {position} sau {timeout:.0f}s"
        )

    def return_home(self, timeout: float = 60.0) -> None:
        self.context.stage("returning-own-home")
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            self.context.ensure_running()
            if self.is_own_home():
                self.context.log("Đã quay về nhà clone")
                return
            match = self.vision.find(
                "icon_home",
                threshold=0.80,
                zone=self.VISITING_HOME_ZONE,
                click=True,
            )
            if match is None:
                self.popup.dismiss_one()
            self.waiter.sleep(0.8)
        raise ScreenTimeout("Không quay về được nhà clone")
