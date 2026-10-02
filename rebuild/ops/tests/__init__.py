"""Offline tests of the provider campaign machinery and the Sonnet 5 QA runner (ops/provider_campaign.py,
ops/sonnet5_qa.py). No provider is ever reached: every provider interaction goes through an in-process fake transport,
and `network_guard` refuses every socket except the synthetic QA database on 127.0.0.1:55731."""
