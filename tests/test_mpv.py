import json
import socket
import threading

import pytest

from pd.mpv import IpcConnection, MpvError


def make_pair() -> tuple[socket.socket, socket.socket]:
    return socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)


def read_request(peer_sock: socket.socket) -> dict:
    buf = b""
    while b"\n" not in buf:
        buf += peer_sock.recv(4096)
    line, _, _ = buf.partition(b"\n")
    return json.loads(line)


def run_fake_server(peer_sock: socket.socket, respond) -> threading.Thread:
    def server() -> None:
        request = read_request(peer_sock)
        for reply in respond(request):
            peer_sock.sendall((json.dumps(reply) + "\n").encode("utf-8"))

    thread = threading.Thread(target=server)
    thread.start()
    return thread


def test_send_command_round_trip():
    client_sock, server_sock = make_pair()
    conn = IpcConnection(client_sock)

    thread = run_fake_server(
        server_sock,
        lambda req: [{"error": "success", "data": 42, "request_id": req["request_id"]}],
    )
    result = conn.send_command(["get_property", "time-pos"])
    thread.join()

    assert result == 42
    conn.close()
    server_sock.close()


def test_send_command_error_raises():
    client_sock, server_sock = make_pair()
    conn = IpcConnection(client_sock)

    thread = run_fake_server(
        server_sock,
        lambda req: [{"error": "property unavailable", "request_id": req["request_id"]}],
    )
    with pytest.raises(MpvError):
        conn.send_command(["get_property", "time-pos"])
    thread.join()

    conn.close()
    server_sock.close()


def test_get_property_returns_none_when_unavailable():
    client_sock, server_sock = make_pair()
    conn = IpcConnection(client_sock)

    thread = run_fake_server(
        server_sock,
        lambda req: [{"error": "property unavailable", "request_id": req["request_id"]}],
    )
    assert conn.get_property("path") is None
    thread.join()

    conn.close()
    server_sock.close()


def test_ignores_unrelated_events_before_response():
    client_sock, server_sock = make_pair()
    conn = IpcConnection(client_sock)

    def respond(req):
        yield {"event": "property-change", "id": 1}
        yield {"error": "success", "data": "abc", "request_id": req["request_id"]}

    thread = run_fake_server(server_sock, respond)
    result = conn.send_command(["get_property", "path"])
    thread.join()

    assert result == "abc"
    conn.close()
    server_sock.close()


def test_loadfile_sends_start_option():
    client_sock, server_sock = make_pair()
    conn = IpcConnection(client_sock)

    received = {}

    def server() -> None:
        received["request"] = read_request(server_sock)
        reply = {"error": "success", "data": None, "request_id": received["request"]["request_id"]}
        server_sock.sendall((json.dumps(reply) + "\n").encode("utf-8"))

    thread = threading.Thread(target=server)
    thread.start()
    conn.loadfile("/videos/a.mp4", start=12.5)
    thread.join()

    assert received["request"]["command"] == [
        "loadfile",
        "/videos/a.mp4",
        "replace",
        -1,
        "start=12.5",
    ]
    conn.close()
    server_sock.close()
