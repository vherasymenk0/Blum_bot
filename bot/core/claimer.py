import asyncio
import aiohttp
from aiohttp_proxy import ProxyConnector
from pyrogram import Client
from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from .bot_info import bot_info
from better_proxy import Proxy

api_url = bot_info['api']


class Claimer:
    def __init__(self, client: Client, proxy_str: str | None, agent):
        self.client = client
        self.session_name = client.name

        proxy_conn = ProxyConnector().from_url(proxy_str) if proxy_str else None
        clientHeaders = {
            **headers,
            **agent
        }
        self.http_client = aiohttp.ClientSession(headers=clientHeaders, connector=proxy_conn)

        if proxy_str:
            self.check_proxy(proxy=proxy_str)
            proxy = Proxy.from_str(proxy_str)
            self.client.proxy = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.http_client.close()

    async def check_proxy(self, proxy: str) -> None:
        try:
            response = await self.http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

    async def run(self) -> None:
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
        async with Claimer(client=tg_client, proxy_str=proxy, agent=agent) as claimer:
            await claimer.run()
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
