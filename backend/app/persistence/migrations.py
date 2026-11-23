from app.persistence.database import Database, create_database


SCHEMA_VERSION = "1.3"


def initialize_database(database_url: str) -> Database:
    """Create the fixed V1.3 schema if it does not exist and return the handle."""
    database = create_database(database_url)
    database.create_schema()
    return database
