# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013 Zachary Spector,  zacharyspector@gmail.com
from LiSE import __path__
from LiSE import closet
from LiSE.gui.app import LiSEApp
from sys import argv
from sqlite3 import connect, DatabaseError
from os.path import abspath


def lise():
    i = 0
    lang = "eng"
    dbfn = None
    debugfn = ""
    DEBUG = False
    for arg in argv:
        if arg == "-l":
            try:
                lang = argv[i + 1]
            except:
                raise ValueError("Couldn't parse language")
        elif arg == "-d":
            DEBUG = True
        elif DEBUG:
            debugfn = arg
            try:
                df = open(debugfn, 'w')
                df.write('--begin debug file for LiSE--\n')
                df.close()
            except IOError:
                exit("Couldn't write to the debug log file "
                     "\"{}\".".format(debugfn))
        elif arg[-4:] == "lise":
            dbfn = arg
        i += 1

    if dbfn is None:
        dbfn = "default.lise"

    try:
        conn = connect(dbfn)
        i = 0
        for stmt in conn.iterdump():
            i += 1
            if i > 3:
                break
        if i < 3:
            conn.close()
            closet.mkdb(dbfn, __path__[-1])
        else:
            try:
                conn.cursor().execute("SELECT * FROM game;")
                conn.close()
            except DatabaseError:
                exit("The database contains data that does not "
                     "conform to the expected schema.")
    except IOError:
        closet.mkdb(dbfn, __path__[-1])

    print("Starting LiSE with database {}, language {}, path {}".format(
        dbfn, lang, __path__[-1]))

    LiSEApp(dbfn=dbfn, lang=lang,
            lise_path=abspath(__path__[-1]),
            menu_name='Main',
            dimension_name='Physical',
            character_name='household').run()


if __name__ == '__main__':
    lise()
