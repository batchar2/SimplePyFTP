# -*- coding: utf-8 -*-

import os
import sys
import signal
import socket

class ParseData(object):
    """ Парсинг ответов ftp клиента. Реализация процедур в виде статическийх методов """

    @staticmethod
    def parse_data(data, key):
        """ Парсинг данных, полученных от клиента """
        if key is None: 
            return None
        
        index = data.find(key)
        if -1 == index:
            return None
        else:
            return data[index + len(key) + 1:-1].strip()

    @staticmethod
    def parse_command(data):
        """ Определение команды, полученной от клиента """
        if len(data) == 0:
            return None

        index = data.find(' ')
        if index == -1:
            return data.upper().strip()
        else:
            return data[0:index].upper().strip()


class FtpSession(object):
    """ Класс заведует проверкай пользователя на "наличие" и авторизацией """
    def __init__(self):
        self.user = None
        self.password = None
        self.__is_autorization = False

    def user_authorization(self):
        self.__is_autorization = True
        return True

    @property
    def is_autorization(self):
        return self.__is_autorization
    


class ClientConnect(object):
    """ Класс описывает клиенское подключение к серверу. """
    def __init__(self, conn, addr):
        self.__conn = conn
        self.__addr = addr
        self.__session = FtpSession()
        self.__is_run = True

        self.__file_from = None
        self.__file_to = None

        # режим передачи файлов: A-ASCII, I-Binary
        self.__mode = 'I'
        
    def send_data(method):
        """ Декоратор, описывающий передачу данных """
        def wrapper(self, recv_data):
            #print '-- decorator send'
            data = method(self, recv_data)
            self.__conn.send(data + '\r\n')
        return wrapper

        
    def run(self):
        """ Цикл обработки сообщений """

        # представляемся клиенту
        self.__conn.send(b'220 (SimplePyFTP)\r\n')

        while self.__is_run is True:
            recv_data = self.__conn.recv(1024)
            command = ParseData.parse_command(recv_data)
            print command
            try:
                f = getattr(self, command)
                f(recv_data)
            except Exception as e:
                print e
                print '>>> Uncown Command: "%s"' % command
                self.__conn.send('500 Uncown Command.\r\n')
        self.__conn.close()
        sys.exit(0)
    
    def __open_datasock(self):
        """ Создание сокета для "активного" режима. 
        В таком случае сервер пересылает данные клиенту НАПРЯМУЮ
        """
        self.__sock_dataport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__sock_dataport.connect((self.__data_addr, self.__data_port,)) 
        
        return self.__sock_dataport

    def __close_datasock(self):
        self.__sock_dataport.close()

    @send_data
    def USER(self, recv_data):
        """ Имя пользователя для входа на сервер """
        self.__session.user = ParseData.parse_data(recv_data, 'USER')
        return '331 Please specify the password.'

    @send_data
    def PASS(self, recv_data):
        """ Получает пароль пользователя. Проводит авторизацию """
        self.__session.password = ParseData.parse_data(recv_data, 'PASS')
        if self.__session.user_authorization():  
            return '230 Login successful.'
        else:
            pass

    @send_data
    def LIST(self, recv_data):
        # костылик, сообщаем клиенту что-бы начал приемку данных
        self.__conn.send('150 Here comes the directory listing.\r\n')

        """ Возврат списка файлов каталога """
        s = self.__open_datasock()
        for item in os.listdir('.'):
            print '>>>> %s ' % item
            s.send(str(item) + '\r\n')

        self.__close_datasock()
        return '226 Directory send OK.'

    @send_data
    def SYST(self, recv_data):
        """ Определение типа системы """
        return '215 UNIX Type: L8'

    @send_data
    def PWD(self, recv_data):
        """ Возвращает текщий каталог """
        pwd = os.path.abspath('.')
        return '257 "%s"' % (pwd,)

    @send_data
    def QUIT(self, recv_data):
        """ Разрыв соединения и выход """
        self.__is_run = False
        return 'Goodbye :)'

    @send_data
    def PORT(self, recv_data):
        """ Задает номер порта, используемый для активного режима работы """
        # отсекаю команду, и перехожу к парсингу данных: фдресса и порта
        lst = recv_data[5:].split(',')
        # "воссоздаю" ip-шник клиента =) 
        self.__data_addr = '.'.join(lst[:4])
        # компинирую и получаю номер порта клиента, на который нужно слать данные
        self.__data_port = (int(lst[4]) << 8) + int(lst[5])

        return '200 Get port.'

    @send_data
    def CWD(self, recv_data):
        """ Смена каталога """
        cdir = ParseData.parse_data(recv_data, 'CWD')
        os.chdir(cdir)
        return '250 OK.'

    @send_data
    def MKD(self, recv_data):
        """ Создание каталога """
        cdir = ParseData.parse_data(recv_data, 'MKD')
        os.mkdir(cdir)
        return '250 OK.'

    @send_data
    def RMD(self, recv_data):
        """ Удаление каталога """
        cdir = ParseData.parse_data(recv_data, 'RMD')
        os.rmdir(cdir)
        return '250 OK.'

    @send_data
    def DELE(self, recv_data):
        """ Удаление файла """
        file_name = ParseData.parse_data(recv_data, 'DELE')
        os.remove(file_name)
        return '250 OK.'

    @send_data
    def RNFR(self, recv_data):
        """ Переименование файла: ЧТО переименовать """
        self.__file_from = ParseData.parse_data(recv_data, 'RNFR')
        return '350 Ready.'

    @send_data
    def RNTO(self, recv_data):
        """ Переименование файла: ВО ЧТО переименовать """
        self.__file_to = ParseData.parse_data(recv_data, 'RNTO')
        os.rename(self.__file_from, self.__file_to)
        return '250 OK.'
    
    @send_data
    def RETR(self, recv_data):
        """ Скачать файл с сервера командой get, в ftp-клиенте """
        file_name = ParseData.parse_data(recv_data, 'RETR')
        
        if self.__mode == 'I':
            fp = open(file_name, 'rb')
        else:
            fp = open(file_name, 'r')
        self.__conn.send('150 Opening data connection.\r\n')
        
        s = self.__open_datasock()

        data = fp.read(1024)
        while data:
            s.send(data)
            data = fp.read(1024)
        fp.close()
        self.__close_datasock()

        return '226 Transfer complete.'

    @send_data
    def TYPE(self, recv_data):
        """ Устанавливает режим передачи файлов: A-ASCII, I-Binary """
        self.__mode = ParseData.parse_data(recv_data, 'TYPE')
        print "->>>", recv_data

        if self.__mode == 'I':
            return '200 Binary mode.'
        else:
            return '200 Text mode.'

    @send_data
    def STOR(self, recv_data):
        """ Закачать файл на сервер """
        file_name = ParseData.parse_data(recv_data, 'STOR')
        if self.__mode == 'I':
            fp = open(file_name, 'wb')
        else:
            fp = open(file_name, 'r')
        
        self.__conn.send('150 Opening data connection.\r\n')
        
        s = self.__open_datasock()
        while True:
            data = s.recv(1024)
            if not data:
                break

            data = fp.write(data)
        fp.close()
        self.__close_datasock()

        return '226 Transfer complete.'


class Server(object):
    """ Класс описиывает сервер, ожидающий подкючения пользователей """
    
    def __init__(self, host, port, listen_size):
        signal.signal(signal.SIGINT, self.handle_signal)

        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__sock.bind((host, port,))

        self.__sock.listen(listen_size)
    

    def handle_signal(self, signum, frame):
        self.__sock.close()
        sys.exit(0)


    def run(self):
        print 'run'
        while True:
            conn, addr = self.__sock.accept()
            print 'accept'
            pid = os.fork()
            
            if pid == 0:
                ClientConnect(conn, addr).run()
            elif pid == -1:
                print("Error fork()")
                sys.exit(-1)
            else:
                pass




if __name__ == '__main__':
    s = Server('127.0.0.1', 21, 100)
    s.run()
    
