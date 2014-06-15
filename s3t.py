# coding=utf-8
# need extra pacakage: python-zbar
# under ubuntu install this package in software centre
# v0.39
import base64
from datetime import date
import os
import sqlite3
import zbar
import Image
import re

__author__ = 'gino'

DATABASE = 'shadowsocks.db'
LOCAL_PORT = '8020'
TIMEOUT = '600'
PN = '2'

TEMPLATE = '''{
    "server":"%s",
    "server_port":%s,
    "local_port":%s,
    "password":"%s",
    "timeout":%s,
    "method":"%s"
}'''


# Shadow class
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

    # close database connection
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
            for row in self.cur.execute(
                    'SELECT * FROM account WHERE method="aes-256-cfb" AND status="normal" ORDER BY {} LIMIT 3'.
                            format(order_str)):
                print(Shadow(row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))
        except sqlite3.Error:
            print('No best server')

    #output specific one
    def get_specifi_one(self, id):
        for row in self.cur.execute('SELECT * FROM account WHERE id=?', (id,)):
            print(Shadow(row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]))

    #check all item in database and change status column
    def check_all_items(self):
        try:
            self.cur.execute('SELECT server FROM account')
            rows = self.cur.fetchall()
            for row in rows:
                print('server %s is be checking...' % row[0])
                #via ping to check ip address reachable
                rel = os.popen('ping -c %s %s' % (PN, row[0])).read()
                che = '{} packets transmitted, 0 received, +{} errors, 100% packet loss,'.format(PN, PN)
                if che in rel:
                    print('failed!')
                    self.cur.execute('UPDATE account SET status="dead" WHERE server=?', (row[0],))
                else:
                    print('success!')
                    #base on ping time to set priority
                    result = re.findall('time=(\d+) ms', rel)
                    mul = int(PN) - len(result) + 1
                    _sum = 0
                    for r in result:
                        _sum += int(r)
                    avg = _sum / len(result)
                    priority = avg * mul
                    self.cur.execute('UPDATE account SET status="normal", priority=? WHERE server=?',
                                     (str(priority), row[0]))
                self.conn.commit()
        except sqlite3.Error as e:
            print(e)

    #delete dead item
    def delete_item(self):
        self.cur.execute('DELETE FROM account WHERE status = "dead"')
        self.conn.commit()


# scan images of barcode in ./image directory and get code string
#return list like:[[file_name, code_string],[]....]
def scan_image():
    #get list of files in path
    files = os.listdir("image")
    data = []
    #create scanner
    scanner = zbar.ImageScanner()
    scanner.parse_config('enable')

    #save unscan image name
    f = open('manual', 'a')

    #open each image to scan
    for _item in files:
        pil = Image.open('image/%s' % _item).convert('L')
        width, height = pil.size
        raw = pil.tostring()

        image = zbar.Image(width, height, 'Y800', raw)
        scanner.scan(image)

        #save code to list
        suc = '0'
        for symbol in image:
            data.append([_item, symbol.data])
            suc = '1'
            # print 'decoded', symbol.type, 'symbol', '"%s"' % symbol.data
        if suc == '0':
            print("!!!Important: %s can't be scanned" % _item)
            f.write(_item + ',\n')
    f.close()

    return data


#decode base64 string to Shadow object
def decode_data(_data):
    #remove ss://
    coded_string = _data[1][5:]
    #get len of code string, make it multiple of four by add '='
    length = len(coded_string)
    for i in xrange(4 - length % 4):
        coded_string += '='
    #decode
    rel = base64.b64decode(coded_string)
    #translate to Shadow object
    _item = rel.split(':')
    _shadow = Shadow(_item[1].split('@')[1], _item[2], _item[1].split('@')[0], _item[0], memo=_data[0])
    return _shadow


#insert shadow in database
def update_shadows(_db):
    #scan images
    scan_data = scan_image()
    # print(scan_data)
    #decode and insert to database
    for _item in scan_data:
        shadow = decode_data(_item)
        _db.add_item(shadow)


# manual update from manual file
def manual_update(_db):
    f = open('manual', 'r+')
    for line in f:
        print line
        mdata = line.split(',')
        if mdata[1][-1] == '\n':
            mdata[1] = mdata[1][:-1]
        shadow = decode_data(mdata)
        _db.add_item(shadow)
    f.close()
    #clear file
    #open('manual', 'w').close()


if __name__ == '__main__':
    #connect database
    db = DataBase(DATABASE)
    choose = 'H'
    while True:
        if choose == '1':
            print('Update Server')
            update_shadows(db)
        elif choose == '2':
            manual_update(db)
        elif choose == '3':
            print('Check Server')
            db.check_all_items()
        elif choose == '4':
            db.get_best_item()
        elif choose == '5':
            db.delete_item()
        elif choose == '6':
            input_id = raw_input('please input server id: ')
            db.get_specifi_one(input_id)
        elif choose == '0':
            print('Exit')
            break
        elif choose == 'H':
            print('''1. Upate server
2. Manual update
3. Check server
4. Best server
5. Delete dead server
6. Select one server
0. Exit
H. Help''')
        choose = raw_input('Please select: ').upper()
    #close database connect
    db.close()