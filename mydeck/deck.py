import sys
import threading
import asyncio
from abc import ABC, abstractmethod
import time
from dataclasses import dataclass
from collections.abc import Iterable, Callable, Awaitable
from typing import Self, Literal
import itertools
import queue
from datetime import timedelta

from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.Devices.StreamDeck import StreamDeck
from StreamDeck.ImageHelpers import PILHelper
from PIL import Image, ImageDraw, ImageFont


class Icon(ABC):
    @abstractmethod
    def render(self) -> Image.Image:
        pass


@dataclass(frozen=True)
class ColorIcon(Icon):
    bg: tuple[int, int, int] = (0, 0, 0)

    __cache: Image.Image | None = None

    def render(self) -> Image.Image:
        if self.__cache is not None:
            return self.__cache

        image = Image.new("RGB", (72, 72), self.bg)
        super().__setattr__("_ColorIcon__cache", image)
        return image


@dataclass(frozen=True)
class TextIcon(ColorIcon):
    fg: tuple[int, int, int] = (255, 255, 255)
    text: str = ""
    font: str = "NotoSansCJK-Regular.ttc"
    lang: str = "ja"
    size: int = 16
    x: int = 36
    y: int = 36

    __cache: Image.Image | None = None

    def render(self) -> Image.Image:
        if self.__cache is not None:
            return self.__cache

        image = super().render()
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(self.font, self.size)
        draw.text(
            (self.x, self.y),
            self.text,
            fill=self.fg,
            font=font,
            anchor="mm",
            language=self.lang,
        )

        super().__setattr__("_TextIcon__cache", image)

        return image


