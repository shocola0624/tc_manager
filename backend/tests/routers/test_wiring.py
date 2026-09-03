from routers.activities import router as activities_router
from routers.assignments import router as assignments_router
from routers.attendance import router as attendance_router
from routers.items import router as items_router
from routers.users import router as users_router


def test_router_prefixes_match_api_layout():
    assert users_router.prefix == "/api/users"
    assert items_router.prefix == "/api/items"
    assert activities_router.prefix == "/api/activities"
    assert attendance_router.prefix == "/api/attendance"
    assert assignments_router.prefix == "/api/assignments"
