from slippi import Game
from writer import Version, DataAndType, Writer
import ubjson

g = Game('samples/test.slp')

#with open('samples/test.slp', 'rb') as f:
#    test = ubjson.loadb(f.read())

#print(test['raw'].keys())

w = Writer(g=g)
#w.read_base_json()

w.write()