from slippi import Game
from writer import Version, DataAndType, Writer
import ubjson

slp_path = 'samples/test.slp'

g = Game(slp_path)

#with open('samples/test.slp', 'rb') as f:
#    test = ubjson.loadb(f.read())

#print(test['raw'].keys())

w = Writer(bin_path=slp_path, g=g)
#print(w.gecko)
#w.read_base_json()

w.write()