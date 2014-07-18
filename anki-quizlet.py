#-------------------------------------------------------------------------------
# Name:        Quizlet plugin for Anki 2.0
# Purpose:     Import decks from Quizlet.com into Anki 2.0
#
# Author:      Rolph Recto
#
# Created:     12/06/2012

# Copyright:   (c) Rolph Recto 2012
# Licence:     <your licence>
# Revised and upGraded By Abdolmahdi saravi
# image support functionality added
#-------------------------------------------------------------------------------
#!/usr/bin/env python

__window = None

import sys
import math
import time
import datetime as dt
import urllib as url1
import urllib2 as url2
import json

#Anki
from aqt import mw
from aqt.qt import *

#PyQT
from PyQt4.QtGui import *
# from PyQt4.Qt import Qt

#copied straight from anki.stdmodels
#it is necessary to create a custom model
#because the user might have changed the default model
def addCustomModel(name, col):
    """create a new custom model for the imported deck"""
    mm = col.models
    m = mm.new(u"{} ({})".format(_("Basic"), name))
    fm = mm.newField(_("Front"))
    mm.addField(m, fm)
    fm = mm.newField(_("Back"))
    mm.addField(m, fm)
    t = mm.newTemplate(_("Card 1"))
    t['qfmt'] = "{{"+_("Front")+"}}"
    t['afmt'] = "{{FrontSide}}\n\n<hr id=answer>\n\n"+"{{"+_("Back")+"}}"
    mm.addTemplate(m, t)
    mm.add(m)
    return m

