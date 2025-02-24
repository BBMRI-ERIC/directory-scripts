#!/usr/local/bin/python3.6
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
import pandas as pd
from flatten_json import flatten

# Internal
from directory import Directory

#import sys
#sys.stdout.reconfigure(encoding='utf-8') # NOTE: Needed on Windows to redirect strout


cachesList = ['directory', 'geocoding']

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
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (directory and geocoding)')
parser.add_argument('--print-filtered-df', dest='printDf', default=False, action="store_true", help='Print filtered data frame to stdout')
#parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='disable particular long remote checks')

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
        if not pd.isna(biobank[locFeature]):
                lookBy.append(biobank[locFeature])
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
      print ("Successfully sent email")
   except SMTPException:
      print ("Error: unable to send email")

##########
## Main ##
##########

# Get info from Directory
pp = pprint.PrettyPrinter(indent=4)
if args.username is not None and args.password is not None:
	dir = Directory(schema=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp, username=args.username, password=args.password)
else:
	dir = Directory(schema=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

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
# Flatten the results and create a pandas dataframe. Every entry per biobank is going to be a new column. As there are nested dictionaries, consecutive numbers are asigned to repeated keys.
dic_flattened = [flatten(d, '-') for d in dir.getBiobanks()]
df = pd.DataFrame(dic_flattened)

# Filter dataframe according to user input
for column, value in config['Filter dataset'].items():
    # Convert column name to regex, based on getBiobanks_keyList
    column_regex = column.replace('>', '-[0-9]*-')
    # Get all column names containing that expression
    if '*' in column_regex:
        wanted_Columns = list(df.filter(regex=column_regex, axis=1).columns)
    else:
        wanted_Columns = list(df.filter(items=[column_regex], axis=1).columns)
    # Check if any of these columns match the input conditions and get the rows in which conditions are met
    for condition in config['Filter dataset'][column].split(','):
        # Look for the exact same string that is provided as input
        if config['Filter dataset exact string']['searchExactString'] == 'Yes':
            new_df = df[(df[wanted_Columns] == condition.strip('\n')).any(axis=1)] # This only works matching the exact same string.
        # Search for the provided string as a substring (if it is contained as part of another string it is also taken into account):
        elif config['Filter dataset exact string']['searchExactString'] == 'No':
            new_df = df[(df[wanted_Columns].apply(lambda col: col.str.contains(condition.strip('\n'), na=False), axis=1)).any(axis=1)]
        # Add the new filtered df to the final one
        if not 'filtered_df' in locals():
            filtered_df = new_df
        else:
            filtered_df = pd.concat([filtered_df,new_df])
            filtered_df.loc[filtered_df.astype(str).drop_duplicates().index]

# If there is not filtered dataframe because not filters were selected, use the original df:
if not 'filtered_df' in locals():
    filtered_df = df

if args.printDf:
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_colwidth', None)
    print (filtered_df)

# Iterate dataframe rows
for index, biobank in filtered_df.iterrows():

    if biobank['name'] not in biobanksNameSkip and biobank['id'].split(':')[2].split('_')[0] not in biobanksCountrySkip:
        biobankDict = {}
        # Biobank properties:
        biobankPropertiesDict = {}
        if 'biobankID' in biobankInputFeatures:
            biobankPropertiesDict['biobankID'] = biobank['id']
        if 'biobankSize' in biobankInputFeatures:
            try:
                # Get a list of column names for order of magnitude
                collections_order_of_magnitude_id_columns = list(filtered_df.filter(regex='collections-[0-9]*-order_of_magnitude-id', axis=1).columns)
                # Within those columns get the one with the maximum value
                biobankPropertiesDict['biobankSize'] = int(biobank[collections_order_of_magnitude_id_columns].max())
            except ValueError:
                pass
        if 'biobankName' in biobankInputFeatures:
            biobankPropertiesDict['biobankName'] = biobank['name']
        if 'biobankType' in biobankInputFeatures:
            biobankPropertiesDict['biobankType'] = 'biobank' ### DEFAULT

        if 'covid19biobank' in biobankInputFeatures and 'capabilities' in biobank.keys():
            biobankCOVID = []
            # For each capabilities-_href column, look for covid19 information and store it in the dictionary:
            for idx in range(0,len(list(filtered_df.filter(regex='capabilities-[0-9]*-_href', axis=1).columns))):
                biobankCOVIDDict = {}
                if not pd.isna(biobank['capabilities-'+ str(idx) +'-_href']):
                    if 'covid19' in biobank['capabilities-'+str(idx)+'-_href']:
                        biobankCOVIDDict['_href']=biobank['capabilities-'+ str(idx) +'-_href']
                        biobankCOVIDDict['id']=biobank['capabilities-'+str(idx)+'-id']
                        biobankCOVIDDict['name']=biobank['capabilities-'+str(idx)+'-label']
                        biobankCOVID.append(biobankCOVIDDict)
            biobankPropertiesDict['biobankCOVID'] = biobankCOVID

        #New 0106
        network_columns = list(filtered_df.filter(regex='network-[0-9]*-_href', axis=1).columns)
        if not biobankCOVID and 'COVID19' in str(biobank[network_columns].values):
            biobankCOVID = []
            biobankCOVIDDict = {}
            biobankCOVIDDict['name']='COVID19 Network'
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

        elif not pd.isna(biobank['longitude']) and not pd.isna(biobank['latitude']):
            dmsSymbols = ['º','°']
            #if '°' in biobank['longitude'] or '°' in biobank['latitude'] or '°' in biobank['longitude'] or '°' in biobank['latitude']: # Change to decimal coordinates
            if any(x in biobank['longitude'] for x in dmsSymbols) or any(x in biobank['latitude'] for x in dmsSymbols):
                biobankGeometryDict['coordinates'] = [dms2dec(biobank['longitude']), dms2dec(biobank['latitude'])]
            else:
                biobankGeometryDict['coordinates'] = [float(re.sub(r',', r'.', biobank['longitude'])), float(re.sub(r',', r'.', biobank['latitude']))]
            log.info(biobank['name'] + ': Coordinates provided')
        elif biobank['contact-_href']:
            lookForCoordinatesFeatures = ['contact-address', 'contact-zip', 'contact-city', 'contact-country-name']
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
