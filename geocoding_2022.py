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
import json
import hashlib
import configparser
import ssl
import logging as log
import smtplib
import time
from pathlib import Path
import os

# Internal
from cli_common import (
    add_directory_auth_arguments,
    add_directory_schema_argument,
    add_logging_arguments,
    add_purge_cache_arguments,
    add_withdrawn_scope_arguments,
    build_directory_kwargs,
    build_parser,
    configure_logging,
)
from directory import Directory
from diskcache import Cache

cachesList = ['directory', 'geocoding']
REPO_ROOT = Path(__file__).resolve().parent

#####################
## Parse arguments ##
#####################

parser = build_parser()
add_logging_arguments(parser)
add_directory_auth_arguments(parser)
add_directory_schema_argument(parser, default='ERIC')
parser.add_argument('configFile', help='Provide config file') #NOTE: Provide better description.
parser.add_argument('-o', '--out-name', '--outName', dest='outName', default='bbmri-directory-5-0', help='Output file name')
add_withdrawn_scope_arguments(parser)
add_purge_cache_arguments(parser, cachesList)
parser.add_argument('--print-filtered-dataframe', '--print-filtered-df', dest='printDf', default=False, action="store_true", help='Print filtered data frame to stdout')

parser.set_defaults(purgeCaches=[])
args = parser.parse_args()

configure_logging(args)

import geopy.geocoders
import pandas as pd
from dms2dec.dms_convert import dms2dec
from flatten_json import flatten


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

if 'biobanksIDSkip' in config['Skip ID']:
    biobanksIDSkip = config['Skip ID']['biobanksIDSkip'].split(',')
else:
    biobanksIDSkip = []

###############
## Functions ##
###############

def geocoding_cache_dir() -> str:
    """Return the persistent global geocoding cache directory."""
    cache_root = os.environ.get('DIRECTORY_CACHE_ROOT')
    if cache_root:
        return str(Path(cache_root) / 'data-check-cache' / 'geocoding')
    return str(Path.cwd() / 'data-check-cache' / 'geocoding')


def geocoding_cache_key(contactID, lookBy):
    """Return a stable cache key for one contact lookup signature."""
    look_by_text = ' | '.join(str(value).strip() for value in lookBy if str(value).strip())
    digest = hashlib.sha256(look_by_text.encode('utf-8')).hexdigest()
    if contactID:
        return f'contact:{contactID}:{digest}'
    return f'query:{digest}'


def biobank_coordinate_cache_key(biobankID, longitude_raw, latitude_raw, contactID):
    """Return a stable cache key for one biobank fallback-coordinate situation."""
    source_text = ' | '.join(
        str(value).strip()
        for value in (biobankID, longitude_raw, latitude_raw, contactID)
        if value is not None and str(value).strip()
    )
    digest = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
    return f'biobank:{biobankID}:{digest}'


def get_cached_biobank_coordinates(geocodingCache, biobankID, longitude_raw, latitude_raw, contactID):
    """Return cached fallback coordinates for one biobank/source signature."""
    cacheKey = biobank_coordinate_cache_key(biobankID, longitude_raw, latitude_raw, contactID)
    cachedEntry = geocodingCache.get(cacheKey)
    if cachedEntry and cachedEntry.get('status') == 'resolved':
        return cachedEntry.get('coordinates')
    return None


def cache_biobank_coordinates(
    geocodingCache,
    biobankID,
    longitude_raw,
    latitude_raw,
    contactID,
    coordinates,
    source,
):
    """Persist fallback coordinates for one biobank/source signature."""
    cacheKey = biobank_coordinate_cache_key(biobankID, longitude_raw, latitude_raw, contactID)
    geocodingCache[cacheKey] = {
        'status': 'resolved',
        'coordinates': coordinates,
        'source': source,
        'longitude_raw': longitude_raw,
        'latitude_raw': latitude_raw,
        'contact_id': contactID,
    }


def format_coordinate_pair(coordinates):
    """Return a compact human-readable coordinate pair for warnings."""
    if not coordinates or len(coordinates) < 2:
        return "unknown"
    try:
        return f"{float(coordinates[0]):.6f}, {float(coordinates[1]):.6f}"
    except (TypeError, ValueError):
        return f"{coordinates[0]!r}, {coordinates[1]!r}"


