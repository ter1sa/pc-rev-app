"""
Author: SOURAV S BHOWMICK
Desc: Procedures to read data from DBLP.
"""

from urllib.request import urlopen
import requests
# import accents
from unidecode import unidecode
import xml.etree.ElementTree as ETree
from collections import Counter
from lxml import etree
import time
import os
import pandas as pd
# import reviewerStore as SancusDB
# import ClosetIO
import gc


"""
Desc: Convert to XML address of a DBLP web page
Input: Web address of a DBLP author
Output: XML file location of the page.
"""


def xmlifyAdd(add):

    style = 'html'
    if style in add:  # if the URL format contains .html
        xml_add = add.replace('html', 'xml')
        loc = xml_add.find('pers/')  # old URL
        if loc > 0:
            loc = loc + len('pers/')
            xml_add = xml_add[:loc] + 'xx/' + xml_add[loc:]
    else:  # old URL
        xml_add = add.replace('hd', 'xx')
        xml_add = xml_add + ".xml"

    return xml_add


"""
Desc: Connect to the XML version of a DBLP page
Input: Web address of XML DBLP page
Output: If successful, return the entire XML file string
"""


def connectToDBLPPage(add):

    my_file = ''
    request = requests.get(add)
    if request.status_code == 200:
        print('Web page', add,  'exists.')
        f = urlopen(add)
        my_file = f.read()
    else:
        print('Web page', add, 'does not exist!')

    return my_file


"""
Desc: Extract all coauthor information of a DBLP author (excluding those papers in the white list).
Input: XML file string, white list details
Output: Name of author, set of names in DBLP, aggregated dictionary coauthor name -> list of (year, frequency), 
coauthor name -> total frequency.
 Set of all coauthors. Set of all years of publications
"""


def readAuthorDBLP(xml_file, title_year_dict, title_venue_dict, dblp_url_dict, r_dblp):

    cauthor_year_dict = dict()  # Dictionary coauthor name -> list of years of publication
    cauthor_hist_dict = dict()  # aggregated dictionary coauthor name -> list of (year, frequency)
    cauthor_freq_dict = dict()  # Dictionary coauthor name -> total frequency
    temp_author_set = set()  # set of co-authors of an author
    year_set = set()  # set of all years of publications
    coauthor_set = set()  # Set of all co-authors. Some co-authors may appear multiple times due to homonyms.
    affl_set = set()  # Stores affiliations of the author
    person_name_set = set()  # set of DBLP names of the person

    root = ETree.fromstring(xml_file)
    records = root.findall(".//r")  # Extract all r elements in DBLP
    person_file_name = (root.attrib['name']).lower()  # Get name of the author in DBLP
    person_file_name = unidecode(person_file_name)
    author = root.find(".//person")  # Get the first person element (contains affiliation information)
    if author is None:
        print("XML content for ", person_file_name, "is missing!")
        return person_file_name, person_name_set, cauthor_hist_dict, cauthor_freq_dict, \
            year_set, coauthor_set, affl_set

    # The person element contains notes elements (affiliation info)
    notes = list(author)
    for note in notes:  # Get affiliations
        if note.tag == "note":
            if note.attrib['type'] == 'affiliation':
                affl = note.text.split(',')[0]
                affl_set.add(affl.lower())
        if note.tag == "author":
            person_name_set.add(unidecode(note.text.lower()))

    print("Name identifier in DBLP: ", person_file_name)
    print("Set of all names: ", person_name_set)
    print("Affiliations: ", affl_set)

    for record in records:  # scan all r elements in the XML
        # list of papers
        papers = list(record)
        for paper in papers:
            white_list_match = 0  # set to 1 if a paper title matches a white paper
            false_positive_flag = 0  # set to 1 if a paper is erroneously assigned to the author
            year_flag = 'unseen'  # set to seen if year element is encountered
            # authors, year, etc. of a paper
            info = list(paper)
            for item in info:
                if len(title_venue_dict) > 0:  # white list is available
                    if item.tag == "title":
                        if item.text in title_venue_dict.keys():  # check if the paper is in white list
                            print("White paper detected:", item.text)
                            white_list_match = 1
                if item.tag == "author":
                    temp_author_set.add(unidecode(item.text.lower()))
                if item.tag == "year":
                    year_flag = 'seen'  # year element is visited
                    a_year = item.text
                if item.tag == "url":
                    # false positive article
                    if r_dblp in dblp_url_dict.keys() and item.text in dblp_url_dict[r_dblp]:
                        print("Paper to exclude due to false positive:", item.text)
                        false_positive_flag = 1
            # only consider paper information if it is not in the white paper list or false positive list
            if white_list_match == 0 and year_flag == 'seen' and false_positive_flag == 0:
                year_set.add(a_year)
                for author in temp_author_set:  # generate set of co-authors
                    coauthor_set.add(unidecode(author.lower()))
                    if author not in cauthor_year_dict.keys():  # generate co-authorship history dictionary
                        cauthor_year_dict[author] = [a_year]
                    else:
                        cauthor_year_dict[author].append(a_year)
            temp_author_set.clear()

    """ Generate aggregated temporal history of collaboration"""
    for key in cauthor_year_dict:
        agg_year = Counter(cauthor_year_dict[key])
        freq = 0
        for (y, c) in agg_year.items():
            freq = freq + c
            if key not in cauthor_hist_dict.keys():
                cauthor_hist_dict[key] = [(y, c)]
            else:
                cauthor_hist_dict[key].append((y, c))
        cauthor_freq_dict[key] = freq

    return person_file_name, person_name_set, cauthor_hist_dict, cauthor_freq_dict, year_set, coauthor_set, affl_set


