from app.config import get_settings
from app.persistence.migrations import SCHEMA_VERSION, initialize_database


def main() -> None:
    settings = get_settings()
    database = initialize_database(settings.database_url)
    database.engine.dispose()
    print(f"Initialized Game Gene Agent schema {SCHEMA_VERSION}.")


if __name__ == "__main__":
    main()
