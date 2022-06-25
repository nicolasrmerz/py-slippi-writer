from slippi import Game
from enum import Enum
import os
from collections import OrderedDict
import json
import struct

DataEnum = {
    'uint8': 'B',
    'uint16': 'H',
    'uint32': 'L',
    'int8': 'b',
    'int16': 'h',
    'int32': 'l',
    'f32': 'f',
    'bool': '?',
    # TODO: Treating string as uint8 will not work once strings are taken from py-slippi Game - need to handle DataAndType val being an actual string
    'string': 'B'
}

class DataAndType:
    """Data type and value"""
    
    val: int #: Value to be written
    dtype: str #: Type to write to binary
    l: int #: Number of times to write this data
    def __init__(self, val: str, dtype: str, l: int):
        self.dtype = dtype

        if self._check_is_hex(val):
            self.val = struct.unpack('>' + DataEnum[self.dtype], bytes.fromhex(val[2:]))[0]
        else:
            if dtype == 'f32':
                self.val = float(val)
            else:
                self.val = int(val)

        self.l = int(l)

    def _check_is_hex(self, s):
        return len(s) > 2 and s[:2] == '0x'

    def write(self, stream):
        stream.write(struct.pack('>' + str(self.l) + DataEnum[self.dtype], *[self.val]*self.l))


class Writer:
    """Write a py-slippi Game object back to a .slp binary"""
    
    g: int #: Game object from py-slippi

    def __init__(self, json_path=os.path.join('resources', 'json_base.json'), g=None):
        self.start = None
        self.gecko = None
        self.frametemplate = None
        self.frames = None
        self.end = None
        self.read_base_json(json_path)
        if g:
            self.load_game(g)

    def _postprocess_json(self, j, root_key):
        key_list = list(j[root_key].keys())
        if 'val' in key_list and 'dtype' in key_list:
            if 'len' in key_list:
                l = j[root_key]['len']
            else:
                l = 1
            j[root_key] = DataAndType(j[root_key]['val'], j[root_key]['dtype'], l)
        elif 'data' in key_list and 'repetitions' in key_list:
            self._postprocess_json(j[root_key], 'data')
            j[root_key] = [j[root_key]['data']] * int(j[root_key]['repetitions'])
        else:
            for k in key_list:
                self._postprocess_json(j[root_key], k)
            
    def read_base_json(self, json_path=os.path.join('resources', 'json_base.json')):
        with open(json_path, 'r') as f:
            data = json.load(f, object_pairs_hook=OrderedDict)
            for k in list(data.keys()):
                self._postprocess_json(data, k)
            
            keys = list(data.keys())
            if 'start' in keys:
                self.start = data['start']
            if 'gecko' in keys:
                self.gecko = data['gecko']
            if 'frametemplate' in keys:
                self.frametemplate = data['frametemplate']
            if 'end' in keys:
                self.end = data['end']

    def load_game(self, g):
        pass

    def _write_helper(self, d, stream):
        if isinstance(d, DataAndType):
            d.write(stream)

        elif isinstance(d, list):
            for e in d:
                self._write_helper(e, stream)
        else:
            for key in list(d.keys()):
                self._write_helper(d[key], stream)

    def write(self, bin_path=os.path.join('output', 'out.slp')):
        with open(bin_path, 'wb') as stream:
            for od in [self.start, self.gecko, self.frames, self.end]:
                if od:
                    for key in list(od.keys()):
                        self._write_helper(od[key], stream)
