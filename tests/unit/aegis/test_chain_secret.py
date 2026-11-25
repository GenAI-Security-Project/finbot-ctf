"""The audit chain must not sign records with a secret that ships in the code."""

import pytest

from finbot.aegis.telemetry.chain import AuditChain
from finbot.config import Settings, settings


@pytest.mark.unit
def test_no_chain_secret_is_built_in():
    assert Settings.model_fields["AEGIS_CHAIN_SECRET"].default == ""


@pytest.mark.unit
def test_chain_refuses_to_start_without_a_secret(monkeypatch):
    monkeypatch.setattr(settings, "AEGIS_CHAIN_SECRET", "")

    with pytest.raises(RuntimeError, match="AEGIS_CHAIN_SECRET"):
        AuditChain()