@dataclass(frozen=True)
class MarkerIcon(TextIcon):
    marker_color: tuple[int, int, int] = (255, 255, 255)
    position: Literal["top", "bottom", "left", "right"] = "bottom"
    kind: Literal["square", "triangle"] = "square"
    width: int = 4

    __cache: Image.Image | None = None

    def render(self) -> Image.Image:
        if self.__cache is not None:
            return self.__cache

        image = super().render()
        draw = ImageDraw.Draw(image)

        if self.kind == "square":
            if self.position == "top":
                draw.rectangle((0, 0, 72, self.width), fill=self.marker_color)
            elif self.position == "bottom":
                draw.rectangle((0, 72 - self.width, 72, 72), fill=self.marker_color)
            elif self.position == "left":
                draw.rectangle((0, 0, self.width, 72), fill=self.marker_color)
            elif self.position == "right":
                draw.rectangle((72 - self.width, 0, 72, 72), fill=self.marker_color)
        elif self.kind == "triangle":
            if self.position == "top":
                draw.polygon(
                    ((0, 0), (72, 0), (72 // 2, self.width * 2)), fill=self.marker_color
                )
            elif self.position == "bottom":
                draw.polygon(
                    ((0, 72), (72, 72), (72 // 2, 72 - self.width * 2)),
                    fill=self.marker_color,
                )
            elif self.position == "left":
                draw.polygon(
                    ((0, 0), (self.width * 2, 72 // 2), (0, 72)), fill=self.marker_color
                )
            elif self.position == "right":
                draw.polygon(
                    ((72, 0), (72 - self.width * 2, 72 // 2), (72, 72)),
                    fill=self.marker_color,
                )

        super().__setattr__("_MarkerIcon__cache", image)

        return image


@dataclass
class GaugeIcon(Icon):
    bg: tuple[int, int, int] = (0, 0, 0)
    gauge: tuple[int, int, int] = (255, 255, 255)
    fg: tuple[int, int, int] = (255, 255, 255)
    text: str = ""
    font: str = "NotoSansCJK-Regular.ttc"
    lang: str = "ja"
    size: int = 16
    width: int = 12

    # Gauge will be drawn as {key_offset}-th of {n_keys} keys.
    n_keys: int = 1
    key_offset: int = 0

    # If horizontal is True, gauge will be drawn horizontaly.
    horizontal: bool = False

    # Value of the gauge, between 0 and 1.
    value: float = 0

    def render(self) -> Image.Image:
        image = Image.new("RGB", (72, 72), self.bg)
        draw = ImageDraw.Draw(image)

        key_size = 72
        margin_size = 13
        total_length = key_size * self.n_keys + margin_size * (self.n_keys - 1)
        virtual_gauge_length = int(total_length * self.value)

        actual_gauge_length = max(
            0, virtual_gauge_length - self.key_offset * (key_size + margin_size)
        )

        if actual_gauge_length >= key_size:
            draw.rectangle((0, 0, self.width, 71), fill=self.gauge)
            draw.rectangle((71 - self.width, 0, 71, 71), fill=self.gauge)
        elif actual_gauge_length > 0:
            if self.horizontal:
                draw.rectangle((0, 0, actual_gauge_length, self.width), fill=self.gauge)
                draw.rectangle(
                    (0, 71 - self.width, actual_gauge_length, 71), fill=self.gauge
                )
                draw.line(
                    (actual_gauge_length, 0, actual_gauge_length, 71), fill=self.fg
                )
            else:
                draw.rectangle(
                    (0, 71 - actual_gauge_length, self.width, 71), fill=self.gauge
                )
                draw.rectangle(
                    (71 - self.width, 71 - actual_gauge_length, 71, 71), fill=self.gauge
                )
                draw.line(
                    (0, 71 - actual_gauge_length, 71, 71 - actual_gauge_length),
                    fill=self.fg,
                )

        font = ImageFont.truetype(self.font, self.size)
        draw.text(
            (36, 36),
            self.text,
            fill=self.fg,
            font=font,
            stroke_width=2,
            stroke_fill=self.bg,
            anchor="mm",
            language=self.lang,
        )

        return image


Task = Callable[[], Awaitable[None]] | Callable[[], None]


class TaskRunner:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)

    def now(self, task: Task) -> None:
        def run() -> None:
            r = task()
            if isinstance(r, Awaitable):
                asyncio.run_coroutine_threadsafe(r, self.loop)

        self.loop.call_soon_threadsafe(run)

    def after(self, delay: float, task: Task) -> None:
        async def run() -> None:
            await asyncio.sleep(delay)
            r = task()
            if isinstance(r, Awaitable):
                await r

        asyncio.run_coroutine_threadsafe(run(), self.loop)

    def at(self, when: float, task: Task) -> None:
        self.after(when - time.time(), task)


class Deck:
    def __init__(self, deck: StreamDeck) -> None:
        self.deck = deck

        deck.open()
        deck.reset()

        def noop(key_number: int, state: bool) -> None:
            pass

        self.on_key_callback = noop

        def callback(deck: StreamDeck, key_number: int, state: bool) -> None:
            self.on_key_callback(key_number, state)

        deck.set_key_callback(callback)

    @classmethod
    def open(cls, index: int = 0) -> Self:
        deck = DeviceManager().enumerate()[index]
        return cls(deck)

    def set_brightness(self, brightness: int) -> None:
        self.deck.set_brightness(brightness)

    def set_image(self, key_numbers: int | set[int], image: Image.Image | Icon) -> None:
        match key_numbers, image:
            case int(n), Icon():
                self.set_image(n, image.render())
            case int(n), Image.Image() if 0 <= n < self.deck.key_count():
                self.deck.set_key_image(n, PILHelper.to_native_format(self.deck, image))
            case set(ns), _:
                for n in ns:
                    self.set_image(n, image)

    def key_count(self) -> int:
        return self.deck.key_count()

    def key_layout(self) -> tuple[int, int]:
        return self.deck.key_layout()


class Context:
    def __init__(self, deck: Deck, runner: TaskRunner | None = None) -> None:
        self.deck = deck
        if runner is None:
            runner = TaskRunner()
        self.runner = runner

    def set_image(self, key_numbers: int | set[int], image: Image.Image | Icon) -> None:
        self.deck.set_image(key_numbers, image)

    def now(self, task: Task) -> None:
        self.runner.now(task)

    def after(self, delay: float, task: Task) -> None:
        self.runner.after(delay, task)

    def at(self, time: float, task: Task) -> None:
        self.runner.at(time, task)

    def execute_application(self, app: "Application") -> None:
        def on_key_callback(key_number: int, state: bool) -> None:
            async def run() -> None:
                try:
                    if state:
                        await app.on_press(self, key_number)
                    else:
                        await app.on_release(self, key_number)
                except Exception as e:
                    print(e, file=sys.stderr)

            self.runner.now(run)

        self.deck.on_key_callback = on_key_callback

        async def on_display() -> None:
            try:
                await app.on_display(self)
            except Exception as e:
                print(e, file=sys.stderr)

        asyncio.run(on_display())
        self.runner.start()


class Application(ABC):
    def __init__(self, key_numbers: set[int]) -> None:
        self.key_numbers = key_numbers

    @abstractmethod
    async def on_display(self, ctx: Context) -> None:
        pass

    async def on_hide(self, ctx: Context) -> None:
        pass

    async def on_press(self, ctx: Context, key_number: int) -> None:
        pass

    async def on_release(self, ctx: Context, key_number: int) -> None:
        pass


class StaticKey(Application):
    def __init__(self, key_numbers: set[int], icon: Icon = ColorIcon()) -> None:
        super().__init__(key_numbers)
        self.icon = icon

    async def on_display(self, ctx: Context) -> None:
        ctx.set_image(self.key_numbers, self.icon)


class Group(Application):
    def __init__(self, apps: list[Application]) -> None:
        super().__init__(set(x for app in apps for x in app.key_numbers))
        self.__apps = apps

    @property
    def apps(self) -> list[Application]:
        return self.__apps

    @apps.setter
    def apps(self, value: list[Application]) -> None:
        self.__apps = value
        self.key_numbers = set(x for app in value for x in app.key_numbers)

    async def on_display(self, ctx: Context) -> None:
        await asyncio.gather(*[app.on_display(ctx) for app in self.apps])

    async def on_hide(self, ctx: Context) -> None:
        await asyncio.gather(*[app.on_hide(ctx) for app in self.apps])

    async def on_press(self, ctx: Context, key_number: int) -> None:
        for app in self.apps:
            if key_number in app.key_numbers:
                await app.on_press(ctx, key_number)

    async def on_release(self, ctx: Context, key_number: int) -> None:
        for app in self.apps:
            if key_number in app.key_numbers:
                await app.on_release(ctx, key_number)


class NoSuchPageError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"No such page: {name}")
        self.page_name = name


class Pager(Application):
    def __init__(self, apps: dict[str, Application], default="default") -> None:
        super().__init__(set(x for app in apps.values() for x in app.key_numbers))
        self.__apps = apps
        self.__current = apps[default]
        self.__default = default

    @property
    def pages(self) -> list[str]:
        return list(self.__apps.keys())

    def __getitem__(self, name: str) -> Application:
        return self.__apps[name]

    def __setitem__(self, name: str, app: Application) -> None:
        if name in self.pages:
            raise ValueError(f"Page [{name}] is already registered.")

        self.__apps[name] = app
        self.key_numbers |= app.key_numbers

    @property
    def current(self) -> Application:
        return self.__current

    @property
    def default(self) -> str:
        return self.__default

    async def on_display(self, ctx: Context) -> None:
        await self.current.on_display(ctx)

    async def on_hide(self, ctx: Context) -> None:
        await self.current.on_hide(ctx)

    async def on_press(self, ctx: Context, key_number: int) -> None:
        await self.current.on_press(ctx, key_number)

    async def on_release(self, ctx: Context, key_number: int) -> None:
        try:
            await self.current.on_release(ctx, key_number)
        except NoSuchPageError as e:
            if e.page_name in self.pages:
                name = e.page_name
                await self.switch(ctx, name)
            else:
                raise e

    async def switch(self, ctx: Context, name: str) -> None:
        old = self.current
        await self.current.on_hide(ctx)
        self.__current = self[name]
        await self.current.on_display(ctx)

        keys_to_reset = old.key_numbers - self.current.key_numbers
        black = ColorIcon()
        for key_number in keys_to_reset:
            ctx.set_image(key_number, black)


class PagerKey(StaticKey):
    def __init__(
        self, key_numbers: set[int], name: str, icon: Icon | None = None
    ) -> None:
        if icon is None:
            icon = TextIcon(text=name)

        super().__init__(key_numbers, icon)
        self.__name = name

    @property
    def name(self) -> str:
        return self.__name

    async def on_release(self, ctx: Context, key_number: int) -> None:
        raise NoSuchPageError(self.name)


class LongPressKey(Application):
    def __init__(self, key_numbers: set[int], long_press_delay: float = 0.5) -> None:
        super().__init__(key_numbers)
        self.__long_press_delay = long_press_delay
        self.__pressed_at = 0.0

    async def on_press(self, ctx: Context, key_number: int) -> None:
        at = self.__pressed_at = time.time()

        await self.on_short_press(ctx, key_number)

        await asyncio.sleep(self.__long_press_delay)

        if self.__pressed_at == at:
            await self.on_long_press(ctx, key_number)

    async def on_release(self, ctx: Context, key_number: int) -> None:
        pressed_at = self.__pressed_at
        self.__pressed_at = 0.0

        if time.time() - pressed_at >= self.__long_press_delay:
            await self.on_long_release(ctx, key_number)
        else:
            await self.on_short_release(ctx, key_number)

    async def on_short_press(self, ctx: Context, key_number: int) -> None:
        pass

    async def on_long_press(self, ctx: Context, key_number: int) -> None:
        pass

    async def on_short_release(self, ctx: Context, key_number: int) -> None:
        pass

    async def on_long_release(self, ctx: Context, key_number: int) -> None:
        pass


class ToggleKey(Application):
    def __init__(self, key_numbers: set[int], icons: list[Icon]) -> None:
        super().__init__(key_numbers)
        self.icons = icons
        self.__state = 0

        self.on_switch_handler: Callable[
            [Context, int, int], Awaitable[None]
        ] | None = None

    @property
    def state(self) -> int:
        return self.__state

    def draw(self, ctx: Context) -> None:
        ctx.set_image(self.key_numbers, self.icons[self.state])

    async def on_display(self, ctx: Context) -> None:
        self.draw(ctx)

    async def on_press(self, ctx: Context, key_number: int) -> None:
        state = self.__state = (self.__state + 1) % len(self.icons)
        self.draw(ctx)
        await self.on_switch(ctx, key_number, state)

    async def on_switch(self, ctx: Context, key_number: int, state: int) -> None:
        if self.on_switch_handler is not None:
            await self.on_switch_handler(ctx, key_number, state)
