import re
import logging as log

# this is ugly and only for assertive programming
import __main__ 

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

from geopy.geocoders import Nominatim

class BiobankGeo(IPlugin):
	def check(self, dir, args):
		geolocator = Nominatim(user_agent='Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0')
		warnings = []
		log.info("Running geographical location checks (BiobankGeo)")
		# This is to be enabled for real runs.
		assert 'geocoding' in __main__.remoteCheckList
		if 'geocoding' in args.disableChecksRemote:
			geoCodingEnabled = False
		else:
			geoCodingEnabled = True
		for biobank in dir.getBiobanks():
			if 'latitude' in biobank and not re.search('^\s*$', biobank['latitude']) and 'longitude' in biobank and not re.search('^\s*$', biobank['longitude']):
				if re.search ('^-?\d+\.\d*$', biobank['latitude']) and re.search ('^-?\d+\.\d*$', biobank['longitude']):
					logMessage = ""
					if geoCodingEnabled:
						logMessage += "Checking reverse geocoding for " + biobank['latitude'] + ", " + biobank['longitude']
						try:
							location = geolocator.reverse(biobank['latitude'] + ", " + biobank['longitude'], language='en')
							country_code = location.raw['address']['country_code']
							logMessage += " -> OK"
							if (biobank['country']['id'] != "IARC" and country_code.upper() != biobank['country']['id'] and 
									not (country_code.upper() == "GB" and biobank['country']['id'] == "UK")):
								warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Geolocation of the biobank is likely outside of its country; biobank seems to be in " + country_code.upper())
								warnings.append(warning)
						except Exception as e:
							logMessage += " -> failed (" + str(e) + ")"
							warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Reverse geocoding of the biobank  location failed (" + str(e) + ")")
							warnings.append(warning)
					log.info(logMessage)

				else:
					if not re.search ('^-?\d+\.\d*$', biobank['latitude']):
						warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Invalid biobank latitude: " + biobank['latitude'])
						warnings.append(warning)
					if not re.search ('^-?\d+\.\d*$', biobank['longitude']):
						warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Invalid biobank longitude: " + biobank['longitude'])
						warnings.append(warning)
			else:
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, biobank['id'], "Missing geographical coordinates")
				warnings.append(warning)


		return warnings
