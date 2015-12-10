#!/usr/bin/python
##########################################################
## grpbibedit.py
##    pulls data down from RT
##    created: 2013-05-11
##    major update: 2015-06
##    major extension: 2015-12
##    last mod: 2015-12-10 10:29
##
## hosted at:
##    test: https://tislnx3.slac.stanford.edu/cgi-bin/testgrpbibedit.py
##    prod: https://tislnx3.slac.stanford.edu/cgi-bin/grpbibedit.py
##
## dashboards created at, ex.,
##    https://tislnx3.slac.stanford.edu/mhuangbibedit.html
##
##########################################################
#### Ideas../ notes
## 1 find/create another RT account to use
## 3 rewrite with cookielib (per example)
## 4 check out python-rt https://git.nic.cz/redmine/projects/python-rt
## # http://docs.python.org/2/howto/urllib2.html

# import base64, json
import cgi
import cgitb
import datetime
import urllib
import urllib2

from invenio.bibcheck_task import AmendableRecord
from invenio.bibedit_utils import get_bibrecord
from invenio.search_engine import get_fieldvalues

cgitb.enable()

CLAIM_LOG = 'RT_ticket_claim.log'

RUN_MODE = 'development'
# RUN_MODE = 'production'

# user and pass parms supported
# http://www.gossamer-threads.com/lists/rt/users/75160
# base64string = base64.encodestring('%s:%s' % (ux, px)).replace('\n', '')


############################################################################
def logThis(msg):
    LOGFILE = open(CLAIM_LOG, 'a')
    LOGFILE.write(str(datetime.datetime.now()) + '\t' + msg + '\n')
    LOGFILE.close()


#############################################################################
def build_form_body():

    formbod = '''
    <form name="input" action="grpbibedit.py" method="get">
    <hr/>

    <div>Select your RT account:<select name="cataloger">
        <option value="mhuang">mhuang</option>
        <option value="kornienk">kornienk</option>
        <option value="sul">sul</option>
        <option value="bhecker">bhecker</option>
        <option value="thschwander">thschwander</option>
        <option selected value="none">none</option>
    </select>
    RT Password:<input type="password" name="pwd" required>
    Queue: <select name="queue">
       <option selected value="HEP_Curation">HEP_Curation</option>
        <option value="Inspire-References">Inspire-References</option>
    </select>
    </div>

    <div>Select the number of tickets you want:<select name="quantity">
    <option value="5">5</option>
    <option value="25">25</option>
    <option value="50" selected>50</option>
    </select></div>

    <input type="submit" value="Submit">
    </form>

    '''

    return formbod


###################################################################
def send_request(req_url):
    try:
        request = urllib2.Request(req_url)
        # request.add_header("Authorization", "Basic %s" % base64string)
        outx = urllib2.urlopen(request)
        fromRT = outx.read()
        outx.close()

    except urllib2.URLError:
        # no server connection
        fromRT = "Could not connect to server."

    if "Credentials required" in fromRT:
        fromRT = 'Error. Credentials required.'

    return fromRT


#############################################################################
def get_available_tickets(queuex, catx, passx):

    # query RT for a sorted list of tickets in queue QUEUE that are
    # owned by "Nobody" and are status="new"

    reqdatx = {}
    reqdatx['user'] = catx
    reqdatx['pass'] = passx
    reqdatx['query'] = "Queue='" + queuex + \
                       "' AND Owner='Nobody' AND status='new'"
    reqdatx['orderby'] = '+Created'  # ordering; use '-' for descending
    reqdatx['format'] = 'l'

    base_url = 'https://inspirert.cern.ch/REST/1.0/search/ticket'
    # encode parameter list, build request URL
    req_url = base_url + '?' + urllib.urlencode(reqdatx)

    result = send_request(req_url)
    return result


