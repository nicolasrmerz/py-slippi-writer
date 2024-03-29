from slippi import Game
from slippi.event import StateFlags
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

SizeEnum = {
    'uint8': 1,
    'uint16': 2,
    'uint32': 4,
    'int8': 1,
    'int16': 2,
    'int32': 4,
    'f32': 4,
    'bool': 1,
    # TODO: Treating string as uint8 will not work once strings are taken from py-slippi Game - need to handle DataAndType val being an actual string
    'string': 1
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
        
        self.size = SizeEnum[self.dtype]

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

    def __init__(self, json_path=os.path.join('resources', 'json_base.json'), bin_path=None, g=None):
        self.version = None
        self.payloads = None
        self.start = None
        self.gecko = None
        self.preframetemplate = None
        self.postframetemplate = None
        self.preframes = None
        self.postframes = None
        self.end = None
        self.read_base_json(json_path)
        if g:
            self.load_game(g)
        if bin_path:
            try:
                self.load_gecko_code(bin_path)
            except Exception as e:
                raise Exception(str(e))
                
            
    def unpack(self, fmt, stream):
        fmt = '>' + fmt
        size = struct.calcsize(fmt)
        bytes = stream.read(size)
        if not bytes:
            raise EOFError()
        return struct.unpack(fmt, bytes)
        
    def expect_bytes(self, expected_bytes, stream):
        read_bytes = stream.read(len(expected_bytes))
        if read_bytes != expected_bytes:
            raise Exception(f'expected {expected_bytes}, but got: {read_bytes}')
    
    def _parse_event_payloads(self, stream):
        (code, this_size) = self.unpack('BB', stream)

        this_size -= 1 # includes size byte for some reason
        command_count = this_size // 3
        if command_count * 3 != this_size:
            raise Exception(f'payload size not divisible by 3: {this_size}')

        sizes = {}
        for i in range(command_count):
            (code, size) = self.unpack('BH', stream)
            sizes[code] = size

        return (2 + this_size, sizes)
        
    def load_gecko_code(self, bin_path, gecko_event_code=0x3D):
        with open(bin_path, 'rb') as stream:
            self.expect_bytes(b'{U\x03raw[$U#l', stream)
            (length,) = self.unpack('l', stream)
            (bytes_read, payload_sizes) = self._parse_event_payloads(stream)
            if gecko_event_code not in payload_sizes:
                return
                
            bytes_read = 0
            while bytes_read != length:
                (code,) = self.unpack('B', stream)
                if code in payload_sizes:
                    size = payload_sizes[code]
                    b = stream.read(size)
                    if code == gecko_event_code:
                        self.gecko = bytes([gecko_event_code]) + b
                        return
                        
                    bytes_read += 1 + size
                else:
                    return
            
            return
                    

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
            if 'preframeupdatetemplate' in keys:
                self.preframetemplate = data['preframeupdatetemplate']
            if 'postframeupdatetemplate' in keys:
                self.postframetemplate = data['postframeupdatetemplate']
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
            
    def _convert_stateflags(self, sf):
        reflect = bool(sf & StateFlags.REFLECT)
        untouchable = bool(sf & StateFlags.UNTOUCHABLE)
        fast_fall = bool(sf & StateFlags.FAST_FALL)
        hit_lag = bool(sf & StateFlags.HIT_LAG)
        shield = bool(sf & StateFlags.SHIELD)
        hit_stun = bool(sf & StateFlags.HIT_STUN)
        shield_touch = bool(sf & StateFlags.SHIELD_TOUCH)
        power_shield = bool(sf & StateFlags.POWER_SHIELD)
        follower = bool(sf & StateFlags.FOLLOWER)
        sleep = bool(sf & StateFlags.SLEEP)
        dead = bool(sf & StateFlags.DEAD)
        off_screen = bool(sf & StateFlags.OFF_SCREEN)
        
        sf_1 = 0 | (reflect << 4)
        sf_2 = 0 | (untouchable << 2) | (fast_fall << 3) | (hit_lag << 5)
        sf_3 = 0 | (shield << 7)
        sf_4 = 0 | (hit_stun << 1) | (shield_touch << 2) | (power_shield << 5)
        sf_5 = 0 | (follower << 3) | (sleep << 4) | (dead << 6) | (off_screen << 7)
        
        return sf_1, sf_2, sf_3, sf_4, sf_5
    
    def _handle_frames(self, frames):
        self.preframes = []
        self.postframes = []
        for f in frames:
            frame_num = f.index
            curr_preframe = [None, None, None, None]
            curr_postframe = [None, None, None, None]
            for i, port in enumerate(f.ports):
                if port != None:
                    if hasattr(port, 'leader') and hasattr(port, 'follower'):
                        if port.leader:
                            data = port.leader
                            is_follower = False
                        elif port.follower:
                            data = port.follower
                            is_follower = True
                            
                        pre = copy.deepcopy(self.preframetemplate)
                        post = copy.deepcopy(self.postframetemplate)
                        if hasattr(data, 'post'):
                            post['framenumber'].val = frame_num
                            post['playerindex'].val = i
                            post['isfollower'].val = is_follower
                            if hasattr(data.post, 'airborne'):
                                post['groundairstate'].val = data.post.airborne
                            if hasattr(data.post, 'character'):
                                post['internalcharacterid'].val = data.post.character
                            if hasattr(data.post, 'combo_count'):
                                post['currentcombocount'].val = data.post.combo_count
                            if hasattr(data.post, 'damage'):
                                post['percent'].val = data.post.damage
                            if hasattr(data.post, 'direction'):
                                post['facingdirection'].val = data.post.direction
                            if hasattr(data.post, 'flags'):
                                post['statebitflags1'].val, post['statebitflags2'].val, post['statebitflags3'].val, post['statebitflags4'].val, post['statebitflags5'].val = self._convert_stateflags(data.post.flags)
                            if hasattr(data.post, 'ground'):
                                post['lastgroundid'].val = data.post.ground
                            if hasattr(data.post, 'hit_stun'):
                                post['miscas'].val = data.post.hit_stun
                            if hasattr(data.post, 'jumps'):
                                post['jumpsremaining'].val = data.post.jumps
                            if hasattr(data.post, 'l_cancel'):
                                post['lcancelstatus'].val = data.post.l_cancel
                            if hasattr(data.post, 'last_attack_landed'):
                                post['lasthittingattackid'].val = data.post.last_attack_landed
                            if hasattr(data.post, 'last_hit_by'):
                                post['lasthitby'].val = data.post.last_hit_by
                            if hasattr(data.post, 'position'):
                                post['xposition'].val = data.post.position[0]
                                post['yposition'].val = data.post.position[1]
                            if hasattr(data.post, 'state'):
                                post['actionstateid'].val = data.post.state
                            if hasattr(data.post, 'state_age'):
                                post['actionstateframecounter'].val = data.post.state_age
                            if hasattr(data.post, 'stocks'):
                                post['stocksremaining'].val = data.post.stocks
                                
                        if hasattr(data, 'post'):
                            post['framenumber'].val = frame_num
                            post['playerindex'].val = i
                            post['isfollower'].val = is_follower
                            
        
    def load_game(self, g):
        if hasattr(g.start, 'slippi') and hasattr(g.start.slippi, 'version'):
            self.version = Version(str(g.start.slippi.version.major) + '.' + str(g.start.slippi.version.minor) + '.' + str(g.start.slippi.version.revision))
        if g.start:
            self._handle_start(g.start)
        if g.frames != None and len(g.frames) > 0:
            self._handle_frames(g.frames)

    def _write_helper(self, d, stream):
        if isinstance(d, DataAndType):
            d.write(stream, self.version)

        elif isinstance(d, list):
            for e in d:
                self._write_helper(e, stream)
        else:
            for key in list(d.keys()):
                self._write_helper(d[key], stream)

    def _write_helper_caller(self, od, stream):
        if od:
            for key in list(od.keys()):
                self._write_helper(od[key], stream)
                
    def _calc_payload_size(self, od):
        if isinstance(od, DataAndType):
            if od.version <= self.version:
                return (od.size * od.l)
            else:
                return 0
            
        accum = 0
        if isinstance(od, list):
            for e in od:
                accum += self._calc_payload_size(e)
        else:
            for k in od.keys():
                accum += self._calc_payload_size(od[k])
                
        return accum
    
    def calc_and_write_prefix(self, stream):
        payloads = {}
        payloads[self.start['commandbyte'].val] = self._calc_payload_size(self.start) - 1
        payloads[0x3D] = len(self.gecko) - 1
        # Each payload size is code + 2-byte size, except for the payload itself which is code + 1-byte size
        payloads[0x35] = (len(payloads.keys()) * 3) + 2
        
        l = 0
        for code in payloads:
            l += payloads[code]
            # TODO: When frames are added, will need to add length of frametemplate * number of frames
            
        stream.write(b'{U\x03raw[$U#l')
        stream.write(struct.pack('>l', l))
        
        for code in sorted(payloads.keys()):
            stream.write(struct.pack('>B', code))
            fmt_str = '>B' if code == 0x35 else '>H'
            stream.write(struct.pack(fmt_str, payloads[code]))

        
        
    
    def write(self, bin_path=os.path.join('output', 'out.slp')):
        with open(bin_path, 'wb') as stream:
            self.calc_and_write_prefix(stream)
            self._write_helper_caller(self.start, stream)
            if self.gecko:
                stream.write(self.gecko)
            #_write_helper_caller(self.frames, stream)
            #_write_helper_caller(self.end, stream)

