from __future__ import annotations

import asyncio

import discord
import structlog
from discord import app_commands

from app.core.backend_client import BackendClient
from app.core.config import get_settings
from app.core.emoji_resolver import EmojiResolver
from app.core.logging import configure_logging
from app.features.discord_bindings.bootstrap import bootstrap_bindings
from app.features.matches.publisher import run_outbox_publisher
from app.features.pinned.leaderboard import ensure_leaderboard_message, refresh_leaderboard_message
from app.features.pinned.live_games import ensure_live_message, refresh_live_message
from app.features.tracked_players.commands import register as register_tracked_players


class App(discord.Client):
    def __init__(self, backend: BackendClient) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.backend = backend
        self.settings = get_settings()
        self.log = structlog.get_logger("discord")
        self.tree = app_commands.CommandTree(self)
        self.emoji = EmojiResolver(self, application_id=self.settings.discord_application_id)
        self._publisher_task: asyncio.Task | None = None
        self._pinned_started = False
        self._live_task: asyncio.Task | None = None
        self._leaderboard_task: asyncio.Task | None = None

        register_tracked_players(
            self.tree,
            self.backend,
            guild_id=self.settings.discord_guild_id,
        )

    async def _clear_bot_messages_in_channel(self, channel_id: int) -> int:
        channel = self.get_channel(channel_id)
        if channel is None or not isinstance(channel, discord.TextChannel) or self.user is None:
            return 0

        deleted = 0
        async for message in channel.history(limit=None):
            if message.author.id != self.user.id:
                continue
            try:
                await message.delete()
                deleted += 1
            except discord.NotFound:
                continue
            except discord.Forbidden as e:
                self.log.error("startup_cleanup_forbidden", channel_id=channel_id, error=str(e))
                break
            except discord.HTTPException as e:
                self.log.error("startup_cleanup_delete_failed", channel_id=channel_id, message_id=message.id, error=str(e))
        return deleted

    async def _cleanup_pinned_feed_channels(self) -> None:
        channel_ids = [
            self.settings.discord_leaderboard_channel_id,
            self.settings.discord_live_channel_id,
        ]
        for channel_id in channel_ids:
            if channel_id is None:
                continue
            deleted = await self._clear_bot_messages_in_channel(channel_id)
            self.log.info("startup_feed_cleanup_done", channel_id=channel_id, deleted=deleted)

    async def _delete_stale_command_group(self, *, guild: discord.abc.Snowflake | None) -> None:
        try:
            commands = await self.tree.fetch_commands(guild=guild)
        except Exception as e:
            self.log.error(
                "fetch_commands_failed",
                guild_id=None if guild is None else int(guild.id),
                error=str(e),
            )
            return

        for command in commands:
            if command.name != "lol":
                continue
            try:
                await command.delete()
                self.log.info(
                    "deleted_stale_command",
                    command_name=command.name,
                    guild_id=None if guild is None else int(guild.id),
                )
            except Exception as e:
                self.log.error(
                    "delete_stale_command_failed",
                    command_name=command.name,
                    guild_id=None if guild is None else int(guild.id),
                    error=str(e),
                )

    async def on_ready(self) -> None:
        self.log.info("bot_ready", user=str(self.user))

        await self._delete_stale_command_group(guild=None)

        if self.settings.discord_guild_id is not None:
            guild = discord.Object(id=self.settings.discord_guild_id)
            await self._delete_stale_command_group(guild=guild)
            global_synced = await self.tree.sync()
            self.log.info(
                "slash_commands_synced_global",
                commands=[cmd.name for cmd in global_synced],
                count=len(global_synced),
            )
            synced = await self.tree.sync(guild=guild)
            self.log.info(
                "slash_commands_synced_guild",
                guild_id=self.settings.discord_guild_id,
                commands=[cmd.name for cmd in synced],
                count=len(synced),
            )
        else:
            synced = await self.tree.sync()
            self.log.info(
                "slash_commands_synced_global",
                commands=[cmd.name for cmd in synced],
                count=len(synced),
            )

        await self.emoji.warmup()

        if self._publisher_task is None:
            self._publisher_task = asyncio.create_task(
                run_outbox_publisher(
                    bot=self,
                    backend=self.backend,
                    consumer_id=self.settings.discord_consumer_id,
                    poll_interval_seconds=self.settings.publish_poll_interval_seconds,
                    guild_id=self.settings.discord_guild_id,
                )
            )

        if self._pinned_started:
            return

        if self.settings.discord_guild_id is None:
            return

        if (
            self.settings.discord_leaderboard_channel_id is None
            or self.settings.discord_live_channel_id is None
            or self.settings.discord_finished_channel_id is None
        ):
            return

        self._pinned_started = True

        await self._cleanup_pinned_feed_channels()

        await bootstrap_bindings(
            backend=self.backend,
            guild_id=self.settings.discord_guild_id,
            leaderboard_channel_id=self.settings.discord_leaderboard_channel_id,
            live_channel_id=self.settings.discord_live_channel_id,
            finished_channel_id=self.settings.discord_finished_channel_id,
        )

        await asyncio.sleep(0.2)

        bindings = await self.backend.list_discord_bindings(guild_id=self.settings.discord_guild_id)
        lb = next((b for b in bindings if str(b.get("binding_key") or "") == "LEADERBOARD_MESSAGE"), None)
        lv = next((b for b in bindings if str(b.get("binding_key") or "") == "LIVE_GAMES_MESSAGE"), None)

        if lb is not None:
            await ensure_leaderboard_message(
                bot=self,
                backend=self.backend,
                guild_id=self.settings.discord_guild_id,
                binding=lb,
            )

        await asyncio.sleep(0.12)

        if lv is not None:
            await ensure_live_message(
                bot=self,
                backend=self.backend,
                guild_id=self.settings.discord_guild_id,
                binding=lv,
            )

        self._leaderboard_task = asyncio.create_task(self._loop_leaderboard())
        self._live_task = asyncio.create_task(self._loop_live())

    async def _loop_live(self) -> None:
        if self.settings.discord_guild_id is None:
            return
        guild_id = self.settings.discord_guild_id

        while not self.is_closed():
            try:
                bindings = await self.backend.list_discord_bindings(guild_id=guild_id)
                lv = next((b for b in bindings if str(b.get("binding_key") or "") == "LIVE_GAMES_MESSAGE"), None)
                if lv is not None:
                    await refresh_live_message(bot=self, backend=self.backend, guild_id=guild_id, binding=lv)
            except Exception as e:
                self.log.error("live_loop_error", error=str(e))
            await asyncio.sleep(self.settings.live_refresh_interval_seconds)

    async def _loop_leaderboard(self) -> None:
        if self.settings.discord_guild_id is None:
            return
        guild_id = self.settings.discord_guild_id

        while not self.is_closed():
            try:
                bindings = await self.backend.list_discord_bindings(guild_id=guild_id)
                lb = next((b for b in bindings if str(b.get("binding_key") or "") == "LEADERBOARD_MESSAGE"), None)
                if lb is not None:
                    await refresh_leaderboard_message(bot=self, backend=self.backend, guild_id=guild_id, binding=lb)
            except Exception as e:
                self.log.error("leaderboard_loop_error", error=str(e))
            await asyncio.sleep(3600)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    if not settings.discord_token.strip():
        structlog.get_logger("discord").error("missing_discord_token")
        return

    backend = BackendClient(
        settings.backend_base_url,
        proxy_secret=settings.backend_proxy_secret,
    )
    app = App(backend)
    try:
        await app.start(settings.discord_token)
    finally:
        await backend.aclose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
