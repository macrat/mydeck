import os
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from collections.abc import Callable, Awaitable
import time

import aiohttp

from mydeck.deck import Application, Context, Icon, ColorIcon, TextIcon, GaugeIcon


@dataclass
class RoomState:
    temperature: float
    timestamp: datetime


@dataclass
class ACState:
    temperature: str = ""
    temperature_list: list[str] = field(default_factory=list)
    mode: str = "unknown"
    mode_list: list[str] = field(default_factory=list)
    volume: str = "unknown"
    volume_list: list[str] = field(default_factory=list)
    power: bool = False
    timestamp: datetime = datetime(1970, 1, 1)

    def as_request(self) -> dict[str, object]:
        return {
            "air_direction": "",
            "air_direction_h": "",
            "air_volume": self.volume,
            "button": "power-on" if self.power else "power-off",
            "operation_mode": self.mode,
            "temperature": str(self.temperature),
            "temperature_unit": "c",
        }


class NatureRemo:
    room_lock: asyncio.Lock = asyncio.Lock()
    room_cache: dict[str, RoomState] = {}
    ac_lock: asyncio.Lock = asyncio.Lock()
    ac_cache: dict[str, ACState] = {}

    @staticmethod
    async def request(
        path: str, method: str = "GET", body: dict[str, object] | None = None
    ):
        url = f"https://api.nature.global{path}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {os.environ.get('NATURE_REMO_TOKEN')}",
        }

        async with aiohttp.ClientSession() as session:
            if method == "POST":
                async with session.post(url, data=body, headers=headers) as resp:
                    if resp.status >= 400:
                        raise ValueError(await resp.text())
                    return await resp.json()
            else:
                async with session.get(url, headers=headers) as resp:
                    if resp.status >= 400:
                        raise ValueError(await resp.text())
                    return await resp.json()

    @classmethod
    async def get_devices(cls):
        return await cls.request("/1/devices")

    @classmethod
    async def get_appliances(cls):
        return await cls.request("/1/appliances")

    @classmethod
    async def get_room_state(cls, device_id: str, force=False) -> RoomState:
        async with cls.room_lock:
            if device_id in NatureRemo.room_cache and not force:
                if NatureRemo.room_cache[
                    device_id
                ].timestamp > datetime.now() - timedelta(minutes=1):
                    return NatureRemo.room_cache[device_id]

            devices = await NatureRemo.get_devices()
            for device in devices:
                if device["id"] == device_id:
                    cls.room_cache[device_id] = RoomState(
                        temperature=devices[0]["newest_events"]["te"]["val"],
                        timestamp=datetime.now(),
                    )

                    return cls.room_cache[device_id]

            raise ValueError(f"Device {device_id} is not found")

    @classmethod
    async def get_ac_state(cls, appliance_id: str, force=False) -> ACState:
        async with cls.ac_lock:
            if appliance_id in NatureRemo.ac_cache and not force:
                if NatureRemo.ac_cache[
                    appliance_id
                ].timestamp > datetime.now() - timedelta(minutes=1):
                    return NatureRemo.ac_cache[appliance_id]

            appliances = await cls.get_appliances()

            for appliance in appliances:
                if appliance["id"] == appliance_id:
                    cls.ac_cache[appliance_id] = ACState(
                        temperature=appliance["settings"]["temp"],
                        temperature_list=appliance["aircon"]["range"]["modes"][
                            appliance["settings"]["mode"]
                        ]["temp"],
                        mode=appliance["settings"]["mode"],
                        mode_list=appliance["aircon"]["range"]["modes"].keys(),
                        volume=appliance["settings"]["vol"],
                        volume_list=appliance["aircon"]["range"]["modes"][
                            appliance["settings"]["mode"]
                        ]["vol"],
                        power=appliance["settings"]["button"] != "power-off",
                        timestamp=datetime.now(),
                    )

                    return cls.ac_cache[appliance_id]

            raise ValueError(f"Appliance {appliance_id} is not found")

    @classmethod
    async def set_ac_state(cls, appliance_id: str, state: ACState) -> None:
        await cls.request(
            f"/1/appliances/{appliance_id}/aircon_settings",
            method="POST",
            body=state.as_request(),
        )
        state.timestamp = datetime.now()
        cls.ac_cache[appliance_id] = state


class ACKey(Application, ABC):
    def __init__(
        self, key_numbers: set[int], appliance_id: str, loading_icon: Icon = ColorIcon()
    ):
        super().__init__(key_numbers)

        self.__appliance_id = appliance_id
        self.__loading = False
        self.loading_icon = loading_icon

        async def dummy_handler(state: ACState) -> None:
            pass

        self.__handler = dummy_handler

    @abstractmethod
    async def draw(self, ctx: Context) -> None:
        pass

    async def on_display(self, ctx: Context) -> None:
        self.showing = True
        ctx.set_image(self.key_numbers, self.loading_icon)

        if self.showing:
            await self.draw(ctx)

    async def on_hide(self, ctx: Context) -> None:
        self.showing = False

    async def get_state(self) -> ACState:
        return await NatureRemo.get_ac_state(self.__appliance_id)

    async def set_state(self, ctx: Context, state: ACState) -> None:
        self.__loading = True
        await self.draw(ctx)

        await NatureRemo.set_ac_state(self.__appliance_id, state)

        self.__loading = False

        await NatureRemo.get_ac_state(self.__appliance_id, force=True)

        await self.draw(ctx)

    @property
    def loading(self) -> bool:
        return self.__loading


