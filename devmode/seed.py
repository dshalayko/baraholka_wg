"""Test data for debug mode.

Only ever writes to the debug database (devmode.env points DB_PATH at
data/debug/debug.db). Published ads are also registered in the fake outbox so
the virtual channel is populated the moment the server starts.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiosqlite
import pytz

from devmode import fake_telegram as fake
from devmode.users import TEST_USERS

BELGRADE = pytz.timezone("Europe/Belgrade")


def _now() -> datetime:
    return datetime.now(pytz.utc).astimezone(BELGRADE)


def _display_stamp(offset: timedelta = timedelta()) -> str:
    """announcements.timestamp / updated_at format ('%d.%m.%Y в %H:%M')."""
    return (_now() + offset).strftime("%d.%m.%Y в %H:%M")


def _auction_stamp(offset: timedelta = timedelta()) -> str:
    """auction_end_at / auction_bids.created_at format (string-comparable)."""
    return (_now() + offset).strftime("%Y-%m-%d %H:%M:%S")


def _user(key: str) -> Dict[str, Any]:
    user = TEST_USERS[key]
    return {
        "id": user["id"],
        "username": user.get("username") or "None",
        "language_code": user.get("language_code") or "ru",
    }


class _Ad:
    """One seeded announcement."""

    def __init__(
        self,
        owner: str,
        description: str,
        *,
        price: str = "",
        price_in_description: bool = False,
        contact_info: str = "",
        photos: int = 0,
        photo_slug: str = "ad",
        published: bool = False,
        published_offset: timedelta = timedelta(minutes=-30),
        is_reserved: bool = False,
        last_published_is_edit: bool = False,
        ad_type: str = "fixed",
        start_price: Optional[int] = None,
        current_price: Optional[int] = None,
        min_step: Optional[int] = None,
        buyout_price: Optional[int] = None,
        duration_hours: Optional[int] = None,
        ends_in: Optional[timedelta] = None,
        currency: str = "RSD",
        auction_status: Optional[str] = None,
        winner: Optional[str] = None,
        bids: Optional[List[Dict[str, Any]]] = None,
    ):
        self.owner = owner
        self.description = description
        self.price = price
        self.price_in_description = price_in_description
        self.contact_info = contact_info
        self.photos = photos
        self.photo_slug = photo_slug
        self.published = published
        self.published_offset = published_offset
        self.is_reserved = is_reserved
        self.last_published_is_edit = last_published_is_edit
        self.ad_type = ad_type
        self.start_price = start_price
        self.current_price = current_price
        self.min_step = min_step
        self.buyout_price = buyout_price
        self.duration_hours = duration_hours
        self.ends_in = ends_in
        self.currency = currency
        self.auction_status = auction_status
        self.winner = winner
        self.bids = bids or []


def _catalog() -> List[_Ad]:
    return [
        # ---------------- fixed-price ads ----------------
        _Ad(
            "owner",
            "Черновик без фото. Диван IKEA KIVIK, тёмно-серый, 3 места.\n"
            "Проверь тут: **жирный**, _курсив_, ~~зачёркнутый~~, `моно`, ||спойлер||.",
            price="18 000 RSD",
        ),
        _Ad(
            "owner",
            "Черновик с фото. Велосипед Cube Aim, рама M, колёса 29\".",
            price="250 EUR",
            photos=2,
            photo_slug="bike",
        ),
        _Ad(
            "owner",
            "Опубликовано: кофемашина Delonghi Magnifica S, полный сервис в мае.\n"
            "Забирать в Новом Београде, район Блок 45.",
            price="15 500 RSD",
            photos=3,
            photo_slug="coffee",
            published=True,
            published_offset=timedelta(hours=-5),
        ),
        _Ad(
            "owner",
            "Забронировано: детское автокресло Britax Römer, группа 1/2/3.\n"
            "Цена в описании: 6 000 RSD, торг небольшой.",
            price_in_description=True,
            photos=1,
            photo_slug="carseat",
            published=True,
            published_offset=timedelta(days=-2),
            is_reserved=True,
            last_published_is_edit=True,
        ),
        _Ad(
            "owner",
            "Старое объявление (35 дней) — должно попасть в админский список просроченных.\n"
            "Монитор Dell U2419H, 24\", IPS.",
            price="9 000 RSD",
            published=True,
            published_offset=timedelta(days=-35),
        ),
        _Ad(
            "noname",
            "Объявление от пользователя без @username — контакт указан текстом.\n"
            "Стол письменный, 120x60, светлое дерево.",
            price="4 500 RSD",
            contact_info="Telegram: +381 60 000 0000",
            photos=1,
            photo_slug="desk",
            published=True,
            published_offset=timedelta(hours=-20),
        ),
        # ---------------- auctions ----------------
        _Ad(
            "owner",
            "Аукцион без ставок. Гитара Yamaha FG800, натуральный сатин, чехол в комплекте.",
            photos=3,
            photo_slug="guitar",
            published=True,
            published_offset=timedelta(minutes=-45),
            ad_type="auction",
            auction_status="active",
            start_price=8000,
            min_step=500,
            buyout_price=20000,
            duration_hours=24,
            ends_in=timedelta(hours=6),
            currency="RSD",
        ),
        _Ad(
            "owner",
            "Аукцион со ставками, EUR, без выкупа. Объектив Fujifilm XF 35mm f/2 WR.",
            photos=2,
            photo_slug="lens",
            published=True,
            published_offset=timedelta(hours=-3),
            ad_type="auction",
            auction_status="active",
            start_price=180,
            current_price=225,
            min_step=15,
            duration_hours=12,
            ends_in=timedelta(minutes=90),
            currency="EUR",
            winner="bidder",
            bids=[
                {"user": "bidder", "amount": 195, "ago": timedelta(hours=-2)},
                {"user": "noname", "amount": 210, "ago": timedelta(minutes=-70)},
                {"user": "bidder", "amount": 225, "ago": timedelta(minutes=-12)},
            ],
        ),
        _Ad(
            "owner",
            "Завершённый аукцион с победителем. Наушники Sony WH-1000XM4.",
            photos=1,
            photo_slug="headphones",
            published=True,
            published_offset=timedelta(days=-1),
            ad_type="auction",
            auction_status="finished",
            start_price=12000,
            current_price=19500,
            min_step=500,
            duration_hours=24,
            ends_in=timedelta(minutes=-20),
            currency="RSD",
            winner="bidder",
            bids=[
                {"user": "bidder", "amount": 12500, "ago": timedelta(hours=-20)},
                {"user": "noname", "amount": 17000, "ago": timedelta(hours=-8)},
                {"user": "bidder", "amount": 19500, "ago": timedelta(hours=-1)},
            ],
        ),
        _Ad(
            "owner",
            "Черновик аукциона — ещё не опубликован, время окончания появится при публикации.",
            photos=2,
            photo_slug="draftauction",
            ad_type="auction",
            start_price=3000,
            min_step=250,
            buyout_price=9000,
            duration_hours=48,
            currency="RSD",
        ),
        _Ad(
            "bidder",
            "Auction owned by the OTHER test user — switch to 'owner' and place a bid here.\n"
            "Mechanical keyboard, Keychron K2 Pro, brown switches.",
            photos=2,
            photo_slug="keyboard",
            published=True,
            published_offset=timedelta(hours=-1),
            ad_type="auction",
            auction_status="active",
            start_price=90,
            min_step=10,
            buyout_price=180,
            duration_hours=24,
            ends_in=timedelta(hours=10),
            currency="EUR",
        ),
    ]


def _display_name_for(user_id: int) -> str:
    for user in TEST_USERS.values():
        if user["id"] == user_id:
            return f"{user['first_name']} {user.get('last_name', '')}".strip()
    return f"id:{user_id}"


def render_channel_text(
    *,
    ann_id: int,
    user_id: int,
    username: str,
    description: str,
    contact_info: Optional[str],
    language_code: str,
    ad_type: str,
    price: str = "",
    price_in_description: bool = False,
    is_updated: bool = False,
    is_reserved: bool = False,
    start_price=None,
    current_price=None,
    min_step=None,
    buyout_price=None,
    auction_end_at=None,
    auction_status=None,
    winner_username=None,
    currency: str = "RSD",
) -> str:
    """Render an ad exactly the way the bot posts it to the channel."""
    from webserver.telegram_client import format_announcement_text, format_auction_text, make_bid_link_md

    display_name = _display_name_for(user_id)
    if ad_type == "auction":
        text = format_auction_text(
            description,
            username,
            contact_info,
            display_name,
            start_price,
            current_price,
            min_step,
            auction_end_at,
            winner_username,
            auction_status,
            language_code=language_code,
            currency=currency,
            buyout_price=buyout_price,
        )
        if auction_status == "active":
            text = f"{text}\n\n{make_bid_link_md(ann_id, language_code)}"
        return text

    return format_announcement_text(
        description,
        price,
        price_in_description,
        username,
        contact_info,
        display_name,
        is_updated,
        is_reserved,
    )


async def seed(db_path: str) -> Dict[str, int]:
    """Insert the catalog. Assumes the schema already exists (ensure_db)."""
    ads = _catalog()
    inserted = 0
    bids_inserted = 0

    async with aiosqlite.connect(db_path) as db:
        for ad in ads:
            owner = _user(ad.owner)
            photo_ids = fake.ensure_seed_photos(ad.photo_slug, ad.photos) if ad.photos else []

            message_ids: List[int] = []
            if ad.published:
                count = max(1, len(photo_ids))
                message_ids = [fake.outbox.next_message_id() for _ in range(count)]

            winner = _user(ad.winner) if ad.winner else None
            timestamp = _display_stamp(ad.published_offset) if ad.published else None

            cursor = await db.execute(
                """
                INSERT INTO announcements (
                    user_id, username, description, price, price_in_description, contact_info,
                    photo_file_ids, message_ids, timestamp, updated_at, last_published_is_edit,
                    is_reserved, ad_type, auction_status, start_price, current_price, min_step,
                    buyout_price, auction_end_at, auction_duration_hours, currency,
                    winner_user_id, winner_username, owner_language_code, winner_language_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner["id"],
                    owner["username"],
                    ad.description,
                    ad.price,
                    1 if ad.price_in_description else 0,
                    ad.contact_info,
                    json.dumps(photo_ids),
                    json.dumps(message_ids) if message_ids else None,
                    timestamp,
                    _display_stamp(ad.published_offset),
                    1 if ad.last_published_is_edit else 0,
                    1 if ad.is_reserved else 0,
                    ad.ad_type,
                    ad.auction_status,
                    ad.start_price,
                    ad.current_price,
                    ad.min_step,
                    ad.buyout_price,
                    _auction_stamp(ad.ends_in) if ad.ends_in else None,
                    ad.duration_hours,
                    ad.currency if ad.ad_type == "auction" else None,
                    winner["id"] if winner else None,
                    f"@{winner['username']}" if winner and winner["username"] != "None" else None,
                    owner["language_code"],
                    winner["language_code"] if winner else None,
                ),
            )
            ann_id = cursor.lastrowid
            inserted += 1

            for bid in ad.bids:
                bidder = _user(bid["user"])
                handle = f"@{bidder['username']}" if bidder["username"] != "None" else str(bidder["id"])
                await db.execute(
                    "INSERT INTO auction_bids (announcement_id, user_id, username, amount, created_at) VALUES (?, ?, ?, ?, ?)",
                    (ann_id, bidder["id"], handle, bid["amount"], _auction_stamp(bid["ago"])),
                )
                bids_inserted += 1

            if message_ids:
                text = render_channel_text(
                    ann_id=ann_id,
                    user_id=owner["id"],
                    username=owner["username"],
                    description=ad.description,
                    contact_info=ad.contact_info,
                    language_code=owner["language_code"],
                    ad_type=ad.ad_type,
                    price=ad.price,
                    price_in_description=ad.price_in_description,
                    is_updated=ad.last_published_is_edit,
                    is_reserved=ad.is_reserved,
                    start_price=ad.start_price,
                    current_price=ad.current_price,
                    min_step=ad.min_step,
                    buyout_price=ad.buyout_price,
                    auction_end_at=_auction_stamp(ad.ends_in) if ad.ends_in else None,
                    auction_status=ad.auction_status,
                    winner_username=f"@{winner['username']}" if winner and winner["username"] != "None" else None,
                    currency=ad.currency,
                )
                fake.outbox.put_channel_post(message_ids[0], text, photo_ids, [])

        # Counters so the admin stats screen has something to show.
        for key, value in (
            ("app_open", 137),
            ("publish_success", 24),
            ("publish_fail", 3),
            ("open_comments", 41),
            ("api_errors", 6),
        ):
            await db.execute(
                """
                INSERT INTO app_stats (stat_key, stat_value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(stat_key) DO UPDATE SET stat_value = excluded.stat_value, updated_at = excluded.updated_at
                """,
                (key, value, _display_stamp()),
            )

        await db.commit()

    return {"ads": inserted, "bids": bids_inserted}


