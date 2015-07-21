"""
Transitional module for moving to the w3lib library.

For new code, always import from w3lib.http instead of this module
"""

from w3lib.http import *

def decode_chunked_transfer(chunked_body):
    """Parsed body received with chunked transfer encoding, and return the
    decoded body.

    For more info see:
    http://en.wikipedia.org/wiki/Chunked_transfer_encoding
    
    Encoded data:

    In the following example, every second line is the start of a new chunk, with the chunk size as a hexadecimal number followed by \r\n as a line separator.
    4\r\n
    Wiki\r\n
    5\r\n
    pedia\r\n
    e\r\n
    in\r\n\r\nchunks.\r\n
    0\r\n
    \r\n
    Note: the chunk size indicates the size of only the chunk data. 
    This does not include the trailing CRLF ("\r\n") at the end of the counted characters.[3]
    In this particular example, the CRLF following "in" is counted 2 toward the chunk length of 0xE (14), and the CRLF in its own line is also counted 2 toward the chunk length of 0xE (14). 
    The period character at the end of "chunks" is the 14th character, so it is the last character of the chunk of length 0xE (14). 
    The CRLF following the period is the trailing CRLF, so it is not counted toward the chunk length of 0xE (14).
    Decoded data:

    Wikipedia in

    chunks.

    """
    body, h, t = '', '', chunked_body
    while t:
        h, t = t.split('\r\n', 1)
        if h == '0':
            break
        size = int(h, 16)
        body += t[:size]
        t = t[size+2:]
    return body

