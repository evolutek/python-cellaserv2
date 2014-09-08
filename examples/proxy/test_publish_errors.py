#!/usr/bin/env python3
import pytest


def test_proxy_bad_publish(capsys):
    from cellaserv.proxy import CellaservProxy
    cs = CellaservProxy()

    # Event no data
    cs('event')
    out, err = capsys.readouterr()
    assert not err
    assert not out

    # Event kw data
    cs('event', a=0)
    out, err = capsys.readouterr()
    assert not err
    assert not out

    # Rational for raise: this have no meaning
    with pytest.raises(TypeError):
        cs()

    # Rational for raise: arg must by passed as kw
    with pytest.raises(TypeError):
        cs('event', 0)

    # Cannot encode, do not raise, print traceback
    # Rational for soft-fail: the user can trigger more easily than the other
    # errors
    cs('event', a=b'42')
    out, err = capsys.readouterr()
    assert err
    assert not out
