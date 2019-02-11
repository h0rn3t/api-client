import logging
from unittest.mock import Mock, patch, sentinel

import pytest

from api_client.authentication_methods import NoAuthentication
from api_client.client import BaseClient, LOG as client_logger
from api_client.exceptions import (
    ClientBadRequestError, ClientRedirectionError, ClientServerError, ClientUnexpectedError,
)
from api_client.request_formatters import BaseRequestFormatter, JsonRequestFormatter
from api_client.response_handlers import BaseResponseHandler, JsonResponseHandler


# Minimal client - no implementation
class Client(BaseClient):
    pass


# Real world api client with GET methods implemented.
class JSONPlaceholderClient(BaseClient):
    base_url = "https://jsonplaceholder.typicode.com"

    def get_all_todos(self) -> dict:
        url = f"{self.base_url}/todos"
        return self.read(url)

    def get_todo(self, todo_id: int) -> dict:
        url = f"{self.base_url}/todos/{todo_id}"
        return self.read(url)


mock_response_handler_call = Mock()
mock_request_formatter_call = Mock()


class MockResponseHandler(BaseResponseHandler):
    """Mock class for testing."""

    @staticmethod
    def get_request_data(response):
        mock_response_handler_call(response)
        return response


class MockRequestFormatter(BaseRequestFormatter):
    """Mock class for testing."""

    @classmethod
    def format(cls, data: dict):
        mock_request_formatter_call(data)
        return data


client = Client(
    authentication_method=NoAuthentication(),
    response_handler=MockResponseHandler,
    request_formatter=MockRequestFormatter,
)


def test_client_initialization_with_invalid_authentication_method():
    with pytest.raises(RuntimeError) as exc_info:
        Client(
            authentication_method=None,
            response_handler=MockResponseHandler,
            request_formatter=MockRequestFormatter,
        )
    assert str(exc_info.value) == "provided authentication_method must be an instance of BaseAuthenticationMethod."


def test_client_initialization_with_invalid_response_handler():
    with pytest.raises(RuntimeError) as exc_info:
        Client(
            authentication_method=NoAuthentication(),
            response_handler=None,
            request_formatter=MockRequestFormatter,
        )
    assert str(exc_info.value) == "provided response_handler must be a subclass of BaseResponseHandler."


def test_client_initialization_with_invalid_requests_handler():
    with pytest.raises(RuntimeError) as exc_info:
        Client(
            authentication_method=NoAuthentication(),
            response_handler=MockResponseHandler,
            request_formatter=None,
        )
    assert str(exc_info.value) == "provided request_formatter must be a subclass of BaseRequestFormatter."


def test_set_and_get_default_headers():
    client = Client(
        authentication_method=NoAuthentication(),
        response_handler=MockResponseHandler,
        request_formatter=MockRequestFormatter,
    )
    assert client.get_default_headers() == {}
    client.set_default_headers({"first": "header"})
    assert client.get_default_headers() == {"first": "header"}
    # Setting the default headers should overwrite the original
    client.set_default_headers({"second": "header"})
    assert client.get_default_headers() == {"second": "header"}


def test_set_and_get_default_query_params():
    client = Client(
        authentication_method=NoAuthentication(),
        response_handler=MockResponseHandler,
        request_formatter=MockRequestFormatter,
    )
    assert client.get_default_query_params() == {}
    client.set_default_query_params({"first": "header"})
    assert client.get_default_query_params() == {"first": "header"}
    # Setting the default query params should overwrite the original
    client.set_default_query_params({"second": "header"})
    assert client.get_default_query_params() == {"second": "header"}


def test_set_and_get_default_username_password_authentication():
    client = Client(
        authentication_method=NoAuthentication(),
        response_handler=MockResponseHandler,
        request_formatter=MockRequestFormatter,
    )
    assert client.get_default_username_password_authentication() == None
    client.set_default_username_password_authentication(("username", "password"))
    assert client.get_default_username_password_authentication() == ("username", "password")
    # Setting the default username password should overwrite the original
    client.set_default_username_password_authentication(("username", "morecomplicatedpassword"))
    assert client.get_default_username_password_authentication() == ("username", "morecomplicatedpassword")


@patch("api_client.client.requests")
def test_create_method_success(mock_requests):
    mock_requests.post.return_value.status_code = 201
    client.create(sentinel.url, data={"foo": "bar"})
    mock_requests.post.assert_called_once_with(
        sentinel.url, auth=None, headers={}, data={'foo': 'bar'}, params={}
    )


