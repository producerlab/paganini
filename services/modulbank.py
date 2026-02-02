"""
Модуль для интеграции с платёжным API Модуль Банка.

Документация API: https://sup.modulbank.ru/
"""

import base64
import hashlib
import json
import os
import time
from typing import Optional

import httpx

from services.logging import logger

# API endpoints
MODULBANK_API_URL = "https://pay.modulbank.ru/api/v1"


def get_merchant_id() -> str:
    return os.getenv("MODULBANK_MERCHANT_ID", "").strip()


def get_secret_key() -> str:
    """Возвращает секретный ключ в зависимости от режима (тест/боевой)."""
    if os.getenv("MODULBANK_TEST_MODE", "1") == "1":
        return os.getenv("MODULBANK_TEST_SECRET_KEY", "").strip()
    return os.getenv("MODULBANK_SECRET_KEY", "").strip()


def get_webhook_url() -> str:
    return os.getenv("MODULBANK_WEBHOOK_URL", "")


def get_success_url() -> str:
    """URL для редиректа после успешной оплаты."""
    bot_username = os.getenv("BOT_USERNAME", "")
    return f"https://t.me/{bot_username}"


def calculate_signature(params: dict, secret_key: str) -> str:
    """
    Расчёт криптографической подписи для API Модуль Банка.

    Алгоритм:
    1. Взять все непустые параметры (кроме signature)
    2. Отсортировать по алфавиту ключей
    3. Закодировать каждое значение в Base64
    4. Объединить в строку: "key1=base64(val1)&key2=base64(val2)"
    5. Двойной SHA1: SHA1(secret_key + SHA1(secret_key + строка))

    Документация: https://sup.modulbank.ru/algorithm_for_calculating_signature_field
    """
    # Фильтруем пустые значения и signature
    filtered = {
        k: v for k, v in params.items()
        if v is not None and v != "" and k != "signature"
    }

    # Сортируем по ключам и кодируем значения в Base64
    sorted_params = sorted(filtered.items())
    encoded_parts = []
    for key, value in sorted_params:
        # Конвертируем значение в строку и кодируем в Base64
        value_str = str(value)
        value_b64 = base64.b64encode(value_str.encode("utf-8")).decode("utf-8")
        encoded_parts.append(f"{key}={value_b64}")

    encoded_string = "&".join(encoded_parts)

    # Двойной SHA1
    first_hash = hashlib.sha1(
        (secret_key + encoded_string).encode("utf-8")
    ).hexdigest()

    final_hash = hashlib.sha1(
        (secret_key + first_hash).encode("utf-8")
    ).hexdigest()

    return final_hash


def verify_signature(params: dict, secret_key: str) -> bool:
    """
    Верификация подписи из callback Модуль Банка.

    Сравнивает signature из params с рассчитанной подписью.
    """
    received_signature = params.get("signature", "")
    if not received_signature:
        return False

    calculated_signature = calculate_signature(params, secret_key)
    return received_signature.lower() == calculated_signature.lower()


def create_receipt_items(generations_num: int, price: int) -> str:
    """
    Формирование позиций чека для фискализации (54-ФЗ).

    Документация: https://sup.modulbank.ru/sending_receipts

    Args:
        generations_num: Количество генераций
        price: Цена в рублях

    Returns:
        JSON-строка с массивом позиций чека
    """
    items = [{
        "name": f"Оплата генераций отчетов Paganini: {generations_num} шт",
        "quantity": 1,
        "price": price,
        "sno": "usn_income",           # УСН (доходы)
        "payment_object": "service",    # Услуга
        "payment_method": "full_prepayment",  # Полная предоплата
        "vat": "none"                   # Без НДС
    }]
    return json.dumps(items, ensure_ascii=False)


