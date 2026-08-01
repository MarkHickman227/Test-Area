from app.core.config import Settings


def test_supabase_health_rejects_mismatched_service_role_key():
    settings = Settings(
        SUPABASE_URL="https://newproject.supabase.co",
        SUPABASE_SERVICE_KEY=(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9sZHByb2plY3QiLCJyb2xlIjoic2VydmljZV9yb2xlIn0."
            "signature"
        ),
        ANTHROPIC_API_KEY="replace-with-anthropic-api-key",
        PERPLEXITY_API_KEY="replace-with-perplexity-api-key",
    )

    assert settings.supabase_configured is False


def test_supabase_health_accepts_matching_service_role_key():
    settings = Settings(
        SUPABASE_URL="https://newproject.supabase.co",
        SUPABASE_SERVICE_KEY=(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5ld3Byb2plY3QiLCJyb2xlIjoic2VydmljZV9yb2xlIn0."
            "signature"
        ),
        ANTHROPIC_API_KEY="replace-with-anthropic-api-key",
        PERPLEXITY_API_KEY="replace-with-perplexity-api-key",
    )

    assert settings.supabase_configured is True


def test_database_url_is_detected():
    settings = Settings(
        SUPABASE_URL="https://newproject.supabase.co",
        SUPABASE_SERVICE_KEY="replace-with-service-role-key",
        DATABASE_URL="postgresql://postgres.example:secret@pooler.supabase.com:6543/postgres",
        ANTHROPIC_API_KEY="replace-with-anthropic-api-key",
        PERPLEXITY_API_KEY="replace-with-perplexity-api-key",
    )

    assert settings.database_configured is True


def test_placeholder_database_url_is_not_configured():
    settings = Settings(
        DATABASE_URL=(
            "postgresql://postgres.project-ref:replace-with-db-password@"
            "aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"
        ),
    )

    assert settings.database_configured is False
