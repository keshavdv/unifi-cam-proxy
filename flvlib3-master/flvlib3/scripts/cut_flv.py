import sys
import logging
from optparse import OptionParser

from flvlib3 import __version__
from flvlib3.astypes import MalformedFLV, FLVObject
from flvlib3.constants import (TAG_TYPE_AUDIO, TAG_TYPE_VIDEO, TAG_TYPE_SCRIPT,
                               FRAME_TYPE_KEYFRAME,
                               H264_PACKET_TYPE_SEQUENCE_HEADER,
                               H264_PACKET_TYPE_NALU)
from flvlib3.tags import FLV, AudioTag, VideoTag, ScriptTag, create_flv_header, create_script_tag

log = logging.getLogger('flvlib.cut-flv')


class CuttingAudioTag(AudioTag):

    def parse(self):
        parent = self.parent_flv
        AudioTag.parse(self)

        if not parent.first_media_tag_offset:
            parent.first_media_tag_offset = self.offset


class CuttingVideoTag(VideoTag):

    def parse(self):
        parent = self.parent_flv
        VideoTag.parse(self)

        parent.no_video = False

        if not parent.first_media_tag_offset and self.h264_packet_type != H264_PACKET_TYPE_SEQUENCE_HEADER:
            parent.first_media_tag_offset = self.offset


tag_to_class = {
    TAG_TYPE_AUDIO: CuttingAudioTag,
    TAG_TYPE_VIDEO: CuttingVideoTag,
    TAG_TYPE_SCRIPT: ScriptTag
}


class CuttingFLV(FLV):

    def __init__(self, f):
        super().__init__(f)
        self.metadata = None
        self.keyframes = FLVObject()
        self.keyframes.file_positions = []
        self.keyframes.times = []
        self.no_video = True
        self.audio_tag_number = 0
        self.first_media_tag_offset = None

    def tag_type_to_class(self, tag_type):
        try:
            return tag_to_class[tag_type]
        except KeyError:
            raise MalformedFLV('Invalid tag type: %d' % tag_type)


def cut_file(in_path, out_path, start_time, end_time):
    log.debug('Cutting file "%s" into file "%s"', in_path, out_path)

    try:
        f = open(in_path, 'rb')
    except IOError as e:
        log.error('Failed to open "%s": %s', in_path, e)
        return False

    try:
        fo = open(out_path, 'wb')
    except IOError as e:
        log.error('Failed to open "%s": %s', out_path, e)
        return False

    if start_time is None:
        start_time = 0
    else:
        start_time = int(start_time)
    if end_time is None:
        end_time = -1
    else:
        end_time = int(end_time)

    flv = CuttingFLV(f)
    tag_iterator = flv.iter_tags()
    last_tag = None
    tag_after_last_tag = None
    first_keyframe_after_start = None

    try:
        script_tag = next(tag_iterator)
        for tag in tag_iterator:
            # some buggy software, like GStreamer's flvmux, puts a metadata tag
            # at the end of the file with timestamp 0, and we don't want to
            # base our duration computation on that
            if tag.timestamp != 0 and (tag.timestamp <= end_time or end_time == -1):
                last_tag = tag
            elif tag_after_last_tag is None and tag.timestamp != 0:
                tag_after_last_tag = tag
            if not first_keyframe_after_start and tag.timestamp > start_time:
                if isinstance(tag, VideoTag):
                    if tag.frame_type == FRAME_TYPE_KEYFRAME and tag.h264_packet_type == H264_PACKET_TYPE_NALU:
                        first_keyframe_after_start = tag
                elif flv.no_video:
                    first_keyframe_after_start = tag
    except MalformedFLV as e:
        log.error('The file "%s" is not a valid FLV file: %s', in_path, e)
        return False
    except EOFError:
        log.error('Unexpected end of file on file "%s"', in_path)
        return False

    if not flv.first_media_tag_offset:
        log.error('The file "%s" does not have any media content', in_path)
        return False

    if not last_tag:
        log.error('The file "%s" does not have any content with a non-zero timestamp', in_path)
        return False

    if not first_keyframe_after_start:
        log.error('The file "%s" has no keyframes greater than start time %d', in_path, start_time)
        return False

    log.debug('Creating the output file')

    log.debug('First tag to output %s', first_keyframe_after_start)
    log.debug('Last tag to output %s', last_tag)
    log.debug('Tag after last tag %s', tag_after_last_tag)

    f.seek(0)
    log.debug('copying up to %d bytes', flv.first_media_tag_offset)

    # 'duration' in onMetaData should be rewrite
    script_tag.variable[b'duration'] = (end_time - start_time) / 1000
    fo.write(create_flv_header(flv.has_audio, flv.has_video) + create_script_tag('onMetaData', script_tag, timestamp=0))
    f.seek(flv.first_media_tag_offset)

    log.debug('seeking to %d bytes', first_keyframe_after_start.offset)
    if tag_after_last_tag:
        end_offset = tag_after_last_tag.offset
    else:
        f.seek(0, 2)
        end_offset = f.tell()
    log.debug('end offset %d', end_offset)
    f.seek(first_keyframe_after_start.offset)

    copy_bytes = end_offset - first_keyframe_after_start.offset
    log.debug('copying %d bytes', copy_bytes)
    fo.write(f.read(copy_bytes))
    f.close()
    fo.close()
    return True


def process_options():
    usage = '%prog [options] in_file out_file'
    description = (
        'Cut out part of a FLV file. Start and end times are '
        'timestamps that will be compared to the timestamps '
        'of tags from inside the file. Tags from outside of the '
        'start/end range will be discarded, taking care to always '
        'start the new file with a keyframe. '
        'The script accepts one input and one output file path.'
    )
    version = '%%prog flvlib %s' % __version__
    parser = OptionParser(usage=usage, description=description,
                          version=version)
    parser.add_option('-s', '--start-time', help='start time to cut from (millisecond)')
    parser.add_option('-e', '--end-time', help='end time to cut to (millisecond)')
    parser.add_option('-v', '--verbose', action='count',
                      default=0, dest='verbosity',
                      help='be more verbose, each -v increases verbosity')
    options, args = parser.parse_args(sys.argv)

    if len(args) < 2:
        parser.error('You have to provide an input and output file path')

    if not options.start_time and not options.end_time:
        parser.error('You need to provide at least '
                     'one of start time or end time ')

    if options.verbosity > 3:
        options.verbosity = 3

    level = ({
        0: logging.ERROR,
        1: logging.WARNING,
        2: logging.INFO,
        3: logging.DEBUG
    }[options.verbosity])

    log.setLevel(level)

    return options, args


def cut_files():
    options, args = process_options()
    return cut_file(args[1], args[2], options.start_time, options.end_time)


def main():
    try:
        outcome = cut_files()
    except KeyboardInterrupt:
        # give the right exit status, 128 + signal number
        # signal.SIGINT = 2
        sys.exit(128 + 2)
    except EnvironmentError as e:
        print(e, file=sys.stderr)
        sys.exit(2)

    if outcome:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