class QuizletWindow(QWidget):
    """main window of Quizlet plugin; shows search results"""

    PAGE_FIRST       = 1
    PAGE_PREVIOUS    = 2
    PAGE_NEXT        = 3
    PAGE_LAST        = 4
    RESULT_ERROR     = -1
    RESULTS_PER_PAGE = 50
    __APIKEY         = "ke9tZw8YM6" #used to access Quizlet API

    def __init__(self):
        super(QuizletWindow, self).__init__()

        self.results = None
        self.thread = None
        self.name = ""
        self.user = ""
        self.sort = "most_studied"
        self.result_page = -1

        self.initGUI()

    def initGUI(self):
        """create the GUI skeleton"""

        self.box_top = QVBoxLayout()
        self.box_upper = QHBoxLayout()

        #left side
        self.box_left = QVBoxLayout()

        #name field
        self.box_name = QHBoxLayout()
        self.label_name = QLabel("Name")
        self.text_name = QLineEdit("",self)

        self.box_name.addWidget(self.label_name)
        self.box_name.addWidget(self.text_name)

        #user field
        self.box_user = QHBoxLayout()
        self.label_user = QLabel("User")
        self.text_user = QLineEdit("",self)

        self.box_user.addWidget(self.label_user)
        self.box_user.addWidget(self.text_user)

        #add layouts to left
        self.box_left.addLayout(self.box_name)
        self.box_left.addLayout(self.box_user)

        #right side
        self.box_right = QVBoxLayout()

        #sort type
        self.box_sort = QHBoxLayout()
        self.label_sort = QLabel("Sort by:", self)
        self.buttongroup_sort = QButtonGroup()
        self.radio_popularity = QRadioButton("Popularity", self)
        self.radio_name = QRadioButton("Name", self)
        self.radio_date = QRadioButton("Date created", self)
        self.radio_popularity.setChecked(True)
        self.buttongroup_sort.addButton(self.radio_popularity)
        self.buttongroup_sort.addButton(self.radio_name)
        self.buttongroup_sort.addButton(self.radio_date)

        self.box_sort.addWidget(self.label_sort)
        self.box_sort.addWidget(self.radio_popularity)
        self.box_sort.addWidget(self.radio_name)
        self.box_sort.addWidget(self.radio_date)
        self.box_sort.addStretch(1)

        #search button
        self.box_search = QHBoxLayout()
        self.button_search = QPushButton("Search", self)

        self.box_search.addStretch(1)
        self.box_search.addWidget(self.button_search)

        self.button_search.clicked.connect(self.onSearch)

        #add layouts to right
        self.box_right.addLayout(self.box_sort)
        self.box_right.addLayout(self.box_search)

        #add left and right layouts to upper
        self.box_upper.addLayout(self.box_left)
        self.box_upper.addSpacing(20)
        self.box_upper.addLayout(self.box_right)

        #table navigation
        self.box_tablenav = QHBoxLayout()

        self.button_first = QPushButton("<<", self)
        self.button_first.setMaximumWidth(30)
        self.button_first.setVisible(False)

        self.button_previous = QPushButton("<", self)
        self.button_previous.setMaximumWidth(30)
        self.button_previous.setVisible(False)

        self.button_current = QPushButton(str(self.result_page), self)
        self.button_current.setMaximumWidth(50)
        self.button_current.setVisible(False)

        self.button_next = QPushButton(">", self)
        self.button_next.setMaximumWidth(30)
        self.button_next.setVisible(False)

        self.button_last = QPushButton(">>", self)
        self.button_last.setMaximumWidth(30)
        self.button_last.setVisible(False)

        self.box_tablenav.addStretch(1)
        self.box_tablenav.addWidget(self.button_first)
        self.box_tablenav.addWidget(self.button_previous)
        self.box_tablenav.addWidget(self.button_current)
        self.box_tablenav.addWidget(self.button_next)
        self.box_tablenav.addWidget(self.button_last)
        self.box_tablenav.addStretch(1)

        self.button_first.clicked.connect(self.onPageFirst)
        self.button_previous.clicked.connect(self.onPagePrevious)
        self.button_current.clicked.connect(self.onPageCurrent)
        self.button_next.clicked.connect(self.onPageNext)
        self.button_last.clicked.connect(self.onPageLast)

        #results label
        self.label_results = QLabel("")

        #table of results
        self.table_results = QTableWidget(2, 4, self)
        self.table_results.setHorizontalHeaderLabels(["Name", "User",
            "Items", "Date created"])
        self.table_results.verticalHeader().hide()
        self.table_results.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_results.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_results.horizontalHeader().setSortIndicatorShown(False)
        self.table_results.horizontalHeader().setClickable(False)
        self.table_results.horizontalHeader().setResizeMode(QHeaderView.Interactive)
        self.table_results.horizontalHeader().setStretchLastSection(True)
        self.table_results.horizontalHeader().setMinimumSectionSize(100)
        self.table_results.verticalHeader().setResizeMode(QHeaderView.Fixed)
        self.table_results.setMinimumHeight(275)
        self.table_results.setVisible(False)

        #import selected deck
        self.box_import = QHBoxLayout()
        self.button_import = QPushButton("Import Deck", self)
        self.button_import.setVisible(False)

        self.box_import.addStretch(1)
        self.box_import.addWidget(self.button_import)

        self.button_import.clicked.connect(self.onImportDeck)

        #add all widgets to top layout
        self.box_top.addLayout(self.box_upper)
        self.box_top.addLayout(self.box_tablenav)
        self.box_top.addWidget(self.label_results)
        self.box_top.addWidget(self.table_results)
        self.box_top.addLayout(self.box_import)
        self.box_top.addStretch(1)
        self.setLayout(self.box_top)

        self.setMinimumWidth(500)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.setWindowTitle("Import from Quizlet")
        self.show()

    def onSearch(self):
        """user clicked search button; load first page of results"""
        self.name = self.text_name.text()
        self.user = self.text_user.text()
        self.result_page = -1

        #sort
        if self.buttongroup_sort.checkedButton() == self.radio_popularity:
            self.sort = "most_studied"
        elif self.buttongroup_sort.checkedButton() == self.radio_name:
            self.sort = "title"
        elif self.buttongroup_sort.checkedButton() == self.radio_date:
            self.sort = "most_recent"

        self.fetchResults()

    def onImportDeck(self):
        """user clicked Import Deck button, load the deck from Quizlet"""
        #find the selected deck in the table
        index = self.table_results.currentRow()

        #set the GUI
        self.hideTable()
        self.button_search.setEnabled(False)
        self.label_results.setText( (u"Importing deck <b>{0}</b> ..."
            .format(self.results["sets"][index]["title"])) )

        #build URL
        deck_url = (u"https://api.quizlet.com/2.0/sets/{0}/terms".
            format(self.results["sets"][index]["id"]))

        deck_url += u"?client_id={0}".format(QuizletWindow.__APIKEY)

        #stop the previous thread first
        if not self.thread == None:
            self.thread.terminate()

        #download the data!
        self.thread = QuizletDownloader(self, deck_url)
        self.thread.start()

        while not self.thread.isFinished():
            mw.app.processEvents()
            self.thread.wait(50)

        #error with fetching data
        if self.thread.error:
            self.label_results.setText( (u"Failed to load deck <b>{0}</b>!"
                .format(self.results["sets"][index]["title"])) )
        #everything went through!
        else:
            terms = self.thread.results
            self.createDeck(self.results["sets"][index]["title"], terms)

            self.showTable()
            self.button_search.setEnabled(True)
            self.label_results.setText( (u"Successfully imported deck <b>{0}</b>."
                .format(self.results["sets"][index]["title"])) )

        self.thread.terminate()
        self.thread = None

    def createDeck(self, name, terms):
        """create new Anki deck from downloaded data"""
        #create new deck and custom model
        deck = mw.col.decks.get(mw.col.decks.id(name))
        model = addCustomModel(name, mw.col)

        #assign custom model to new deck
        mw.col.decks.select(deck["id"])
        mw.col.decks.get(deck)["mid"] = model["id"]
        mw.col.decks.save(deck)

        #assign new deck to custom model
        mw.col.models.setCurrent(model)
        mw.col.models.current()["did"] = deck["id"]
        mw.col.models.save(model)
