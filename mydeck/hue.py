import os
import json
from dataclasses import dataclass
import asyncio
import time

import aiohttp

from mydeck.deck import Application, Context, Icon, TextIcon, MarkerIcon


@dataclass
class Light:
    id: str
    name: str
    on: bool
    color: tuple[int, int, int] = (255, 255, 255)
    brightness: float = 1


@dataclass(frozen=True)
class LightsCache:
    lights: list[Light]
    timestamp: float


def xy2rgb(x: float, y: float) -> tuple[int, int, int]:
    # https://developers.meethue.com/develop/application-design-guidance/color-conversion-formulas-rgb-to-xy-and-back/#xy-to-rgb-color

    z = 1.0 - x - y
    Y = 1.0  # always set brightness as 100%.
    X = (Y / y) * x
    Z = (Y / y) * z

    r = X * 1.656492 - Y * 0.354851 - Z * 0.255038
    g = -X * 0.707196 + Y * 1.655397 + Z * 0.036152
    b = X * 0.051713 - Y * 0.121364 + Z * 1.011530

    r = 12.92 * r if r <= 0.0031308 else (1.0 + 0.055) * pow(r, 1 / 2.4) - 0.055
    g = 12.92 * g if g <= 0.0031308 else (1.0 + 0.055) * pow(g, 1 / 2.4) - 0.055
    b = 12.92 * b if b <= 0.0031308 else (1.0 + 0.055) * pow(b, 1 / 2.4) - 0.055

    r = int(max(0, min(255, r * 255)))
    g = int(max(0, min(255, g * 255)))
    b = int(max(0, min(255, b * 255)))

    return r, g, b


class Hue:
    __bridge_ip: str | None = os.environ.get("PHILIPS_HUE_BRIDGE_IP")

    __lock: asyncio.Lock = asyncio.Lock()
    __lights_cache: LightsCache = LightsCache(lights=[], timestamp=0)

    @classmethod
    async def find_bridge(cls) -> str:
        if cls.__bridge_ip is not None:
            return cls.__bridge_ip

        async with aiohttp.ClientSession() as session:
            async with session.get("https://discovery.meethue.com/") as response:
                cls.__bridge_ip = (await response.json())[0]["internalipaddress"]
                return cls.__bridge_ip

    @classmethod
    async def request(
        cls, method: str, endpoint: str, json: dict[str, object] | None = None
    ):
        async with aiohttp.ClientSession() as session:
            bridge = await cls.find_bridge()
            headers = {
                "hue-application-key": os.environ["PHILIPS_HUE_USERNAME"],
            }
            async with session.request(
                method,
                f"https://{bridge}/clip/v2{endpoint}",
                json=json,
                headers=headers,
                ssl=False,
            ) as response:
                return await response.json()

    @classmethod
    async def get_lights(cls) -> list[Light]:
        async with cls.__lock:
            if time.time() - cls.__lights_cache.timestamp < 1:
                return cls.__lights_cache.lights

            raw = await cls.request("GET", "/resource/light")

            lights = [
                Light(
                    id=light["id"],
                    name=light["metadata"]["name"],
                    on=light["on"]["on"],
                    color=xy2rgb(light["color"]["xy"]["x"], light["color"]["xy"]["y"])
                    if "color" in light
                    else (255, 255, 255),
                    brightness=light["dimming"]["brightness"] / 100
                    if "dimming" in light
                    else 1.0,
                )
                for light in raw["data"]
            ]

            cls.__lights_cache = LightsCache(lights=lights, timestamp=time.time())

        return lights

    @classmethod
    async def get_light(cls, id_: str) -> Light:
        lights = await cls.get_lights()
        for light in lights:
            if light.id == id_:
                return light
        raise KeyError(f"Light {id_} not found")

    @classmethod
    async def set_on(cls, id_: str, on: bool) -> None:
        await cls.request("PUT", f"/resource/light/{id_}", {"on": {"on": on}})


class LightKey(Application):
    def __init__(self, key_numbers: set[int], id_: str, name: str) -> None:
        super().__init__(key_numbers)
        self.name = name
        self.id = id_
        self.color = (255, 255, 255)
        self.on = False
        self.showing = False

    async def draw(self, ctx: Context) -> None:
        icon = MarkerIcon(
            marker_color=self.color,
            text=self.name,
            width=12,
            kind="triangle" if self.on else "square",
        )
        ctx.set_image(self.key_numbers, icon)

    async def on_display(self, ctx: Context) -> None:
        self.showing = True

        ctx.set_image(self.key_numbers, TextIcon(text=self.name))
        await self.draw(ctx)

        async def loop() -> None:
            while self.showing:
                light = await Hue.get_light(self.id)
                self.color = light.color
                self.on = light.on

                await self.draw(ctx)

                await asyncio.sleep(5)

        ctx.now(loop)

    async def on_hide(self, ctx: Context) -> None:
        self.showing = False

    async def on_press(self, ctx: Context, key_number: int) -> None:
        self.on = not self.on
        await Hue.set_on(self.id, self.on)
        await self.draw(ctx)
