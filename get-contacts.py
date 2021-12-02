#!/usr/bin/python3
# vim:ts=8:sw=8:sts=8:tw=0:noet

# This is an exporter of contact to collection mapping, to be used for invitations into the Negotiator

from typing import List

import pprint
import re
import string
import argparse
import logging as log
import time
from typing import List
import os.path
from nameparser import HumanName

import xlsxwriter

from directory import Directory
from nncontacts import NNContacts

cachesList = ['directory', 'emails', 'geocoding', 'URLs']

# if some nodes don't want to get the invitations
#turnedOffNNs = {'UK'}
turnedOffNNs = {}

pp = pprint.PrettyPrinter(indent=4)

class ExtendAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)

parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', nargs=1, help='output of results into XLSX with filename provided as parameter')
parser.add_argument('-N', '--output-no-stdout', dest='nostdout', action='store_true', help='no output of results into stdout (default: enabled)')
parser.add_argument('-n', '--negotiator-invitation', dest='negotiator', action='store_true', help='output compatible with Negotiator invitation system')
parser.add_argument('-e', '--unique-emails', dest='emails', action='store_true', help='sort contacts by unique emails')
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='disable particular long remote checks')
parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
args = parser.parse_args()

if args.debug:
	log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
elif args.verbose:
	log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
else:
	log.basicConfig(format="%(levelname)s: %(message)s")


if args.negotiator and not args.outputXLSX:
	raise Exception('Negotiator-compatible output must produce Excel output, hence -X or --output-XLSX must be provided, too')


# Main code

dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

