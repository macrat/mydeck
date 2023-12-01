import threading

from mydeck.deck import (
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
from mydeck.testapps import CounterKey, ClockKey, StopWatchKey, KitchenTimerKey
from mydeck.remo import (
    ACModeKeySet,
    ACModeKeySetting,
    ACTempKeySet,
    ACVolumeKey,
    SimpleRemoKey,
)
from mydeck.hue import LightKey, LightGroupKey


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
                    ACTempKeySet(
                        "416bbca3-eb0b-4095-817d-aa7e455d89eb",
                        "02f3e48c-50c8-40f2-aac8-5828d0abef1f",
                        3,
                        8,
                        13,
                    ),
                    SimpleRemoKey(
                        {11},
                        "934f5876-4c99-45d7-a2c6-d3c83fd0ec37",
                        TextIcon(text="dir"),
                    ),
                    ACVolumeKey({12}, "02f3e48c-50c8-40f2-aac8-5828d0abef1f"),
                    StaticKey(
                        {0}, MarkerIcon(text="AC", position="left", kind="triangle")
                    ),
                    PagerKey({5}, "LIGHT", MarkerIcon(text="LIGHT", position="left")),
                    PagerKey({10}, "SCENE", MarkerIcon(text="SCENE", position="left")),
                    PagerKey({4}, "AUDIO", MarkerIcon(text="AUDIO", position="right")),
                    PagerKey({9}, "BGM", MarkerIcon(text="BGM", position="right")),
                    PagerKey({14}, "STBY", MarkerIcon(text="STBY", position="right")),
                ]
            ),
            "LIGHT": Group(
                [
                    LightKey({1}, "874fdfdf-6fb0-4c80-9cec-b87affa2e281", "Frt-L"),
                    LightKey({2}, "7dbcab08-75b9-48be-b3f6-adb9ea9083a6", "Mon-L"),
                    LightKey({3}, "0128f3f1-93ab-48d1-9104-4d7121cf7f79", "Frt-R"),
                    LightKey({6}, "f6a4917b-62c8-4d96-88ef-3a64d6508af8", "Cnt-L"),
                    LightKey({7}, "8c3d3f53-425e-4a68-8d8d-03c2ef0d81f0", "Mon-R"),
                    LightKey({8}, "8194ad68-2a58-4744-8933-b95bd6af42d3", "Cnt-R"),
                    LightKey({11}, "2696d10c-29d1-4c34-894c-f6853dbe39a2", "Rer-L"),
                    LightGroupKey({12}, "ab8e08a9-9a5f-4604-be62-20e6c1ac63e4", "All"),
                    LightKey({13}, "6c35ff7a-a0b6-4b81-8941-4185e755b6a9", "Rer-R"),
                    StaticKey(
                        {5}, MarkerIcon(text="LIGHT", position="left", kind="triangle")
                    ),
                    PagerKey({0}, "AC", MarkerIcon(text="AC", position="left")),
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
