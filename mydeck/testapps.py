import asyncio
import threading
import time
from datetime import timedelta

from mydeck.deck import TextIcon, Context, Application, LongPressKey, ToggleKey


class CounterKey(LongPressKey):
    def __init__(
        self, key_numbers: set[int], bg=(0, 0, 0), fg=(255, 255, 255), size=24
    ) -> None:
        super().__init__(key_numbers)

        self.__lock = threading.Lock()
        self.__count = 0
        self.__pressing = False

        self.bg = bg
        self.fg = fg
        self.size = size

    @property
    def count(self) -> int:
        with self.__lock:
            return self.__count

    @count.setter
    def count(self, value: int) -> None:
        with self.__lock:
            self.__count = value

    def draw(self, ctx: Context) -> None:
        bg, fg = self.bg, self.fg
        with self.__lock:
            if self.__pressing:
                bg = (64, 64, 64)
        ctx.set_image(
            self.key_numbers,
            TextIcon(text=str(self.count), bg=bg, fg=fg, size=self.size),
        )

    async def on_display(self, ctx: Context) -> None:
        self.draw(ctx)

    async def on_release(self, ctx: Context, key_number: int) -> None:
        await super().on_release(ctx, key_number)
        with self.__lock:
            self.__pressing = False
        self.draw(ctx)

    async def on_short_press(self, ctx: Context, key_number: int) -> None:
        with self.__lock:
            self.__pressing = True
            self.__count += 1
        self.draw(ctx)

    async def on_long_press(self, ctx: Context, key_number: int) -> None:
        with self.__lock:
            self.__count = 0
        self.draw(ctx)


class ClockKey(Application):
    def __init__(
        self, key_numbers: set[int], format_: str = "%H:%M:%S", size: int = 16
    ) -> None:
        super().__init__(key_numbers)
        self.format = format_
        self.size = size
        self._last_text = ""
        self.displayed = False

    def draw(self, ctx: Context, force=False) -> None:
        text = time.strftime(self.format)
        if text != self._last_text or force:
            ctx.set_image(self.key_numbers, TextIcon(text=text, size=self.size))
            self._last_text = text

    async def on_display(self, ctx: Context) -> None:
        self.displayed = True

        async def loop() -> None:
            while self.displayed:
                self.draw(ctx)
                await asyncio.sleep(1)

        ctx.now(loop)
        self.draw(ctx, force=True)

    async def on_hide(self, ctx: Context) -> None:
        self.displayed = False


class StopWatchKey(Application):
    def __init__(self, key_numbers: set[int]) -> None:
        super().__init__(key_numbers)
        self.running = False
        self.start_at = 0.0
        self.pressed_at = 0.0
        self.lock = threading.Lock()

    def draw(self, ctx: Context) -> None:
        bg, fg = (0, 0, 0), (255, 255, 255)
        if self.pressed_at > 0:
            bg = (64, 64, 64)
        elif self.running:
            bg, fg = fg, bg
        text = (
            str(timedelta(seconds=int(time.time() - self.start_at)))
            if self.start_at > 0
            else "0:00:00"
        )
        ctx.set_image(self.key_numbers, TextIcon(bg=bg, fg=fg, text=text))

    async def on_display(self, ctx: Context) -> None:
        self.draw(ctx)

    async def on_hide(self, ctx: Context) -> None:
        self.running = False

    async def on_press(self, ctx: Context, key_number: int) -> None:
        async def loop() -> None:
            while self.running:
                self.draw(ctx)
                await asyncio.sleep(1)

        with self.lock:
            at = self.pressed_at = time.time()
            if self.running:
                self.running = False
            else:
                self.running = True
                self.start_at = at
                ctx.now(loop)
            self.draw(ctx)

    async def on_release(self, ctx: Context, key_number: int) -> None:
        with self.lock:
            self.pressed_at = 0
            self.draw(ctx)


class KitchenTimerKey(Application):
    def __init__(self, minute_key: int, second_key: int, startstop_key: int) -> None:
        super().__init__({minute_key, second_key, startstop_key})

        self.__lock = threading.Lock()
        self.running = False
        self.shown = False
        self.end_at = 0.0

        self.minute = CounterKey({minute_key}, size=24)
        self.second = CounterKey({second_key}, size=24)
        self.startstop = ToggleKey(
            {startstop_key},
            [
                TextIcon(bg=(0, 0, 0), fg=(255, 255, 255), text="Start"),
                TextIcon(bg=(255, 0, 0), fg=(255, 255, 255), text="Stop"),
            ],
        )

        self.startstop.on_switch_handler = self.on_startstop

    async def on_display(self, ctx: Context) -> None:
        with self.__lock:
            self.shown = True
            running = self.running

        if running:
            await self.startstop.on_display(ctx)
            self._tick(ctx)
        else:
            await asyncio.gather(
                self.minute.on_display(ctx),
                self.second.on_display(ctx),
                self.startstop.on_display(ctx),
            )

    async def on_hide(self, ctx: Context) -> None:
        with self.__lock:
            self.shown = False

        await asyncio.gather(
            self.minute.on_hide(ctx),
            self.second.on_hide(ctx),
            self.startstop.on_hide(ctx),
        )

    async def on_press(self, ctx: Context, key_number: int) -> None:
        if key_number in self.minute.key_numbers:
            await self.minute.on_press(ctx, key_number)
        elif key_number in self.second.key_numbers:
            await self.second.on_press(ctx, key_number)
            if self.second.count == 60:
                self.minute.count += 1
                self.second.count = 0
        elif key_number in self.startstop.key_numbers:
            await self.startstop.on_press(ctx, key_number)

    async def on_release(self, ctx: Context, key_number: int) -> None:
        if key_number in self.minute.key_numbers:
            await self.minute.on_release(ctx, key_number)
        elif key_number in self.second.key_numbers:
            await self.second.on_release(ctx, key_number)
        elif key_number in self.startstop.key_numbers:
            await self.startstop.on_release(ctx, key_number)

    async def on_startstop(self, ctx: Context, key_number: int, state: int) -> None:
        if state == 0:
            await asyncio.gather(
                self.minute.on_display(ctx),
                self.second.on_display(ctx),
            )

            with self.__lock:
                self.running = False
        else:
            await asyncio.gather(
                self.minute.on_hide(ctx),
                self.second.on_hide(ctx),
            )

            with self.__lock:
                self.end_at = time.time() + self.minute.count * 60 + self.second.count
                self.running = True
                self._tick(ctx)

    def _tick(self, ctx: Context) -> None:
        if self.running and self.shown:
            if time.time() >= self.end_at:
                bg = (128, 0, 0) if int(time.time()) % 2 == 0 else (64, 0, 0)
                ctx.set_image(
                    self.minute.key_numbers,
                    TextIcon(
                        text=str(int((time.time() - self.end_at) / 60)), bg=bg, size=24
                    ),
                )
                ctx.set_image(
                    self.second.key_numbers,
                    TextIcon(
                        text=str(int((time.time() - self.end_at) % 60)), bg=bg, size=24
                    ),
                )
            else:
                ctx.set_image(
                    self.minute.key_numbers,
                    TextIcon(text=str(int((self.end_at - time.time()) / 60)), size=24),
                )
                ctx.set_image(
                    self.second.key_numbers,
                    TextIcon(text=str(int((self.end_at - time.time()) % 60)), size=24),
                )

            ctx.after(1, lambda: self._tick(ctx))
