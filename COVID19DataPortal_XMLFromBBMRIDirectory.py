#!/usr/local/bin/python3.6
"""
Script for creating XML for COVID19DataPortal from Directory collections
"""

#############
## Imports ##
#############

# External
import pprint
import argparse
import xml.etree.ElementTree as ET

# Internal
from directory import Directory

cachesList = ['directory', 'geocoding']

#####################
## Parse arguments ##
#####################

parser = argparse.ArgumentParser()
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (directory and geocoding)')
parser.add_argument('-o', '--outName', dest='outNameExcludedBiobanks', default='bbmri-directory-missing-COVID19DataPortal-Values.tsv', help='Output file name')
parser.add_argument('-x', '--outNameXML', dest='outXML', default='bbmriDirectory_Covid19DataPortal.xml', help='Output XML name')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-p', '--password', dest='password', help='Password of the account used to login to the Directory')
parser.add_argument('-u', '--username', dest='username', help='Username of the account used to login to the Directory')
parser.add_argument('-P', '--package', dest='package', default='eu_bbmri_eric', help='MOLGENIS Package that contains the data (default eu_bbmri_eric).')

parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
args = parser.parse_args()

# Open output tsv file (did not add the path as option, so it always writes in the working directory):
outFile = open(args.outNameExcludedBiobanks, 'w')


# Get info from Directory
pp = pprint.PrettyPrinter(indent=4)
if args.username is not None and args.password is not None:
    dir = Directory(schema=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp, username=args.username, password=args.password)
else:
    dir = Directory(schema=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)


### Functions

# From https://stackoverflow.com/questions/749796/pretty-printing-xml-in-python/38573964#38573964
def prettify(element, indent='  '):
    queue = [(0, element)]  # (level, element)
    while queue:
        level, element = queue.pop(0)
        children = [(level + 1, child) for child in list(element)]
        if children:
            element.text = '\n' + indent * (level+1)  # for child open
        if queue:
            element.tail = '\n' + indent * queue[0][0]  # for sibling open
        else:
            element.tail = '\n' + indent * (level-1)  # for parent close
        queue[0:0] = children  # prepend so children come before siblings

### Main

# XML Level 1 - Database
xml_doc = ET.Element('database')

# Inside level 1
ET.SubElement(xml_doc, 'name').text = 'BBMRI-ERIC Directory'
ET.SubElement(xml_doc, 'description').text = 'The BBMRI-ERIC Directory is a tool that collects and makes available information about biobanks throughout Europe that are willing to share their data and/or samples, and to collaborate with other research groups. The Directory is one of the services offered by BBMRI-ERIC Common Services for IT (CS-IT) to the global biobank community and was created in collaboration with the BBMRI National Nodes and partners. The Directory provides a central listing of biobanks and their collections in the BBMRI-ERIC member states. For researchers, the Directory offers a means of finding samples and data, while for biobanks it offers a platform to share the existence of their holdings and services and to connect with researchers interested in them.'

# Level 2 - entries
entries = ET.SubElement(xml_doc, 'entries')

# Inside level 2
# Level 3 - entry

### For collection in colls
counter = 0
for coll in dir.getCollections():
    # For the moment capability collections are not included:
    if 'Covid-19' in str(coll['categories']) and 'Ability to ' not in coll['name']:
                            
        # Inside level 3
        try:
            colldescrip = coll['description'].strip().replace('\n', ' ')
        except KeyError:
            # For the moment, only collections with values for mandatory fields are going to be included. If the collection is excluded its country, biobank and name are written in a separate file:
            outFile.write(coll['country']['id'] +'\t'+ coll['biobank']['name'] +'\t'+ coll['name'] +'\n')
            continue

        try:
            colldate = coll['timestamp']
        except KeyError:
            # For the moment, only collections with values for mandatory fields are going to be included. If the collection is excluded its country, biobank and name are written in a separate file:
            outFile.write(coll['country']['id'] +'\t'+ coll['biobank']['name'] +'\t'+ coll['name'] +'\n')
            continue

        try:
            collurl = coll['url']
        except KeyError:
            # For the moment, only collections with values for mandatory fields are going to be included. If the collection is excluded its country, biobank and name are written in a separate file:
            try:
                collurl = coll['biobank']['url']
            except KeyError:
                outFile.write(coll['country']['id'] +'\t'+ coll['biobank']['name'] +'\t'+ coll['name'] +'\n')
                continue

        counter += 1
        entry = ET.SubElement(entries, 'entry', id=coll['id'])
        ET.SubElement(entry, 'name').text = coll['name']
        ET.SubElement(entry, 'description').text = colldescrip
        dates = ET.SubElement(entry, 'dates')
        ET.SubElement(dates, 'date', type='submission').text = colldate.split('T')[0]
        ET.SubElement(entry, 'repository').text = coll['biobank']['name']
        # EG-A: from the COVID19DataPortal documentation, I understand this as a external link, thus this is the one I am including here.
        ET.SubElement(entry, 'full_dataset_link').text = collurl
        #ET.SubElement(entry, 'full_dataset_link').text = 'https://directory.bbmri-eric.eu/#/collection/' + coll['id']
        
ET.SubElement(xml_doc, 'entry_count').text = str(counter)
ET.SubElement(xml_doc, 'keywords').text = 'biobank,samples,bbmri-directory'
ET.SubElement(xml_doc, 'url').text = 'https://directory.bbmri-eric.eu/'


# Write XML output
prettify(xml_doc)

tree = ET.ElementTree(xml_doc)
tree.write(args.outXML, encoding='UTF-8', xml_declaration=True)