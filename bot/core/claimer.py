import asyncio

import aiohttp
from aiohttp_proxy import ProxyConnector
from pyrogram import Client
from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from .bot_info import bot_info

api_url = bot_info['api']


class Claimer:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.http_client = None

    async def check_proxy(self, proxy: str) -> None:
        try:
            response = await self.http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

    async def run(self, proxy: str | None, agent) -> None:
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        clientHeaders = {
            **headers,
            **agent
        }

        async with aiohttp.ClientSession(headers=clientHeaders, connector=proxy_conn) as http_client:
            self.http_client = http_client
            if proxy:
                await self.check_proxy(proxy=proxy)

            while True:
                try:
                    logger.info(f"{self.session_name} | claimer is running")

                except InvalidSession as error:
                    raise error

                except Exception as error:
                    logger.error(f"{self.session_name} | Unknown error: {error}")
                    await asyncio.sleep(delay=3)

                else:
                    sleep_between_clicks = 2

                    logger.info(f"Sleep between claim {sleep_between_clicks}s")
                    await asyncio.sleep(delay=sleep_between_clicks)


async def run_claimer(tg_client: Client, proxy: str | None, agent):
    try:
        await Claimer(tg_client=tg_client).run(proxy=proxy, agent=agent)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