async def create_bill(
    email: str,
    amount: int,
    generations_num: int,
    tg_id: int,
    custom_order_id: Optional[str] = None
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Создание счёта на оплату в Модуль Банке.

    Документация: https://sup.modulbank.ru/creating_invoice_for_payment

    Args:
        email: Email клиента для чека
        amount: Сумма платежа в рублях
        generations_num: Количество генераций
        tg_id: Telegram ID пользователя
        custom_order_id: Опциональный ID заказа

    Returns:
        Tuple (payment_url, bill_id, error_message)
        - payment_url: URL для оплаты (None при ошибке)
        - bill_id: ID счёта в системе Модуль Банка (None при ошибке)
        - error_message: Сообщение об ошибке (None при успехе)
    """
    merchant_id = get_merchant_id()
    secret_key = get_secret_key()
    webhook_url = get_webhook_url()
    success_url = get_success_url()

    # Debug logging
    logger.info(f"Modulbank: merchant_id={merchant_id[:8]}... (len={len(merchant_id)})")
    logger.info(f"Modulbank: secret_key set: {bool(secret_key)}, len={len(secret_key)}")
    logger.info(f"Modulbank: test_mode={os.getenv('MODULBANK_TEST_MODE', '1')}")

    if not merchant_id or not secret_key:
        logger.error("Modulbank: merchant_id или secret_key не установлены!")
        return None, None, "Модуль Банк не настроен"

    # Формируем order_id если не передан
    order_id = custom_order_id or f"paganini_{tg_id}_{int(time.time())}"

    # Параметры запроса
    params = {
        "merchant": merchant_id,
        "amount": str(amount),
        "description": f"Оплата генераций отчетов в боте Paganini: {generations_num} шт",
        "unix_timestamp": int(time.time()),
        "success_url": success_url,
        "callback_url": webhook_url,
        "callback_on_failure": "1",
        "custom_order_id": order_id,
        "client_email": email,
        "receipt_contact": email,
        "receipt_items": create_receipt_items(generations_num, amount),
    }

    # Добавляем тестовый режим если включён
    if os.getenv("MODULBANK_TEST_MODE", "1") == "1":
        params["testing"] = "1"

    # Рассчитываем подпись
    signature = calculate_signature(params, secret_key)
    params["signature"] = signature

    # Debug: логируем параметры (без полного ключа)
    logger.info(f"Modulbank: creating bill for order_id={order_id}, amount={amount}")
    logger.debug(f"Modulbank params (без signature): {[(k, v[:20] + '...' if len(str(v)) > 20 else v) for k, v in params.items() if k != 'signature']}")
    logger.info(f"Modulbank: signature={signature[:16]}... (len={len(signature)})")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MODULBANK_API_URL}/bill/",
                data=params
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                bill = data.get("bill", {})
                payment_url = bill.get("url")
                bill_id = bill.get("id")
                return payment_url, bill_id, None
            else:
                # Собираем ошибки
                errors = []
                if "form_errors" in data:
                    errors.extend(data["form_errors"])
                if "field_errors" in data:
                    for field, msgs in data["field_errors"].items():
                        errors.append(f"{field}: {', '.join(msgs)}")
                error_msg = "; ".join(errors) if errors else "Неизвестная ошибка"
                return None, None, error_msg

    except httpx.HTTPStatusError as e:
        logger.error(f"Modulbank HTTP error: {e.response.status_code}, body: {e.response.text}")
        return None, None, f"HTTP ошибка: {e.response.status_code}"
    except httpx.RequestError as e:
        return None, None, f"Ошибка соединения: {str(e)}"
    except Exception as e:
        return None, None, f"Ошибка: {str(e)}"


async def get_bill_status(bill_id: str) -> tuple[Optional[dict], Optional[str]]:
    """
    Получение информации о счёте.

    Документация: https://sup.modulbank.ru/getting_information_about_invoice_issued_for_payment

    Args:
        bill_id: ID счёта в системе Модуль Банка

    Returns:
        Tuple (bill_info, error_message)
    """
    merchant_id = get_merchant_id()
    secret_key = get_secret_key()

    params = {
        "id": bill_id,
        "merchant": merchant_id,
        "unix_timestamp": int(time.time()),
    }
    params["signature"] = calculate_signature(params, secret_key)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{MODULBANK_API_URL}/bill/",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                return data.get("bill"), None
            else:
                return None, data.get("message", "Ошибка получения информации о счёте")

    except Exception as e:
        return None, str(e)


async def refund_payment(
    transaction_id: str,
    amount: int
) -> tuple[bool, Optional[str]]:
    """
    Полный возврат платежа.

    Документация: https://sup.modulbank.ru/full-refund

    Args:
        transaction_id: ID транзакции
        amount: Сумма возврата

    Returns:
        Tuple (success, error_message)
    """
    merchant_id = get_merchant_id()
    secret_key = get_secret_key()

    params = {
        "merchant": merchant_id,
        "transaction": transaction_id,
        "amount": str(amount),
        "unix_timestamp": int(time.time()),
    }
    params["signature"] = calculate_signature(params, secret_key)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MODULBANK_API_URL}/refund",
                data=params
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                return True, None
            else:
                return False, data.get("message", "Ошибка возврата")

    except Exception as e:
        return False, str(e)


def parse_callback_data(data: dict) -> dict:
    """
    Парсинг данных из callback Модуль Банка.

    Args:
        data: Данные из POST запроса

    Returns:
        Словарь с распознанными полями:
        - state: COMPLETE или FAILED
        - transaction_id: ID транзакции
        - order_id: Наш custom_order_id (paganini_...)
        - amount: Сумма платежа
        - is_success: True если оплата успешна
    """
    # ВАЖНО: Модуль Банк возвращает order_id как свой внутренний ID (bill_1, bill_2...),
    # а наш custom_order_id — в поле custom_order_id
    return {
        "state": data.get("state"),
        "transaction_id": data.get("transaction_id"),
        "order_id": data.get("custom_order_id"),  # Используем custom_order_id!
        "modulbank_order_id": data.get("order_id"),  # Внутренний ID Модуль Банка
        "amount": data.get("amount"),
        "currency": data.get("currency", "RUB"),
        "client_email": data.get("client_email"),
        "payment_method": data.get("payment_method"),
        "is_success": data.get("state") == "COMPLETE",
        "error_message": data.get("message") if data.get("state") == "FAILED" else None
    }
