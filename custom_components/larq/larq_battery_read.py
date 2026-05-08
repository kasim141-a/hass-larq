#!/usr/bin/env python3
"""Read LARQ bottle battery and print percentage to stdout. Run with bleak venv."""
import asyncio
from bleak import BleakClient, BleakScanner

BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

async def main():
    device = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "LARQ" in d.name, timeout=15
    )
    if not device:
        raise RuntimeError("LARQ device not found")
    async with BleakClient(device.address) as client:
        val = await client.read_gatt_char(BATTERY_UUID)
        print(val[0])

asyncio.run(main())
