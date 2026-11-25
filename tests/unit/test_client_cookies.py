"""The shared test client must send only the session a request asks for."""

import pytest

URL = "/vendor/api/v1/invoices"


@pytest.mark.unit
def test_explicit_cookie_replaces_the_one_set_by_an_earlier_response(
    fast_client, vendor_pair_setup
):
    first, second = vendor_pair_setup["s1"], vendor_pair_setup["s2"]

    fast_client.get(URL, cookies={"finbot_session": first.session_id})
    response = fast_client.get(URL, cookies={"finbot_session": second.session_id})

    sent = response.request.headers["cookie"]
    assert sent.count("finbot_session=") == 1
    assert second.session_id in sent
