# utils/ton_api.py
import aiohttp
from config import TONCENTER_API_KEY, TON_WALLET

async def check_transaction(comment, expected_amount):
    """
    Проверяет, была ли получена транзакция с указанным комментарием и суммой (в TON).
    Возвращает True, если найдена подходящая транзакция.
    """
    url = "https://toncenter.com/api/v2/getTransactions"
    params = {
        "address": TON_WALLET,
        "limit": 50,
        "archival": "true",
        "api_key": TONCENTER_API_KEY
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
            if not data.get("ok"):
                return False
            txs = data.get("result", [])
            for tx in txs:
                in_msg = tx.get("in_msg", {})
                if not in_msg:
                    continue
                msg_comment = in_msg.get("message", "")
                value_nano = int(in_msg.get("value", 0))
                value_ton = value_nano / 1e9
                if msg_comment == comment and value_ton >= expected_amount * 0.99:
                    return True
            return False