"""
Desc: Extract quality information of a reviewer using DBLP
Input: XML file, quality venue set
Output: Quality venue statistics.
"""


def getQualityVenuePublications(xml_file, quality_venue_set):

    venue_year_dict = dict()  # Dictionary venue name -> list of years of publication
    venue_hist_dict = dict()  # aggregated dictionary venue name -> list of (year, frequency)
    venue_freq_dict = dict()  # Dictionary venue name -> total frequency
    year_set = set()  # set of all years of quality-venue publications

    root = ETree.fromstring(xml_file)
    records = root.findall(".//r")  # Extract all r elements in DBLP
    person_file_name = (root.attrib['name']).lower()  # Get name of the author in DBLP
    person_file_name = unidecode(person_file_name)

    author = root.find(".//person")  # Get the first person element (contains affiliation information)
    if author is None:
        print("XML content for ", person_file_name, "is missing!")
        return person_file_name, venue_hist_dict, venue_freq_dict, year_set

    print("Name identifier in DBLP: ", person_file_name)

    for record in records:  # scan all r elements in the XML
        papers = list(record)
        for paper in papers:
            quality_venue_match = 0  # set to 1 when there is a match
            year_flag = 'unseen'  # set to seen if year element is encountered
            info = list(paper)
            for item in info:
                if item.tag == "booktitle":
                    if item.text in quality_venue_set:  # check if the paper is in venue list
                        quality_venue_match = 1
                        venue_title = item.text
                if item.tag == "journal":
                    if item.text in quality_venue_set:  # check if the paper is in venue list
                        quality_venue_match = 1
                        venue_title = item.text
                if item.tag == "year":
                    year_flag = 'seen'  # year element is visited
                    a_year = item.text
            # only consider paper information if it is in quality venue
            if quality_venue_match == 1 and year_flag == 'seen':
                year_set.add(a_year)
                if venue_title not in venue_year_dict.keys():  # generate quality venue history dictionary
                    venue_year_dict[venue_title] = [a_year]
                else:
                    venue_year_dict[venue_title].append(a_year)

    """ Generate aggregated temporal history of quality venue publications"""
    for key in venue_year_dict:
        agg_year = Counter(venue_year_dict[key])
        freq = 0
        for (y, c) in agg_year.items():
            freq = freq + c
            if key not in venue_hist_dict.keys():
                venue_hist_dict[key] = [(y, c)]
            else:
                venue_hist_dict[key].append((y, c))
        venue_freq_dict[key] = freq

    return person_file_name, venue_hist_dict, venue_freq_dict, year_set