async def rehydrate_channel(db_path: str) -> int:
    """Rebuild the virtual channel from the debug database.

    The outbox lives in memory, so a restart would otherwise show an empty
    channel and — worse — start handing out message_ids that published ads
    already own. Returns the number of posts restored.
    """
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT id, user_id, username, description, price, price_in_description, contact_info,
                   photo_file_ids, message_ids, last_published_is_edit, is_reserved,
                   COALESCE(ad_type,'fixed'), auction_status, start_price, current_price, min_step,
                   buyout_price, auction_end_at, winner_username, currency, owner_language_code
            FROM announcements
            WHERE message_ids IS NOT NULL AND message_ids != '[]'
            ORDER BY id
            """
        )
        rows = await cursor.fetchall()

    highest = 0
    restored = 0
    for row in rows:
        (
            ann_id,
            user_id,
            username,
            description,
            price,
            price_in_description,
            contact_info,
            photo_file_ids_raw,
            message_ids_raw,
            last_published_is_edit,
            is_reserved,
            ad_type,
            auction_status,
            start_price,
            current_price,
            min_step,
            buyout_price,
            auction_end_at,
            winner_username,
            currency,
            owner_language_code,
        ) = row

        try:
            message_ids = json.loads(message_ids_raw) or []
            photo_ids = json.loads(photo_file_ids_raw) if photo_file_ids_raw else []
        except (TypeError, ValueError):
            continue
        if not message_ids:
            continue
        highest = max(highest, max(int(mid) for mid in message_ids))

        text = render_channel_text(
            ann_id=ann_id,
            user_id=user_id,
            username=username or "None",
            description=description or "",
            contact_info=contact_info,
            language_code=owner_language_code or "ru",
            ad_type=ad_type,
            price=price or "",
            price_in_description=bool(price_in_description),
            is_updated=bool(last_published_is_edit),
            is_reserved=bool(is_reserved),
            start_price=start_price,
            current_price=current_price,
            min_step=min_step,
            buyout_price=buyout_price,
            auction_end_at=auction_end_at,
            auction_status=auction_status,
            winner_username=winner_username,
            currency=currency or "RSD",
        )
        fake.outbox.put_channel_post(int(message_ids[0]), text, photo_ids, [])
        restored += 1

    fake.outbox.reserve_message_ids_up_to(highest)
    return restored


async def is_seeded(db_path: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM announcements")
        return int((await cursor.fetchone())[0] or 0) > 0


async def wipe(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM auction_bids")
        await db.execute("DELETE FROM announcements")
        await db.execute("DELETE FROM app_stats")
        # Reset AUTOINCREMENT so a reseed always yields the same ids (the
        # auction with bids is always #8, and so on) — otherwise every reseed
        # shifts them and any noted id or bookmarked ?bid=N goes stale.
        await db.execute("DELETE FROM sqlite_sequence WHERE name IN ('announcements', 'auction_bids')")
        await db.commit()
    fake.outbox.clear()
    fake.outbox.reset_message_ids()