@patch("api_client.client.requests")
def test_read_method_success(mock_requests):
    mock_requests.get.return_value.status_code = 200
    client.read(sentinel.url)
    mock_requests.get.assert_called_once_with(
        sentinel.url, auth=None, headers={}, params={}, data=None
    )


@patch("api_client.client.requests")
def test_replace_method_success(mock_requests):
    mock_requests.put.return_value.status_code = 200
    client.replace(sentinel.url, data={"foo": "bar"})
    mock_requests.put.assert_called_once_with(
        sentinel.url, auth=None, headers={}, data={'foo': 'bar'}, params={}
    )


@patch("api_client.client.requests")
def test_update_method_success(mock_requests):
    mock_requests.patch.return_value.status_code = 200
    client.update(sentinel.url, data={"foo": "bar"})
    mock_requests.patch.assert_called_once_with(
        sentinel.url, auth=None, headers={}, data={'foo': 'bar'}, params={}
    )


@patch("api_client.client.requests")
def test_delete_method_success(mock_requests):
    mock_requests.delete.return_value.status_code = 200
    client.delete(sentinel.url)
    mock_requests.delete.assert_called_once_with(
        sentinel.url, auth=None, headers={}, params={}, data=None
    )


@pytest.mark.parametrize("client_method,client_args,patch_methodname",[
    (client.create, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.post"),
    (client.read, (sentinel.url,), "api_client.client.requests.get"),
    (client.replace, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.put"),
    (client.update, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.patch"),
    (client.delete, (sentinel.url,), "api_client.client.requests.delete"),
])
def test_make_request_error_raises_and_logs_unexpected_error(client_method, client_args, patch_methodname, caplog):
    caplog.set_level(level=logging.ERROR, logger=client_logger.name)
    with patch(patch_methodname) as mock_requests_method:
        mock_requests_method.side_effect = (ValueError("Error raised for testing"),)
        with pytest.raises(ClientUnexpectedError) as exc_info:
            client_method(*client_args)
    assert str(exc_info.value) == "Error when contacting 'sentinel.url'"
    assert "An error occurred when contacting sentinel.url" in caplog.messages


@pytest.mark.parametrize("client_method,client_args,patch_methodname",[
    (client.create, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.post"),
    (client.read, (sentinel.url,), "api_client.client.requests.get"),
    (client.replace, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.put"),
    (client.update, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.patch"),
    (client.delete, (sentinel.url,), "api_client.client.requests.delete"),
])
def test_server_error_raises_and_logs_client_server_error(client_method, client_args, patch_methodname, caplog):
    caplog.set_level(level=logging.WARNING, logger=client_logger.name)
    with patch(patch_methodname) as mock_requests_method:
        mock_requests_method.return_value.status_code = 500
        mock_requests_method.return_value.url = sentinel.url
        mock_requests_method.return_value.reason = "A TEST server error occurred"

        with pytest.raises(ClientServerError) as exc_info:
            client_method(*client_args)
    assert str(exc_info.value) == "500 Error: A TEST server error occurred for url: sentinel.url"
    assert "500 Error: A TEST server error occurred for url: sentinel.url" in caplog.messages


@pytest.mark.parametrize("client_method,client_args,patch_methodname",[
    (client.create, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.post"),
    (client.read, (sentinel.url,), "api_client.client.requests.get"),
    (client.replace, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.put"),
    (client.update, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.patch"),
    (client.delete, (sentinel.url,), "api_client.client.requests.delete"),
])
def test_not_modified_response_raises_and_logs_client_redirection_error(client_method, client_args, patch_methodname, caplog):
    caplog.set_level(level=logging.ERROR, logger=client_logger.name)
    with patch(patch_methodname) as mock_requests_method:
        mock_requests_method.return_value.status_code = 304
        mock_requests_method.return_value.url = sentinel.url
        mock_requests_method.return_value.reason = "A TEST redirection error occurred"

        with pytest.raises(ClientRedirectionError) as exc_info:
            client_method(*client_args)
    assert str(exc_info.value) == "304 Error: A TEST redirection error occurred for url: sentinel.url"
    assert "304 Error: A TEST redirection error occurred for url: sentinel.url" in caplog.messages

@pytest.mark.parametrize("client_method,client_args,patch_methodname",[
    (client.create, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.post"),
    (client.read, (sentinel.url,), "api_client.client.requests.get"),
    (client.replace, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.put"),
    (client.update, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.patch"),
    (client.delete, (sentinel.url,), "api_client.client.requests.delete"),
])
def test_not_found_response_raises_and_logs_client_bad_request_error(client_method, client_args, patch_methodname, caplog):
    caplog.set_level(level=logging.ERROR, logger=client_logger.name)
    with patch(patch_methodname) as mock_requests_method:
        mock_requests_method.return_value.status_code = 404
        mock_requests_method.return_value.url = sentinel.url
        mock_requests_method.return_value.reason = "A TEST not found error occurred"

        with pytest.raises(ClientBadRequestError) as exc_info:
            client_method(*client_args)
    assert str(exc_info.value) == "404 Error: A TEST not found error occurred for url: sentinel.url"
    assert "404 Error: A TEST not found error occurred for url: sentinel.url" in caplog.messages


@pytest.mark.parametrize("client_method,client_args,patch_methodname",[
    (client.create, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.post"),
    (client.read, (sentinel.url,), "api_client.client.requests.get"),
    (client.replace, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.put"),
    (client.update, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.patch"),
    (client.delete, (sentinel.url,), "api_client.client.requests.delete"),
])
def test_unexpected_status_code_response_raises_and_logs_unexpected_error(client_method, client_args, patch_methodname, caplog):
    caplog.set_level(level=logging.ERROR, logger=client_logger.name)
    with patch(patch_methodname) as mock_requests_method:
        mock_requests_method.return_value.status_code = 100
        mock_requests_method.return_value.url = sentinel.url
        mock_requests_method.return_value.reason = "A TEST bad status code error occurred"

        with pytest.raises(ClientUnexpectedError) as exc_info:
            client_method(*client_args)
    assert str(exc_info.value) == "100 Error: A TEST bad status code error occurred for url: sentinel.url"
    assert "100 Error: A TEST bad status code error occurred for url: sentinel.url" in caplog.messages


@pytest.mark.parametrize("client_method,client_args,patch_methodname",[
    (client.read, (sentinel.url,), "api_client.client.requests.get"),
    (client.replace, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.put"),
    (client.update, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.patch"),
    (client.delete, (sentinel.url,), "api_client.client.requests.delete"),
])
def test_query_params_are_updated_and_not_overwritten(client_method, client_args, patch_methodname):
    # Params are not expected on POST endpoints, so this method is not placed under test.
    with patch(patch_methodname) as mock_requests_method:
        mock_requests_method.return_value.status_code = 200

        client_method(*client_args, params={"New": "Header"})

    assert mock_requests_method.call_count == 1
    args, kwargs = mock_requests_method.call_args
    assert "params" in kwargs
    assert kwargs["params"]["New"] == "Header"


@pytest.mark.parametrize("client_method,client_args,patch_methodname", [
    (client.create, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.post"),
    (client.read, (sentinel.url,), "api_client.client.requests.get"),
    (client.replace, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.put"),
    (client.update, (sentinel.url, {"foo": "bar"}), "api_client.client.requests.patch"),
    (client.delete, (sentinel.url,), "api_client.client.requests.delete"),
])
def test_delegates_to_response_handler(client_method, client_args, patch_methodname):
    mock_response_handler_call.reset_mock()

    with patch(patch_methodname) as mock_requests_method:
        requests_response = Mock(status_code=200)
        mock_requests_method.return_value = requests_response

        client_method(*client_args)

    mock_response_handler_call.assert_called_once_with(requests_response)


@pytest.mark.parametrize("client_method,url,patch_methodname", [
    (client.create, sentinel.url, "api_client.client.requests.post"),
    (client.replace, sentinel.url, "api_client.client.requests.put"),
    (client.update, sentinel.url, "api_client.client.requests.patch"),
])
def test_data_parsing_delegates_to_request_formatter(client_method, url, patch_methodname):
    # GET and DELETE requests dont pass data so they are not being tested
    mock_request_formatter_call.reset_mock()

    with patch(patch_methodname) as mock_requests_method:
        requests_response = Mock(status_code=200)
        mock_requests_method.return_value = requests_response

        client_method(url, sentinel.data)

    mock_request_formatter_call.assert_called_once_with(sentinel.data)


def test_read_real_world_api(json_placeholder_cassette):
    client = JSONPlaceholderClient(
        authentication_method=NoAuthentication(),
        response_handler=JsonResponseHandler,
        request_formatter=JsonRequestFormatter,
    )
    assert len(client.get_all_todos()) == 200

    expected_todo = {
        'completed': False,
        'id': 45,
        'title': 'velit soluta adipisci molestias reiciendis harum',
        'userId': 3,
    }
    assert client.get_todo(45) == expected_todo