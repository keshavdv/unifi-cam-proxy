import os
import sys
import shutil
import logging
import tempfile

from optparse import OptionParser

from flvlib3 import __version__
from flvlib3.astypes import MalformedFLV
from flvlib3.constants import (TAG_TYPE_AUDIO, TAG_TYPE_VIDEO, TAG_TYPE_SCRIPT,
                               AAC_PACKET_TYPE_SEQUENCE_HEADER,
                               H264_PACKET_TYPE_SEQUENCE_HEADER)
from flvlib3.helpers import force_remove
from flvlib3.primitives import make_ui8, make_ui24, make_si32_extended
from flvlib3.tags import FLV, AudioTag, VideoTag, ScriptTag

log = logging.getLogger('flvlib3.retimestamp-flv')

class_to_tag = {
    AudioTag: TAG_TYPE_AUDIO,
    VideoTag: TAG_TYPE_VIDEO,
    ScriptTag: TAG_TYPE_SCRIPT
}


def is_non_header_media(tag):
    if isinstance(tag, ScriptTag):
        return False
    if isinstance(tag, AudioTag):
        return tag.aac_packet_type != AAC_PACKET_TYPE_SEQUENCE_HEADER
    if isinstance(tag, VideoTag):
        return tag.h264_packet_type != H264_PACKET_TYPE_SEQUENCE_HEADER


def output_offset_tag(fin, fout, tag, offset):
    new_timestamp = tag.timestamp - offset
    # do not offset non-media and media header
    if not is_non_header_media(tag):
        new_timestamp = tag.timestamp

    # write the FLV tag value
    fout.write(make_ui8(class_to_tag[type(tag)]))
    # the tag size remains unchanged
    fout.write(make_ui24(tag.size))
    # write the new timestamp
    fout.write(make_si32_extended(new_timestamp))
    # seek inside the input file
    #   seek position: tag offset + tag (1) + size (3) + timestamp (4)
    fin.seek(tag.offset + 8, os.SEEK_SET)
    # copy the tag content to the output file
    #   content size:  tag size + stream ID (3) + previous tag size (4)
    fout.write(fin.read(tag.size + 7))


def retimestamp_tags_inplace(f, fu):
    flv = FLV(f)
    offset = None

    for tag in flv.iter_tags():
        if offset is None and is_non_header_media(tag):
            offset = tag.timestamp
            log.debug('Determined the offset to be %d', offset)

        # optimise for offset == 0, which in case of inplace updating is a noop
        if offset is not None and offset != 0:
            fu.seek(tag.offset + 4, os.SEEK_SET)
            fu.write(make_si32_extended(tag.timestamp - offset))


def retimestamp_file_inplace(in_path):
    try:
        f = open(in_path, 'rb')
        fu = open(in_path, 'rb+')
    except IOError as e:
        log.error('Failed to open "%s": %s', in_path, e)
        return False

    try:
        retimestamp_tags_inplace(f, fu)
    except IOError as e:
        log.error('Failed to create the retimestamped file: %s', e)
        return False
    except MalformedFLV as e:
        log.error('The file "%s" is not a valid FLV file: %s', in_path, e)
        return False
    except EOFError:
        log.error('Unexpected end of file on file "%s"', in_path)
        return False

    f.close()
    fu.close()

    return True


def retimestamp_file_atomically(in_path, out_path):
    try:
        fin = open(in_path, 'rb')
    except IOError as e:
        log.error('Failed to open "%s": %s', in_path, e)
        return False

    if out_path:
        try:
            fout = open(out_path, 'w+b')
        except IOError as e:
            log.error('Failed to open "%s": %s', out_path, e)
            return False
    else:
        try:
            fd, temp_path = tempfile.mkstemp()
            # preserve the permission bits
            shutil.copymode(in_path, temp_path)
            fout = os.fdopen(fd, 'wb')
        except EnvironmentError as e:
            log.error('Failed to create temporary file: %s', e)
            return False

    try:
        shutil.copyfileobj(fin, fout)
    except EnvironmentError as e:
        log.error('Failed to create temporary copy: %s', e)
        force_remove(temp_path)
        return False

    fin.seek(0)
    fout.seek(0)

    try:
        retimestamp_tags_inplace(fin, fout)
    except IOError as e:
        log.error('Failed to create the retimestamped file: %s', e)
        if not out_path:
            force_remove(temp_path)
        return False
    except MalformedFLV as e:
        log.error('The file "%s" is not a valid FLV file: %s', in_path, e)
        if not out_path:
            force_remove(temp_path)
        return False
    except EOFError:
        log.error('Unexpected end of file on file "%s"', in_path)
        if not out_path:
            force_remove(temp_path)
        return False

    fin.close()
    fout.close()

    if not out_path:
        # If we were not writing directly to the output file
        # we need to overwrite the original
        try:
            shutil.move(temp_path, in_path)
        except EnvironmentError as e:
            log.error('Failed to overwrite the original file '
                      'with the indexed version: %s', e)
            return False

    return True


def retimestamp_file(in_path, out_path=None, inplace=False):
    out_text = (out_path and ('into file "%s"' % out_path)) or 'and overwriting'
    log.debug('Retimestamping file "%s" %s', in_path, out_text)

    if inplace:
        log.debug('Operating in inplace mode')
        return retimestamp_file_inplace(in_path)
    else:
        log.debug('Not operating in inplace mode, using temporary files')
        return retimestamp_file_atomically(in_path, out_path)


def process_options():
    usage = '%prog [-i] [-U] file [out_file|file2 file3 ...]'
    description = (
        'Rewrites timestamps in FLV files making by the first media tag timestamped '
        'with 0. The rest of the tags is retimestamped relatively. With the -i '
        '(inplace) option modifies the files without creating temporary copies. With '
        'the -U (update) option operates on all parameters, updating the files in '
        'place. Without the -U option accepts one input and one output file path.'
    )
    version = '%%prog flvlib3 %r' % __version__
    parser = OptionParser(usage=usage, description=description,
                          version=version)
    parser.add_option('-i', '--inplace', action='store_true',
                      help=('inplace mode, does not create temporary files, but '
                            'risks corruption in case of errors'))
    parser.add_option('-U', '--update', action='store_true',
                      help=('update mode, overwrites the given files '
                            'instead of writing to out_file'))
    parser.add_option('-v', '--verbose', action='count',
                      default=0, dest='verbosity',
                      help='be more verbose, each -v increases verbosity')
    options, args = parser.parse_args(sys.argv)

    if len(args) < 2:
        parser.error('You have to provide at least one file path')

    if not options.update and options.inplace:
        parser.error('You need to use the update mode if you are updating '
                     'files in place')

    if not options.update and len(args) != 3:
        parser.error('You need to provide one in_file and one out_file '
                     'when not using the update mode')

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


def retimestamp_files():
    options, args = process_options()

    clean_run = True

    if not options.update:
        clean_run = retimestamp_file(args[1], args[2])
    else:
        for filename in args[1:]:
            if not retimestamp_file(filename, inplace=options.inplace):
                clean_run = False

    return clean_run


def main():
    try:
        outcome = retimestamp_files()
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
