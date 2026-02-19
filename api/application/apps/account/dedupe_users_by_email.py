from __future__ import annotations

import asyncio

from dotenv import load_dotenv
from tortoise import Tortoise, run_async

import application.settings as settings
from application.apps.account.models import OAuthToken, User, UserIdentity


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


async def _ensure_single_user_by_email(email: str) -> User | None:
    normalized = _normalize_email(email)
    if not normalized:
        return None

    users = await User.filter(email__iexact=normalized).order_by("created_at", "id")
    if not users:
        return None

    primary = users[0]
    if len(users) == 1:
        if primary.email != normalized:
            primary.email = normalized
            await primary.save(update_fields=["email", "updated_at"])
        return primary

    await primary.fetch_related("identities", "oauth_tokens")
    primary_tokens_by_provider: dict[str, OAuthToken] = {t.provider: t for t in primary.oauth_tokens}

    for dupe in users[1:]:
        await dupe.fetch_related("identities", "oauth_tokens")

        for ident in dupe.identities:
            existing = await UserIdentity.get_or_none(provider=ident.provider, provider_subject=ident.provider_subject)
            if existing and existing.user_id != primary.id:
                await ident.delete()
                continue
            ident.user = primary
            await ident.save()

        for token in dupe.oauth_tokens:
            existing_token = primary_tokens_by_provider.get(token.provider)
            if not existing_token:
                token.user = primary
                await token.save()
                primary_tokens_by_provider[token.provider] = token
                continue

            should_replace = False
            if token.updated_at and existing_token.updated_at:
                should_replace = token.updated_at > existing_token.updated_at

            if should_replace:
                existing_token.access_token = token.access_token
                existing_token.refresh_token = token.refresh_token
                existing_token.app_refresh_token = token.app_refresh_token
                existing_token.scope = token.scope
                existing_token.expires_at = token.expires_at
                await existing_token.save()

            await token.delete()

        await dupe.delete()

    if primary.email != normalized:
        primary.email = normalized
        await primary.save(update_fields=["email", "updated_at"])

    return primary


async def _list_duplicate_emails() -> list[str]:
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(
        """
        SELECT lower(email) AS email
        FROM "user"
        WHERE email IS NOT NULL
        GROUP BY lower(email)
        HAVING count(*) > 1
        ORDER BY lower(email)
        """
    )
    return [r["email"] for r in rows if r.get("email")]


async def _ensure_email_unique_index() -> None:
    conn = Tortoise.get_connection("default")
    await conn.execute_query(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uid_user_email_lower
        ON "user" (lower(email))
        WHERE email IS NOT NULL
        """
    )


async def main() -> None:
    load_dotenv()
    await Tortoise.init(config=settings.TORTOISE_ORM)

    dupes = await _list_duplicate_emails()
    if dupes:
        for email in dupes:
            await _ensure_single_user_by_email(email)

    await _ensure_email_unique_index()
    await Tortoise.close_connections()


if __name__ == "__main__":
    run_async(main())

