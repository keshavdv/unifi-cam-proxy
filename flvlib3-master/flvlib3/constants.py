"""
The constants used in FLV files and their meanings.
"""

# Tag type
(
    TAG_TYPE_AUDIO,
    TAG_TYPE_VIDEO,
    TAG_TYPE_SCRIPT_AMF3,
    TAG_TYPE_SCRIPT
) = (8, 9, 15, 18)

# Sound format
(
    SOUND_FORMAT_PCM_PLATFORM_ENDIAN,
    SOUND_FORMAT_ADPCM,
    SOUND_FORMAT_MP3,
    SOUND_FORMAT_PCM_LITTLE_ENDIAN,
    SOUND_FORMAT_NELLYMOSER_16KHZ,
    SOUND_FORMAT_NELLYMOSER_8KHZ,
    SOUND_FORMAT_NELLYMOSER,
    SOUND_FORMAT_G711_A_LAW,
    SOUND_FORMAT_G711_MU_LAW
) = range(9)

(
    SOUND_FORMAT_AAC,
    SOUND_FORMAT_SPEEX
) = range(10, 12)

(
    SOUND_FORMAT_MP3_8KHZ,
    SOUND_FORMAT_DEVICE_SPECIFIC
) = range(14, 16)

sound_format_to_string = {
    SOUND_FORMAT_PCM_PLATFORM_ENDIAN: 'Linear PCM, platform endian',
    SOUND_FORMAT_ADPCM: 'ADPCM',
    SOUND_FORMAT_MP3: 'MP3',
    SOUND_FORMAT_PCM_LITTLE_ENDIAN: 'Linear PCM, little endian',
    SOUND_FORMAT_NELLYMOSER_16KHZ: 'Nellymoser 16-kHz mono',
    SOUND_FORMAT_NELLYMOSER_8KHZ: 'Nellymoser 8-kHz mono',
    SOUND_FORMAT_NELLYMOSER: 'Nellymoser',
    SOUND_FORMAT_G711_A_LAW: 'G.711 A-law logarithmic PCM',
    SOUND_FORMAT_G711_MU_LAW: 'G.711 mu-law logarithmic PCM',
    SOUND_FORMAT_AAC: 'AAC',
    SOUND_FORMAT_SPEEX: 'Speex',
    SOUND_FORMAT_MP3_8KHZ: 'MP3 8-kHz',
    SOUND_FORMAT_DEVICE_SPECIFIC: 'Device-specific sound'
}

# Sound rate
(
    SOUND_RATE_5_5_KHZ,
    SOUND_RATE_11_KHZ,
    SOUND_RATE_22_KHZ,
    SOUND_RATE_44_KHZ
) = range(4)

sound_rate_to_string = {
    SOUND_RATE_5_5_KHZ: '5.5-kHz',
    SOUND_RATE_11_KHZ: '11-kHz',
    SOUND_RATE_22_KHZ: '22-kHz',
    SOUND_RATE_44_KHZ: '44-kHz'
}

# Sound size
SOUND_SIZE_8_BIT, SOUND_SIZE_16_BIT = range(2)

sound_size_to_string = {
    SOUND_SIZE_8_BIT: 'snd8Bit',
    SOUND_SIZE_16_BIT: 'snd16Bit'
}

# Sound type
SOUND_TYPE_MONO, SOUND_TYPE_STEREO = range(2)

sound_type_to_string = {
    SOUND_TYPE_MONO: 'sndMono',
    SOUND_TYPE_STEREO: 'sndStereo'
}

# AAC packet type
AAC_PACKET_TYPE_SEQUENCE_HEADER, AAC_PACKET_TYPE_RAW = range(2)

aac_packet_type_to_string = {
    AAC_PACKET_TYPE_SEQUENCE_HEADER: 'sequence header',
    AAC_PACKET_TYPE_RAW: 'raw'
}

# Codec ID
(
    CODEC_ID_JPEG,
    CODEC_ID_H263,
    CODEC_ID_SCREEN_VIDEO,
    CODEC_ID_VP6,
    CODEC_ID_VP6_WITH_ALPHA,
    CODEC_ID_SCREEN_VIDEO_V2,
    CODEC_ID_H264
) = range(1, 8)

codec_id_to_string = {
    CODEC_ID_JPEG: 'JPEG',
    CODEC_ID_H263: 'Sorenson H.263',
    CODEC_ID_SCREEN_VIDEO: 'Screen video',
    CODEC_ID_VP6: 'On2 VP6',
    CODEC_ID_VP6_WITH_ALPHA: 'On2 VP6 with alpha channel',
    CODEC_ID_SCREEN_VIDEO_V2: 'Screen video version 2',
    CODEC_ID_H264: 'H.264'
}

# Frame type
(
    FRAME_TYPE_KEYFRAME,
    FRAME_TYPE_INTERFRAME,
    FRAME_TYPE_DISPOSABLE_INTERFRAME,
    FRAME_TYPE_GENERATED_KEYFRAME,
    FRAME_TYPE_INFO_FRAME
) = range(1, 6)

frame_type_to_string = {
    FRAME_TYPE_KEYFRAME: 'keyframe',
    FRAME_TYPE_INTERFRAME: 'interframe',
    FRAME_TYPE_DISPOSABLE_INTERFRAME: 'disposable interframe',
    FRAME_TYPE_GENERATED_KEYFRAME: 'generated keyframe',
    FRAME_TYPE_INFO_FRAME: 'video info/command frame'
}

# H.264 packet type
(
    H264_PACKET_TYPE_SEQUENCE_HEADER,
    H264_PACKET_TYPE_NALU,
    H264_PACKET_TYPE_END_OF_SEQUENCE
) = range(3)

h264_packet_type_to_string = {
    H264_PACKET_TYPE_SEQUENCE_HEADER: 'sequence header',
    H264_PACKET_TYPE_NALU: 'NAL unit',
    H264_PACKET_TYPE_END_OF_SEQUENCE: 'sequence end'
}

# Value type
(
    VALUE_TYPE_NUMBER,
    VALUE_TYPE_BOOLEAN,
    VALUE_TYPE_STRING,
    VALUE_TYPE_OBJECT,
    VALUE_TYPE_MOVIE_CLIP,
    VALUE_TYPE_NULL,
    VALUE_TYPE_UNDEFINED,
    VALUE_TYPE_REFERENCE,
    VALUE_TYPE_ECMA_ARRAY
) = range(9)

(
    VALUE_TYPE_STRICT_ARRAY,
    VALUE_TYPE_DATE,
    VALUE_TYPE_LONG_STRING
) = range(10, 13)

value_type_to_string = {
    VALUE_TYPE_NUMBER: 'Number',
    VALUE_TYPE_BOOLEAN: 'Boolean',
    VALUE_TYPE_STRING: 'String',
    VALUE_TYPE_OBJECT: 'Object',
    VALUE_TYPE_MOVIE_CLIP: 'Movie clip',
    VALUE_TYPE_NULL: 'Null',
    VALUE_TYPE_UNDEFINED: 'Undefined',
    VALUE_TYPE_REFERENCE: 'Reference',
    VALUE_TYPE_ECMA_ARRAY: 'ECMA array',
    VALUE_TYPE_STRICT_ARRAY: 'Strict array',
    VALUE_TYPE_DATE: 'Date',
    VALUE_TYPE_LONG_STRING: 'Long string'
}