"""
Desc: Extract author information for disambiguating a DBLP page. The input page is a disambiguation page in DBLP.
"""


def readDisambDBLP(xml_file):

    temp_author_set = set()  # set of co-authors of an author
    coauthor_set = set()  # Set of all co-authors. Some co-authors may appear multiple times due to homonyms.
    affl_set = set()  # Stores affiliations of the author
    person_name_set = set()  # set of DBLP names of the person
    title_year_dict = dict()  # title->year map
    title_coauthor_dict = dict()  # title->co-author set map

    root = ETree.fromstring(xml_file)
    records = root.findall(".//r")  # Extract all r elements in DBLP
    person_file_name = (root.attrib['name']).lower()  # Get name of the author in DBLP
    person_file_name = unidecode(person_file_name)
    author = root.find(".//person")  # Get the first person element (contains affiliation information)
    if author is None:
        print("XML content for ", person_file_name, "is missing!")
        return person_file_name, person_name_set, coauthor_set, affl_set, title_year_dict, title_coauthor_dict

    notes = list(author)
    for note in notes:  # Get affiliations
        if note.tag == "note":
            if note.attrib['type'] == 'affiliation':
                affl_set.add(note.text)
        if note.tag == "author":
            person_name_set.add(unidecode(note.text.lower()))

    print("Name identifier in DBLP: ", person_file_name)
    print("Set of all names: ", person_name_set)
    print("Affiliations: ", affl_set)

    for record in records:  # scan all r elements in the XML
        papers = list(record)
        for paper in papers:
            info = list(paper)
            for item in info:
                if item.tag == "title":
                    p_title = str(item.text).replace('.', '').replace('"', '').lower()
                if item.tag == "author":
                    temp_author_set.add(unidecode(item.text.lower()))
                if item.tag == "year":
                    a_year = item.text
            for author in temp_author_set:  # generate set of co-authors
                coauthor_set.add(unidecode(author.lower()))
                if p_title not in title_coauthor_dict.keys():  # create title-> authors map
                    title_coauthor_dict[p_title] = {unidecode(author.lower())}
                else:
                    title_coauthor_dict[p_title].add(unidecode(author.lower()))
            if p_title not in title_year_dict.keys():  # create title -> year of pub map
                title_year_dict[p_title] = {a_year}
            else:
                title_year_dict[p_title].add(a_year)
            temp_author_set.clear()

    return person_file_name, person_name_set, coauthor_set, affl_set, title_year_dict, title_coauthor_dict


"""
Desc: Extract set of affiliation information and DBLP names of a homonymous author name.
"""


def readDBLPHomonyms(xml_file):

    id_affl_dict = dict()  # dblp id->affiliation

    root = ETree.fromstring(xml_file)
    homonyms = root.findall(".//person")  # Get all homonym persons

    for homonym in homonyms:
        affl_set = set()
        info = list(homonym)
        for data in info:
            if data.tag == "author":
                dblp_name = data.text.lower()
            if data.tag == "note":
                if data.attrib['type'] == 'affiliation':
                    affl_set.add(data.text.lower())
        id_affl_dict[dblp_name] = affl_set

    return id_affl_dict


"""
Desc: Create a dblp data iterator.
"""


def context_iter(dblp_path):

    """Create a dblp data iterator of (event, element) pairs for processing"""
    return etree.iterparse(source=dblp_path, dtd_validation=True, load_dtd=True)  # required dtd


"""
Desc: Retrieve all authors in DBLP and stores them in SANCUS DB.
"""


def getDBLPAuthors():

    start_time = time.time()  # to measure running time of the program
    dblp_path = os.path.join(os.getcwd(), 'DataStore', 'dblp.xml')
    author_set = set()
    count = 0
    pub_type = ["article", "inproceedings", "book", "incollection"]

    print("Reading authors from DBLP file..")
    try:
        context_iter(dblp_path)
        for _, elem in context_iter(dblp_path):
            if elem.tag in pub_type:
                for sub in elem:
                    if sub.tag == 'author':
                        author_set.add(sub.text)
                        count = count + 1
    except IOError:
        exit()

    print("Number of distinct authors:", len(author_set))
    print("Inserting into SANCUS DB...")
    # SancusDB.insertDBLPAuthors(author_set)
    print("Insertion completed.")
    print("\n----Time take to execute the program: %s seconds -----" % round((time.time() - start_time), 3))


