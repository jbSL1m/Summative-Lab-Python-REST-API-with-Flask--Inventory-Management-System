from unittest.mock import Mock

import cli


def test_cli_add_sends_inventory_request(monkeypatch, capsys):
    response = Mock(ok=True, status_code=201)
    response.json.return_value = {"id": 3, "product_name": "Green Tea"}
    request_mock = Mock(return_value=response)
    monkeypatch.setattr(cli.requests, "request", request_mock)

    exit_code = cli.main(["add", "Green Tea", "--price", "2.5", "--stock", "7"])

    assert exit_code == 0
    assert "Green Tea" in capsys.readouterr().out
    assert request_mock.call_args.args[:2] == (
        "POST",
        "http://127.0.0.1:5000/inventory",
    )
    assert request_mock.call_args.kwargs["json"]["stock"] == 7


def test_cli_update_requires_a_change(capsys):
    exit_code = cli.main(["update", "1"])
    assert exit_code == 1
    assert "Provide" in capsys.readouterr().err


def test_cli_reports_api_connection_error(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.requests,
        "request",
        Mock(side_effect=cli.requests.RequestException("offline")),
    )
    exit_code = cli.main(["list"])
    assert exit_code == 1
    assert "Could not connect" in capsys.readouterr().err