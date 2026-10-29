from app.modules.analytics.free_usage import allocation


def test_equal_share_and_personal_percentage():
    result = allocation(4000, 50, 20)
    assert result['allocated_tokens'] == 80
    assert result['remaining_tokens'] == 60
    assert result['used_percent'] == 25


def test_exhausted_and_tiny_pool():
    assert allocation(4000, 50, 90)['used_percent'] == 100
    assert allocation(4000, 50, 90)['remaining_tokens'] == 0
    assert allocation(1, 50, 0)['allocated_tokens'] == 0
    assert allocation(0, 0, 0)['configured'] is False


def test_multiple_users_change_share_without_resetting_consumption():
    assert allocation(4000, 25, 20)['used_percent'] == 12.5
    assert allocation(4000, 50, 20)['used_percent'] == 25