"""
Desc: Retrieve authors in DBLP who has published in specified venues and on specified topics.
"""


def searchDBLPAuthors(key_word, venue_set):

    dblp_path = os.path.join(os.getcwd(), 'DataStore', 'dblp.xml')
    title_authors_dict = dict()
    title_venue_dict = dict()
    pub_type = ["article", "inproceedings"]

    print("Reading authors from DBLP file..")
    try:
        context_iter(dblp_path)
        for _, elem in context_iter(dblp_path):
            title_match = 0
            quality_venue_match = 0
            p_title = ''
            venue_title = ''
            author_set = set()
            if elem.tag in pub_type:
                for sub in elem:
                    if sub.tag == "booktitle":
                        if sub.text in venue_set:  # check if the paper is in venue list
                            quality_venue_match = 1
                            venue_title = sub.text
                    if sub.tag == "journal":
                        if sub.text in venue_set:  # check if the paper is in venue list
                            quality_venue_match = 1
                            venue_title = sub.text
                    if sub.tag == 'author':
                        author_set.add(sub.text)
                    if sub.tag == "title" and sub.text is not None:
                        if key_word in sub.text.lower():
                            title_match = 1
                            p_title = sub.text
            if title_match == 1 and quality_venue_match == 1 and len(author_set) > 0:
                if p_title not in title_authors_dict.keys():
                    title_authors_dict[p_title] = author_set
                if p_title not in title_venue_dict.keys():
                    title_venue_dict[p_title] = venue_title
            else:
                author_set.clear()
    except IOError:
        exit()

    return title_venue_dict, title_authors_dict


"""
Desc: Retrieve homonymous authors and their affiliations from DBLP
"""


def retrieveDBLPHomonymousAuthorsOld():

    dblp_path = os.path.join(os.getcwd(), 'DataStore', 'dblp.xml')
    hom_author_set = set()
    pub_type = ["article", "inproceedings", "book", "incollection"]

    print("Reading authors from DBLP file..")
    try:
        context_iter(dblp_path)
        for _, elem in context_iter(dblp_path):
            if elem.tag in pub_type:
                for sub in elem:
                    if sub.tag == 'author':
                        word_list = sub.text.split()
                        last_item = word_list[-1]
                        if last_item.isnumeric():  # check if the last word is a numeric value
                            hom_author_set.add(sub.text.lower())

    except IOError:
        exit()
    print("No. of homonymous authors:", len(hom_author_set))

    return hom_author_set


"""
Desc: Retrieve homonymous authors and their affiliations from DBLP
"""


def retrieveDBLPHomonymousAuthors():

    dblp_path = os.path.join(os.getcwd(), 'DataStore', 'dblp.xml')
    hom_author_set = set()
    pub_type = ["article", "inproceedings", "book", "incollection"]

    print("Reading authors from DBLP file..")

    count = 0
    with open(dblp_path, "rb") as infile:
        for event, elem in etree.iterparse(infile, load_dtd=True, dtd_validation=True, events=("end",)):

            if elem.tag in pub_type:
                for sub in elem:
                    if sub.tag == 'author':
                        word_list = sub.text.split()
                        last_item = word_list[-1]
                        if last_item.isnumeric():  # check if the last word is a numeric value
                            hom_author_set.add(sub.text.lower())  # address lower case issue

            if 'key' in elem.attrib: elem.clear()  # reduces memory footprint

            count += 1
            if count % 1000000 == 0:
                print('%d events ....' % count)
                gc.collect()

    print('done after %d events.' % count)
    print('collected %d names.' % len(hom_author_set))

    return hom_author_set


"""
Desc: Retrieve title and authors of a conference venue.
"""


