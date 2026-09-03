from repositories import get_users_repository
from sheets.schemas import User

from ._common import make_list_router

router = make_list_router(
    prefix="/api/users", tags=["users"], model=User, get_repository=get_users_repository
)
