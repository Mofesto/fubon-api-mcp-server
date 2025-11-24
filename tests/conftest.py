from types import SimpleNamespace

import pytest


@pytest.fixture
def sample_accounts():
    """Provide sample accounts for tests.

    This keeps sample/test-only data out of production config.
    """
    return [
        {
            "account": "C04",
            "name": "Sample C04",
            "branch_no": "99999",
            "account_type": "stock",
        }
    ]


@pytest.fixture
def sample_account_objs(sample_accounts):
    # Return simple objects resembling SDK account objects
    return [SimpleNamespace(**a) for a in sample_accounts]
