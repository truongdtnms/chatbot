from threading import Thread, Lock
import time
from six.moves import _thread

lock = Lock()
a = []
def thread_action(no):
    global a
    # lock.acquire()
    for i in range(10):
        a.append(i)
        print(no, a)
        time.sleep(1)
    # lock.release()

if __name__ == '__main__':
    thread1 = Thread(target=thread_action, args=(1,))
    thread2 = Thread(target=thread_action, args=(2,))
    thread1.start()
    thread2.start()
