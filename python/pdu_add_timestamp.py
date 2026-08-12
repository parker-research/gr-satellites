#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2026 Daniel Estevez <daniel@destevez.net>
#
# This file is part of gr-satellites
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import datetime

from gnuradio import gr
import pmt

from .submit import parse_timestamp


class pdu_add_timestamp(gr.basic_block):
    """
    Adds a 'timestamp' metadata entry to PDUs

    The timestamp is computed from the PDU 'sample_offset' metadata entry
    (if present), which some deframers set to the offset, in symbols, of
    the frame within the stream fed to the deframer. This is combined with
    the symbol rate and a start time (corresponding to the first symbol
    of the recording) to compute an absolute timestamp for the packet.

    This allows getting correct per-packet timestamps when replaying a
    recording as fast as possible (i.e., without using --throttle to play
    it back at 1x speed), as long as the deframer that produced the PDU
    attaches 'sample_offset' metadata to it.

    If the PDU has no 'sample_offset' metadata, or no start time is given,
    the PDU is passed through unmodified, so that downstream blocks fall
    back to their wall-clock based timestamping.

    Args:
        baudrate: symbol rate of the deframer that produced the PDU (float)
        start_time: timestamp corresponding to the first symbol
            of the recording (string, ISO 8601 format)
    """
    def __init__(self, baudrate, start_time=''):
        gr.basic_block.__init__(
            self,
            name='pdu_add_timestamp',
            in_sig=None,
            out_sig=None)
        self.baudrate = baudrate
        self.start_time = parse_timestamp(start_time) if start_time else None

        self.message_port_register_in(pmt.intern('in'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)
        self.message_port_register_out(pmt.intern('out'))

    def handle_msg(self, msg_pmt):
        if self.start_time is None:
            self.message_port_pub(pmt.intern('out'), msg_pmt)
            return

        meta = pmt.car(msg_pmt)
        data = pmt.cdr(msg_pmt)

        offset_key = pmt.intern('sample_offset')
        if pmt.is_dict(meta) and pmt.dict_has_key(meta, offset_key):
            offset = pmt.to_uint64(pmt.dict_ref(meta, offset_key, pmt.PMT_NIL))
            timestamp = self.start_time + datetime.timedelta(
                seconds=offset / self.baudrate)
            meta = pmt.dict_add(
                meta, pmt.intern('timestamp'),
                pmt.from_double(timestamp.timestamp()))

        self.message_port_pub(pmt.intern('out'), pmt.cons(meta, data))
