import aiohttp


class Hue:
    @staticmethod
    async def find_bridge() -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discovery.meethue.com/") as response:
                return (await response.json())[0]["internalipaddress"]


if __name__ == "__main__":
    import asyncio

    async def main():
        print(await Hue.find_bridge())

    asyncio.run(main())
