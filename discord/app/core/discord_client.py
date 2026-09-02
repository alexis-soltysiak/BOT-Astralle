from __future__ import annotations

import discord


def build_intents(*, message_content: bool = True) -> discord.Intents:
    """message_content est un intent privilegie.

    Il doit etre coche dans le Discord Developer Portal, sinon discord.py leve
    PrivilegedIntentsRequired au demarrage et le bot entier refuse de se
    connecter. On le rend donc conditionnel : couper LISNARD_ENABLED suffit a
    faire redemarrer le bot sans toucher au portail.
    """
    intents = discord.Intents.default()
    intents.message_content = message_content
    return intents
