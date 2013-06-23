from civomega import Parser, Match
from jinja2 import Environment, PackageLoader
from civomega.registry import REGISTRY

env = Environment(loader=PackageLoader('civomega', 'templates'))

import re
import json
import requests

SIMPLE_PATTERN = re.compile('^\s*(?:how many|how much|which are|which)(?P<noun>.+?)\s+(?:live in|are in|in)\s+(?P<place>[\w\s]+)\??',re.IGNORECASE)

def find_places(p):
    url = 'http://api.censusreporter.org/1.0/geo/search?prefix=%s' % p
    response = requests.get(url)
    return response.json()

SPECIFIC_HISPANIC_ORIGIN = { # table ID B03001
	'b03001001': 'Total:',
	#'b03001002': 'Not Hispanic or Latino',
	'b03001003': 'Hispanic or Latino', # cumulative
	'b03001004': 'Mexican',
	'b03001005': 'Puerto Rican',
	'b03001006': 'Cuban',
	'b03001007': 'Dominican (Dominican Republic)',
	'b03001008': 'Central American:',
	'b03001009': 'Costa Rican',
	'b03001010': 'Guatemalan',
	'b03001011': 'Honduran',
	'b03001012': 'Nicaraguan',
	'b03001013': 'Panamanian',
	'b03001014': 'Salvadoran',
	'b03001015': 'Other Central American',
	'b03001016': 'South American', # cumulative
	'b03001017': 'Argentinean',
	'b03001018': 'Bolivian',
	'b03001019': 'Chilean',
	'b03001020': 'Colombian',
	'b03001021': 'Ecuadorian',
	'b03001022': 'Paraguayan',
	'b03001023': 'Peruvian',
	'b03001024': 'Uruguayan',
	'b03001025': 'Venezuelan',
	'b03001026': 'Other South American',
	'b03001027': 'Other Hispanic or Latino', # cumulative
	'b03001028': 'Spaniard',
	'b03001029': 'Spanish',
	'b03001030': 'Spanish American',
	'b03001031': 'All other Hispanic or Latino',
}

SPECIFIC_ASIAN_ORIGIN = { # table id = B02006
    'b02006001': 'Asian', #'Total:',
    'b02006002': 'Indian (Asian)', #'Asian Indian',
    'b02006003': 'Bangladeshi',
    'b02006004': 'Cambodian',
    'b02006005': 'Chinese , except Taiwanese',
    'b02006006': 'Filipino',
    'b02006007': 'Hmong',
    'b02006008': 'Indonesian',
    'b02006009': 'Japanese',
    'b02006010': 'Korean',
    'b02006011': 'Laotian',
    'b02006012': 'Malaysian',
    'b02006013': 'Pakistani',
    'b02006014': 'Sri Lankan',
    'b02006015': 'Taiwanese',
    'b02006016': 'Thai',
    'b02006017': 'Vietnamese',
    'b02006018': 'Other Asian',
    'b02006019': 'Other Asian, not specified',
}

RACE_PATTERNS = [ # pattern, field, label
    (re.compile('black( people|s|folks?)?|(african|afro)[-\s]?american|african american|negro.*'), 'b02001003', 'Black or African American alone'),
    (re.compile('white( people|s|folks?)?'), 'b02001002', 'White alone'),
    (re.compile('asian( people|s|folks?)?'), 'b02001005', 'Asian alone'),
]

MAX_RESULTS = 5

class SimpleCensusParser(Parser):
    def search(self, s):
        if SIMPLE_PATTERN.match(s):
            d = SIMPLE_PATTERN.match(s).groupdict()
            places = find_places(d['place'])
            if places:
            # figure out which table for noun
                results = []
                noun = d['noun'].strip().lower()
                if noun[-1] == 's': noun = noun[:-1]
                for field,name in SPECIFIC_HISPANIC_ORIGIN.items():
                    if name.lower().startswith(noun):
                        #results.append(HispanicOriginMatch(field, places[0]))
                        for place in places:
                            if len(results) >= MAX_RESULTS: break
                            results.append(HispanicOriginMatch(field, place))
                for field,name in SPECIFIC_ASIAN_ORIGIN.items():
                    if (name.lower().startswith(noun)) and not (field == 'b02006002' and re.match('asians?',noun)):
                        #results.append(AsianOriginMatch(field, places[0]))
                        for place in places:
                            if len(results) >= MAX_RESULTS: break
                            results.append(AsianOriginMatch(field, place))
                for pat, field, label in RACE_PATTERNS:
                    if pat.match(noun):
                        for place in places:
                            if len(results) >= MAX_RESULTS: break
                            results.append(RaceMatch(field,place,label))
                results.sort(key=lambda x: x._context()['population'], reverse=True)
                return results or None
        return None



class FieldInTableMatch(Match):
    template = None # specify in subclass
    table = None # specify in subclass
    label = None # evaluate in subclass, e.g. "Dominican", "Chinese"
    def __init__(self, field, place):
        self.field = field
        self.place = place
        self.geoid = place['full_geoid']
        self.load_table_data()
        
    def load_table_data(self):
        # we would need to get some data
        url = 'http://api.censusreporter.org/1.0/acs2011_5yr/%s?geoids=%s' % (self.table,self.geoid)
        resp = requests.get(url)
        self.data = resp.json()

    def _context(self):
        return {
            'label': self.label,
            'place': self.place,
            'population': int(self.data[self.geoid][self.field]),
            'full_data': self.data[self.geoid],
        }

    def as_json(self):
        return json.dumps(self._context())

    def as_html(self):
        return env.get_template(self.template).render(**self._context())

        
class HispanicOriginMatch(FieldInTableMatch):
    template = 'census/b03001.html'
    table = 'B03001'

    def __init__(self, field, place):
        super(HispanicOriginMatch,self).__init__(field, place)
        self.label = SPECIFIC_HISPANIC_ORIGIN[self.field]

    def _context(self):
        d = super(HispanicOriginMatch,self)._context()
        d['field_labels'] = SPECIFIC_HISPANIC_ORIGIN
        return d
        
class AsianOriginMatch(FieldInTableMatch):
    template = 'census/b02006.html'
    table = 'B02006'

    def __init__(self, field, place):
        super(AsianOriginMatch,self).__init__(field, place)
        self.label = SPECIFIC_ASIAN_ORIGIN[self.field]

class RaceMatch(FieldInTableMatch):
    template = 'census/b02001.html'
    table = 'B02001'

    def __init__(self, field, place, label):
        super(RaceMatch,self).__init__(field, place)
        self.label = label
    
REGISTRY.add_parser('simple_census_parser', SimpleCensusParser)