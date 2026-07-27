import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


class MpvError(Exception):
    pass


def _connect_unix_socket(socket_path: Path, timeout: float) -> socket.socket:
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect(str(socket_path))
            return sock
        except OSError as e:
            last_error = e
            time.sleep(0.05)
    raise MpvError(f"could not connect to mpv IPC socket: {last_error}")


class WindowsNamedPipeTransport:
    """Wraps a Windows named pipe handle with a socket-like sendall/recv/close interface."""

    def __init__(self, handle):
        self._handle = handle

    @classmethod
    def connect(cls, pipe_name: str, timeout: float = 5.0) -> "WindowsNamedPipeTransport":
        import pywintypes
        import win32file
        import win32pipe

        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                handle = win32file.CreateFile(
                    pipe_name,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )
                win32pipe.SetNamedPipeHandleState(
                    handle, win32pipe.PIPE_READMODE_BYTE, None, None
                )
                return cls(handle)
            except pywintypes.error as e:
                last_error = e
                time.sleep(0.05)
        raise MpvError(f"could not connect to mpv named pipe: {last_error}")

    def sendall(self, data: bytes) -> None:
        import win32file

        win32file.WriteFile(self._handle, data)

    def recv(self, n: int) -> bytes:
        import win32file

        _, data = win32file.ReadFile(self._handle, n)
        return data

    def close(self) -> None:
        import win32file

        win32file.CloseHandle(self._handle)


class IpcConnection:
    """Synchronous newline-delimited JSON connection to an mpv IPC endpoint.

    `transport` is anything exposing sendall(bytes)/recv(int)->bytes/close() —
    a plain socket.socket on POSIX, a WindowsNamedPipeTransport on Windows.
    """

    def __init__(self, transport):
        self._transport = transport
        self._buffer = b""
        self._next_id = 1

    def close(self) -> None:
        self._transport.close()

    def send_command(self, command: list):
        request_id = self._next_id
        self._next_id += 1
        payload = json.dumps({"command": command, "request_id": request_id}) + "\n"
        self._transport.sendall(payload.encode("utf-8"))
        return self._await_response(request_id)

    def _await_response(self, request_id: int):
        while True:
            message = json.loads(self._read_line())
            if message.get("request_id") != request_id:
                continue  # an event notification, not the response we're waiting for
            if message.get("error") != "success":
                raise MpvError(f"mpv command failed: {message.get('error')}")
            return message.get("data")

    def _read_line(self) -> bytes:
        while b"\n" not in self._buffer:
            try:
                chunk = self._transport.recv(4096)
            except socket.timeout as e:
                raise MpvError("timed out waiting for mpv IPC response") from e
            if not chunk:
                raise MpvError("mpv IPC connection closed")
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(b"\n")
        return line

    def get_property(self, name: str):
        try:
            return self.send_command(["get_property", name])
        except MpvError as e:
            if "property unavailable" in str(e) or "property not found" in str(e):
                return None
            raise

    def loadfile(self, path: str, start: float | None = None) -> None:
        if start is not None:
            # loadfile's signature is <url> [<flags> [<index> [<options>]]] (index
            # added in mpv 0.38.0); index is ignored for the "replace" flag but the
            # slot must still be present to reach the options argument.
            self.send_command(["loadfile", path, "replace", -1, f"start={start}"])
        else:
            self.send_command(["loadfile", path, "replace"])

    def seek(self, seconds: float, mode: str = "absolute") -> None:
        self.send_command(["seek", seconds, mode])


class Controller:
    """Owns a single mpv subprocess for the lifetime of a pd session."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._tmp_dir: Path | None = None
        self._conn: IpcConnection | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def connection(self) -> IpcConnection | None:
        return self._conn if self.is_running else None

    def ensure_running(self, timeout: float = 5.0) -> IpcConnection:
        if self.is_running and self._conn is not None:
            return self._conn

        self.close()

        if sys.platform == "win32":
            ipc_endpoint = rf"\\.\pipe\pd-mpv-{uuid.uuid4().hex}"
        else:
            self._tmp_dir = Path(tempfile.mkdtemp(prefix="pd-mpv-"))
            ipc_endpoint = str(self._tmp_dir / "mpv.sock")

        self._process = subprocess.Popen(
            [
                "mpv",
                "--idle=yes",
                f"--input-ipc-server={ipc_endpoint}",
                "--force-window=yes",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if sys.platform == "win32":
            transport = WindowsNamedPipeTransport.connect(ipc_endpoint, timeout=timeout)
        else:
            socket_path = Path(ipc_endpoint)
            deadline = time.monotonic() + timeout
            while not socket_path.exists():
                if self._process.poll() is not None:
                    raise MpvError("mpv exited before creating its IPC socket")
                if time.monotonic() > deadline:
                    raise MpvError("timed out waiting for mpv IPC socket")
                time.sleep(0.05)
            transport = _connect_unix_socket(socket_path, timeout=timeout)

        self._conn = IpcConnection(transport)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        if self._tmp_dir is not None:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None