if args.negotiator:
	contactsToCollections = {}
	collectionsToContacts = {}
	contactsToEmails = {}

	for collection in dir.getCollections():
		log.debug("Analyzing collection " + collection['id'])
		collectionId = collection['id']
		biobankId = dir.getCollectionBiobankId(collection['id'])
		biobank = dir.getBiobankById(biobankId)
		if 'contact' in collection:
			contactId = collection['contact']['id']
			contactEmail = collection['contact']['email']
			if contactId not in contactsToEmails:
				contactsToEmails[contactId] = contactEmail
			else:
				if(contactsToEmails[contactId] != contactEmail):
					log.error("Contact mismatch for %s: previously provided <%s>, now provided <%s>"%(contactId, contactsToEmails[contactId], contactEmail))
			log.debug("   collection %s maps to %s <%s>"%(collectionId, contactId, contactEmail))
			if contactId in contactsToCollections:
				contactsToCollections[contactId].append(collectionId)
			else:
				contactsToCollections[contactId] = [collectionId]
			assert collectionId not in collectionsToContacts
			collectionsToContacts[collectionId] = contactId
		else:
			log.warning("Collection %s does not provide contact information!"%(collectionId))


	def printCollectionStdout(collectionList : List, headerStr : str):
		print(headerStr + " - " + str(len(collectionList)) + " collections")
		for collection in collectionList:
			biobankId = dir.getCollectionBiobankId(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			print("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " +  biobankId + " - " + biobank['name'])

	if not args.nostdout:
		for c in contactsToCollections:
			print("%s\t%s\t%s"%(c, contactsToEmails[c], ",".join(contactsToCollections[c])))

	if args.outputXLSX is not None:
		log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
		workbook = xlsxwriter.Workbook(args.outputXLSX[0])
		worksheet = workbook.add_worksheet('collection_to_contact')
		worksheet_row = 0
		worksheet.set_column(0,0, 120)
		worksheet.set_column(1,1, 60)
		worksheet.set_column(2,2, 40)
		for c in collectionsToContacts:
			worksheet.write_string(worksheet_row, 0, c)
			worksheet.write_string(worksheet_row, 1, collectionsToContacts[c])
			worksheet.write_string(worksheet_row, 2, contactsToEmails[collectionsToContacts[c]])
			worksheet_row += 1
		worksheet = workbook.add_worksheet('contact_to_collection')
		worksheet_row = 0
		wrapped_cell_format = workbook.add_format()
		wrapped_cell_format.set_text_wrap()
		worksheet.set_column(0,0, 60)
		worksheet.set_column(1,1, 40)
		worksheet.set_column(2,2, 120)
		worksheet.set_column(3,3, 20)
		worksheet.set_column(4,4, 120)
		for c in contactsToCollections:
			worksheet.write_string(worksheet_row, 0, c)
			worksheet.write_string(worksheet_row, 1, contactsToEmails[c])
			worksheet.write_string(worksheet_row, 2, "\n".join(contactsToCollections[c]), wrapped_cell_format)
			correspondingNNs = {dir.getBiobankNN(dir.getCollectionBiobankId(collection)) for collection in contactsToCollections[c]}
			if len(correspondingNNs) > 1:
				log.warning("Multiple national nodes found for contact %s: %s"%(c, ",".join(correspondingNNs)))
			elif len(correspondingNNs) == 1: 
				NN = correspondingNNs.pop()
				if (NN not in turnedOffNNs):
					if (NN in NNContacts.NNtoEmails):
						additionalContacts = NNContacts.NNtoEmails[NN]
						NN = "BBMRI." + NN.lower()
					else:
						additionalContacts = "petr.holub@bbmri-eric.eu"
						NN = "BBMRI-nonmember." + NN.lower()
					worksheet.write_string(worksheet_row, 3, NN)
					worksheet.write_string(worksheet_row, 4, additionalContacts.replace(",",";"))
			else:
				log.warning("No national nodes found for contact %s"%(c))
			worksheet_row += 1
		workbook.close()

else:
	contactsToCollections = {}
	contactsToBiobanks = {}
	contactsToEmails = {}
	contactsToNames = {}
	activeContacts = set()

	def initContact (contactId : str):
		assert contactId not in activeContacts
		activeContacts.add(contactId)
		contact = dir.getContact(contactId)
		contactsToEmails[contactId] = contact['email']
		name = " ".join(filter(None,[contact.get('title_before_name'), contact.get('first_name'), contact.get('last_name'), contact.get('title_after_name')]))
		#name = name.translate(str.maketrans('', '', string.punctuation))
		name = name.translate(str.maketrans('', '', '@'))
		name = HumanName(name.lower().strip())
		name.capitalize()
		if re.search('^(\w\.)+$', name.first):
			name.first = name.first.upper()
		contactsToNames[contactId] = name.__str__()


	for collection in dir.getCollections():
		log.debug("Analyzing collection " + collection['id'])
		collectionId = collection['id']
		biobankId = dir.getCollectionBiobankId(collection['id'])
		biobank = dir.getBiobankById(biobankId)
		if 'contact' in collection:
			contactId = collection['contact']['id']
			if contactId not in activeContacts:
				initContact(contactId)
			log.debug("   collection %s maps to %s <%s>"%(collectionId, contactsToNames[contactId], contactsToEmails[contactId]))
			if contactId in contactsToCollections:
				contactsToCollections[contactId].append(collectionId)
			else:
				contactsToCollections[contactId] = [collectionId]
		else:
			log.warning("Collection %s does not provide contact information!"%(collectionId))

	for biobank in dir.getBiobanks():
		log.debug("Analyzing biobank " + biobank['id'])
		biobankId = biobank['id']
		if 'contact' in biobank:
			contactId = biobank['contact']['id']
			if contactId not in activeContacts:
				initContact(contactId)
			log.debug("   biobank %s maps to %s <%s>"%(biobankId, contactsToNames[contactId], contactsToEmails[contactId]))
			if contactId in contactsToBiobanks:
				contactsToBiobanks[contactId].append(biobankId)
			else:
				contactsToBiobanks[contactId] = [biobankId]
		else:
			log.warning("Biobank %s does not provide contact information!"%(biobankId))

	uniqueEmails = {}
	emailToNames = {}
	for c in activeContacts:
		email = contactsToEmails[c]
		if email in uniqueEmails:
			uniqueEmails[email].add(c)
			if emailToNames[email] != contactsToNames[c]:
				log.warning("Conflicting name found for the same email %s: %s, using existing %s"%(email,contactsToNames[c],emailToNames[email]))
		else:
			uniqueEmails[email] = {c}
			emailToNames[email] = contactsToNames[c]
			

	if not args.nostdout:
		if args.emails:
			for email in uniqueEmails:
				biobanks = set()
				collections = set()
				for contact in uniqueEmails[email]:
					if contact in contactsToBiobanks:
						biobanks.update(contactsToBiobanks[contact])
					if contact in contactsToCollections:
						collections.update(contactsToCollections[contact])
				print("%s\t%s\t%s\t%s\t%s"%(email, emailToNames[email], ",".join(uniqueEmails[email]), ",".join(biobanks), ",".join(collections)))
		else:
			for c in activeContacts:
				print("%s\t%s\t%s\t%s\t%s"%(c, contactsToEmails[c], contactsToNames[c], ",".join(contactsToCollections[c]) if c in contactsToCollections else "", ",".join(contactsToBiobanks[c]) if c in contactsToBiobanks else ""))

