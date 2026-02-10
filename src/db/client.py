from supabase import create_client, Client
from src.config.settings import settings

_client: Client | None = None


def get_supabase_client() -> Client:
    """Get or create the Supabase client singleton using service_role key.

    Service role key bypasses RLS. App-level user_id filtering
    is the primary access control guard.
    """
    global _client
    if _client is None:
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _client