#         f=open('terms.txt','wb')
        txt=u"""
        <div><img src="{0}" /></div>
        """
        for term in terms:            
            note = mw.col.newNote()
            note[_("Front")] = term["term"]
            note[_("Back")] = term["definition"]
            if not term["image"] is None:
                #stop the previous thread first
                self.fileDownloader(term["image"]["url"])
                note[_("Back")]+=txt.format(term["image"]["url"].split('/')[-1])
                mw.app.processEvents()
            mw.col.addNote(note)
#         f.close()
        mw.col.reset()
        mw.reset()

    def onPageFirst(self):
        """first page button clicked"""
        self.__changePage(QuizletWindow.PAGE_FIRST)

    def onPagePrevious(self):
        """first page button clicked"""
        self.__changePage(QuizletWindow.PAGE_PREVIOUS)

    def onPageCurrent(self):
        """let user jump to any page"""
        page, ok = QInputDialog.getInteger(self, "Jump to Page",
            u"What page? ({0} - {1})".format(1, self.results["total_pages"]),
            1, 1, self.results["total_pages"])

        if ok:
            self.fetchResults(page)

    def onPageNext(self):
        """first page button clicked"""
        self.__changePage(QuizletWindow.PAGE_NEXT)

    def onPageLast(self):
        """first page button clicked"""
        self.__changePage(QuizletWindow.PAGE_LAST)

    def __changePage(self, change):
        """determine what page to fetch"""
        if change == QuizletWindow.PAGE_FIRST:
            self.fetchResults(1)
        elif change == QuizletWindow.PAGE_PREVIOUS:
            if self.result_page - 1 >= 1:
                self.fetchResults(self.result_page-1)
        elif change == QuizletWindow.PAGE_NEXT:
            if self.result_page + 1 <= self.results["total_pages"]:
                self.fetchResults(self.result_page+1)
        elif change == QuizletWindow.PAGE_LAST:
            self.fetchResults( self.results["total_pages"] )

    def showTable(self, show=True):
        """set results table visible/invisible"""
        self.button_first.setVisible(show)
        self.button_previous.setVisible(show)
        self.button_current.setVisible(show)
        self.button_next.setVisible(show)
        self.button_last.setVisible(show)
        self.table_results.setVisible(show)
        self.button_import.setVisible(show)

    def hideTable(self):
        """make results table invisible"""
        self.showTable(False)

    def loadResultsToTable(self):
        """insert data from results dict into table widget"""
        #clear table first
        self.table_results.setRowCount(0)
        deckList = self.results["sets"]

        #iterate through the decks and add them to the table
        for index in range(len(deckList)):
            if index+1 > self.table_results.rowCount():
                self.table_results.insertRow(index)

            #deck name
            name = QTableWidgetItem(deckList[index]["title"])
            name.setToolTip(deckList[index]["title"])
            self.table_results.setItem(index, 0, name)

            #user who created deck
            user = QTableWidgetItem(deckList[index]["created_by"])
            user.setToolTip(deckList[index]["created_by"])
            self.table_results.setItem(index, 1, user)

            #number of items in the deck
            items = QTableWidgetItem(str(deckList[index]["term_count"]))
            items.setToolTip(str(deckList[index]["term_count"]))
            self.table_results.setItem(index, 2, items)

            #last date that the deck was modified
            date_str = time.strftime("%m/%d/%Y",
                time.localtime(deckList[index]["created_date"]))
            date = QTableWidgetItem(date_str)
            date.setToolTip(date_str)
            self.table_results.setItem(index, 3, date)

    def getResultsDescription(self):
        """return a description of search parameters"""
        #if textfields are empty, return an error
        if self.name == "" and self.user == "":
            return "Error: Must have input to search!"
        #search for deck name only
        elif not self.name == "" and self.user == "":
            return u"Searching for \"{0}\" ...".format(self.name)
        #search for deck name and user
        elif not self.name == "" and not self.user == "":
            return (u"Searching for \"{0}\" by user <u>{1}</u> ..."
                .format(self.name, self.user))
        #search for user only
        elif self.name == "" and not self.user == "":
            return u"Searching for decks by user <u>{0}</u> ...".format(self.user)

    def fetchResults(self, page=1):
        """load results"""

        #if the page being fetched is the same as the current page,
        #don't fetch it!
        if page == self.result_page: return

        global __APIKEY

        self.results = None
        self.hideTable()
        self.label_results.setText(self.getResultsDescription())

        #textfields are empty
        if self.label_results.text() == "Error: Must have input to search!":
            return

        #build search URL
        search_url = u"https://api.quizlet.com/2.0/search/sets"
        search_url += u"?q={0}".format(self.name)
        if not self.user == "":
            search_url += u"&creator={0}".format(self.user)
        search_url += u"&page={0}".format(page)
        search_url += u"&per_page={0}".format(QuizletWindow.RESULTS_PER_PAGE)
        search_url += u"&sort={0}".format(self.sort)
        search_url += u"&client_id={0}".format(QuizletWindow.__APIKEY)

        #stop the previous thread first
        if not self.thread == None:
            self.thread.terminate()

        #download the data!
        self.thread = QuizletDownloader(self, search_url)
        self.thread.start()

        while not self.thread.isFinished():
            mw.app.processEvents()
            self.thread.wait(50)

        self.results = self.thread.results

        #error with fetching data; don't display table
        if self.thread.error:
            self.setPage(QuizletWindow.RESULT_ERROR)
        #everything went through!
        else:
            self.setPage(page)
            self.loadResultsToTable()
            self.showTable()

        self.thread.terminate()
        self.thread = None

    def setPage(self, page):
        """set page of results to load"""
        if page == QuizletWindow.RESULT_ERROR:
            self.result_page = -1
            self.button_current.setText(" ")
            self.label_results.setText( ("No results found!") )
        else:
            num_results = self.results["total_results"]
            first = ((page-1)*50)+1
            last = (page*QuizletWindow.RESULTS_PER_PAGE
                if page*QuizletWindow.RESULTS_PER_PAGE < num_results
                else num_results)
            self.result_page = page
            self.button_current.setText(str(page))
            self.label_results.setText( (u"Displaying results {0} - {1} of {2}."
                .format(first, last, num_results)) )
            self.table_results.verticalHeader().setOffset(first)
            
    def fileDownloader(self, url):
        file_name = url.split('/')[-1]
        url1.urlretrieve(url,file_name)
#         u = url2.urlopen(url)
#         f = open(file_name, 'wb')
#         meta = u.info()
#         file_size = int(meta.getheaders("Content-Length")[0])
#         
#         file_size_dl = 0
#         block_sz = 8192
#         while True:
#             buffer = u.read(block_sz)
#             if not buffer:
#                 break       
#             file_size_dl += len(buffer)
#             f.write(buffer)
#             f.close()               


class QuizletDownloader(QThread):
    """thread that downloads results from the Quizlet API"""

    def __init__(self, window, url):
        super(QuizletDownloader, self).__init__()
        self.window=window
        self.url = url
        self.error = False
        self.results = None

    def run(self):
        """run thread; download results!"""
        try:
            self.results = json.load(url2.urlopen(self.url))
        except url2.URLError:
            self.error = True
        else:
            #if no results, there was an error
            if self.results == None:
                self.error = True


def runQuizletPlugin():
    """menu item pressed; display search window"""
    global __window
    __window = QuizletWindow()

#create menu item
action = QAction("Import from Quizlet", mw)
mw.connect(action, SIGNAL("triggered()"), runQuizletPlugin)
mw.form.menuTools.addAction(action)

