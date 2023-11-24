import threading

from deck import (
    Deck,
    Context,
    Group,
    Pager,
    PagerKey,
    StaticKey,
    TextIcon,
    GaugeIcon,
    MarkerIcon,
)
from testapps import CounterKey, ClockKey, StopWatchKey, KitchenTimerKey
from remo import (
    ACPowerKey,
    ACModeKeySet,
    ACModeKeySetting,
    ACTempKeySet,
    ACVolumeKey,
    RoomTempKey,
)


def main() -> None:
    deck = Deck.open(0)
    deck.set_brightness(30)

    ctx = Context(deck)

    """
    pager = Pager(
        {
            "default": Group(
                [
                    CounterKey({0, 1}),
                    CounterKey({2, 3}),
                    ClockKey({4}),
                    ClockKey({5}, "%Y-%m-%d", 12),
                    ClockKey({6}, "%H", 32),
                    ClockKey({7}, "%M", 32),
                    ClockKey({8}, "%S", 32),
                    StopWatchKey({9, 10}),
                    KitchenTimerKey(11, 12, 13),
                    PagerKey({14}, "eight"),
                ]
            ),
            "eight": Group(
                [
                    StaticKey(set(x for x in range(10)), TextIcon(text="8")),
                    PagerKey({14}, "default"),
                ]
            ),
        }
    )
    """

    pager = Pager(
        {
            "STBY": Group(
                [
                    PagerKey({0}, "AC", MarkerIcon(text="AC", position="left")),
                    PagerKey({5}, "LIGHT", MarkerIcon(text="LIGHT", position="left")),
                    PagerKey({10}, "SCENE", MarkerIcon(text="SCENE", position="left")),
                    PagerKey({4}, "AUDIO", MarkerIcon(text="AUDIO", position="right")),
                    PagerKey({9}, "BGM", MarkerIcon(text="BGM", position="right")),
                    StaticKey(
                        {14}, MarkerIcon(text="STBY", position="right", kind="triangle")
                    ),
                ]
            ),
            "AC": Group(
                [
                    ACPowerKey(
                        {0},
                        "02f3e48c-50c8-40f2-aac8-5828d0abef1f",
                        MarkerIcon(text="ON", position="left", kind="triangle"),
                        MarkerIcon(text="OFF", position="left", kind="triangle"),
                        MarkerIcon(text="...", position="left", kind="triangle"),
                    ),
                    ACModeKeySet(
                        "02f3e48c-50c8-40f2-aac8-5828d0abef1f",
                        {
                            1: ACModeKeySetting(
                                "warm",
                                MarkerIcon(text="暖房", width=16),
                                TextIcon(text="暖房"),
                            ),
                            2: ACModeKeySetting(
                                "cool",
                                MarkerIcon(text="冷房", width=16),
                                TextIcon(text="冷房"),
                            ),
                            6: ACModeKeySetting(
                                "blow",
                                MarkerIcon(text="送風", width=16),
                                TextIcon(text="送風"),
                            ),
                            7: ACModeKeySetting(
                                "dry",
                                MarkerIcon(text="除湿", width=16),
                                TextIcon(text="除湿"),
                            ),
                        },
                    ),
                    ACTempKeySet("02f3e48c-50c8-40f2-aac8-5828d0abef1f", 3, 8, 13),
                    RoomTempKey({11}, "416bbca3-eb0b-4095-817d-aa7e455d89eb"),
                    ACVolumeKey({12}, "02f3e48c-50c8-40f2-aac8-5828d0abef1f"),
                    PagerKey({5}, "LIGHT", MarkerIcon(text="LIGHT", position="left")),
                    PagerKey({10}, "SCENE", MarkerIcon(text="SCENE", position="left")),
                    PagerKey({4}, "AUDIO", MarkerIcon(text="AUDIO", position="right")),
                    PagerKey({9}, "BGM", MarkerIcon(text="BGM", position="right")),
                    PagerKey({14}, "STBY", MarkerIcon(text="STBY", position="right")),
                ]
            ),
        },
        default="STBY",
    )

    ctx.execute_application(pager)

    for t in threading.enumerate():
        if t is threading.current_thread():
            continue
        t.join()


if __name__ == "__main__":
    main()
