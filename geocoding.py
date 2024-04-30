#!/usr/local/bin/python
# vim:ts=4:sw=4:tw=0:sts=4:et
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
import json
import configparser
import geopy.geocoders
from dms2dec.dms_convert import dms2dec
import ssl
import logging as log
import smtplib

# Internal
from directory import Directory

#####################
## Parse arguments ##
#####################

parser = argparse.ArgumentParser()
parser.add_argument('configFile', help='Provide config file') #NOTE: Provide better description.
parser.add_argument('-o', '--outName', dest='outName', default='bbmri-directory-5-0', help='Output file name')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-p', '--password', dest='password', help='Password of the account used to login to the Directory')
parser.add_argument('-u', '--username', dest='username', help='Username of the account used to login to the Directory')
parser.add_argument('-P', '--package', dest='package', default='eu_bbmri_eric', help='MOLGENIS Package that contains the data (default eu_bbmri_eric).')

parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
args = parser.parse_args()

# Set logs:
if args.debug:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
elif args.verbose:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
else:
    log.basicConfig(format="%(levelname)s: %(message)s")


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

if 'biobanksCountrySkip' in config['Skip country']:
    biobanksCountrySkip = config['Skip country']['biobanksCountrySkip'].split(',')
else:
    biobanksCountrySkip = []

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
        log.debug('Coordinates from: '+ ', '.join(lookBy))
        return location
    # If location not found, remove specific fields and retain general ones.
    else:
        places = 1
        while places<len(lookBy):

            location = geolocator.geocode(', '.join(lookBy[places:len(lookBy)+1]))
            
            if location:
                log.debug('Coordinates from: '+ ', '.join(lookBy[places:len(lookBy)+1]))
                return location
            places += 1


def disableSSLCheck():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    geopy.geocoders.options.default_ssl_context = ctx


def sendEmail(sender, receivers, message):
   '''
   Sender: String containing sender email.
   Receivers: List containing receivers emails.
   Message: String containing the message.
   '''
   try:
      smtpObj = smtplib.SMTP('localhost')
      smtpObj.sendmail(sender, receivers, message)         
      log.info("Successfully sent email")
   except ConnectionRefusedError:
      log.info("Error: unable to send email")

##########
## Main ##
##########

# Get info from Directory
pp = pprint.PrettyPrinter(indent=4)
if args.username is not None and args.password is not None:
	dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp, username=args.username, password=args.password)
else:
	dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

# Initialize main dictionary
features = {}
features['type'] = 'FeatureCollection'
features['features'] = []

# Get geolocator information
geolocator = geopy.geocoders.Nominatim(user_agent='Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0',timeout=15)

# Try geolocator certificates
try:
    geolocator.geocode('Graz, Austria')
# If this does not work, disable ssl certificates:
except geopy.exc.GeocoderUnavailable:
    log.debug('Disable SSL')
    disableSSLCheck()
    geolocator = geopy.geocoders.Nominatim(user_agent='Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0',timeout=15)

    # Try again:
    try:
        geolocator.geocode('Graz, Austria')
    # If this does not work, change adapter:
    except geopy.exc.GeocoderUnavailable:
        log.debug('Change adapter')
        disableSSLCheck() # Need to be done again
        geopy.geocoders.options.default_adapter_factory = geopy.adapters.URLLibAdapter
        geolocator = geopy.geocoders.Nominatim(user_agent='Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0',timeout=15)

        # Try again:
        try:
            geolocator.geocode('Graz, Austria')
        except:
            log.warning('Geolocator fails with the following error:')
            sendEmail('eva.gaal93@gmail.com', ['eva.garcia-alvarez@bbmri-eric.eu'], 'Geolocator failed!')
            raise

# Get biobanks from Directory:
for biobank in dir.getBiobanks():
    if biobank['name'] not in biobanksNameSkip and biobank['id'].split(':')[2].split('_')[0] not in biobanksCountrySkip:
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
            dmsSymbols = ['o','°']
            #if '°' in biobank['longitude'] or '°' in biobank['latitude'] or '°' in biobank['longitude'] or '°' in biobank['latitude']: # Change to decimal coordinates
            if any(x in biobank['longitude'] for x in dmsSymbols) or any(x in biobank['latitude'] for x in dmsSymbols):
                biobankGeometryDict['coordinates'] = [dms2dec(biobank['longitude']), dms2dec(biobank['latitude'])]
            else:
                biobankGeometryDict['coordinates'] = [float(re.sub(r',', r'.', biobank['longitude'])), float(re.sub(r',', r'.', biobank['latitude']))]
            log.info(biobank['name'] + ': Coordinates provided')
        elif 'contact' in biobank.keys():
            lookForCoordinatesFeatures = ['address', 'zip', 'city', 'country']
            location = lookForCoordinates(biobank, lookForCoordinatesFeatures)
            if location:
                biobankGeometryDict['coordinates'] = [float(location.longitude), float(location.latitude)]
                log.info(biobank['name'] + ": geodecoding done ")
            else:
                log.warning(biobank['name'] + ": geodecoding failed ")
        else:
            log.warning(biobank['name'] + ": no contact provided")

        # Skip biobank if not available coordinates:
        if biobankGeometryDict:
            biobankGeometryDict['type'] = 'Point' ### DEFAULT
            biobankDict['geometry'] = biobankGeometryDict

            features['features'].append(biobankDict)
        else:
            log.warning("Skipping " + str(biobank['name']))


# Write geoJSON
outFile = args.outName + '.geojson'
with open(outFile, 'w') as outfile:
    json.dump(features, outfile, indent=4)
