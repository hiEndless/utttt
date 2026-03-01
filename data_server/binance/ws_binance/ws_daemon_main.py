from __future__ import annotations

import asyncio
import signal

from data_server.binance.ws_binance.ws_supervisor import BinanceWSSupervisor


async def _run() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _on_sig(*_) -> None:
        stop.set()

    try:
        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    except Exception:
        pass

    sup = BinanceWSSupervisor()
    await sup.bootstrap()
    try:
        await stop.wait()
    finally:
        await sup.shutdown()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