def retrieveProceedingsFromDBLP(venue, year):

    dblp_path = os.path.join(os.getcwd(), 'DataStore', 'dblp.xml')
    title_authors_dict = dict()
    pub_type = ["article", "inproceedings"]

    print("Reading data from DBLP file..")
    try:
        context_iter(dblp_path)
        for _, elem in context_iter(dblp_path):
            p_title = ''
            venue_match = 0
            year_match = 0
            author_set = set()
            if elem.tag in pub_type:
                for sub in elem:
                    if sub.tag == "booktitle":
                        if sub.text == venue:  # check if the paper is in venue list
                            venue_match = 1
                    if sub.tag == 'author':
                        author_set.add(sub.text)
                    if sub.tag == "title" and sub.text is not None:
                        p_title = sub.text
                    if sub.tag == 'year' and sub.text == year:
                        year_match = 1
            if venue_match == 1 and year_match == 1 and len(author_set) > 0:
                if p_title not in title_authors_dict.keys():
                    title_authors_dict[p_title] = author_set
            else:
                author_set.clear()
    except IOError:
        exit()

    return title_authors_dict


"""
Desc: Procedure to search for potential PC members in DBLP  
"""


def searchDBLPforPC(key_word, conf_name, input_dir, output_dir, venue_file_name):

    author_venue_dict = dict()
    author_count_dict = dict()
    venue_file = os.path.join(os.getcwd(), 'Venues', conf_name, input_dir, venue_file_name)
    venue_df = pd.read_excel(venue_file)
    venue_set = set(venue_df['Venue'])
    print("Set of quality venues: ", venue_set)

    title_venue_dict, title_authors_dict = searchDBLPAuthors(key_word, venue_set)
    print("No. of articles found:", len(title_venue_dict))
    for title in title_authors_dict.keys():
        for author in title_authors_dict[title]:
            if author not in author_venue_dict.keys():
                author_venue_dict[author] = {title_venue_dict[title]}
            else:
                author_venue_dict[author].add(title_venue_dict[title])
            if author not in author_count_dict.keys():
                author_count_dict[author] = 1
            else:
                author_count_dict[author] = author_count_dict[author] + 1
    print("No. of potential candidates:", len(author_venue_dict))
    output_file_name = ''.join([key_word, '.txt'])
    output_file = os.path.join(os.getcwd(), 'Venues', conf_name, output_dir, output_file_name)
    # ClosetIO.outputPotentialPC(output_file, author_count_dict, author_venue_dict)


"""
Desc: Retrieve co-authorship data of a reviewer
"""


def getDBLPData(r_email, dblp_add, title_year_dict, title_venue_dict, rev_dblp_name_dict, dblp_name_rev_dict,
                rev_coauthors_dict, dblp_url_dict):

    c_author_freq_dict = dict()

    x_dblp = xmlifyAdd(dblp_add)
    xml_file = connectToDBLPPage(x_dblp)  # Connecting to DBLP page and get the XML file
    if len(xml_file) > 4:  # file exists
        person, person_name_set, c_author_hist_dict, c_author_freq_dict, years_of_pub, coauthor_set, affl_set = \
            readAuthorDBLP(xml_file, title_year_dict, title_venue_dict, dblp_url_dict, dblp_add)
        if len(person_name_set) > 0:
            rev_dblp_name_dict[r_email] = person_name_set
            for name in person_name_set:
                dblp_name_rev_dict[name] = r_email
        else:
            print("XML file of ", r_email, "cannot be located!")
        rev_coauthors_dict[r_email] = coauthor_set

    return c_author_freq_dict


"""
Desc: Refine co-author set by removing DBLP identifiers 
"""


def refineCoAuthors(coauthor_set):

    refined_coauthor_set = set()

    for c_author in coauthor_set:
        word_list = c_author.split()
        last_item = word_list[-1]
        if last_item.isnumeric():  # check if the last word is a numeric value
            new_author = c_author.replace(last_item, '')
            refined_coauthor_set.add(new_author.strip())
        else:
            refined_coauthor_set.add(c_author.strip())

    return refined_coauthor_set


"""
Desc: Retrieve authors in DBLP who has published in a given venue (e.g., SIGMOD).
"""


