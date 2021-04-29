""""
Helper program to inject absolute wall clock time into FLV stream for recordings
"""

import struct
import sys
import time


def make_ui8(num):
    return struct.pack("B", num)


def make_ui32(num):
    return struct.pack(">I", num)


def make_si32_extended(num):
    ret = struct.pack(">i", num)
    return ret[1:] + bytes([ret[0]])


def make_ui24(num):
    ret = struct.pack(">I", num)
    return ret[1:]


def make_ui16(num):
    return struct.pack(">H", num)


def create_script_tag(name, data, timestamp=0):
    payload = make_ui8(2)  # VALUE_TYPE_STRING

    payload += make_string(name)
    payload += make_ui8(3)  # VALUE_TYPE_OBJECT

    for k, v in data.items():
        payload += make_string(k)
        payload += make_ui8(0)  # VALUE_TYPE_NUMBER
        payload += make_number(v)
    payload += make_ui24(9)  # End of object

    tag_type = make_ui8(18)  # 18 = TAG_TYPE_SCRIPT
    timestamp = make_si32_extended(timestamp)
    stream_id = make_ui24(0)

    data_size = len(payload)
    tag_size = data_size + 11

    return b"".join(
        [
            tag_type,
            make_ui24(data_size),
            timestamp,
            stream_id,
            payload,
            make_ui32(tag_size),
        ]
    )


def make_string(string):
    s = string.encode("UTF-8")
    length = make_ui16(len(s))
    return length + string.encode("UTF-8")


def make_number(num):
    return struct.pack(">d", num)


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
    sys.stdout.buffer.write(data)


def main():
    if sys.platform == "win32":
        import msvcrt
        import os

        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
    source = sys.stdin.buffer

    header = read_bytes(source, 3)

    if header != b"FLV":
        print("Not a valid FLV file")
        return
    write(header)

    # Skip rest of FLV header
    write(read_bytes(source, 6))

    i = 0
    while True:

        # Packet structure from Wikipedia:
        #
        # Size of previous packet	uint32_be	0	For first packet set to NULL
        # Packet Type	uint8	18	For first packet set to AMF Metadata
        # Payload Size	uint24_be	varies	Size of packet data only
        # Timestamp Lower	uint24_be	0	For first packet set to NULL
        # Timestamp Upper	uint8	0	Extension to create a uint32_be value
        # Stream ID	uint24_be	0	For first stream of same type set to NULL
        #
        # Payload Data	freeform	varies	Data as defined by packet type

        header = read_bytes(source, 15)
        if len(header) != 15:
            write(header)
            return

        # Get payload size to know how many bytes to read
        high, low = struct.unpack(">BH", header[5:8])
        payload_size = (high << 16) + low

        # Get timestamp to inject into clock sync tag
        low_high = header[8:12]
        combined = bytes([low_high[3]]) + low_high[:3]
        timestamp = struct.unpack(">i", combined)[0]

        if i % 3:
            # Insert a custom packet every so often for time synchronization

            # Reference based on flvlib:
            #   data = flv.libastypes.FLVObject()
            #   data["streamClock"] = int(timestamp)
            #   data["streamClockBase"] = 0
            #   data["wallClock"] = time.time() * 1000
            #   packet_to_inject = flvlib.tags.create_script_tag(
            #       "onClockSync", data, timestamp))

            data = {
                "streamClock": int(timestamp),
                "streamClockBase": 0,
                "wallClock": time.time() * 1000,
            }
            write(make_ui32(payload_size + 15))  # Write previous packet size
            write(create_script_tag("onClockSync", data, timestamp))

            # Write rest of original packet minus previous packet size
            write(header[4:])
            write(read_bytes(source, payload_size))
        else:
            # Write the original packet
            write(header)
            write(read_bytes(source, payload_size))

        i += 1


if __name__ == "__main__":
    main()
