"""Collection scheduler - runs collectors at configured intervals."""

import asyncio
import logging

import config
from collectors.fourchan import FourChanCollector
from collectors.mastodon import MastodonCollector
from collectors.truthsocial import TruthSocialCollector

logger = logging.getLogger(__name__)


async def run_collector_loop():
    """Run all collectors on their configured intervals."""
    fourchan = FourChanCollector()
    mastodon = MastodonCollector()

    loops = []

    async def fourchan_loop():
        while True:
            try:
                logger.info("Starting 4chan collection cycle...")
                count = await fourchan.collect()
                logger.info(f"4chan collection complete: {count} new posts")
            except Exception as e:
                logger.error(f"4chan collection error: {e}")
            await asyncio.sleep(config.FOURCHAN_COLLECT_INTERVAL_MINUTES * 60)

    async def mastodon_loop():
        while True:
            try:
                logger.info("Starting Mastodon collection cycle...")
                count = await mastodon.collect()
                logger.info(f"Mastodon collection complete: {count} new posts")
            except Exception as e:
                logger.error(f"Mastodon collection error: {e}")
            await asyncio.sleep(config.MASTODON_COLLECT_INTERVAL_MINUTES * 60)

    loops.append(fourchan_loop())
    loops.append(mastodon_loop())

    # Only start Truth Social collector if credentials are configured
    truthsocial = None
    if TruthSocialCollector.is_configured():
        truthsocial = TruthSocialCollector()

        async def truthsocial_loop():
            while True:
                try:
                    logger.info("Starting Truth Social collection cycle...")
                    count = await truthsocial.collect()
                    logger.info(f"Truth Social collection complete: {count} new posts")
                except Exception as e:
                    # Include stack trace because Cloudflare/geo/JSON decode errors
                    # are otherwise hard to diagnose from a single line.
                    logger.exception(f"Truth Social collection error: {e}")
                await asyncio.sleep(config.TRUTHSOCIAL_COLLECT_INTERVAL_MINUTES * 60)

        loops.append(truthsocial_loop())
        logger.info("Truth Social collector enabled (credentials found)")
    else:
        logger.warning(
            "Truth Social collector disabled — set TRUTHSOCIAL_USERNAME + TRUTHSOCIAL_PASSWORD "
            "or TRUTHSOCIAL_TOKEN env vars to enable"
        )

    try:
        await asyncio.gather(*loops)
    finally:
        await fourchan.close()
        await mastodon.close()
        if truthsocial:
            await truthsocial.close()
