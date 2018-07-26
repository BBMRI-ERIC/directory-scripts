import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

from geopy.geocoders import Nominatim

class BiobankGeo(IPlugin):
	def check(self, dir, args):
		geolocator = Nominatim()
		warnings = []
		log.info("Running geographical location checks (BiobankGeo)")
		# This is to be enabled for real runs.
		if args.distableChecksAllRemote or (args.disableChecksRemote != None and 'geocoding' in args.disableChecksRemote):
			geoCodingEnabled = False
		else:
			geoCodingEnabled = True
		for biobank in dir.getBiobanks():
			if 'latitude' in biobank and not re.search('^\s*$', biobank['latitude']) and 'longitude' in biobank and not re.search('^\s*$', biobank['longitude']):
				if re.search ('^-?\d+\.\d*$', biobank['latitude']) and re.search ('^-?\d+\.\d*$', biobank['longitude']):
					if geoCodingEnabled:
						log.info("Checking reverse geocoding for " + biobank['latitude'] + ", " + biobank['longitude'], end=' ')
						try:
							location = geolocator.reverse(biobank['latitude'] + ", " + biobank['longitude'])
							country_code = location.raw['address']['country_code']
							log.info(" -> OK")
							if (biobank['country']['id'] != "IARC" and country_code.upper() != biobank['country']['id'] and 
									not (country_code.upper() == "GB" and biobank['country']['id'] == "UK")):
								warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Geolocation of the biobank is likely outside of its country; biobank seems to be in " + country_code.upper())
								warnings.append(warning)
						except Exception as e:
							log.info(" -> failed")
							warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Reverse geocoding of the biobank  location failed (" + str(e) + ")")
							warnings.append(warning)

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
