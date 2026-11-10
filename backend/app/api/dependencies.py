from typing import Annotated
from uuid import UUID

from fastapi import Depends
from psycopg import Connection
from psycopg.rows import DictRow

from app.core.database import get_database
from app.core.security import verify_user

# Commit or roll back before the HTTP response leaves the app.
Database = Annotated[Connection[DictRow], Depends(get_database, scope="function")]
CurrentUser = Annotated[UUID, Depends(verify_user)]
