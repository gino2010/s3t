# coding=utf-8
# need extra pacakage: python-zbar
# under ubuntu install this package in software centre
import base64
from datetime import date
import os
import sqlite3
import zbar
import Image

__author__ = 'gino'

DATABASE = 'shadowsocks.db'
LOCAL_PORT = '8020'
TIMEOUT = '600'

TEMPLATE = '''{
    "server":"%s",
    "server_port":%s,
    "local_port":%s,
    "password":"%s",
    "timeout":%s,
    "method":"%s"
}'''


#Shadow class
class Shadow:
    def __init__(self, server, port, password, method, status='unknown', save_date=date.today().strftime('%Y%m%d'),
                 priority='0', memo=''):
        self.server = server
        self.port = port
        self.password = password
        self.method = method
        self.status = status
        self.save_date = save_date
        self.priority = priority
        self.memo = memo

    def __str__(self):
        return TEMPLATE % (self.server, self.port, LOCAL_PORT, self.password, TIMEOUT, self.method)


# Database class
class DataBase:
    def __init__(self, database):
        self._shadows = []
        try:
            self.conn = sqlite3.connect(database)
            self.cur = self.conn.cursor()
        except sqlite3.Error as e:
            print(e.message)

    #close database connection
    def close(self):
        if self.conn:
            self.conn.close()

    #add shadow item in database
    def add_item(self, _shadow):
        try:
            #check server is not existed
            self.cur.execute('SELECT * FROM account WHERE server = ? ', (_shadow.server,))
            if len(self.cur.fetchall()) != 0:
                print('server:%s is already have' % _shadow.server)
                return
            #insert item
            self.cur.execute(
                'INSERT INTO account (server, server_port, password, method, status, save_date, priority, memo) VALUES '
                '(?, ?, ?, ?, ?, ?, ?, ?)', (_shadow.server, _shadow.port, _shadow.password, _shadow.method,
                                             _shadow.status, _shadow.save_date, _shadow.priority, _shadow.memo))
            self.conn.commit()
        except sqlite3.Error as e:
            print(e)
            self.conn.rollback()

    #get all shadow object
    def get_items(self, _status='normal'):
        try:
            for row in self.cur.execute('SELECT * FROM account WHERE status=?', (_status,)):
                print row
                self._shadows.append(Shadow(row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))
        except sqlite3.Error as e:
            print(e)
        return self._shadows

    #get the best one shadow object
    def get_best_item(self, latest=False, priority=True):
        order_str = ''
        if latest:
            order_str += 'save_date DESC, '
        if priority:
            order_str += ' priority'
        if order_str == '':
            order_str = 'id'
        order_str = order_str.strip()
        if order_str[-1] == ',':
            order_str = order_str[:-1]
        try:
            for row in self.cur.execute('SELECT * FROM account WHERE status="normal" ORDER BY {} LIMIT 1'.format(order_str)):
                return Shadow(row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8])
        except sqlite3.Error as e:
            print(e)

    #check all item in database and change status column
    def check_all_items(self):
        try:
            for row in self.cur.execute('SELECT * FROM account'):
                pass
        except sqlite3.Error as e:
            print(e)

    #sort all shadow item that's status is normal, change priority column
    def sort_items(self):
        self.get_items()

        pass

    # def select_test(self):
    #     self.cur.execute('SELECT * FROM account WHERE server = "1" ')
    #     if len(self.cur.fetchall()) == 0:
    #         print('0000')
    #     else:
    #         print('11111')
    #     return


#scan images of barcode and get code string
#return list like:[[file_name, code_string],[]....]
def scan_image():
    #get list of files in path
    files = os.listdir("image")
    data = []
    #create scanner
    scanner = zbar.ImageScanner()
    scanner .parse_config('enable')

    #open each image to scan
    for item in files:
        pil = Image.open('image/%s' % item).convert('L')
        width, height = pil.size
        raw = pil.tostring()

        image = zbar.Image(width, height, 'Y800', raw)
        scanner.scan(image)

        #save code to list
        for symbol in image:
            data.append([item, symbol.data])
            # print 'decoded', symbol.type, 'symbol', '"%s"' % symbol.data

    return data


#decode base64 string to Shadow object
def decode_image(_data):
    #remove ss://
    coded_string = _data[1][5:]
    #get len of code string, make it multiple of four by add '='
    length = len(coded_string)
    for i in xrange(4 - length % 4):
        coded_string += '='
    #decode
    rel = base64.b64decode(coded_string)
    #translate to Shadow object
    item = rel.split(':')
    _shadow = Shadow(item[1].split('@')[1], item[2], item[1].split('@')[0], item[0], memo=_data[0])
    return _shadow


if __name__ == '__main__':
    #connect database
    db = DataBase(DATABASE)
    #scan images
    scan_data = scan_image()
    print(scan_data)
    #decode and insert to database
    for item in scan_data:
        shadow = decode_image(item)
        db.add_item(shadow)

    #close database connect
    db.close()

    # db.select_test()
    # shadows = db.get_items('unknown')
    # for item in shadows:
    #     print(item)

    # shadow = db.get_best_item(True)
    # print(shadow)
    # shadow = Shadow('1', '2', '3', '4')
    # print(shadow)
    # db.add_item(shadow)

    # scan_image()