@dataclass
class ACModeKeySetting:
    mode: str
    on_icon: Icon | None = None
    off_icon: Icon | None = None

    def icon(self, on: bool) -> Icon:
        if on:
            return self.on_icon or TextIcon(
                text=self.mode, bg=(255, 255, 255), fg=(0, 0, 0)
            )
        else:
            return self.off_icon or TextIcon(
                text=self.mode, bg=(0, 0, 0), fg=(255, 255, 255)
            )


class ACModeKeySet(ACKey):
    def __init__(
        self,
        appliance_id: str,
        keys: dict[int, ACModeKeySetting],
        loading_icon: Icon = ColorIcon(),
    ):
        super().__init__(set(keys.keys()), appliance_id, loading_icon)

        self.keys = keys

    async def draw(self, ctx: Context):
        if self.loading:
            for key, setting in self.keys.items():
                ctx.set_image({key}, setting.icon(on=False))
            return

        state = await self.get_state()

        for key, setting in self.keys.items():
            ctx.set_image(
                {key}, setting.icon(on=state.power and state.mode == setting.mode)
            )

    async def on_press(self, ctx: Context, key_number: int):
        if key_number not in self.keys:
            return

        state = await self.get_state()
        if state.power and state.mode == self.keys[key_number].mode:
            state.power = False
        else:
            state.mode = self.keys[key_number].mode
            state.power = True
        await self.set_state(ctx, state)


class ACTempKeySet(ACKey):
    def __init__(
        self, appliance_id: str, up_key: int, middle_key: int, bottom_key: int
    ):
        super().__init__({up_key, middle_key, bottom_key}, appliance_id, ColorIcon())

        self.up_key = up_key
        self.middle_key = middle_key
        self.bottom_key = bottom_key
        self.pressed_at = 0.0
        self.target = -1

    async def draw(self, ctx: Context):
        state = await self.get_state()

        if state.temperature == "" or state.temperature not in state.temperature_list:
            ctx.set_image({self.up_key, self.bottom_key}, ColorIcon((64, 64, 64)))
            ctx.set_image(self.middle_key, TextIcon(bg=(64, 64, 64), text="--℃"))
            return

        temp = state.temperature
        if self.target >= 0:
            temp = state.temperature_list[self.target]

        current_index = state.temperature_list.index(temp)
        level = (current_index + 1) / (len(state.temperature_list) + 1)

        ctx.set_image(
            {self.up_key}, GaugeIcon(text="▲", value=level, n_keys=3, key_offset=2)
        )
        ctx.set_image(
            {self.middle_key},
            GaugeIcon(text=f"{temp}℃", value=level, n_keys=3, key_offset=1),
        )
        ctx.set_image(
            {self.bottom_key}, GaugeIcon(text="▼", value=level, n_keys=3, key_offset=0)
        )

    async def on_press(self, ctx: Context, key_number: int):
        if key_number != self.up_key and key_number != self.bottom_key:
            return

        at = self.pressed_at = time.time()

        state = await self.get_state()

        if len(state.temperature_list) == 1 and state.temperature_list[0] == "":
            return

        if state.temperature not in state.temperature_list:
            self.target = 0

        if self.target < 0:
            self.target = int(state.temperature_list.index(state.temperature))

        while self.pressed_at == at:
            if key_number == self.up_key:
                self.target = min(self.target + 1, len(state.temperature_list) - 1)
            elif key_number == self.bottom_key:
                self.target = max(self.target - 1, 0)
            else:
                return

            await self.draw(ctx)
            await asyncio.sleep(0.5)

    async def on_release(self, ctx: Context, key_number: int):
        if key_number != self.up_key and key_number != self.bottom_key:
            return

        at = self.pressed_at = time.time()

        await asyncio.sleep(1)

        if self.pressed_at == at and self.target >= 0:
            state = await self.get_state()
            temp = state.temperature_list[self.target]

            if temp != state.temperature:
                state.temperature = temp
                await self.set_state(ctx, state)

            self.target = -1


class ACVolumeKey(ACKey):
    def __init__(self, key_numbers: set[int], appliance_id: str):
        super().__init__(key_numbers, appliance_id, ColorIcon())

        self.pressed_at = 0.0
        self.target = -1

    async def draw(self, ctx: Context):
        state = await self.get_state()

        volume = state.volume
        if self.target >= 0:
            volume = state.volume_list[self.target]

        if volume == "auto":
            ctx.set_image(self.key_numbers, TextIcon(text=volume))
        else:
            level = state.volume_list.index(volume) / (len(state.volume_list) - 2)
            ctx.set_image(self.key_numbers, GaugeIcon(text=f"{level:.0%}", value=level))

    async def on_press(self, ctx: Context, key_number: int):
        at = self.pressed_at = time.time()

        state = await self.get_state()
        if self.target < 0:
            self.target = state.volume_list.index(state.volume)

        self.target = (self.target + 1) % len(state.volume_list)
        await self.draw(ctx)

        await asyncio.sleep(1)

        if self.pressed_at == at and self.target >= 0:
            state = await self.get_state()
            volume = state.volume_list[self.target]

            if volume != state.volume:
                state.volume = volume
                await self.set_state(ctx, state)

            self.target = -1


class RoomTempKey(Application):
    def __init__(self, key_numbers: set[int], device_id: str):
        super().__init__(key_numbers)

        self.device_id = device_id
        self.showing = False

    async def draw(self, ctx: Context):
        state = await NatureRemo.get_room_state(self.device_id)
        ctx.set_image(self.key_numbers, TextIcon(text=f"{state.temperature}℃"))

    async def on_display(self, ctx: Context) -> None:
        self.showing = True

        async def loop():
            while self.showing:
                await self.draw(ctx)
                await asyncio.sleep(60)

        ctx.now(loop)

    async def on_hide(self, ctx: Context) -> None:
        self.showing = False
