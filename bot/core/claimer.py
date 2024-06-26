import asyncio
from typing import Union, Optional
import aiohttp
from aiohttp_proxy import ProxyConnector
from pyrogram import Client
from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from .bot_info import bot_info
from pyrogram.raw.functions.messages import RequestWebView
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from urllib.parse import unquote
from better_proxy import Proxy

api_url = bot_info['api']
auth_api_url = 'https://gateway.blum.codes/v1/auth/provider/PROVIDER_TELEGRAM_MINI_APP'


class Claimer:
    def __init__(self, client: Client, proxy_str: str | None, agent):
        self.client = client
        self.proxy_str = proxy_str
        self.session_name = client.name

        proxy_conn = ProxyConnector().from_url(proxy_str) if proxy_str else None
        clientHeaders = {
            **headers,
            **agent
        }
        self.http_client = aiohttp.ClientSession(headers=clientHeaders, connector=proxy_conn)

        if proxy_str:
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

    async def check_proxy(self) -> None:
        try:
            response = await self.http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {self.proxy_str} | Error: {error}")
            return

    async def get_tg_web_data(self):
        try:
            if not self.client.is_connected:
                try:
                    await self.client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            web_view = await self.client.invoke(RequestWebView(
                peer=await self.client.resolve_peer(bot_info['username']),
                bot=await self.client.resolve_peer(bot_info['username']),
                platform='android',
                from_bot_menu=False,
                url=bot_info['origin']
            ))

            auth_url = web_view.url
            await self.client.disconnect()
            return unquote(string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def claim(self):
        resp = await self.http_client.post(f"{api_url}/farming/claim")
        data = await resp.json()

        if 'message' in data:
            raise Exception(data['message'])
        else:
            return int(data.get("timestamp") / 1000), data.get("availableBalance")

    async def start(self):
        resp = await self.http_client.post(f"{api_url}/farming/start")
        data = await resp.json()

        if 'message' in data:
            raise Exception(data['message'])

    async def balance(self) -> tuple[int, Union[int, None], Union[int, None], int]:
        resp = await self.http_client.get(f"{api_url}/user/balance")
        data = await resp.json()

        if 'message' in data:
            raise Exception(data['message'])
        else:
            timestamp = data.get("timestamp")
            balance = data.get("availableBalance")
            if data.get("farming"):
                start_time = data.get("farming").get("startTime")
                end_time = data.get("farming").get("endTime")
                return int(timestamp / 1000), int(start_time / 1000), int(end_time / 1000), balance
            else:
                return timestamp, None, None, balance

    async def login(self, tg_web_data: str):
        resp = await self.http_client.post(auth_api_url, json={"query": tg_web_data})
        data = await resp.json()

        if 'message' in data:
            raise Exception(data['message'])
        else:
            token = data.get("token").get("access")
            self.http_client.headers['Authorization'] = f"Bearer {token}"

    async def run(self) -> None:
        if self.proxy_str:
            await self.check_proxy()

        tg_web_data = await self.get_tg_web_data()
        await self.login(tg_web_data)

        while True:
            try:
                timestamp, start_time, end_time, balance = await self.balance()

                if start_time is None and end_time is None:
                    await self.start()
                    logger.success(f"{self.session_name} | Start farming!")
                    await asyncio.sleep(1)
                    continue

                if timestamp >= end_time:
                    timestamp, balance = await self.claim()
                    logger.success(f"{self.session_name} | Claimed reward! Balance: {balance}")
                    await asyncio.sleep(1)
                    continue
                else:
                    sleep_time = divmod(end_time - timestamp, 3600)
                    sleep_time_min, sleep_time_sec = divmod(sleep_time[1], 60)

                    logger.info(f"{self.session_name} | {sleep_time[0]}h-{sleep_time_min}m-{sleep_time_sec}s left until to the next claim")
                    await asyncio.sleep(end_time - timestamp)
                    continue

            except Exception as error:
                if str(error) == 'Invalid jwt token':
                    logger.error(f"{self.session_name} | {error}")
                    logger.info(f"{self.session_name} | Relogin...")
                    self.http_client.headers['Authorization'] = ''
                    await self.login(tg_web_data)
                    await asyncio.sleep(delay=2)
                    continue
                else:
                    logger.error(f"{self.session_name} | Unknown error: {error}")
                    await asyncio.sleep(delay=3)


async def run_claimer(tg_client: Client, proxy: str | None, agent):
    try:
        async with Claimer(client=tg_client, proxy_str=proxy, agent=agent) as claimer:
            await claimer.run()
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
