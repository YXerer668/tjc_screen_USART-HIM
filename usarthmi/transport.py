from __future__ import annotations

import time
from dataclasses import dataclass

import serial

TERMINATOR = b"\xff\xff\xff"


class SerialTransportError(RuntimeError):
    """Raised when a serial transaction cannot be completed."""


@dataclass(slots=True)
class SerialConfig:
    port: str
    baud: int = 9600
    timeout_ms: int = 800
    verbose: bool = False

    @property
    def timeout_s(self) -> float:
        return max(self.timeout_ms, 1) / 1000.0


class SerialTransport:
    """Small wrapper around pyserial for one-shot command transactions."""

    def __init__(self, config: SerialConfig):
        self.config = config

    def _debug(self, message: str) -> None:
        if self.config.verbose:
            print(f"[transport] {message}")

    def transact(self, command: str) -> tuple[bytes, bytes]:
        payload = self.encode_command(command)
        self._debug(
            f"open {self.config.port} @ {self.config.baud}, send {payload.hex(' ')}"
        )
        try:
            with serial.Serial(
                self.config.port,
                self.config.baud,
                timeout=self.config.timeout_s,
                write_timeout=self.config.timeout_s,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            ) as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(payload)
                ser.flush()
                response = self._read_response(ser)
        except serial.SerialException as exc:
            raise SerialTransportError(str(exc)) from exc
        self._debug(f"recv {response.hex(' ')}")
        return payload, response

    @staticmethod
    def encode_command(command: str) -> bytes:
        return command.encode("ascii") + TERMINATOR

    def _read_response(self, ser: serial.Serial) -> bytes:
        deadline = time.monotonic() + self.config.timeout_s
        data = bytearray()
        saw_data = False

        while time.monotonic() < deadline:
            waiting = ser.in_waiting
            chunk = ser.read(waiting or 1)
            if chunk:
                data.extend(chunk)
                saw_data = True
                if data.endswith(TERMINATOR):
                    break
            elif saw_data:
                break

        return bytes(data)