#############################################################################
def claim_tix(available_tix_result, quantx, catx, passx):
    '''Break the result of the RT query for QUANTITY unclaimed RT tickets
       into an array of dictionaries  { id, created, subject },
       then claim QUANTITY tickets, and log the result.'''

    header = True
    rx = []
    xmsg = ''
    current_id = current_created = current_subject = None

    if (available_tix_result == "Could not connect to server.") \
       | (available_tix_result == 'Error. Credentials required.'):
        xmsg += "<h3>ERROR: %s </h3>" % available_tix_result
        logThis("REQUEST ERROR:" + available_tix_result)
    else:
        # parse the result returned by the query for available tickets,
        # harvest RT IDs
        for rec in available_tix_result.split('\n'):
            if ("id:" in rec) | ("Created:" in rec) | ("Subject" in rec):
                (label, value) = rec.split(': ', 1)
                if "id" in label:
                    # it's a new ticket, so store the values from the last
                    # ticket unless it's the very first record found
                    if header:
                        header = False
                    else:
                        rx.append({'id': current_id,
                                   'created': current_created,
                                   'subject': current_subject})
                    _, current_id = value.split('ticket/')
                elif "Created" in label:
                    current_created = value
                elif "Subject" in label:
                    current_subject = value

        selected_ticket_ids = []

        if RUN_MODE == 'production':
            logThis("Requesting ownership of " + str(quantx)
                    + " tickets for " + catx + '...')

            # take ownership of QUANTITY tickets ##############################
            reqdatx = {}
            reqdatx['user'] = catx
            reqdatx['pass'] = passx
            reqdatx['content'] = 'Owner: ' + catx
            reqdatx['type'] = 'force'

            for i in range(0, quantx):
                startTime = datetime.datetime.now()
                # xmsg += "<p>  ===> " + rx[i]['id'] + "   " \
                #    + rx[i]['created'] + '</p>'

                base_url = 'https://inspirert.cern.ch/REST/1.0/ticket/' \
                           + str(rx[i]['id']) + '/edit'
                req_url = base_url + '?' + urllib.urlencode(reqdatx)

                # change the owner of the selected tickets
                status = send_request(req_url)

                if status == "Could not connect to server.":
                    xmsg += "<h3>ERROR: Could not connect to server.</h3>"
                else:
                    xmsg += '<code class="status">'+status+'</code>'
                    endTime = datetime.datetime.now()
                    tx = endTime - startTime
                    xmsg += "<p>Duration:" \
                            + str(tx.seconds + tx.microseconds/1000000.0) \
                            + " seconds</p>"

                    selected_ticket_ids.append(str(rx[i]['id']))

                xmsg += "."

            logThis("Ownership claimed for " + catx
                    + '\t'+str(selected_ticket_ids) + '\n')
        else:
            #  RUN_MODE='development' ########

            for i in range(0, quantx):
                startTime = datetime.datetime.now()
                selected_ticket_ids.append(str(rx[i]['id']))

            logThis("RUN_MODE=development, tickets not claimed in this run.")
            xmsg = 'Development run, tickets not claimed.'

    # xmsg has durations for the claim operation
    return xmsg, selected_ticket_ids


#############################################################################
def NEWbuildLinkout(idArray, GROUP):
    '''Build the links to RT, INSPIRE records, arXiv PDFs, etc.
       that later get embedded in the display page.'''

    # idArray is a list of dictionaries; each list item has an RT
    # and an INSPIRE id
    bibeditHead = '<a href="https://inspirehep.net/record/edit/' \
                  + '?ln=en#state=search&amp;p='
    bibeditHTML = ''
    inspireIDs = []
    # idArray is a list of dictionaries, ex.,
    # { 'inspireID':inspireID, 'RTid':ticketNum }
    # for convenience, we build a simple inspireIDs list, as in the earlier
    # version of the code
    for record in idArray:
        inspireIDs.append(record['inspireID'])
    if inspireIDs != []:
        grouplink = ''
        linksOutput = ''
        for i in range(0, len(inspireIDs), GROUP):
            detailLinks = ''
            grouplink = 'recid:' + '%20or%20recid:'.join(inspireIDs[i:i+GROUP])
            bibeditLine = '<span class="bibeditLine">'+bibeditHead + grouplink \
                          + '" target=bibeditmult>Open in BibEdit, starting record:' + str(i) \
                          + '</a>' + '</span>\n'

            # place  DOI, Title, PDF links under the grouped linkout to bibedit
            for j in inspireIDs[i:i+GROUP]:
                fieldValueArray = getInspireRecordMetadata(j)

                # IDENTIFIERS (Inspire & RT & arXiv )##################
                # corresponding RT ticket number
                RTlinkout = ''
                for rr in idArray:
                    if rr['inspireID'] == j:
                        RTnumber = rr['RTid']
                        RTlinkout = ' <a href="https://rt.inspirehep.net/Ticket/Display.html?id=%s">RT#: %s</a> ' % (RTnumber, RTnumber)
                # arXiv
                arxivNumber = fieldValueArray['arxivID'].split('arXiv.org:')[1]
                arXivLinks = ' <a href="http://arxiv.org/abs/%s">arxiv:%s</a> <a href="http://arxiv.org/pdf/%s">arXiv:PDF</a> ' % (arxivNumber, arxivNumber, arxivNumber)

                identifierLinks = '<div class="identifierLine"><a href="http://inspirehep.net/record/' + str(j) + '">INSPIRE: ' + str(j) + "</a>" + RTlinkout + arXivLinks + '</div>' \

                # TITLE
                titleLine = '\n' + '<div class="titleLine"> <b>' \
                            + fieldValueArray['245__a'][0] + '</b></div>\n'

                # DOI
                if len(fieldValueArray['0247_2']) > 0 \
                   and fieldValueArray['0247_2'][0] == 'DOI':
                    doiv = fieldValueArray['0247_a'][0]
                    doiLine = '\n  <div class="doiLine">DOI: <a href="http://dx.doi.org/' \
                              + doiv + '">' + doiv + '</a></div>\n'
                else:
                    doiLine = ''

                # PDF
                # NOTE: we won't pick up PDFs like
                # http://www.scielo.br/scielo.php?pid=S0103-97332010000300003&script=sci_arttext
                # b/c we filter for "pdf" on the metadata returned for 8564.
                if len(fieldValueArray['8564_u']) > 0:
                    pdfLinks = ''
                    for p in fieldValueArray['8564_u']:
                        pdfLinks += '<div class="pdfLink"> <a href="' + p \
                                    + '">' + p + '</a></div> '

                pdfLine = '\n   <div class="pdfLine">' + pdfLinks + '</div>\n'
                detailLinks += '\n <div class="articleLine">\n' + titleLine \
                               + identifierLinks + doiLine + pdfLine \
                               + '\n</div>\n'
            # store the cluster of lines for each bibedit linkout group
            linksOutput += '\n<li><div class="linkCluster">'+bibeditLine \
                           + detailLinks+'</div></li>\n'

        # wrap it up, and write the output file
        datex = datetime.datetime.now().strftime("%Y:%m:%d  %H:%M:%S")
        outputHTML = '<html><head><title>Dashboard linkouts</title>' \
                     + '<link href="dashboard1.css" rel="stylesheet" type="text/css" media="all" >' \
                     + '</head><body>\n' + '<h2>' + CATALOGER \
                     + ':  Dashboard for Queue ' + QUEUE\
                     + '</h2>\n \n <ol>' + linksOutput + '</ol>' \
                     + '\n\n <code>' + datex + '</code></body></html>'

        if RUN_MODE == 'production':
            slacfile = '/var/www/html/' + CATALOGER + 'bibedit.html'
        else:
            slacfile = './' + CATALOGER + 'bibedit.html'

        with open(slacfile, 'wb') as outfile:
            outfile.write(outputHTML)

    return bibeditHTML