def generateVenueBasedAuthorStats(venue_set):

    dblp_path = os.path.join(os.getcwd(), 'DataStore', 'dblp.xml')
    author_hist_dict = dict()
    pub_type = ["article", "inproceedings"]

    print("Reading authors from DBLP file..")
    try:
        context_iter(dblp_path)
        for _, elem in context_iter(dblp_path):
            quality_venue_match = 0
            year_match = 0
            venue_title = ''
            a_year = ''
            author_set = set()
            if elem.tag in pub_type:
                for sub in elem:
                    if sub.tag == "booktitle":
                        if sub.text in venue_set:  # check if the paper is in venue list
                            quality_venue_match = 1
                            venue_title = sub.text
                    if sub.tag == "journal":
                        if sub.text in venue_set:  # check if the paper is in venue list
                            quality_venue_match = 1
                            venue_title = sub.text
                    if sub.tag == "year":
                        year_match = 1
                        a_year = sub.text
                    if sub.tag == 'author':
                        author_set.add(sub.text)
            if len(author_set) > 0 and quality_venue_match == 1 and year_match == 1:
                for author in author_set:
                    if author not in author_hist_dict.keys():
                        author_hist_dict[author] = [(venue_title, a_year)]
                    else:
                        author_hist_dict[author].append((venue_title, a_year))
            author_set.clear()
    except IOError:
        exit()

    return author_hist_dict


"""
Desc: Retrieve the first year of publication of reviewers.
"""


def getFirstYearOfPub(conf_pc_file, title_venue_dict, dblp_url_dict, cur_year):

    pc_first_yr_pub_dict = dict()  # rev email -> first year of publication
    missing_url = set()  # set containing invalid URL addresses
    r_email_exp_dict = dict()  # rev email -> no. of years of experience
    title_year_dict = dict()  # placeholder - currently not used.

    print("Retrieving first year of publication info from DBLP using the following file:", conf_pc_file)

    reviewers = pd.read_excel(conf_pc_file)
    for index, row in reviewers.iterrows():
        r_name = str(row['NAME']).strip().lower()
        r_email = str(row['EMAIL']).strip()
        r_dblp = str(row['DBLP']).strip()
        if len(r_dblp) > 5:
            x_dblp = xmlifyAdd(r_dblp)  # Format to XML URL
            time.sleep(2.1)
            print("\nReading XML DBLP file of", r_name, "located at:", x_dblp)
            xml_file = connectToDBLPPage(x_dblp)  # Connecting to DBLP page and get the XML file
            if len(xml_file) > 4:  # file exists
                person, person_name_set, c_author_hist_dict, c_author_freq_dict, years_of_pub, coauthor_set, \
                    affl_set = readAuthorDBLP(xml_file, title_year_dict, title_venue_dict, dblp_url_dict, r_dblp)
                if len(coauthor_set) > 0:
                    first_pub_name = ''  # dblp name containing first pub year
                    temp_year = 9999
                    if r_email not in pc_first_yr_pub_dict.keys():
                        for item in person_name_set:  # find the dblp name which contains the first pub year
                            if item in c_author_hist_dict.keys():
                                first_year = int(c_author_hist_dict[item][-1][0])
                                if first_year < temp_year:
                                    temp_year = first_year
                                    first_pub_name = item
                        # get first year of pub
                        pc_first_yr_pub_dict[r_email] = c_author_hist_dict[first_pub_name][-1][0]
                else:
                    missing_url.add(r_name)
            else:
                print("XML address is invalid for ", r_name)
                missing_url.add(r_name)
        else:
            print("DBLP page of the following reviewer is missing:", r_name)

    if len(missing_url) > 0:
        print("Total number of invalid URLs of reviewers detected: ", len(missing_url))
        print("Names: ", missing_url)
        print("Please rectify the URLs. Exiting CLOSET....")
        exit()

    # Compute experience
    for email in pc_first_yr_pub_dict.keys():
        experience = cur_year - int(pc_first_yr_pub_dict[email])
        r_email_exp_dict[email] = experience

    return r_email_exp_dict


if __name__ == '__main__':
    print("Running DBLP file")
