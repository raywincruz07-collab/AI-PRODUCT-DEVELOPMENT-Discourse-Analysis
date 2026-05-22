"""Truth Social data collector using truthbrush (Stanford IO)."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# Well-known active Truth Social accounts for bulk collection
POPULAR_ACCOUNTS = [
    # ── POLITICS - US (Confirmed on Truth Social) ──────────────────
    "realDonaldTrump", "DonaldJTrumpJr", "dbongino", "EricTrump",
    "RepMTG", "SenTedCruz", "CharlieKirk", "JackPosobiec",
    "KariLake", "RandPaul", "TulsiGabbard", "KashPatel",
    "TomFitton", "StephenMiller", "JudgeJeanine", "MarkLevin",
    "MattGaetz", "GreggJarrett", "KatrinaPierson", "SebGorka",
    "RealCandaceO", "MikeLindell", "GenFlynn", "DevinNunes",
    "RonDeSantis", "VivekGRamaswamy", "ElonMusk", "JDVance",
    "LauraLoomer", "RichardGrenell", "PeteHegseth", "GregAbbott",
    "GlennBeck", "AlexJones", "ScottPresler", "JimJordan",
    "MikePompeo", "TomCotton", "JoshHawley", "RickScott",
    "BenShapiro", "DanBongino", "TuckerCarlson", "SeanHannity",
    "MariaBartiromo", "LaraLogan", "SaraCarterDC", "JohnSolomon",
    "MirandaDevine", "ByronDonalds", "ClayHiggins",
    "catturd2", "PaulJosephWatson", "LibsOfTikTok",
    "EndWokeness", "RealMattCouch",
    "AndrewTate", "MichaelFlynn", "SidneyPowell",
    "LLinWood", "RudyGiuliani", "MyPillowMike",
    "BrianKilmeade", "JesseBWatters", "GregGutfeld",
    "IngrahamAngle", "EmeraldRobinson",
    "ChrisSalcedo", "RealAmericaVoice", "RSBN",
    "ProjectVeritas",

    # ── POLITICS - INTERNATIONAL (Confirmed on Truth Social) ────────
    "NayibBukele",
    "JavierMilei",
    "NigelFarage",
    "ViktorOrban",
    "BolsonaroJair",
    "GlennGreenwald",
    "MattTaibbi",
    "JimmyDore",
    "ScottRitter",
    "TimcastIRL",
    "StevenCrowder",
    "DineshDSouza",
    "RealJamesWoods",

    # ── NEWS MEDIA (Confirmed on Truth Social) ─────────────────────
    "Breitbart", "OANN", "Newsmax", "epochtimes",
    "gatewaypundit", "WashingtonExaminer", "DailyWire",
    "FoxNews", "NYPost", "RealAmericasVoice", "NationalPulse",
    "TheFederalist", "HumanEvents", "RedState",
    "ThePostMillennial", "NationalReview", "TheBabylonBee",
    "RumbleVideo", "ZeroHedge", "UncoverDC", "RealClearPolitics",
    "TheHill", "JustTheNews", "WesternJournal",
    "PJMedia", "TownhallMedia", "AmericanThinker",
    "ConservativeTreehouse", "TheGatewayPundit",

    # ── OSINT (Some confirmed on Truth Social) ─────────────────────
    "OSINTdefender",
    "IntelSlava",
    "GeopoliticsLive",

    # ── HEALTH / MEDICAL (Confirmed on Truth Social) ───────────────
    "DrMcCulloughTruth", "RealDrGina", "DrRobertMalone",
    "DrJohnCampbell", "NaturalNews", "ChildrensHealthDef",
    "DrNaomiWolf", "DrPierreKory", "DrJanMarkell",
    "AmericanFrontlineDoctors", "FlcccAlliance",

    # ── CRIME / LEGAL (Confirmed on Truth Social) ──────────────────
    "JonathanTurley",

    # ── MILITARY / DEFENCE (Confirmed on Truth Social) ─────────────
    "IsraelWarRoom",

    # ── BUSINESS / FINANCE (Confirmed on Truth Social) ─────────────
    "LarryKudlow", "SteveForbesCEO",
    "CryptoNews", "BitcoinMagazine",

    # ── CLIMATE / ENVIRONMENT (Confirmed on Truth Social) ──────────
    "ClimateDepot", "WattsUpWithThat", "ClimateRealism",
    "NoTricksZone", "RealClimateScience",

    # ── RELIGION / CULTURE (Confirmed on Truth Social) ─────────────
    "JackHibbs", "FranklinGraham", "CBNNews",
    "ChristianPost", "CatholicNewsAgency",
    "VaticanNews", "ChurchMilitant",

    # ── ENTERTAINMENT (Some confirmed on Truth Social) ─────────────
    "RealRoseanne", "KidRock",
    "JohnRich", "TedNugent", "ClintEastwood",
]


class TruthSocialCollector(BaseCollector):
    platform = "truthsocial"

    def __init__(self):
        self._api = None
        self._account_index = 0  # rotate through accounts each cycle

    def _get_api(self):
        """Lazy-init the truthbrush Api (requires credentials)."""
        if self._api is None:
            from truthbrush import Api

            if config.TRUTHSOCIAL_TOKEN:
                self._api = Api(token=config.TRUTHSOCIAL_TOKEN)
            elif config.TRUTHSOCIAL_USERNAME and config.TRUTHSOCIAL_PASSWORD:
                self._api = Api(
                    username=config.TRUTHSOCIAL_USERNAME,
                    password=config.TRUTHSOCIAL_PASSWORD,
                )
            else:
                raise RuntimeError(
                    "Truth Social credentials not configured. "
                    "Set TRUTHSOCIAL_USERNAME + TRUTHSOCIAL_PASSWORD or TRUTHSOCIAL_TOKEN env vars."
                )
        return self._api

    @staticmethod
    def is_configured() -> bool:
        """Return True if credentials are present."""
        return bool(
            config.TRUTHSOCIAL_TOKEN
            or (config.TRUTHSOCIAL_USERNAME and config.TRUTHSOCIAL_PASSWORD)
        )

    def _parse_status(self, status: dict, feed: str = "trending") -> dict:
        """Parse a Truth Social status into our standard format."""
        content_raw = status.get("content", "")
        media_urls = [m.get("url", "") for m in status.get("media_attachments", [])]
        account = status.get("account", {})
        in_reply_to = status.get("in_reply_to_id")

        posted_at = status.get("created_at", datetime.now(timezone.utc).isoformat())

        return {
            "platform": "truthsocial",
            "external_id": str(status.get("id", "")),
            "board_or_feed": feed,
            "thread_id": str(in_reply_to) if in_reply_to else None,
            "author": account.get("username", account.get("acct", "unknown")),
            "content_raw": content_raw,
            "content_text": self.strip_html(content_raw),
            "media_urls": media_urls,
            "posted_at": posted_at,
            "likes": status.get("favourites_count", 0),
            "replies": status.get("replies_count", 0),
            "shares": status.get("reblogs_count", 0),
            "metadata": {
                "display_name": account.get("display_name", ""),
                "followers_count": account.get("followers_count", 0),
                "language": status.get("language", ""),
            },
        }

    def _collect_user_posts(self, username: str, max_posts: int = 30) -> list[dict]:
        """Collect recent posts from a specific user. Most reliable truthbrush method."""
        api = self._get_api()
        posts = []
        try:
            for i, status in enumerate(api.pull_statuses(username=username, replies=False)):
                if i >= max_posts:
                    break
                if isinstance(status, dict):
                    posts.append(status)
            time.sleep(1)  # be gentle between users
        except Exception as e:
            err_str = str(e)
            if "Cloudflare" not in err_str and "Access denied" not in err_str:
                logger.warning(f"Could not fetch posts for @{username}: {e}")
        return posts

    async def _fetch_user_batch(self, usernames: list[str], max_per_user: int = 30) -> list[dict]:
        """Fetch posts from a batch of user accounts."""
        posts = []
        for username in usernames:
            try:
                raw = await asyncio.to_thread(self._collect_user_posts, username, max_per_user)
                for status in raw:
                    if isinstance(status, dict) and status.get("id"):
                        posts.append(self._parse_status(status, f"user_{username}"))
                if raw:
                    logger.info(f"Truth Social @{username}: {len(raw)} posts fetched")
            except Exception as e:
                logger.warning(f"Truth Social @{username} failed: {e}")
            await asyncio.sleep(1)
        return posts

    async def _fetch_hashtag_safe(self, tag: str) -> list[dict]:
        """Fetch hashtag posts with full error protection."""
        try:
            api = self._get_api()

            def _collect():
                all_items = []
                try:
                    for batch in api.hashtag(tag=tag, limit=40):
                        if isinstance(batch, list):
                            for item in batch:
                                if isinstance(item, dict) and item.get("id"):
                                    all_items.append(item)
                        elif isinstance(batch, dict) and batch.get("id"):
                            all_items.append(batch)
                except (TypeError, KeyError, Exception):
                    pass  # truthbrush pagination bug or Cloudflare
                return all_items

            raw = await asyncio.to_thread(_collect)
            posts = []
            for status in raw:
                posts.append(self._parse_status(status, f"hashtag_{tag}"))
            return posts
        except Exception as e:
            logger.debug(f"Truth Social #{tag} failed: {e}")
            return []

    async def collect(self) -> int:
        """Collect from Truth Social using account-based strategy (bypasses Cloudflare)."""
        if not self.is_configured():
            logger.warning(
                "Truth Social collector skipped: credentials not configured. "
                "Set TRUTHSOCIAL_USERNAME/TRUTHSOCIAL_PASSWORD or TRUTHSOCIAL_TOKEN in .env"
            )
            return 0

        total = 0

        # Strategy 1: Pull posts from popular accounts (MOST RELIABLE - bypasses Cloudflare)
        # Rotate through 5 accounts per cycle to avoid rate limits
        batch_size = 15
        start = self._account_index
        end = start + batch_size
        batch_accounts = POPULAR_ACCOUNTS[start:end]
        if not batch_accounts:
            self._account_index = 0
            batch_accounts = POPULAR_ACCOUNTS[:batch_size]
        self._account_index = end if end < len(POPULAR_ACCOUNTS) else 0

        logger.info(f"Truth Social collecting from accounts: {', '.join(batch_accounts)}")
        posts = await self._fetch_user_batch(batch_accounts, max_per_user=50)
        if posts:
            count = await self.save_posts(posts)
            total += count
            logger.info(f"Truth Social user accounts: {len(posts)} fetched, {count} new")

        await asyncio.sleep(2)

        # Strategy 2: Hashtag feeds (may get Cloudflare-blocked but worth trying)
        for tag in config.TRUTHSOCIAL_HASHTAGS:
            if not tag:
                continue
            posts = await self._fetch_hashtag_safe(tag)
            if posts:
                count = await self.save_posts(posts)
                total += count
                logger.info(f"Truth Social #{tag}: {len(posts)} fetched, {count} new")
            await asyncio.sleep(2)

        logger.info(f"Truth Social cycle complete: {total} new posts total")
        return total

    async def close(self):
        """No persistent connection to close for truthbrush."""
        pass