#############################################################################
def getInspireRecordMetadata(inspireID):
    '''For a given INSPIRE ID, collect the desired metadata fields
       and return them.
    '''

    fieldArray = {'0247_2': 'stdIDsource', '0247_a': 'stdID',
                  '245__a': 'title', '8564_u': 'files'}
    fieldValues = {}
    fieldKeys = fieldArray.keys()
    for fKey in fieldKeys:
        fieldValues[fKey] = get_fieldvalues(inspireID, fKey)
        print "fieldValues=", fKey, ":", fieldValues[fKey]

    # ThS suggested approach for dealing with the problem of two repeating
    # fields that correspond (say, a type in one field, and a value in another)
    record = AmendableRecord(get_bibrecord(inspireID))
    for _, val in record.iterfield('035__a', subfield_filter=('9', 'arXiv')):
        fieldValues['arxivID'] = val

    pdfList = []
    for z in fieldValues['8564_u']:
        if 'pdf' in z:
            pdfList.append(z)
    fieldValues['8564_u'] = pdfList

    return fieldValues


#############################################################################
def NEWgetInspireIDs(list_of_tix, catx, passx):
    '''Get the INSPIRE record IDs associated with the RT tickets numbers
       provided.
    '''

    ticketNum_inspireIDs = []
    logThis("getInspireID request dispatch loop...")

    reqdatx = {}
    reqdatx['user'] = catx
    reqdatx['pass'] = passx

    # one query per InspireID ######################
    for ticketNum in list_of_tix:
        # encode parameter list, build request URL
        req_url = 'https://inspirert.cern.ch/REST/1.0/ticket/' + \
                  str(ticketNum) + '/show' + '?' + urllib.urlencode(reqdatx)

        result = send_request(req_url)
        results = result.split('\n')

        # parse the result for a line like
        #       CF.{RecordID}: 1397515
        foundID = False
        for result_line in results:
            if 'CF.{RecordID}' in result_line:
                inspireID = result_line.split()[1]
                foundID = True

        if not foundID:
            inspireID = "ID NOT FOUND"

        ticketNum_inspireIDs.append({'inspireID': inspireID,
                                     'RTid': ticketNum})

    logThis("NEWgetInspireID request completed...")
    return ticketNum_inspireIDs

#############################################################################
# main

GROUPBY = 5  # number of tickets to include in each bibedit linkout

# read any parameters
xform = cgi.FieldStorage()
formmsg = ''

