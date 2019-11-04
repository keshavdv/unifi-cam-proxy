""""
Helper program to inject absolute wall clock time into FLV stream for recordings
"""

import time
import struct
import sys
from flvlib import astypes
from flvlib import tags
from flvlib import primitives


def read_bytes(source, num_bytes):
    read_bytes = 0
    buf = b""
    while read_bytes < num_bytes:
        d_in = source.read(num_bytes - read_bytes)
        if d_in:
            read_bytes += len(d_in)
            buf += d_in
        else:
            return buf
    return buf


def write(data):
    sys.stdout.write(data)


def main():
    PY3K = sys.version_info >= (3, 0)

    if PY3K:
        source = sys.stdin.buffer
    else:
        if sys.platform == "win32":
            import os, msvcrt

            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        source = sys.stdin

    header = read_bytes(source, 3)

    if header != "FLV":
        print("Not a valid FLV file")
        return
    write(header)

    # Skip rest of FLV header
    write(read_bytes(source, 6))

    i = 0
    while True:
        header = read_bytes(source, 15)
        if len(header) != 15:
            write(header)
            return

        # Packet structure from Wikipedia:
        #
        # Size of previous packet	uint32_be	0	For first packet set to NULL
        # Packet Type	uint8	18	For first packet set to AMF Metadata
        # Payload Size	uint24_be	varies	Size of packet data only
        # Timestamp Lower	uint24_be	0	For first packet set to NULL
        # Timestamp Upper	uint8	0	Extension to create a uint32_be value
        # Stream ID	uint24_be	0	For first stream of same type set to NULL
        # Payload Data	freeform	varies	Data as defined by packet type

        # Get payload size to know how many bytes to read
        high, low = struct.unpack(">BH", header[5:8])
        payload_size = (high << 16) + low

        # Get timestamp to inject into clock sync tag
        low_high = header[8:12]
        combined = low_high[3] + low_high[:3]
        timestamp = struct.unpack(">i", combined)[0]

        if i % 3:
            data = astypes.FLVObject()
            data["streamClock"] = int(timestamp)
            data["streamClockBase"] = 0
            data["wallClock"] = time.time() * 1000

            # Inject clock sync packet
            write(primitives.make_ui32(payload_size + 15))
            write(tags.create_script_tag("onClockSync", data, timestamp))

            # Write rest of original packet minus previous packet size
            write(header[4:])
            write(read_bytes(source, payload_size))
        else:
            # Write normal packet
            write(header)
            write(read_bytes(source, payload_size))

        i += 1


if __name__ == "__main__":
    main()
