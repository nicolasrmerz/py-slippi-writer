from slippi import Game
from writer import Version, DataAndType, Writer
import ubjson
import pdb

slp_path = 'samples/test.slp'


g = Game(slp_path)
pdb.set_trace()
#print(g.frames[0])

#with open('samples/test.slp', 'rb') as f:
#    test = ubjson.loadb(f.read())

#print(test['raw'].keys())

w = Writer(bin_path=slp_path, g=g)
#print(w.gecko)
#w.read_base_json()

w.write()