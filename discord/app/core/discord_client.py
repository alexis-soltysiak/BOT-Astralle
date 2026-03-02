from __future__ import annotations

import discord


def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    return intents
