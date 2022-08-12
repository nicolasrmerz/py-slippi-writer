from slippi import Game
from enum import Enum
import os
from collections import OrderedDict
import json
import struct
import copy

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

class Version:
    def __init__(self, ver_str):
        ver_list = ver_str.split('.')
        if len(ver_list) != 3:
            raise ValueError('Version must be supplied in form x.y.z, given {}'.format(ver_str))
        if len(ver_list[0]) == 0 or len(ver_list[1]) == 0 or len(ver_list[2]) == 0:
            raise ValueError('Version must be supplied in form x.y.z, given {}'.format(ver_str))
        self.major = int(ver_list[0])
        self.minor = int(ver_list[1])
        self.build = int(ver_list[2])
        
    def __lt__(self, other):
        if self.major < other.major:
            return True
        elif self.major == other.major:
            if self.minor < other.minor:
                return True
            elif self.minor == other.minor:
                if self.build < other.build:
                    return True
        
        return False
        
    def __eq__(self, other):
        return self.major == other.major and self.minor == other.minor and self.build == other.build
        
    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

class DataAndType:
    """Data type and value"""
    
    val: int #: Value to be written
    dtype: str #: Type to write to binary
    l: int #: Number of times to write this data
    def __init__(self, val: str, dtype: str, ver_str: str, l: int):
        self.dtype = dtype

        if self._check_is_hex(val):
            self.val = struct.unpack('>' + DataEnum[self.dtype], bytes.fromhex(val[2:]))[0]
        else:
            if dtype == 'f32':
                self.val = float(val)
            else:
                self.val = int(val)
                
        self.version = Version(ver_str)

        self.l = int(l)

    def _check_is_hex(self, s):
        return len(s) > 2 and s[:2] == '0x'

    def write(self, stream, ver):
        if self.version <= ver:
            stream.write(struct.pack('>' + str(self.l) + DataEnum[self.dtype], *[self.val]*self.l))
        
    def __str__(self):
        return "val: {}, format: {}".format(self.val, self.dtype)
    def __repr__(self):
        return "val: {}, format: {}".format(self.val, self.dtype)


class Writer:
    """Write a py-slippi Game object back to a .slp binary"""
    
    g: int #: Game object from py-slippi

    def __init__(self, json_path=os.path.join('resources', 'json_base.json'), g=None):
        self.version = None
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
        if 'val' in key_list and 'dtype' in key_list and 'added' in key_list:
            if 'len' in key_list:
                l = j[root_key]['len']
            else:
                l = 1
            j[root_key] = DataAndType(j[root_key]['val'], j[root_key]['dtype'], j[root_key]['added'], l)
        elif 'data' in key_list and 'repetitions' in key_list:
            self._postprocess_json(j[root_key], 'data')
            j[root_key] = [copy.deepcopy(j[root_key]['data']) for _ in range(int(j[root_key]['repetitions']))]
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

    def _handle_start(self, g_start):
        if hasattr(g_start, 'is_frozen_ps'):
            self.start['frozenps'].val = g_start.is_frozen_ps

        if hasattr(g_start, 'is_pal'):
            self.start['pal'].val = g_start.is_pal
            
        if hasattr(g_start, 'is_teams'):
            self.start['gameinfoblock']['isteams'].val = g_start.is_teams
            
        if hasattr(g_start, 'players'):
            
            for i, p in enumerate(g_start.players):
                if p:
                    self.start['gameinfoblock']['playerdata'][i]['externalcharid'].val = p.character
                    self.start['gameinfoblock']['playerdata'][i]['costumeindex'].val = p.costume
                    self.start['gameinfoblock']['playerdata'][i]['stockstartcount'].val = p.stocks
                    if p.tag:
                        self.start['nametag'][i]['nametag'].val = p.tag
                    if p.team:
                        self.start['gameinfoblock']['playerdata'][i]['teamid'].val = p.team
                    self.start['gameinfoblock']['playerdata'][i]['playertype'].val = p.type
                    if p.ucf:
                        self.start['dashandshieldfix'][i]['dashbackfix'].val = p.ucf.dash_back
                        self.start['dashandshieldfix'][i]['shielddropfix'].val = p.ucf.shield_drop
                        
        if hasattr(g_start, 'random_seed'):
            self.start['randomseed'].val = g_start.random_seed

        if hasattr(g_start, 'slippi') and hasattr(g_start.slippi, 'version'):
            self.start['version']['major'].val = g_start.slippi.version.major
            self.start['version']['minor'].val = g_start.slippi.version.minor
            self.start['version']['build'].val = g_start.slippi.version.revision

        if hasattr(g_start, 'stage'):
            self.start['gameinfoblock']['stage'].val = g_start.stage
        
    def load_game(self, g):
        if hasattr(g.start, 'slippi') and hasattr(g.start.slippi, 'version'):
            self.version = Version(str(g.start.slippi.version.major) + '.' + str(g.start.slippi.version.minor) + '.' + str(g.start.slippi.version.revision))
        if g.start:
            self._handle_start(g.start)

    def _write_helper(self, d, stream):
        if isinstance(d, DataAndType):
            d.write(stream, self.version)

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
