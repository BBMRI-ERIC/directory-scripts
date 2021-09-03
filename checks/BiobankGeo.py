# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import os

# this is ugly and only for assertive programming
import __main__ 

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

from geopy.geocoders import Nominatim
from diskcache import Cache


class BiobankGeo(IPlugin):

	def check(self, dir, args):
		warnings = []
		log.info("Running geographical location checks (BiobankGeo)")
		# This is to be enabled for real runs.
		assert 'geocoding' in __main__.remoteCheckList
		if 'geocoding' in args.disableChecksRemote:
			geoCodingEnabled = False
		else:
			geoCodingEnabled = True

		cache_dir = 'data-check-cache/geolocator'
		if not os.path.exists(cache_dir):
			os.makedirs(cache_dir)
		cache = Cache(cache_dir)
		if 'geocoding' in args.purgeCaches:
			cache.clear()
		
		geocoords_pattern = '^-?\d+\.\d+$'
		geolocator = Nominatim(user_agent='Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0',timeout=15)

		for biobank in dir.getBiobanks():
			if 'latitude' in biobank and not re.search('^\s*$', biobank['latitude']) and 'longitude' in biobank and not re.search('^\s*$', biobank['longitude']):
				# we check before doing any convenience substitutions 
				if not re.search (geocoords_pattern, biobank['latitude']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "Invalid biobank latitude (should be a decimal number with period without any spaces or stray characters around - the surrounding quotes are added in this report): offending value '" + biobank['latitude'] + "'"))
				if not re.search (geocoords_pattern, biobank['longitude']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "Invalid biobank longitude (should be a decimal number with period without any spaces or stray characters around - the surrounding quotes are added in this report): offending value '" + biobank['longitude'] + "'"))
				# this is for convenience - if there are commas used instead of periods, we should still do the remaining checks
				biobank['latitude'] = re.sub(r',', r'.', biobank['latitude'])
				biobank['longitude'] = re.sub(r',', r'.', biobank['longitude'])
				if re.search (geocoords_pattern, biobank['latitude']) and re.search (geocoords_pattern, biobank['longitude']):
					if geoCodingEnabled:
						logMessage = "Checking reverse geocoding for " + biobank['latitude'] + ", " + biobank['longitude']
						try:
							loc_string = biobank['latitude'] + ", " + biobank['longitude']
							if loc_string in cache and cache[loc_string] != "":
								country_code = cache[loc_string]
							else:
								location = geolocator.reverse(loc_string, language='en')
								country_code = location.raw['address']['country_code']
								cache[loc_string] = country_code
							logMessage += " -> OK"
							if ((biobank['country']['id'] != "IARC" and biobank['country']['id'] != "EU") and country_code.upper() != biobank['country']['id'] and 
									not (country_code.upper() == "GB" and biobank['country']['id'] == "UK")):
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, "Geolocation of the biobank is likely outside of its country " + biobank['country']['id'] + "; biobank seems to be in " + country_code.upper() + f" based on geographical coordinates 'latitude'={biobank['latitude']} 'longitude'={biobank['longitude']}"))
						except Exception as e:
							logMessage += " -> failed (" + str(e) + ")"
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, "Reverse geocoding of the biobank  location failed (" + str(e) + ")"))
						log.info(logMessage)
			else:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, biobank['id'], DataCheckEntityType.BIOBANK, "Missing geographical coordinates ('latitude and/or 'longitude' attributes are empty)"))

		for collection in dir.getCollections():
			if 'latitude' in collection and not re.search('^\s*$', collection['latitude']) and 'longitude' in collection and not re.search('^\s*$', collection['longitude']):
				# we check before doing any convenience substitutions 
				if not re.search (geocoords_pattern, collection['latitude']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Invalid collection latitude (should be a decimal number with period without any spaces or stray characters around - the surrounding quotes are added in this report): offending value '" + collection['latitude'] + "'"))
				if not re.search (geocoords_pattern, collection['longitude']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Invalid collection longitude (should be a decimal number with period without any spaces or stray characters around - the surrounding quotes are added in this report): offending value '" + collection['longitude'] + "'"))
				# this is for convenience - if there are commas used instead of periods, we should still do the remaining checks
				collection['latitude'] = re.sub(r',', r'.', collection['latitude'])
				collection['longitude'] = re.sub(r',', r'.', collection['longitude'])
				if re.search (geocoords_pattern, collection['latitude']) and re.search (geocoords_pattern, collection['longitude']):
					if geoCodingEnabled:
						logMessage = "Checking reverse geocoding for " + collection['latitude'] + ", " + collection['longitude']
						try:
							loc_string = collection['latitude'] + ", " + collection['longitude']
							if loc_string in cache and cache[loc_string] != "":
								country_code = cache[loc_string]
							else:
								location = geolocator.reverse(loc_string, language='en')
								country_code = location.raw['address']['country_code']
								cache[loc_string] = country_code
							logMessage += " -> OK"
							biobankId = dir.getCollectionBiobankId(collection['id'])
							biobank = dir.getBiobankById(biobankId)
							if ((biobank['country']['id'] != "IARC" and biobank['country']['id'] != "EU") and country_code.upper() != biobank['country']['id'] and 
									not (country_code.upper() == "GB" and biobank['country']['id'] == "UK")):
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "Geolocation of the collection is likely outside of its country " + collection['country']['id'] + "; collection seems to be in " + country_code.upper() + f" based on geographical coordinates 'latitude'={collection['latitude']} 'longitude'={collection['longitude']}"))
						except Exception as e:
							logMessage += " -> failed (" + str(e) + ")"
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "Reverse geocoding of the collection  location failed (" + str(e) + ")"))
						log.info(logMessage)

		cache.close()
		return warnings