# RUN_MODE is a convenience for testing and development.
#   When set to "development", the run does not claim RT tickets
if RUN_MODE == 'production':

    # check to see if a form has been submitted
    if 'cataloger' in xform:
        HaveParm = True
        CATALOGER = xform.getvalue("cataloger")
        PASSWORD = xform.getvalue('pwd')
        # QUANTITY = total number of tickets to pull
        QUANTITY = int(xform.getvalue('quantity'))
        QUEUE = xform.getvalue('queue')
        formmsg = "<p>cataloger:" + CATALOGER + ' Queue: ' + QUEUE + '</p>\n'
        formmsg += "<p>quantity:" + str(QUANTITY) + '</p>\n\n</hr>'
    else:
        # "no parameters submitted = no form submitted"
        HaveParm = False
else:
<<<<<<< HEAD
<<<<<<< HEAD
	##development run ######################
	## dummy values, only needed for testing
	CATALOGER = 'bhecker'
	PASSWORD = 'fakepassword'
	#QUEUE = 'Inspire-References'
	QUEUE = 'HEP_curation'
	QUANTITY = 5
	HaveParm = True
=======
=======
>>>>>>> d6c01a98b49f9c7cc7a9ffbb3a31efd10a46333f
    # development run ######################
    # dummy values
    CATALOGER = 'bhecker'
    PASSWORD = 'fakepassword'
    # QUEUE = 'Inspire-References'
    QUEUE = 'HEP_curation'
    QUANTITY = 5
    HaveParm = True
<<<<<<< HEAD
>>>>>>> d6c01a98b49f9c7cc7a9ffbb3a31efd10a46333f
=======
>>>>>>> d6c01a98b49f9c7cc7a9ffbb3a31efd10a46333f

# begin build

htmlheader = '''Content-Type: text/html\n\n'''

htmltop = '''<html><head>
    <title>RT ticket batch claim</title></head>
    <body>
    <h1>RT batch ticket claiming for catalogers</h1>
    <h5>v 2.0</h5>
    <p>Please select your account and the number of tickets, and then submit.
'''
htmltail = '</body></html>'

if HaveParm:

    logThis("+================= Run beginning ================+")
    logThis(CATALOGER + ", queue=" + QUEUE + ", quantity=" + str(QUANTITY))

    reqdata = {}
    reqdata['user'] = CATALOGER
    reqdata['pass'] = PASSWORD
    reqdata['query'] = "Queue='" + QUEUE + \
                       "' AND Owner='Nobody' AND status='new'"
    reqdata['orderby'] = '+Created'  # ordering; use '-' for descending
    reqdata['format'] = 'l'

    # execute the query to pull oldest available tickets in QUEUE
    # owned by Nobody
    available_tix = get_available_tickets(QUEUE, CATALOGER, PASSWORD)

    logThis("Tickets pulled....")

    # claim the tickets
    claim_msg, selected_tix = claim_tix(available_tix,
                                        QUANTITY, CATALOGER, PASSWORD)

    # get the INSPIRE IDs that correspond to those RT records
    # RT_inspire_ids is a list of dictionaries
    RT_inspire_ids = NEWgetInspireIDs(selected_tix, CATALOGER, PASSWORD)
    logThis("RT_inspire_ids:"+str(RT_inspire_ids))

    # return the bibedit linkout markup,
    linktext = NEWbuildLinkout(RT_inspire_ids, GROUPBY, CATALOGER, PASSWORD)

    if RT_inspire_ids[0]['inspireID'] == []:
        linktext = ''
        toDashboard = 'No RecIDs found in these tickets.' \
                      + ' No dashboard generated.'
    else:
        toDashboard = 'Go to the dashboard page: <a href=https://tislnx3.slac.stanford.edu/' + \
                      CATALOGER + 'bibedit.html target=bibedit>' + CATALOGER \
                      + 'bibedit.html </a> \n'

    InspireIDlist = []
    for r in RT_inspire_ids:
        InspireIDlist.append(r['inspireID'])

        finalmsg = htmlheader + htmltop + '\n  ' + '\n' + build_form_body() + '\n' + toDashboard \
            + '<hr/>\n<div class="inspire-ids"><h3>Inspire IDs</h3>\n<p>' \
            + ", ".join(InspireIDlist) + '</p>\n\n' \
            + '<hr/></div>\n ' + htmltail

    print finalmsg
    logThis("+----------------- Completed Run ----------------+")


else:
    # no parameters passed, so just display the form
    finalmsg = htmlheader + htmltop + '\n  ' + '\n'+build_form_body() \
        + '<hr/>\n ' + htmltail

    print finalmsg
    logThis("+--     --    -- - Form Displayed - --  --  --  -+")
