#!/usr/bin/python3
"""
Script for creating geoJSON
"""

#############
## Imports ##
#############

# External
import pprint
import re
import argparse
import sys
import json
import configparser
import os
import pdoc
from geopy.geocoders
from dms2dec.dms_convert import dms2dec

# Internal
from directory import Directory

#####################
## Parse arguments ##
#####################

parser = argparse.ArgumentParser()
parser.add_argument('configFile', help='Provide config file') #NOTE: Provide better description.
parser.add_argument('-o', '--outName', dest='outName', default='bbmri-directory', help='Output file name')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-p', '--password', dest='password', help='Password of the account used to login to the Directory')
parser.add_argument('-u', '--username', dest='username', help='Username of the account used to login to the Directory')
parser.add_argument('-P', '--package', dest='package', default='eu_bbmri_eric', help='MOLGENIS Package that contains the data (default eu_bbmri_eric).')

parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
args = parser.parse_args()

# Parse config file
config = configparser.ConfigParser()
config.read(args.configFile)

if 'biobankProperties' in config['Biobank config']:
    biobankInputFeatures = config['Biobank config']['biobankProperties'].split(',')
else:
    biobankInputFeatures = ['biobankID','biobankName','biobankType','covid19biobank','biobankSize']

if 'biobanksNameSkip' in config['Skip biobank']:
    biobanksNameSkip = config['Skip biobank']['biobanksNameSkip'].split(',')
else:
    biobanksNameSkip = []

###############
## Functions ##
###############

def lookForCoordinates(biobank, lookForCoordinatesFeatures):
    '''
    Look for coordinates based on biobank contact.

    NOTE: Address fails a lot, maybe only by first field? But the separator is not consistent.
    '''
    lookBy = []
    for locFeature in lookForCoordinatesFeatures:
        if locFeature in biobank['contact'].keys():
            if locFeature == 'country':
                lookBy.append(biobank['contact'][locFeature]['name'])
            else:
                lookBy.append(biobank['contact'][locFeature])
    location = geolocator.geocode(', '.join(lookBy))
    if location:
        print ('Coordinates from: '+ ', '.join(lookBy))
        return location
    # If location not found, remove specific fields and retain general ones.
    else:
        places = 1
        while places<len(lookBy):

            location = geolocator.geocode(', '.join(lookBy[places:len(lookBy)+1]))
            
            if location:
                print ('Coordinates from: '+ ', '.join(lookBy[places:len(lookBy)+1]))
                return location
            places += 1

def disableSSLCheck():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    geopy.geocoders.options.default_ssl_context = ctx


##########
## Main ##
##########

# Get info from Directory
pp = pprint.PrettyPrinter(indent=4)
if args.username is not None and args.password is not None:
	dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp, username=args.username, password=args.password)
else:
	dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

sys.stdout.reconfigure(encoding='utf-8') # NOTE: Needed on Windows to redirect strout

# Initialize main dictionary
features = {}
features['type'] = 'FeatureCollection'
features['features'] = []

# Get geolocator information
geolocator = geopy.geocoders.Nominatim(user_agent='test_160211112222',timeout=15) # NOTE: Change user agent.

# Try geolocator certificates
try:
    geolocator.geocode('Graz, Austria')
# If this does not work, disable ssl certificates:
except:
    print ('Disable SSL')
    disableSSLCheck()
    geolocator = geopy.geocoders.Nominatim(user_agent='test_160211112222',timeout=15) # NOTE: Change user agent.

# Try again:
try:
    geolocator.geocode('Graz, Austria')
# If this does not work, change adapter:
except:
    print ('Change adapter')
    disableSSLCheck() # Need to be done again
    geopy.geocoders.options.default_adapter_factory = geopy.adapters.URLLibAdapter
    geolocator = geopy.geocoders.Nominatim(user_agent='test_160211112222',timeout=15) # NOTE: Change user agent.

# Try again:
try:
    geolocator.geocode('Graz, Austria')
except:
    print ('Geolocator fails')

# Get biobanks from Directory:
for biobank in dir.getBiobanks():
    if biobank['name'] not in biobanksNameSkip:
        biobankDict = {}

        # Biobank properties:
        biobankPropertiesDict = {}
        if 'biobankID' in biobankInputFeatures:
            biobankPropertiesDict['biobankID'] = biobank['id']
        if 'biobankSize' in biobankInputFeatures:
            try:
                biobankPropertiesDict['biobankSize'] = max(int(coll['order_of_magnitude']['id']) for coll in biobank['collections'])
            except ValueError:
                pass
        if 'biobankName' in biobankInputFeatures:
            biobankPropertiesDict['biobankName'] = biobank['name']
        if 'biobankType' in biobankInputFeatures:
            biobankPropertiesDict['biobankType'] = 'biobank' ### DEFAULT

        if 'covid19biobank' in biobankInputFeatures and 'covid19biobank' in biobank.keys():
            biobankCOVID = []
            for COVIDDict in biobank['covid19biobank']:
                biobankCOVIDDict = {}
                biobankCOVIDDict['_href']=COVIDDict['_href']
                biobankCOVIDDict['id']=COVIDDict['id']
                biobankCOVIDDict['name']=COVIDDict['name']
                biobankCOVID.append(biobankCOVIDDict)
            biobankPropertiesDict['biobankCOVID'] = biobankCOVID

        biobankDict['properties'] = biobankPropertiesDict

        biobankDict['type'] = 'Feature' ### DEFAULT

        # Biobank geometry:
        biobankGeometryDict = {}
        location = None

        # Override biobank location through config file:
        if biobank['name'] in config['Override biobank position'].keys():        
            biobankGeometryDict['coordinates'] = [float(i) for i in config['Override biobank position'][biobank['name']].split(',')]

        elif 'longitude' in biobank.keys() and 'latitude' in biobank.keys():
            if '°' in biobank['longitude'] or '°' in biobank['latitude']: # Change to decimal coordinates
                biobankGeometryDict['coordinates'] = [dms2dec(biobank['longitude']), dms2dec(biobank['latitude'])]
            else:
                biobankGeometryDict['coordinates'] = [float(re.sub(r',', r'.', biobank['longitude'])), float(re.sub(r',', r'.', biobank['latitude']))]
            print ('Coordinates provided')
        elif 'contact' in biobank.keys():
            lookForCoordinatesFeatures = ['address', 'zip', 'city', 'country']
            location = lookForCoordinates(biobank, lookForCoordinatesFeatures)
            if location:
                biobankGeometryDict['coordinates'] = [float(location.longitude), float(location.latitude)]
                print ("(geodecoding done) ")
            else:
                print ("(geodecoding failed) ")
        else:
            print ("(geocoding skipped, no contact provided)")

        # Skip biobank if not available coordinates:
        if biobankGeometryDict:
            biobankGeometryDict['type'] = 'Point' ### DEFAULT
            biobankDict['geometry'] = biobankGeometryDict

            features['features'].append(biobankDict)
        else:
            print ("Skipping " +' '+ str(biobank['name']))


# Write geoJSON
outFile = args.outName + '.geojson'
with open(outFile, 'w') as outfile:
    json.dump(features, outfile, indent=4)