def safe_geocode(query: str):
    """Resolve one geocoding query or disable live geocoding for this run."""
    global geolocator
    global geocodingEnabled
    global geocodingNextRequestMonotonic

    if not geocodingEnabled:
        return ('disabled', None)

    for attempt, backoff_seconds in enumerate((0.0, 3.0, 10.0), start = 1):
        wait_seconds = max(0.0, geocodingNextRequestMonotonic - time.monotonic())
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        geocodingNextRequestMonotonic = time.monotonic() + 1.1

        try:
            location = geolocator.geocode(query)
        except (geopy.exc.GeocoderRateLimited, geopy.exc.GeocoderServiceError) as exc:
            if attempt < 3:
                log.warning(
                    'Geocoding attempt %d for %r failed because the geocoding service is unavailable or rate-limited: %s. Retrying after %.1fs.',
                    attempt,
                    query,
                    exc,
                    backoff_seconds,
                )
                time.sleep(backoff_seconds)
                geocodingNextRequestMonotonic = max(
                    geocodingNextRequestMonotonic,
                    time.monotonic() + 1.1,
                )
                continue
            log.warning(
                'Geocoding failed for %r because the geocoding service is unavailable or rate-limited: %s',
                query,
                exc,
            )
            geocodingEnabled = False
            return ('disabled', None)
        except geopy.exc.GeocoderUnavailable:
            log.debug('Geocoding unavailable for %r; retrying with SSL fallback.', query)
            disableSSLCheck()
            try:
                geolocator = geopy.geocoders.Nominatim(
                    user_agent='Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0',
                    timeout=15,
                )
                location = geolocator.geocode(query)
            except (geopy.exc.GeocoderRateLimited, geopy.exc.GeocoderServiceError, geopy.exc.GeocoderUnavailable) as exc:
                if attempt < 3:
                    log.warning(
                        'Geocoding attempt %d for %r failed after SSL fallback: %s. Retrying after %.1fs.',
                        attempt,
                        query,
                        exc,
                        backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    geocodingNextRequestMonotonic = max(
                        geocodingNextRequestMonotonic,
                        time.monotonic() + 1.1,
                    )
                    continue
                log.warning(
                    'Geocoding failed for %r after SSL fallback: %s',
                    query,
                    exc,
                )
                geocodingEnabled = False
                return ('disabled', None)

        if location:
            return ('resolved', location)
        return ('not_found', None)

    geocodingEnabled = False
    return ('disabled', None)


def lookForCoordinates(contactID, personsContactsById, lookForCoordinatesFeatures, geocodingCache, allowLiveLookup = True):
    '''
    Look for coordinates based on biobank contact.

    NOTE: Address fails a lot, maybe only by first field? But the separator is not consistent.
    '''
    contact = personsContactsById.get(contactID)
    if not contact:
        return None

    lookBy = []
    for locFeature in lookForCoordinatesFeatures:
        if locFeature in contact.keys() and contact[locFeature]:
            lookBy.append(contact[locFeature])
    if not lookBy:
        return None

    lookup_variants = [lookBy[places:len(lookBy) + 1] for places in range(0, len(lookBy))]

    for lookup_values in lookup_variants:
        cacheKey = geocoding_cache_key(contactID, lookup_values)
        cachedEntry = geocodingCache.get(cacheKey)
        if cachedEntry:
            if cachedEntry.get('status') == 'resolved':
                log.debug('Coordinates from geocoding cache: %s', ', '.join(lookup_values))
                return cachedEntry['coordinates']
            if cachedEntry.get('status') == 'not_found':
                continue

        if not allowLiveLookup:
            continue

        if not geocodingEnabled:
            return None

        status, location = safe_geocode(', '.join(lookup_values))
        if status == 'resolved':
            coordinates = [float(location.longitude), float(location.latitude)]
            geocodingCache[cacheKey] = {
                'status': 'resolved',
                'coordinates': coordinates,
                'query': lookup_values,
            }
            log.debug('Coordinates from live geocoder: %s', ', '.join(lookup_values))
            return coordinates
        if status == 'not_found':
            geocodingCache[cacheKey] = {
                'status': 'not_found',
                'query': lookup_values,
            }
            continue
        if status == 'disabled':
            return None

    return None


def dmm_to_dd(coord: str):
    "Convert coordinates in DMM format to decimal degrees"
    pattern = r'([NSWE])(\d+) (\d+\.\d+)'
    match = re.match(pattern, coord)

    if not match:
        raise ValueError(f"Invalid coordinate format: {coord}")

    direction, degrees, minutes = match.groups()

    # Convert to decimal degrees
    decimal_degrees = int(degrees) + float(minutes) / 60

    # Apply negative sign for South and West coordinates
    if direction in ['S', 'W']:
        decimal_degrees *= -1

    return decimal_degrees


def _parse_decimal_coordinate_component(raw_value, label, minimum, maximum):
    """Parse one stored decimal coordinate component and report its own issue."""
    cleaned = re.sub(r',', r'.', str(raw_value))
    try:
        value = float(cleaned)
    except (TypeError, ValueError) as exc:
        return None, f"{label} parse error: {exc}"

    if not (minimum <= value <= maximum):
        return None, f"{label} out of range: {raw_value!r}"

    return value, None


def parse_decimal_coordinates(longitude_raw, latitude_raw):
    """Parse stored Directory coordinates into validated decimal lon/lat."""
    longitude, longitude_issue = _parse_decimal_coordinate_component(longitude_raw, "longitude", -180, 180)
    latitude, latitude_issue = _parse_decimal_coordinate_component(latitude_raw, "latitude", -90, 90)

    issues = [issue for issue in (longitude_issue, latitude_issue) if issue]
    if issues:
        raise ValueError("; ".join(issues))

    return [longitude, latitude]

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
   except smtplib.SMTPException:
      print ("Error: unable to send email")

##########
## Main ##
##########

# Get info from Directory
pp = pprint.PrettyPrinter(indent=4)
dir = Directory(**build_directory_kwargs(args, pp=pp))

# Initialize main dictionary
features = {}
features['type'] = 'FeatureCollection'
features['features'] = []

# Initialize geolocator lazily. Do not perform a startup probe, because
# repeated runs with a complete geocoding cache should not hit the live
# geocoder at all.
geolocator = geopy.geocoders.Nominatim(
    user_agent='Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0',
    timeout=15,
)
geocodingEnabled = True
geocodingNextRequestMonotonic = 0.0

geocodingCacheDir = geocoding_cache_dir()
if not Path(geocodingCacheDir).exists():
    Path(geocodingCacheDir).mkdir(parents=True, exist_ok=True)
geocodingCache = Cache(geocodingCacheDir)
if 'geocoding' in args.purgeCaches:
    geocodingCache.clear()
personsContacts = dir.getContacts()
personsContactsById = {
    contact['id']: contact
    for contact in personsContacts
    if isinstance(contact, dict) and 'id' in contact
}
visibleCollectionsById = {
    collection['id']: collection
    for collection in dir.getCollections()
    if isinstance(collection, dict) and 'id' in collection
}

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
            filtered_df = filtered_df.loc[filtered_df.astype(str).drop_duplicates().index]

# If there is not filtered dataframe because not filters were selected, use the original df:
if not 'filtered_df' in locals():
    filtered_df = df

biobankCollectionIdColumns = list(filtered_df.filter(regex='collections-[0-9]*-id', axis=1).columns)

if args.printDf:
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_colwidth', None)
    print (filtered_df)

# Iterate dataframe rows
for index, biobank in filtered_df.iterrows():

    if biobank['name'] not in biobanksNameSkip and biobank['id'].split(':')[2].split('_')[0] not in biobanksCountrySkip and biobank['id'] not in biobanksIDSkip:
        biobankDict = {}
        # Biobank properties:
        biobankPropertiesDict = {}
        if 'biobankID' in biobankInputFeatures:
            biobankPropertiesDict['biobankID'] = biobank['id']
        if 'biobankSize' in biobankInputFeatures:
            OoM = []
            for collID in biobankCollectionIdColumns:
                if not isinstance(biobank[collID], float):
                    collection = visibleCollectionsById.get(biobank[collID])
                    if collection and 'order_of_magnitude' in collection:
                        OoM.append(int(collection['order_of_magnitude']))
            if OoM:
                biobankPropertiesDict['biobankSize'] = int(max(OoM))

        if 'biobankName' in biobankInputFeatures:
            biobankPropertiesDict['biobankName'] = biobank['name']
        if 'biobankType' in biobankInputFeatures:
            biobankPropertiesDict['biobankType'] = 'biobank' ### DEFAULT
        # TODO: Check this
        biobankCOVID = []
        '''
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
        '''
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
        biobankID = biobank['id']
        contactID = biobank.get('contact-id')
        longitude_raw = biobank.get('longitude')
        latitude_raw = biobank.get('latitude')
        cachedBiobankCoordinates = get_cached_biobank_coordinates(
            geocodingCache,
            biobankID,
            longitude_raw,
            latitude_raw,
            contactID,
        )

        # Override biobank location through config file:
        if biobank['name'] in config['Override biobank position'].keys():        
            biobankGeometryDict['coordinates'] = [float(i) for i in config['Override biobank position'][biobank['name']].split(',')]

        elif not pd.isna(biobank['longitude']) and not pd.isna(biobank['latitude']):
            dmsSymbols = ['º','°']
            try:
                #if '°' in biobank['longitude'] or '°' in biobank['latitude'] or '°' in biobank['longitude'] or '°' in biobank['latitude']: # Change to decimal coordinates
                if any(x in biobank['longitude'] for x in dmsSymbols) or any(x in biobank['latitude'] for x in dmsSymbols):
                    biobankGeometryDict['coordinates'] = [dms2dec(biobank['longitude']), dms2dec(biobank['latitude'])]
                elif any(i in biobank['longitude'] for i in ['N', 'E', 'S', 'W']) or any(i in biobank['latitude'] for i in ['N', 'E', 'S', 'W']):
                    biobankGeometryDict['coordinates'] = [dmm_to_dd(biobank['longitude']), dmm_to_dd(biobank['latitude'])]
                else:
                    biobankGeometryDict['coordinates'] = parse_decimal_coordinates(
                        biobank['longitude'],
                        biobank['latitude'],
                    )
                log.info(biobank['name'] + ': Coordinates provided')
            except (TypeError, ValueError) as exc:
                biobankGeometryDict = {}
                coordinates = None
                log.warning(
                    '%s: invalid stored coordinates longitude=%r latitude=%r (%s)',
                    biobank['name'],
                    biobank['longitude'],
                    biobank['latitude'],
                    exc,
                )
                if cachedBiobankCoordinates:
                    biobankGeometryDict['coordinates'] = cachedBiobankCoordinates
                    log.warning(
                        '%s: replacing invalid stored coordinates with cached address-based fallback coordinates (%s)',
                        biobank['name'],
                        format_coordinate_pair(cachedBiobankCoordinates),
                    )
                elif contactID:
                    lookForCoordinatesFeatures = ['address', 'zip', 'city','country']
                    coordinates = lookForCoordinates(
                        contactID,
                        personsContactsById,
                        lookForCoordinatesFeatures,
                        geocodingCache,
                        allowLiveLookup = False,
                    )
                    if coordinates:
                        biobankGeometryDict['coordinates'] = coordinates
                        cache_biobank_coordinates(
                            geocodingCache,
                            biobankID,
                            longitude_raw,
                            latitude_raw,
                            contactID,
                            coordinates,
                            source = 'query_cache',
                        )
                        log.warning(
                            '%s: replacing invalid stored coordinates with cached address-based geocoding result (%s)',
                            biobank['name'],
                            format_coordinate_pair(coordinates),
                        )
                if not biobankGeometryDict and contactID:
                    lookForCoordinatesFeatures = ['address', 'zip', 'city','country']
                    coordinates = lookForCoordinates(
                        contactID,
                        personsContactsById,
                        lookForCoordinatesFeatures,
                        geocodingCache,
                    )
                    if coordinates:
                        biobankGeometryDict['coordinates'] = coordinates
                        cache_biobank_coordinates(
                            geocodingCache,
                            biobankID,
                            longitude_raw,
                            latitude_raw,
                            contactID,
                            coordinates,
                            source = 'geocoding',
                        )
                        log.warning(
                            '%s: replacing invalid stored coordinates with address-based geocoding result (%s)',
                            biobank['name'],
                            format_coordinate_pair(coordinates),
                        )
                    else:
                        log.warning(biobank['name'] + ": geocoding failed ")
        #elif biobank['contact-_href']: #EMX2:
        elif contactID:
            if cachedBiobankCoordinates:
                biobankGeometryDict['coordinates'] = cachedBiobankCoordinates
                log.info('%s: coordinates restored from fallback cache', biobank['name'])
            else:
                lookForCoordinatesFeatures = ['address', 'zip', 'city','country']
                coordinates = lookForCoordinates(
                    contactID,
                    personsContactsById,
                    lookForCoordinatesFeatures,
                    geocodingCache,
                )
                if coordinates:
                    biobankGeometryDict['coordinates'] = coordinates
                    cache_biobank_coordinates(
                        geocodingCache,
                        biobankID,
                        longitude_raw,
                        latitude_raw,
                        contactID,
                        coordinates,
                        source = 'geocoding',
                    )
                    log.info(biobank['name'] + ": geocoding done ")
                else:
                    log.warning(biobank['name'] + ": geocoding failed ")
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
geocodingCache.close()
